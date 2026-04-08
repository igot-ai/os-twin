"""
Settings API Routes -- Unified settings management with event broadcasting.

All endpoints are protected by get_current_user.
Mutation endpoints broadcast 'settings_updated' events via Broadcaster.
Vault endpoints NEVER return secret values, only is_set status.
"""

import logging
import sys
import subprocess
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query, Body, Path
from pydantic import BaseModel

from dashboard.auth import get_current_user
from dashboard.global_state import broadcaster
from dashboard.models import MasterSettings, EffectiveResolution
from dashboard.lib.settings import get_settings_resolver
from dashboard.lib.settings.vault import get_vault
from dashboard.lib.settings.opencode_sync import sync_opencode_config, SyncResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── Request / Response Models ──────────────────────────────────────────


class VaultValueRequest(BaseModel):
    value: str


class VaultStatusResponse(BaseModel):
    is_set: bool


class VaultScopeResponse(BaseModel):
    keys: Dict[str, VaultStatusResponse]


class VaultInfoResponse(BaseModel):
    """Exposes which vault backend is active and its health."""

    backend: str
    healthy: bool
    message: str
    details: Dict[str, str]


class TargetSyncDetail(BaseModel):
    """Per-target detail (opencode.json or auth.json)."""
    synced: List[str] = []
    removed: List[str] = []
    skipped: List[str] = []
    path: str = ""
    error: Optional[str] = None


class OpenCodeSyncResponse(BaseModel):
    """Result of syncing provider keys to opencode.json + auth.json."""

    synced: List[str]
    removed: List[str]
    skipped: List[str]
    path: str
    error: Optional[str] = None
    opencode_json: Optional[TargetSyncDetail] = None
    auth_json: Optional[TargetSyncDetail] = None


# ── Read Endpoints ─────────────────────────────────────────────────────


@router.get("", response_model=MasterSettings)
async def get_master_settings(
    user: dict = Depends(get_current_user),
):
    """Get master settings with vault refs preserved as ${vault:...} strings.

    Never dereferences vault refs.  Returns the raw config structure.
    """
    resolver = get_settings_resolver()
    return resolver.get_master_settings()


@router.get("/effective", response_model=EffectiveResolution)
async def get_effective_settings(
    role: str = Query(..., description="Role to resolve settings for"),
    plan_id: Optional[str] = Query(None, description="Plan ID for plan-level override"),
    task_ref: Optional[str] = Query(None, description="Task ref for room-level override"),
    user: dict = Depends(get_current_user),
):
    """Get effective settings for a role with provenance.

    Resolves vault refs but masks secrets as ***.
    """
    resolver = get_settings_resolver()
    return resolver.resolve_role(
        role, plan_id=plan_id, task_ref=task_ref, masked=True,
    )


@router.get("/schema")
async def get_settings_schema(
    user: dict = Depends(get_current_user),
):
    """Get JSON schema for MasterSettings (for dynamic frontend forms)."""
    return MasterSettings.model_json_schema()


# ── Mutation Endpoints ─────────────────────────────────────────────────

_VALID_NAMESPACES = frozenset({
    "providers", "roles", "runtime", "memory",
    "channels", "autonomy", "observability",
})


@router.put("/{namespace}")
async def patch_global_namespace(
    namespace: str = Path(..., description="Namespace to patch"),
    value: Dict[str, Any] = Body(..., description="Settings to apply"),
    user: dict = Depends(get_current_user),
):
    """Patch a global namespace in config.json."""
    if namespace not in _VALID_NAMESPACES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid namespace '{namespace}'. Must be one of: {sorted(_VALID_NAMESPACES)}",
        )

    resolver = get_settings_resolver()
    resolver.patch_namespace(namespace, value)

    await broadcaster.broadcast("settings_updated", {
        "namespace": namespace,
        "settings": value,
    })
    return {"status": "ok"}


@router.put("/plan/{plan_id}/role/{role}")
async def patch_plan_role(
    plan_id: str = Path(..., description="Plan ID"),
    role: str = Path(..., description="Role name"),
    value: Dict[str, Any] = Body(..., description="Settings to apply"),
    user: dict = Depends(get_current_user),
):
    """Patch plan-level role override."""
    resolver = get_settings_resolver()
    resolver.patch_plan_role(plan_id, role, value)

    await broadcaster.broadcast("settings_updated", {
        "namespace": "plan",
        "plan_id": plan_id,
        "role": role,
        "settings": value,
    })
    return {"status": "ok"}


@router.put("/room/{plan_id}/{task_ref}/role/{role}")
async def patch_room_role(
    plan_id: str = Path(..., description="Plan ID"),
    task_ref: str = Path(..., description="Task reference"),
    role: str = Path(..., description="Role name"),
    value: Dict[str, Any] = Body(..., description="Settings to apply"),
    user: dict = Depends(get_current_user),
):
    """Patch room-level role override."""
    resolver = get_settings_resolver()
    resolver.patch_room_role(plan_id, task_ref, role, value)

    await broadcaster.broadcast("settings_updated", {
        "namespace": "room",
        "plan_id": plan_id,
        "task_ref": task_ref,
        "role": role,
        "settings": value,
    })
    return {"status": "ok"}


@router.post("/reset/{namespace}")
async def reset_namespace(
    namespace: str = Path(..., description="Namespace to reset"),
    user: dict = Depends(get_current_user),
):
    """Reset namespace to defaults."""
    resolver = get_settings_resolver()
    resolver.reset_namespace(namespace)

    await broadcaster.broadcast("settings_updated", {
        "namespace": namespace,
        "action": "reset",
    })
    return {"status": "ok"}


