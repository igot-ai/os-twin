"""
connector_utils.py — Connector registry + instance storage.

Connectors package now lives at dashboard/connectors/ (moved from connectors/python/src/).
Instances are persisted in the zvec 'connectors' collection via global_state.store.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# ── Core connectors package (dashboard/connectors/) ─────────────────────────
try:
    from dashboard.connectors.registry import registry
    from dashboard.connectors.models import ConnectorConfig
    # Auto-register all connectors defined in the package
    import dashboard.connectors  # triggers __init__.py which imports all connectors
    REGISTRY_AVAILABLE = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(
        "[connector_utils] connectors package unavailable: %s", e
    )
    registry = None
    ConnectorConfig = None
    REGISTRY_AVAILABLE = False

# ── Optional vault / config-resolver (not yet implemented) ───────────────────
try:
    from vault import get_vault
    from config_resolver import ConfigResolver
except ImportError:
    get_vault = None
    ConfigResolver = None


# ── zvec-backed instance storage ─────────────────────────────────────────────
# Accessed via global_state.store (OSTwinStore) which owns the zvec collections.
# Falls back to a local JSON file if the store isn't ready yet (startup race).

_FALLBACK_JSON = Path.home() / ".ostwin" / "connectors.json"


def _get_store():
    """Return the live OSTwinStore, or None if not yet initialized."""
    try:
        from dashboard import global_state
        return global_state.store
    except Exception:
        return None


def _fallback_read() -> List[Dict[str, Any]]:
    if not _FALLBACK_JSON.exists():
        return []
    try:
        data = json.loads(_FALLBACK_JSON.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _fallback_write(instances: List[Dict[str, Any]]) -> None:
    _FALLBACK_JSON.parent.mkdir(parents=True, exist_ok=True)
    _FALLBACK_JSON.write_text(json.dumps(instances, indent=2))


# ── Public API ───────────────────────────────────────────────────────────────

def list_connector_instances() -> List[Dict[str, Any]]:
    """Return all connector instances from zvec (or fallback JSON)."""
    store = _get_store()
    if store is not None:
        return store.list_connector_instances()
    return _fallback_read()


def get_connector_instance(instance_id: str) -> Optional[Dict[str, Any]]:
    """Return a single connector instance by ID."""
    store = _get_store()
    if store is not None:
        return store.get_connector_instance(instance_id)
    return next((c for c in _fallback_read() if c["id"] == instance_id), None)


def save_connector_instance(instance: Dict[str, Any]) -> bool:
    """Upsert a connector instance (zvec or fallback JSON)."""
    if "id" not in instance:
        instance["id"] = str(uuid.uuid4())
    if "created_at" not in instance:
        instance["created_at"] = datetime.utcnow().isoformat()

    store = _get_store()
    if store is not None:
        return store.upsert_connector_instance(instance)

    # Fallback: read-modify-write JSON
    instances = _fallback_read()
    idx = next((i for i, c in enumerate(instances) if c["id"] == instance["id"]), None)
    if idx is not None:
        instances[idx] = instance
    else:
        instances.append(instance)
    _fallback_write(instances)
    return True


def delete_connector_instance(instance_id: str) -> bool:
    """Delete a connector instance by ID."""
    store = _get_store()
    if store is not None:
        return store.delete_connector_instance(instance_id)

    instances = _fallback_read()
    updated = [c for c in instances if c["id"] != instance_id]
    if len(updated) == len(instances):
        return False
    _fallback_write(updated)
    return True


# ── Backwards compat aliases (used by older code paths) ──────────────────────

def read_connector_configs() -> List[Dict[str, Any]]:
    """Alias for list_connector_instances() — kept for compatibility."""
    return list_connector_instances()


def save_connector_configs(configs: List[Dict[str, Any]]) -> None:
    """Bulk-replace connector instances — overwrites all. Kept for compat."""
    store = _get_store()
    if store is not None:
        # Delete all existing then upsert new list
        existing = store.list_connector_instances()
        for inst in existing:
            store.delete_connector_instance(inst["id"])
        for inst in configs:
            store.upsert_connector_instance(inst)
    else:
        _fallback_write(configs)


# ── Vault helpers ─────────────────────────────────────────────────────────────

async def resolve_connector_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Optionally resolve vault references in a config dict."""
    if not ConfigResolver or not get_vault:
        return config
    resolver = ConfigResolver()
    vault = get_vault()
    return await resolver.resolve(config, vault)
