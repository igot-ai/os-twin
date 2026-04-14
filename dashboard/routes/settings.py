"""
Settings API Routes -- Unified settings management with event broadcasting.

All endpoints are protected by get_current_user.
Mutation endpoints broadcast 'settings_updated' events via Broadcaster.
Vault endpoints NEVER return secret values, only is_set status.
"""

import logging
import os
import sys
import subprocess
from pathlib import Path as FSPath
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query, Body, Path
from pydantic import BaseModel

from dashboard.auth import get_current_user
from dashboard.global_state import broadcaster
import dashboard.global_state as global_state
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

    # Restart the bot process when channel config changes so it
    # picks up the new credentials / enabled flags on next boot.
    if namespace == "channels":
        _notify_bot_restart()

    # Sync Vertex AI env vars to ~/.ostwin/.env when provider config changes.
    if namespace == "providers":
        _sync_vertex_env(value)

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
        _sync_provider_key_to_env(key, request.value)
        # When the service-account JSON or Google API key changes,
        # re-run the Vertex env sync so GOOGLE_APPLICATION_CREDENTIALS
        # and related env vars are kept up-to-date in ~/.ostwin/.env.
        if key in ("google_service_account", "google"):
            _try_vertex_env_sync()

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
        # Comment out the corresponding env var in ~/.ostwin/.env
        env_var = _PROVIDER_ENV_MAP.get(key)
        if env_var:
            try:
                _remove_env_vars({env_var})
                os.environ.pop(env_var, None)
                logger.info("[SETTINGS] Removed %s from .env and os.environ", env_var)
            except Exception as exc:
                logger.warning("[SETTINGS] Failed to remove %s from .env: %s", env_var, exc)

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


def _notify_bot_restart() -> None:
    """Schedule a debounced bot restart after channel-related config changes."""
    if global_state.bot_manager is not None:
        logger.info("[SETTINGS] Channel config changed — scheduling bot restart")
        global_state.bot_manager.schedule_restart()
    else:
        logger.debug("[SETTINGS] No bot_manager — skipping restart signal")


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


# ── Vertex AI env-var sync ─────────────────────────────────────────────

_OSTWIN_DIR = FSPath.home() / ".ostwin"
_ENV_FILE = _OSTWIN_DIR / ".env"
_SA_FILE = _OSTWIN_DIR / "google-service-account.json"

# Env vars managed by this sync — never conflate with vault-managed keys.
_VERTEX_ENV_KEYS = {"GOOGLE_CLOUD_PROJECT", "VERTEX_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS"}

# Map vault provider keys -> env-var names that should be synced to ~/.ostwin/.env.
# When a provider secret is stored via the vault endpoint, the corresponding
# env var is upserted into the .env file so that processes reading the file
# (litellm, plan_agent, etc.) pick up the key immediately.
_PROVIDER_ENV_MAP: Dict[str, str] = {
    "google":    "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai":    "OPENAI_API_KEY",
}


def _sync_vertex_env(providers_value: Dict[str, Any]) -> None:
    """Sync Google Vertex AI settings to ~/.ostwin/.env and os.environ.

    Called whenever the ``providers`` namespace is patched.  When Google
    is in vertex mode the three required env vars are written; when it
    switches to gemini mode they are removed.
    """
    try:
        google = providers_value.get("google") or {}
        mode = google.get("deployment_mode", "gemini")

        if mode == "vertex":
            project_id = google.get("project_id", "")
            location = google.get("vertex_location") or "global"

            env_updates = {
                "GOOGLE_CLOUD_PROJECT": project_id,
                "VERTEX_LOCATION": location,
            }

            # Extract service-account JSON from vault → disk file
            try:
                from dashboard.lib.settings.vault import get_vault
                vault = get_vault()
                sa_json = vault.get("providers", "google_service_account")
                if sa_json:
                    # macOS Keychain returns multiline values as hex strings.
                    # Detect hex-encoded content and decode it back to JSON.
                    sa_json = _decode_if_hex(sa_json)
                    _OSTWIN_DIR.mkdir(parents=True, exist_ok=True)
                    _SA_FILE.write_text(sa_json)
                    env_updates["GOOGLE_APPLICATION_CREDENTIALS"] = str(_SA_FILE)
                    logger.info("[SETTINGS] Wrote service-account JSON to %s", _SA_FILE)
            except Exception as exc:
                logger.warning("[SETTINGS] Could not extract service-account from vault: %s", exc)

            _upsert_env_vars(env_updates)

            # Also set in the running process so litellm picks them up immediately
            for k, v in env_updates.items():
                if v:
                    os.environ[k] = v

            logger.info(
                "[SETTINGS] Vertex env synced: project=%s location=%s creds=%s",
                project_id, location,
                "set" if "GOOGLE_APPLICATION_CREDENTIALS" in env_updates else "unchanged",
            )
        else:
            # Switching away from vertex — clean up
            _remove_env_vars(_VERTEX_ENV_KEYS)
            for k in _VERTEX_ENV_KEYS:
                os.environ.pop(k, None)
            # Remove the on-disk service-account file
            if _SA_FILE.exists():
                _SA_FILE.unlink()
            logger.info("[SETTINGS] Vertex env vars removed (mode=%s)", mode)

    except Exception as exc:
        logger.warning("[SETTINGS] Vertex env sync failed: %s", exc)


