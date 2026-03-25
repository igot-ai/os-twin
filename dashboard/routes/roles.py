import json
import logging
import uuid
import asyncio
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from dashboard.models import Role, CreateRoleRequest
from dashboard.api_utils import AGENTS_DIR, PLANS_DIR
from dashboard.auth import get_current_user

router = APIRouter(tags=["roles"])
logger = logging.getLogger(__name__)

ROLES_CONFIG_FILE = AGENTS_DIR / "roles" / "config.json"


def load_roles() -> List[Role]:
    if not ROLES_CONFIG_FILE.exists():
        # Initialize with some defaults if registry exists
        registry_file = AGENTS_DIR / "roles" / "registry.json"
        if registry_file.exists():
            registry = json.loads(registry_file.read_text())
            default_roles = []
            for r in registry.get("roles", []):
                now = datetime.now(timezone.utc).isoformat()
                role = Role(
                    id=str(uuid.uuid4()),
                    name=r["name"],
                    provider="Gemini",  # Default to Gemini as seen in registry
                    version=r.get("default_model", "gemini-3-flash-preview"),
                    temperature=0.7,
                    budget_tokens_max=500000,
                    max_retries=3,
                    timeout_seconds=r.get("timeout_seconds", 300),
                    skill_refs=[],
                    system_prompt_override=None,
                    created_at=now,
                    updated_at=now
                )
                default_roles.append(role)
            return default_roles
        return []

    with open(ROLES_CONFIG_FILE, "r") as f:
        data = json.load(f)
        return [Role(**r) for r in data]


def save_roles(roles: List[Role]):
    ROLES_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ROLES_CONFIG_FILE, "w") as f:
        json.dump([r.model_dump() for r in roles], f, indent=2)


@router.get("/api/models/registry")
async def get_model_registry(user: dict = Depends(get_current_user)):
    """Get the available models from the registry."""
    # In a real app, this might fetch from an external service or a local file
    return {
        'Claude': [
            {"id": 'claude-3-5-sonnet-20241022', "context_window": '200K', "tier": 'flagship'},
            {"id": 'claude-3-5-haiku-20241022', "context_window": '200K', "tier": 'fast'},
            {"id": 'claude-3-opus-20240229', "context_window": '200K', "tier": 'reasoning'},
            {"id": 'claude-3-sonnet-20240229', "context_window": '200K', "tier": 'balanced'},
        ],
        'GPT': [
            {"id": 'gpt-4o-2024-08-06', "context_window": '128K', "tier": 'flagship'},
            {"id": 'gpt-4o-mini-2024-07-18', "context_window": '128K', "tier": 'fast'},
            {"id": 'o1-preview-2024-09-12', "context_window": '128K', "tier": 'reasoning'},
            {"id": 'gpt-4-turbo-2024-04-09', "context_window": '128K', "tier": 'balanced'},
        ],
        'Gemini': [
            {"id": 'gemini-1.5-pro-002', "context_window": '2M', "tier": 'flagship'},
            {"id": 'gemini-1.5-flash-002', "context_window": '1M', "tier": 'fast'},
            {"id": 'gemini-3-flash-preview', "context_window": '1M', "tier": 'balanced'},
        ]
    }


@router.get("/api/roles", response_model=List[Role])
async def list_roles(user: dict = Depends(get_current_user)):
    return load_roles()


@router.post("/api/roles", response_model=Role, status_code=status.HTTP_201_CREATED)
async def create_role(req: CreateRoleRequest, user: dict = Depends(get_current_user)):
    roles = load_roles()
    if any(r.name == req.name for r in roles):
        raise HTTPException(status_code=400, detail="Role name already exists")

    now = datetime.now(timezone.utc).isoformat()
    new_role = Role(
        id=str(uuid.uuid4()),
        **req.model_dump(),
        created_at=now,
        updated_at=now
    )
    roles.append(new_role)
    save_roles(roles)
    return new_role