# ── Provider Test Endpoint ─────────────────────────────────────────────

@router.post("/test/{provider}")
async def test_provider_connection(
    provider: str = Path(
        ...,
        description="Provider name (openai, anthropic, google, or custom name)",
    ),
    user: dict = Depends(get_current_user),
):
    """Test provider connection.  Returns latency_ms on success."""
    from dashboard.routes.roles import test_model_connection

    if provider == "google":
        try:
            resolver = get_settings_resolver()
            master = resolver.get_master_settings()
            google_cfg = master.providers.google
            mode = (google_cfg.deployment_mode or "gemini") if google_cfg else "gemini"
        except Exception:
            mode = "gemini"
        test_model = (
            "google-vertex/gemini-3-flash-preview"
            if mode == "vertex"
            else "gemini/gemini-3-flash-preview"
        )
    else:
        _map = {
            "openai": "gpt-4o",
            "anthropic": "claude-3-5-sonnet-20241022",
            "byteplus": "byteplus/seed-2-0-pro-260328",
        }
        test_model = _map.get(provider, provider)

    return await test_model_connection(test_model, user=user)


# ── Vault Management Endpoints ─────────────────────────────────────────

@router.get("/vault/status", response_model=VaultInfoResponse)
async def vault_status(
    user: dict = Depends(get_current_user),
):
    """Return the active vault backend type and its health status."""
    vault = get_vault()
    health = vault.health()
    return VaultInfoResponse(
        backend=health.backend_type,
        healthy=health.healthy,
        message=health.message,
        details=health.details,
    )


@router.post("/vault/{scope}/{key}", response_model=VaultStatusResponse)
async def store_vault_secret(
    scope: str = Path(..., description="Vault scope (e.g., 'providers')"),
    key: str = Path(..., description="Secret key"),
    request: VaultValueRequest = Body(..., description="Secret value"),
    user: dict = Depends(get_current_user),
):
    """Store a secret in the vault.

    Accepts secret via POST body only.
    Returns ``{is_set: true}`` on success.
    NEVER returns the secret value.

    When *scope* is ``providers``, automatically syncs the opencode.json
    config so the CLI picks up the new key immediately.
    """
    vault = get_vault()
    vault.set(scope, key, request.value)

    # Auto-sync opencode.json when a provider key changes
    if scope == "providers":
        _try_opencode_sync()

    return VaultStatusResponse(is_set=True)


@router.get("/vault/{scope}", response_model=VaultScopeResponse)
async def list_vault_keys(
    scope: str = Path(..., description="Vault scope to list"),
    user: dict = Depends(get_current_user),
):
    """List all keys in a vault scope with status.

    Returns ``{key: {is_set: bool}}`` map.  NEVER returns secret values.
    """
    vault = get_vault()
    keys_data = vault.list_keys(scope)

    keys = {
        key: VaultStatusResponse(is_set=data.get("is_set", False))
        for key, data in keys_data.items()
    }
    return VaultScopeResponse(keys=keys)


@router.delete("/vault/{scope}/{key}")
async def delete_vault_secret(
    scope: str = Path(..., description="Vault scope"),
    key: str = Path(..., description="Secret key to delete"),
    user: dict = Depends(get_current_user),
):
    """Delete a secret from the vault.  Returns 404 if not found."""
    vault = get_vault()
    deleted = vault.delete(scope, key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Secret not found")

    # Auto-sync opencode.json when a provider key is removed
    if scope == "providers":
        _try_opencode_sync()

    return {"status": "deleted"}


# ── Vault Migration Endpoint ──────────────────────────────────────────

@router.post("/vault/migrate")
async def migrate_secrets_to_vault(
    dry_run: bool = Query(False, description="Preview changes without writing"),
    user: dict = Depends(get_current_user),
):
    """Move plaintext secrets from ~/.ostwin/.env into the vault."""
    cmd = [sys.executable, "-m", "dashboard.scripts.migrate_secrets_to_vault"]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# ── OpenCode Config Sync ──────────────────────────────────────────────

@router.post("/opencode/sync", response_model=OpenCodeSyncResponse)
async def sync_opencode(
    user: dict = Depends(get_current_user),
):
    """Sync provider keys + models to ~/.config/opencode/opencode.json.

    Only gemini (non-vertex) and byteplus are synced -- other providers
    are handled natively by OpenCode via env vars.
    """
    result = sync_opencode_config()

    def _target_detail(t):
        if t is None:
            return None
        return TargetSyncDetail(
            synced=t.synced, removed=t.removed,
            skipped=t.skipped, path=t.path, error=t.error,
        )

    return OpenCodeSyncResponse(
        synced=result.synced,
        removed=result.removed,
        skipped=result.skipped,
        path=result.path,
        error=result.error,
        opencode_json=_target_detail(result.opencode_json),
        auth_json=_target_detail(result.auth_json),
    )


# ── Helpers ────────────────────────────────────────────────────────────

def _try_opencode_sync() -> None:
    """Best-effort sync -- never let a sync failure break vault ops."""
    try:
        result = sync_opencode_config()
        if result.error:
            logger.warning("opencode sync error: %s", result.error)
        elif result.synced or result.removed:
            logger.info(
                "opencode sync: synced=%s removed=%s",
                result.synced, result.removed,
            )
    except Exception as exc:
        logger.warning("opencode sync failed: %s", exc)