def _parse_env_file() -> list[dict]:
    """Parse ~/.ostwin/.env into structured entries (reuses system.py format)."""
    if not _ENV_FILE.exists():
        return []
    entries: list[dict] = []
    for line in _ENV_FILE.read_text().splitlines():
        stripped = line.strip()
        if not stripped:
            entries.append({"type": "blank"})
        elif stripped.startswith("#") and "=" in stripped:
            rest = stripped.lstrip("# ").strip()
            key, _, value = rest.partition("=")
            entries.append({"type": "var", "key": key.strip(), "value": value.strip(), "enabled": False})
        elif stripped.startswith("#"):
            entries.append({"type": "comment", "text": stripped})
        elif "=" in stripped:
            key, _, value = stripped.partition("=")
            entries.append({"type": "var", "key": key.strip(), "value": value.strip(), "enabled": True})
        else:
            entries.append({"type": "comment", "text": stripped})
    return entries


def _serialize_env_file(entries: list[dict]) -> str:
    """Serialize structured entries back to .env format."""
    lines: list[str] = []
    for e in entries:
        t = e.get("type", "comment")
        if t == "blank":
            lines.append("")
        elif t == "comment":
            lines.append(e.get("text", ""))
        elif t == "var":
            key = e.get("key", "")
            value = e.get("value", "")
            if e.get("enabled", True):
                lines.append(f"{key}={value}")
            else:
                lines.append(f"# {key}={value}")
    return "\n".join(lines) + "\n"


def _upsert_env_vars(updates: Dict[str, str]) -> None:
    """Upsert env vars into ~/.ostwin/.env.  Creates the file if needed."""
    entries = _parse_env_file()
    existing_keys = {e.get("key"): i for i, e in enumerate(entries) if e.get("type") == "var"}

    for key, value in updates.items():
        if not value:
            continue
        if key in existing_keys:
            idx = existing_keys[key]
            entries[idx]["value"] = value
            entries[idx]["enabled"] = True
        else:
            # Append with a section header on first vertex var
            if not any(e.get("text", "").startswith("# ── Vertex AI") for e in entries):
                entries.append({"type": "blank"})
                entries.append({"type": "comment", "text": "# ── Vertex AI (managed by dashboard) ────────────────────────────────"})
            entries.append({"type": "var", "key": key, "value": value, "enabled": True})

    _OSTWIN_DIR.mkdir(parents=True, exist_ok=True)
    _ENV_FILE.write_text(_serialize_env_file(entries))


def _remove_env_vars(keys_to_remove: set[str]) -> None:
    """Comment out env vars from ~/.ostwin/.env."""
    if not _ENV_FILE.exists():
        return
    entries = _parse_env_file()
    changed = False
    for e in entries:
        if e.get("type") == "var" and e.get("key") in keys_to_remove and e.get("enabled"):
            e["enabled"] = False
            changed = True
    if changed:
        _ENV_FILE.write_text(_serialize_env_file(entries))


def _sync_provider_key_to_env(vault_key: str, secret: str) -> None:
    """Write a provider API key to ~/.ostwin/.env when it's stored via vault.

    Only known provider keys (google, anthropic, openai) are synced.
    This ensures that processes reading the .env file (litellm,
    plan_agent, etc.) see the updated key without a manual edit.
    """
    env_var = _PROVIDER_ENV_MAP.get(vault_key)
    if not env_var or not secret:
        return
    try:
        _upsert_env_vars({env_var: secret})
        os.environ[env_var] = secret
        logger.info("[SETTINGS] Synced %s to .env and os.environ", env_var)
    except Exception as exc:
        logger.warning("[SETTINGS] Failed to sync %s to .env: %s", env_var, exc)


def _try_vertex_env_sync() -> None:
    """Re-run Vertex env sync using current provider settings.

    Called after a vault secret change (e.g. service-account upload or
    Google API key update) so that ~/.ostwin/.env stays consistent with
    the current deployment mode.
    """
    try:
        from dashboard.lib.settings.resolver import get_settings_resolver
        resolver = get_settings_resolver()
        master = resolver.get_master_settings()
        providers_dict = master.providers.model_dump(exclude_none=True) if master.providers else {}
        _sync_vertex_env(providers_dict)
    except Exception as exc:
        logger.warning("[SETTINGS] Vertex env re-sync failed: %s", exc)


def _decode_if_hex(value: str) -> str:
    """Decode a hex-encoded string back to UTF-8 if applicable.

    macOS Keychain (``security find-generic-password -w``) returns
    multiline or binary-ish values as a hex string (no ``0x`` prefix).
    This helper detects that pattern and decodes it; plain-text values
    pass through unchanged.
    """
    stripped = value.strip()
    # Quick heuristic: hex strings are all [0-9a-fA-F] with even length
    if (
        len(stripped) > 2
        and len(stripped) % 2 == 0
        and all(c in "0123456789abcdefABCDEF" for c in stripped)
    ):
        try:
            decoded = bytes.fromhex(stripped).decode("utf-8")
            # Sanity-check: if the decoded content looks like JSON, use it
            if decoded.strip().startswith("{"):
                return decoded
        except (ValueError, UnicodeDecodeError):
            pass
    return value
