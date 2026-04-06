import json
import os
import sys
import uuid
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from dashboard.api_utils import AGENTS_DIR, PROJECT_ROOT
from dashboard.auth import get_current_user

from dashboard.connector_utils import (
    registry, ConnectorConfig, get_vault, ConfigResolver, 
    get_connector_config_path, read_connector_configs, 
    save_connector_configs
)

logger = __import__('logging').getLogger(__name__)

router = APIRouter(tags=["connectors"], prefix="/api/connectors")

# Stub response models — replace with real connector SDK models when available
class ExternalDocument(BaseModel):
    external_id: str
    title: str = ""
    content: Optional[str] = None
    content_type: str = "text/plain"
    url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ExternalDocumentList(BaseModel):
    items: List[ExternalDocument] = Field(default_factory=list)
    cursor: Optional[str] = None
    has_more: bool = False

class ConnectorInstance(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    connector_id: str
    name: str
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)
    credential_status: str = "ok" # 'ok' | 'missing' | 'error'

class CreateInstanceRequest(BaseModel):
    connector_id: str
    name: str
    config: Dict[str, Any]
    store_in_vault: bool = True

class UpdateInstanceRequest(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    store_in_vault: bool = True


def _mask_sensitive_config(config: dict) -> dict:
    import copy
    safe = copy.deepcopy(config)
    for k, v in safe.items():
        if isinstance(v, str) and not v.startswith("${"):
            # If it's a known sensitive key or looks like a token/key, mask it
            if any(s in k.lower() for s in ["token", "key", "secret", "password"]):
                safe[k] = v[:4] + "****" if len(v) > 4 else "****"
    return safe

@router.get("/registry")
async def list_registry(user: dict = Depends(get_current_user)):
    """List all available connector types."""
    if not registry:
        raise HTTPException(status_code=500, detail="Connector registry not available")
    
    result = []
    for connector_id, connector_class in registry.list_connectors().items():
        try:
            # Instantiate once to get config
            instance = connector_class()
            result.append(instance.config.model_dump())
        except Exception as e:
            print(f"Error instantiating connector {connector_id}: {e}")
            continue
    return result

@router.get("/instances", response_model=List[ConnectorInstance])
async def list_instances(user: dict = Depends(get_current_user)):
    """List all configured connector instances."""
    configs = read_connector_configs()
    vault = get_vault() if get_vault else None
    resolver = ConfigResolver() if ConfigResolver else None
    
    result = []
    for c in configs:
        instance = ConnectorInstance(**c)
        # Check credential status
        if resolver and vault:
            refs = resolver.extract_vault_refs(instance.config)
            missing = False
            for s, k in refs:
                if vault.get(s, k) is None:
                    missing = True
                    break
            if missing:
                instance.credential_status = "missing"
        
        # Mask config for security
        instance.config = _mask_sensitive_config(instance.config)
        result.append(instance)
    return result

@router.post("/instances", response_model=ConnectorInstance)
async def create_instance(req: CreateInstanceRequest, user: dict = Depends(get_current_user)):
    """Create a new connector instance."""
    if not registry:
        raise HTTPException(status_code=500, detail="Connector registry not available")
    
    if req.connector_id not in registry.list_connectors():
        raise HTTPException(status_code=400, detail=f"Unknown connector: {req.connector_id}")
    
    configs = read_connector_configs()
    instance_id = str(uuid.uuid4())
    
    processed_config = {}
    vault = get_vault() if get_vault else None
    
    for k, v in req.config.items():
        if req.store_in_vault and vault and any(s in k.lower() for s in ["token", "key", "secret", "password"]):
            # Store in vault as connector/{instance_id}/{k}
            vault_key = k
            vault.set(f"connector/{instance_id}", vault_key, v)
            processed_config[k] = f"${{vault:connector/{instance_id}/{vault_key}}}"
        else:
            processed_config[k] = v
            
    new_instance = {
        "id": instance_id,
        "connector_id": req.connector_id,
        "name": req.name,
        "enabled": True,
        "config": processed_config
    }
    
    configs.append(new_instance)
    save_connector_configs(configs)
    
    # Return masked version
    res = ConnectorInstance(**new_instance)
    res.config = _mask_sensitive_config(res.config)
    return res

@router.get("/instances/{instance_id}", response_model=ConnectorInstance)
async def get_instance(instance_id: str, user: dict = Depends(get_current_user)):
    """Get a single connector instance."""
    configs = read_connector_configs()
    instance_data = next((c for c in configs if c["id"] == instance_id), None)
    if not instance_data:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    instance = ConnectorInstance(**instance_data)
    instance.config = _mask_sensitive_config(instance.config)
    return instance

@router.put("/instances/{instance_id}", response_model=ConnectorInstance)
async def update_instance(
    instance_id: str, 
    req: UpdateInstanceRequest, 
    user: dict = Depends(get_current_user)
):
    """Update an existing connector instance."""
    configs = read_connector_configs()
    instance_idx = next((i for i, c in enumerate(configs) if c["id"] == instance_id), None)
    if instance_idx is None:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    instance_data = configs[instance_idx]
    
    if req.name is not None:
        instance_data["name"] = req.name
    if req.enabled is not None:
        instance_data["enabled"] = req.enabled
    if req.config is not None:
        # Resolve existing config keys if we're not overwriting all of them
        # (Though Pydantic model suggests sending the whole config if provided)
        processed_config = instance_data["config"].copy()
        vault = get_vault() if get_vault else None
        
        for k, v in req.config.items():
            if req.store_in_vault and vault and any(s in k.lower() for s in ["token", "key", "secret", "password"]):
                # Store in vault as connector/{instance_id}/{k}
                vault.set(f"connector/{instance_id}", k, v)
                processed_config[k] = f"${{vault:connector/{instance_id}/{k}}}"
            else:
                processed_config[k] = v
        instance_data["config"] = processed_config
        
    configs[instance_idx] = instance_data
    save_connector_configs(configs)
    
    # Return masked version
    res = ConnectorInstance(**instance_data)
    res.config = _mask_sensitive_config(res.config)
    return res

@router.delete("/instances/{instance_id}")
async def delete_instance(instance_id: str, user: dict = Depends(get_current_user)):
    """Delete a connector instance and its vault entries."""
    configs = read_connector_configs()
    updated_configs = [c for c in configs if c["id"] != instance_id]
    if len(updated_configs) == len(configs):
        raise HTTPException(status_code=404, detail="Instance not found")
    
    save_connector_configs(updated_configs)
    
    # Clear vault entries
    vault = get_vault() if get_vault else None
    if vault:
        # Get keys for this instance scope
        try:
            keys = vault.list_keys(f"connector/{instance_id}")
            for k in keys:
                vault.delete(f"connector/{instance_id}", k)
        except Exception as e:
            print(f"Warning: Failed to clear vault entries for {instance_id}: {e}")
        
    return {"status": "deleted"}

@router.post("/instances/{instance_id}/validate")
async def validate_instance(instance_id: str, user: dict = Depends(get_current_user)):
    """Validate the configuration of a connector instance."""
    configs = read_connector_configs()
    instance_data = next((c for c in configs if c["id"] == instance_id), None)
    if not instance_data:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    if not registry:
        raise HTTPException(status_code=500, detail="Connector registry not available")
    
    connector_id = instance_data["connector_id"]
    try:
        connector_instance = registry.get_instance(connector_id)
        
        # Resolve config from vault
        config = instance_data["config"]
        resolver = ConfigResolver() if ConfigResolver else None
        if resolver:
            config = resolver.resolve(config)
            
        await connector_instance.validate_config(config)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/instances/{instance_id}/documents", response_model=ExternalDocumentList)
async def list_instance_documents(
    instance_id: str, 
    cursor: Optional[str] = None, 
    user: dict = Depends(get_current_user)
):
    """List documents from a connector instance."""
    configs = read_connector_configs()
    instance_data = next((c for c in configs if c["id"] == instance_id), None)
    if not instance_data:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    if not registry:
        raise HTTPException(status_code=500, detail="Connector registry not available")
    
    connector_id = instance_data["connector_id"]
    try:
        connector_instance = registry.get_instance(connector_id)
        
        # Resolve config from vault
        config = instance_data["config"]
        resolver = ConfigResolver() if ConfigResolver else None
        if resolver:
            config = resolver.resolve(config)
            
        return await connector_instance.list_documents(config, cursor=cursor)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/instances/{instance_id}/documents/{external_id}", response_model=ExternalDocument)
async def get_instance_document(
    instance_id: str, 
    external_id: str, 
    user: dict = Depends(get_current_user)
):
    """Fetch a specific document content from a connector instance."""
    configs = read_connector_configs()
    instance_data = next((c for c in configs if c["id"] == instance_id), None)
    if not instance_data:
        raise HTTPException(status_code=404, detail="Instance not found")
    
    if not registry:
        raise HTTPException(status_code=500, detail="Connector registry not available")
    
    connector_id = instance_data["connector_id"]
    try:
        connector_instance = registry.get_instance(connector_id)
        
        # Resolve config from vault
        config = instance_data["config"]
        resolver = ConfigResolver() if ConfigResolver else None
        if resolver:
            config = resolver.resolve(config)
            
        return await connector_instance.get_document(external_id, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
