import json
import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends

from dashboard.auth import get_current_user

from dashboard.connector_utils import (
    registry, ConnectorConfig, get_vault, ConfigResolver,
    list_connector_instances,
    get_connector_instance,
    save_connector_instance,
    delete_connector_instance,
)

logger = __import__('logging').getLogger(__name__)

router = APIRouter(tags=["connectors"], prefix="/api/connectors")


# ── Response models ────────────────────────────────────────────────────────

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
    credential_status: str = "ok"  # 'ok' | 'missing' | 'error'

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


# ── Helpers ────────────────────────────────────────────────────────────────

def _mask_sensitive_config(config: dict) -> dict:
    import copy
    safe = copy.deepcopy(config)
    for k, v in safe.items():
        if isinstance(v, str) and not v.startswith("${"):
            if any(s in k.lower() for s in ["token", "key", "secret", "password"]):
                safe[k] = v[:4] + "****" if len(v) > 4 else "****"
    return safe


def _process_config_for_vault(instance_id: str, raw_config: dict,
                               store_in_vault: bool) -> dict:
    """Optionally store sensitive values in vault and replace with references."""
    vault = get_vault() if get_vault else None
    processed = {}
    for k, v in raw_config.items():
        if store_in_vault and vault and any(
            s in k.lower() for s in ["token", "key", "secret", "password"]
        ):
            vault.set(f"connector/{instance_id}", k, v)
            processed[k] = f"${{vault:connector/{instance_id}/{k}}}"
        else:
            processed[k] = v
    return processed


# ── Routes ────────────────────────────────────────────────────────────────

@router.get("/registry")
async def list_registry(user: dict = Depends(get_current_user)):
    """List all available connector types from the registry."""
    if not registry:
        logger.warning("Connector registry not available — connectors package may not be installed")
        return []

    result = []
    for connector_id, connector_class in registry.list_connectors().items():
        try:
            instance = connector_class()
            result.append(instance.config.model_dump(by_alias=True))
        except Exception as e:
            logger.debug("Error instantiating connector %s: %s", connector_id, e)
    return result


@router.get("/instances", response_model=List[ConnectorInstance])
async def list_instances(user: dict = Depends(get_current_user)):
    """List all configured connector instances."""
    instances_raw = list_connector_instances()
    vault = get_vault() if get_vault else None
    resolver = ConfigResolver() if ConfigResolver else None

    result = []
    for data in instances_raw:
        instance = ConnectorInstance(**data)
        if resolver and vault:
            refs = resolver.extract_vault_refs(instance.config)
            if any(vault.get(s, k) is None for s, k in refs):
                instance.credential_status = "missing"
        instance.config = _mask_sensitive_config(instance.config)
        result.append(instance)
    return result


@router.post("/instances", response_model=ConnectorInstance, status_code=201)
async def create_instance(req: CreateInstanceRequest,
                          user: dict = Depends(get_current_user)):
    """Create a new connector instance."""
    if not registry:
        raise HTTPException(status_code=503, detail="Connector registry not available")
    if req.connector_id not in registry.list_connectors():
        raise HTTPException(status_code=400, detail=f"Unknown connector: {req.connector_id}")

    instance_id = str(uuid.uuid4())
    processed_config = _process_config_for_vault(instance_id, req.config, req.store_in_vault)

    new_instance = {
        "id": instance_id,
        "connector_id": req.connector_id,
        "name": req.name,
        "enabled": True,
        "config": processed_config,
        "credential_status": "ok",
        "created_at": datetime.utcnow().isoformat(),
    }
    save_connector_instance(new_instance)

    res = ConnectorInstance(**new_instance)
    res.config = _mask_sensitive_config(res.config)
    return res


