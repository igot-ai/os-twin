import json
import logging
import uuid
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from dashboard.models import Role, CreateRoleRequest
from dashboard.api_utils import AGENTS_DIR, PLANS_DIR, GLOBAL_ROLES_DIR
from dashboard.auth import get_current_user
import dashboard.global_state as global_state

router = APIRouter(tags=["roles"])
logger = logging.getLogger(__name__)

ROLES_CONFIG_FILE = GLOBAL_ROLES_DIR / "config.json"
ENGINE_CONFIG_FILE = AGENTS_DIR / "config.json"

PROVIDER_MAP = {
    "gemini": "Gemini", "claude": "Claude", "anthropic": "Claude",
    "gpt": "GPT", "openai": "GPT", "o1": "GPT", "o3": "GPT", "o4": "GPT",
}


def _detect_provider(model_id: str) -> str:
    model_lower = model_id.lower()
    for prefix, provider in PROVIDER_MAP.items():
        if prefix in model_lower:
            return provider
    return "Gemini"


def _read_role_json(role_name: str) -> dict:
    """Read individual role.json from disk (the engine's per-role definition)."""
    role_file = GLOBAL_ROLES_DIR / role_name / "role.json"
    if not role_file.exists():
        role_file = AGENTS_DIR / "roles" / role_name / "role.json"
        
    if role_file.exists():
        try:
            return json.loads(role_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _read_engine_config() -> dict:
    """Read the engine's global config.json."""
    if ENGINE_CONFIG_FILE.exists():
        try:
            return json.loads(ENGINE_CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def load_roles() -> List[Role]:
    roles_list = []
    loaded_names = set()
    
    # 1. Load from config.json cache if exists
    if ROLES_CONFIG_FILE.exists():
        with open(ROLES_CONFIG_FILE, "r") as f:
            try:
                data = json.load(f)
                roles_list = [Role(**r) for r in data]
                loaded_names = {r.name for r in roles_list}
            except: pass

    # 2. If config.json doesn't exist or is empty, bootstrap from registry.json
    if not roles_list:
        registry_file = GLOBAL_ROLES_DIR / "registry.json"
        if not registry_file.exists():
            registry_file = AGENTS_DIR / "roles" / "registry.json"
            
        if registry_file.exists():
            registry = json.loads(registry_file.read_text())
            engine_config = _read_engine_config()
            for r in registry.get("roles", []):
                name = r["name"]
                if name in loaded_names: continue
                role_json = _read_role_json(name)
                engine_role = engine_config.get(name, {})
                model = engine_role.get("default_model") or role_json.get("model") or r.get("default_model", "google-vertex/gemini-3-flash-preview")
                timeout = engine_role.get("timeout_seconds") or role_json.get("timeout", r.get("timeout_seconds", 300))
                skill_refs = role_json.get("skill_refs", role_json.get("skills", []))
                mcp_refs = role_json.get("mcp_refs", [])
                description = role_json.get("description", r.get("description", ""))
                role_md_file = GLOBAL_ROLES_DIR / name / "ROLE.md"
                if not role_md_file.exists():
                    role_md_file = AGENTS_DIR / "roles" / name / "ROLE.md"
                instructions = ""
                if role_md_file.exists():
                    try:
                        instructions = role_md_file.read_text()
                    except OSError:
                        pass
                now = datetime.now(timezone.utc).isoformat()
                role = Role(
                    id=str(uuid.uuid4()),
                    name=name,
                    description=description,
                    instructions=instructions,
                    provider=_detect_provider(model).lower(),
                    version=model,
                    temperature=0.7,
                    budget_tokens_max=500000,
                    max_retries=3,
                    timeout_seconds=timeout,
                    skill_refs=skill_refs,
                    mcp_refs=mcp_refs,
                    system_prompt_override=None,
                    created_at=now,
                    updated_at=now
                )
                roles_list.append(role)
                loaded_names.add(name)

    # 3. Dynamically discover any other role directories
    added_new = False
    
    # Helper to scan a directory for valid role folders
    def _scan_dir_for_roles(base_dir: Path):
        nonlocal added_new
        if not base_dir.exists(): return
        engine_config = _read_engine_config()
        for child in base_dir.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                name = child.name
                if name not in loaded_names:
                    role_file = child / "role.json"
                    md_file = child / "ROLE.md"
                    if role_file.exists() or md_file.exists():
                        role_json = _read_role_json(name)
                        engine_role = engine_config.get(name, {})
                        model = engine_role.get("default_model") or role_json.get("model") or "google-vertex/gemini-3-flash-preview"
                        timeout = engine_role.get("timeout_seconds") or role_json.get("timeout", 300)
                        skill_refs = role_json.get("skill_refs", role_json.get("skills", []))
                        mcp_refs = role_json.get("mcp_refs", [])
                        description = role_json.get("description", "")
                        
                        instructions = ""
                        # prefer global md file
                        actual_md = GLOBAL_ROLES_DIR / name / "ROLE.md"
                        if not actual_md.exists(): actual_md = md_file
                        if actual_md.exists():
                            try: instructions = actual_md.read_text()
                            except OSError: pass
                            
                        now = datetime.now(timezone.utc).isoformat()
                        role = Role(
                            id=str(uuid.uuid4()), name=name, description=description, instructions=instructions,
                            provider=_detect_provider(model).lower(), version=model, temperature=0.7,
                            budget_tokens_max=500000, max_retries=3, timeout_seconds=timeout, skill_refs=skill_refs,
                            mcp_refs=mcp_refs, system_prompt_override=None, created_at=now, updated_at=now
                        )
                        roles_list.append(role)
                        loaded_names.add(name)
                        added_new = True

    _scan_dir_for_roles(GLOBAL_ROLES_DIR)
    _scan_dir_for_roles(AGENTS_DIR / "roles")

    if added_new or not ROLES_CONFIG_FILE.exists():
        save_roles(roles_list)
        
    return roles_list


def save_roles(roles: List[Role]):
    ROLES_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ROLES_CONFIG_FILE, "w") as f:
        json.dump([r.model_dump() for r in roles], f, indent=2)


def _sync_role_to_engine(role: Role):
    """Write role config back to engine files so the PowerShell runtime picks it up."""
    # Update engine's global config.json
    engine_config = _read_engine_config()
    if role.name not in engine_config:
        engine_config[role.name] = {}
    engine_config[role.name]["default_model"] = role.version
    engine_config[role.name]["timeout_seconds"] = role.timeout_seconds
    if role.skill_refs:
        engine_config[role.name]["skill_refs"] = role.skill_refs
    if role.mcp_refs:
        engine_config[role.name]["mcp_refs"] = role.mcp_refs
    try:
        ENGINE_CONFIG_FILE.write_text(json.dumps(engine_config, indent=2))
    except OSError as e:
        logger.warning("Failed to update engine config.json: %s", e)

    # Update individual role.json
    role_dir = GLOBAL_ROLES_DIR / role.name
    role_dir.mkdir(parents=True, exist_ok=True)
    role_file = role_dir / "role.json"
    role_json = _read_role_json(role.name)
    role_json["model"] = role.version
    role_json["skill_refs"] = role.skill_refs
    role_json["mcp_refs"] = role.mcp_refs
    role_json["timeout"] = role.timeout_seconds
    role_json["description"] = role.description
    try:
        role_file.write_text(json.dumps(role_json, indent=2))
    except OSError as e:
        logger.warning("Failed to update role.json for %s: %s", role.name, e)

    # Write ROLE.md
    if role.instructions:
        role_md_file = role_dir / "ROLE.md"
        try:
            role_md_file.write_text(role.instructions)
        except OSError as e:
            logger.warning("Failed to write ROLE.md for %s: %s", role.name, e)


def sync_roles_from_disk() -> dict:
    """Merge skill_refs and model from on-disk role.json files into dashboard config.
    Returns a summary of what was updated."""
    roles = load_roles()
    engine_config = _read_engine_config()
    updated = []
    for role in roles:
        role_json = _read_role_json(role.name)
        engine_role = engine_config.get(role.name, {})
        changed = False
        disk_skills = role_json.get("skill_refs", role_json.get("skills", []))
        if disk_skills and not role.skill_refs:
            role.skill_refs = disk_skills
            changed = True
        disk_model = engine_role.get("default_model") or role_json.get("model")
        if disk_model and disk_model != role.version:
            role.version = disk_model
            role.provider = _detect_provider(disk_model)
            changed = True
        disk_timeout = engine_role.get("timeout_seconds") or role_json.get("timeout")
        if disk_timeout and disk_timeout != role.timeout_seconds:
            role.timeout_seconds = disk_timeout
            changed = True
        disk_description = role_json.get("description", "")
        if disk_description and disk_description != role.description:
            role.description = disk_description
            changed = True
        role_md_file = GLOBAL_ROLES_DIR / role.name / "ROLE.md"
        if not role_md_file.exists():
            role_md_file = AGENTS_DIR / "roles" / role.name / "ROLE.md"
        if role_md_file.exists():
            try:
                disk_instructions = role_md_file.read_text()
                if disk_instructions != role.instructions:
                    role.instructions = disk_instructions
                    changed = True
            except OSError:
                pass
        if changed:
            role.updated_at = datetime.now(timezone.utc).isoformat()
            updated.append(role.name)
    if updated:
        save_roles(roles)
        store = global_state.store
        if store:
            for role in roles:
                if role.name in updated:
                    store.index_role(
                        role_id=role.id, name=role.name, provider=role.provider,
                        version=role.version, temperature=role.temperature,
                        budget_tokens_max=role.budget_tokens_max, max_retries=role.max_retries,
                        timeout_seconds=role.timeout_seconds, skill_refs=role.skill_refs,
                        system_prompt_override=role.system_prompt_override,
                        created_at=role.created_at, updated_at=role.updated_at,
                    )
    return {"synced": updated, "total": len(roles)}


@router.post("/api/roles/sync")
async def sync_roles_endpoint(user: dict = Depends(get_current_user)):
    """Re-sync dashboard roles from on-disk role.json and engine config.json."""
    return sync_roles_from_disk()


@router.get("/api/models/registry")
async def get_model_registry(user: dict = Depends(get_current_user)):
    """Get the available models from the registry."""
    # In a real app, this might fetch from an external service or a local file
    return {
        'Claude': [
            {"id": 'claude-opus-4-6', "context_window": '200K', "tier": 'flagship'},
            {"id": 'claude-sonnet-4-6', "context_window": '200K', "tier": 'balanced'},
            {"id": 'claude-haiku-4-5', "context_window": '200K', "tier": 'fast'},
        ],
        'GPT': [
            {"id": 'gpt-4.1', "context_window": '1M', "tier": 'flagship'},
            {"id": 'gpt-4.1-mini', "context_window": '1M', "tier": 'fast'},
            {"id": 'o3', "context_window": '200K', "tier": 'reasoning'},
            {"id": 'o4-mini', "context_window": '200K', "tier": 'reasoning'},
        ],
        'Gemini': [
            {"id": 'google-vertex/gemini-3.1-pro-preview', "context_window": '1M', "tier": 'flagship'},
            {"id": 'google-vertex/gemini-3-flash-preview', "context_window": '1M', "tier": 'balanced'},
            {"id": 'google-vertex/gemini-2.5-pro-preview-05-06', "context_window": '1M', "tier": 'reasoning'},
            {"id": 'google-vertex/gemini-2.5-flash-preview-05-20', "context_window": '1M', "tier": 'fast'},
        ]
    }


@router.get("/api/roles", response_model=List[Role])
async def list_roles(user: dict = Depends(get_current_user)):
    return load_roles()


@router.get("/api/roles/search")
async def search_roles(
    q: str = Query(..., description="Semantic search query"),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    store = global_state.store
    if not store:
        raise HTTPException(status_code=503, detail="Vector store not available")
    return store.search_roles(q, limit=limit)


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
    _sync_role_to_engine(new_role)

    store = global_state.store
    if store:
        store.index_role(
            role_id=new_role.id,
            name=new_role.name,
            provider=new_role.provider,
            version=new_role.version,
            temperature=new_role.temperature,
            budget_tokens_max=new_role.budget_tokens_max,
            max_retries=new_role.max_retries,
            timeout_seconds=new_role.timeout_seconds,
            skill_refs=new_role.skill_refs,
            system_prompt_override=new_role.system_prompt_override,
            created_at=new_role.created_at,
            updated_at=new_role.updated_at,
        )

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
            _sync_role_to_engine(updated_role)

            store = global_state.store
            if store:
                store.index_role(
                    role_id=updated_role.id,
                    name=updated_role.name,
                    provider=updated_role.provider,
                    version=updated_role.version,
                    temperature=updated_role.temperature,
                    budget_tokens_max=updated_role.budget_tokens_max,
                    max_retries=updated_role.max_retries,
                    timeout_seconds=updated_role.timeout_seconds,
                    skill_refs=updated_role.skill_refs,
                    system_prompt_override=updated_role.system_prompt_override,
                    created_at=updated_role.created_at,
                    updated_at=updated_role.updated_at,
                )

            return updated_role

    raise HTTPException(status_code=404, detail="Role not found")


@router.get("/api/roles/{role_id}", response_model=Role)
async def get_role(role_id: str, user: dict = Depends(get_current_user)):
    roles = load_roles()
    role = next((r for r in roles if r.id == role_id), None)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


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

    store = global_state.store
    if store:
        store.delete_role(role_id)

    return


PROVIDER_KEY_MAP = {
    "Claude": "ANTHROPIC_API_KEY",
    "GPT": "OPENAI_API_KEY",
    "Gemini": "GOOGLE_API_KEY",
}
PROVIDER_LANGCHAIN_MAP = {
    "Claude": "anthropic",
    "GPT": "openai",
    "Gemini": "google_genai",
}

_ENV_FILE = Path.home() / ".ostwin" / ".env"


@router.post("/api/models/{version}/test")
async def test_model_connection(version: str, user: dict = Depends(get_current_user)):
    import time
    from dotenv import dotenv_values
    from langchain.chat_models import init_chat_model

    provider = _detect_provider(version)
    env_key = PROVIDER_KEY_MAP.get(provider)
    lc_provider = PROVIDER_LANGCHAIN_MAP.get(provider)

    env_vars = dotenv_values(_ENV_FILE) if _ENV_FILE.exists() else {}
    api_key = env_vars.get(env_key, "")

    if not api_key:
        return {"status": "fail", "error": f"API key not configured for {provider}"}

    def _test():
        llm = init_chat_model(version, model_provider=lc_provider, api_key=api_key)
        llm.invoke("hi")

    start = time.time()
    try:
        await asyncio.get_event_loop().run_in_executor(None, _test)
        latency = int((time.time() - start) * 1000)
        return {"status": "ok", "latency_ms": latency}
    except Exception as exc:
        latency = int((time.time() - start) * 1000)
        return {"status": "fail", "latency_ms": latency, "error": str(exc)}