@router.put("/api/roles/{role_id}", response_model=Role)
async def update_role(role_id: str, req: CreateRoleRequest, user: dict = Depends(get_current_user)):
    roles = load_roles()
    for i, r in enumerate(roles):
        if r.id == role_id:
            # Check name uniqueness if changed
            if r.name != req.name and any(other.name == req.name for other in roles if other.id != role_id):
                raise HTTPException(status_code=400, detail="Role name already exists")
            
            # Propagate name change to plans if needed
            old_name = r.name
            new_name = req.name
            if old_name != new_name:
                plans_dir = PLANS_DIR
                if plans_dir.exists():
                    for f in plans_dir.glob("*.roles.json"):
                        try:
                            config = json.loads(f.read_text())
                            if old_name in config:
                                config[new_name] = config.pop(old_name)
                                f.write_text(json.dumps(config, indent=2))
                        except Exception:
                            pass
            
            updated_role = Role(
                id=role_id,
                **req.model_dump(),
                created_at=r.created_at,
                updated_at=datetime.now(timezone.utc).isoformat()
            )
            roles[i] = updated_role
            save_roles(roles)
            return updated_role
            
    raise HTTPException(status_code=404, detail="Role not found")


@router.get("/api/roles/{role_id}/dependencies")
async def get_role_dependencies(role_id: str, user: dict = Depends(get_current_user)):
    """Check where this role is used in war-rooms and plans."""
    roles = load_roles()
    role = next((r for r in roles if r.id == role_id), None)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    from dashboard.api_utils import WARROOMS_DIR, AGENTS_DIR
    active_warrooms = []
    inactive_warrooms = []
    plans = []
    
    # Check war-rooms
    if WARROOMS_DIR.exists():
        for room_dir in WARROOMS_DIR.glob("room-*"):
            if room_dir.is_dir():
                config_file = room_dir / "config.json"
                status_file = room_dir / "status"
                if config_file.exists():
                    try:
                        with open(config_file, "r") as f:
                            config = json.load(f)
                            candidates = config.get("assignment", {}).get("candidate_roles", [])
                            if role.name in candidates:
                                status = status_file.read_text().strip() if status_file.exists() else "unknown"
                                room_info = {"id": room_dir.name, "status": status}
                                if status not in ["passed", "failed", "signoff"]:
                                    active_warrooms.append(room_info)
                                else:
                                    inactive_warrooms.append(room_info)
                    except Exception:
                        pass
    
    # Check plans
    plans_dir = PLANS_DIR
    if plans_dir.exists():
        for f in plans_dir.glob("*.roles.json"):
            try:
                config = json.loads(f.read_text())
                if role.name in config:
                    plans.append(f.name.replace(".roles.json", ""))
            except Exception:
                pass
            
    return {
        "active_warrooms": active_warrooms,
        "inactive_warrooms": inactive_warrooms,
        "plans": plans
    }


@router.delete("/api/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: str, force: bool = False, user: dict = Depends(get_current_user)):
    roles = load_roles()
    role_to_delete = next((r for r in roles if r.id == role_id), None)
    if not role_to_delete:
        raise HTTPException(status_code=404, detail="Role not found")
    
    deps = await get_role_dependencies(role_id, user)
    
    if len(deps["active_warrooms"]) > 0:
        raise HTTPException(
            status_code=409, 
            detail=f"Cannot delete — this role is actively used by {len(deps['active_warrooms'])} war-rooms."
        )
    
    if not force and (len(deps["inactive_warrooms"]) > 0 or len(deps["plans"]) > 0):
        # We'll rely on the frontend to ask for force=true if there are only inactive/plan refs
        raise HTTPException(
            status_code=412, # Precondition Failed
            detail="Role has inactive references. Use force=true to delete anyway."
        )

    # Actually delete from plans if force=true
    if force:
        plans_dir = PLANS_DIR
        if plans_dir.exists():
            for f in plans_dir.glob("*.roles.json"):
                try:
                    config = json.loads(f.read_text())
                    if role_to_delete.name in config:
                        del config[role_to_delete.name]
                        f.write_text(json.dumps(config, indent=2))
                except Exception: pass
    
    roles = [r for r in roles if r.id != role_id]
    save_roles(roles)
    return


@router.post("/api/models/{version}/test")
async def test_model_connection(version: str, user: dict = Depends(get_current_user)):
    import time
    import random
    
    start_time = time.time()
    # Simulate a small delay for the test
    await asyncio.sleep(random.uniform(0.1, 0.5))
    
    # Mocking success/failure based on version name for testing
    if "fail" in version.lower():
        return {
            "status": "fail",
            "latency_ms": int((time.time() - start_time) * 1000),
            "error": "Model not found or API key invalid"
        }
    
    latency = int((time.time() - start_time) * 1000)
    return {
        "status": "ok",
        "latency_ms": latency
    }