@router.get("/instances/{instance_id}", response_model=ConnectorInstance)
async def get_instance_route(instance_id: str, user: dict = Depends(get_current_user)):
    """Get a single connector instance."""
    data = get_connector_instance(instance_id)
    if not data:
        raise HTTPException(status_code=404, detail="Instance not found")
    instance = ConnectorInstance(**data)
    instance.config = _mask_sensitive_config(instance.config)
    return instance


@router.put("/instances/{instance_id}", response_model=ConnectorInstance)
async def update_instance(instance_id: str, req: UpdateInstanceRequest,
                          user: dict = Depends(get_current_user)):
    """Update an existing connector instance."""
    data = get_connector_instance(instance_id)
    if not data:
        raise HTTPException(status_code=404, detail="Instance not found")

    if req.name is not None:
        data["name"] = req.name
    if req.enabled is not None:
        data["enabled"] = req.enabled
    if req.config is not None:
        existing_cfg = data.get("config", {}).copy()
        updates = _process_config_for_vault(instance_id, req.config, req.store_in_vault)
        existing_cfg.update(updates)
        data["config"] = existing_cfg

    save_connector_instance(data)

    res = ConnectorInstance(**data)
    res.config = _mask_sensitive_config(res.config)
    return res


@router.delete("/instances/{instance_id}")
async def delete_instance_route(instance_id: str, user: dict = Depends(get_current_user)):
    """Delete a connector instance and its vault entries."""
    if not delete_connector_instance(instance_id):
        raise HTTPException(status_code=404, detail="Instance not found")

    vault = get_vault() if get_vault else None
    if vault:
        try:
            keys = vault.list_keys(f"connector/{instance_id}")
            for k in keys:
                vault.delete(f"connector/{instance_id}", k)
        except Exception as e:
            logger.warning("Failed to clear vault for %s: %s", instance_id, e)

    return {"status": "deleted"}


@router.post("/instances/{instance_id}/validate")
async def validate_instance(instance_id: str, user: dict = Depends(get_current_user)):
    """Validate the configuration of a connector instance."""
    data = get_connector_instance(instance_id)
    if not data:
        raise HTTPException(status_code=404, detail="Instance not found")
    if not registry:
        raise HTTPException(status_code=503, detail="Connector registry not available")

    connector_id = data.get("connector_id", "")
    try:
        connector_instance = registry.get_instance(connector_id)
        config = data.get("config", {})
        resolver = ConfigResolver() if ConfigResolver else None
        if resolver:
            config = resolver.resolve(config)
        await connector_instance.validate_config(config)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/instances/{instance_id}/documents", response_model=ExternalDocumentList)
async def list_instance_documents(instance_id: str, cursor: Optional[str] = None,
                                  user: dict = Depends(get_current_user)):
    """List documents from a connector instance."""
    data = get_connector_instance(instance_id)
    if not data:
        raise HTTPException(status_code=404, detail="Instance not found")
    if not registry:
        raise HTTPException(status_code=503, detail="Connector registry not available")

    connector_id = data.get("connector_id", "")
    try:
        connector_instance = registry.get_instance(connector_id)
        config = data.get("config", {})
        resolver = ConfigResolver() if ConfigResolver else None
        if resolver:
            config = resolver.resolve(config)
        return await connector_instance.list_documents(config, cursor=cursor)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances/{instance_id}/documents/{external_id}",
            response_model=ExternalDocument)
async def get_instance_document(instance_id: str, external_id: str,
                                user: dict = Depends(get_current_user)):
    """Fetch a specific document from a connector instance."""
    data = get_connector_instance(instance_id)
    if not data:
        raise HTTPException(status_code=404, detail="Instance not found")
    if not registry:
        raise HTTPException(status_code=503, detail="Connector registry not available")

    connector_id = data.get("connector_id", "")
    try:
        connector_instance = registry.get_instance(connector_id)
        config = data.get("config", {})
        resolver = ConfigResolver() if ConfigResolver else None
        if resolver:
            config = resolver.resolve(config)
        return await connector_instance.get_document(external_id, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
