"""
Models.dev loader -- fetch, filter, and cache model catalog.

On every server startup this module:

1. Fetches the full model catalog from ``https://models.dev/api.json``.
2. Reads ``~/.local/share/opencode/auth.json`` to discover which providers
   the user has API keys for.
3. Reads ``~/.config/opencode/opencode.json`` for any custom providers.
4. Filters the catalog to only include models from configured providers.
5. Writes the result to ``~/.local/share/opencode/configured_models.json``
   so it can be served without re-fetching.

The ``get_configured_models()`` function returns the current in-memory
catalog (populated at startup or on demand).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MODELS_DEV_URL = "https://models.dev/api.json"
MODELS_DEV_LOGO_URL = "https://models.dev/logos/{provider}.svg"

AUTH_JSON_PATH = Path.home() / ".local" / "share" / "opencode" / "auth.json"
OPENCODE_CONFIG_PATH = Path.home() / ".config" / "opencode" / "opencode.json"
CONFIGURED_MODELS_PATH = Path.home() / ".local" / "share" / "opencode" / "configured_models.json"

# In-memory cache
_cached_models: Optional[Dict[str, Any]] = None
_cached_timestamp: float = 0.0


# ── Public API ────────────────────────────────────────────────────────


def load_models_on_startup() -> Dict[str, Any]:
    """Fetch models.dev/api.json and build configured_models.json.

    Called during server startup.  Returns the configured models dict.
    """
    global _cached_models, _cached_timestamp

    raw_catalog = _fetch_models_dev()
    if raw_catalog is None:
        # Fallback: try reading from cached file
        raw_catalog = _read_cached_raw()
        if raw_catalog is None:
            logger.warning("No models catalog available -- using empty catalog")
            _cached_models = {"providers": {}, "loaded_at": _iso_now()}
            return _cached_models

    configured_providers = _read_configured_providers()
    configured = _build_configured_models(raw_catalog, configured_providers)

    # Persist to disk
    _write_json(CONFIGURED_MODELS_PATH, configured)

    _cached_models = configured
    _cached_timestamp = time.time()
    logger.info(
        "Models catalog loaded: %d providers, %d total models",
        len(configured.get("providers", {})),
        sum(
            len(p.get("models", {}))
            for p in configured.get("providers", {}).values()
        ),
    )
    return configured


def get_configured_models() -> Dict[str, Any]:
    """Return the in-memory configured models.

    If not yet loaded (e.g. startup hasn't run), loads from disk cache
    or fetches fresh.
    """
    global _cached_models
    if _cached_models is not None:
        return _cached_models
    # Try disk cache first
    if CONFIGURED_MODELS_PATH.exists():
        try:
            _cached_models = json.loads(CONFIGURED_MODELS_PATH.read_text())
            return _cached_models
        except (json.JSONDecodeError, OSError):
            pass
    # Fall back to full load
    return load_models_on_startup()


def get_configured_providers() -> Dict[str, Any]:
    """Return the configured providers from auth.json + opencode.json."""
    return _read_configured_providers()


def get_provider_logo_url(provider_id: str) -> str:
    """Return the logo URL for a provider."""
    return MODELS_DEV_LOGO_URL.format(provider=provider_id)


def get_model_registry_from_configured() -> Dict[str, List[dict]]:
    """Build the model registry dict in the format the frontend expects.

    Returns ``{provider_display_name: [model_dict, ...]}`` where each
    model_dict has keys: id, label, context_window, tier, provider_id,
    family, cost, logo_url.

    This replaces the old hardcoded ``_CATALOG`` in models_registry.py.
    """
    configured = get_configured_models()
    providers = configured.get("providers", {})

    registry: Dict[str, List[dict]] = {}

    for provider_id, provider_data in providers.items():
        display_name = provider_data.get("name", provider_id)
        models_map = provider_data.get("models", {})

        model_list: List[dict] = []
        for model_id, model_data in models_map.items():
            limit = model_data.get("limit", {})
            ctx = limit.get("context")
            ctx_str = _format_context_window(ctx) if ctx else ""

            cost = model_data.get("cost", {})

            model_entry = {
                "id": model_id,
                "label": model_data.get("name", model_id),
                "context_window": ctx_str,
                "tier": _classify_tier(model_data),
                "provider_id": provider_id,
                "family": model_data.get("family", ""),
                "cost": cost,
                "logo_url": get_provider_logo_url(provider_id),
                "reasoning": model_data.get("reasoning", False),
                "tool_call": model_data.get("tool_call", False),
                "attachment": model_data.get("attachment", False),
                "source": model_data.get("source", "models.dev"),
            }
            model_list.append(model_entry)

        if model_list:
            registry[display_name] = model_list

    return registry


def get_available_providers() -> List[Dict[str, Any]]:
    """Return ALL providers from models.dev (not just configured ones).

    Used by the "Add Provider" modal so users can browse and select
    a provider to configure.  Each entry has:
    ``id``, ``name``, ``logo_url``, ``model_count``, ``doc``, ``env``.
    """
    raw = _read_cached_raw()
    if raw is None:
        raw = _fetch_models_dev() or {}

    configured = set((_read_configured_providers() or {}).keys())

    result: List[Dict[str, Any]] = []
    for pid, pdata in sorted(raw.items(), key=lambda kv: kv[1].get("name", kv[0])):
        if not isinstance(pdata, dict) or "models" not in pdata:
            continue
        result.append({
            "id": pid,
            "name": pdata.get("name", pid),
            "logo_url": get_provider_logo_url(pid),
            "model_count": len(pdata.get("models", {})),
            "doc": pdata.get("doc", ""),
            "env": pdata.get("env", []),
            "already_configured": pid in configured,
        })
    return result


def invalidate_cache() -> None:
    """Clear the in-memory cache, forcing a reload on next access."""
    global _cached_models, _cached_timestamp
    _cached_models = None
    _cached_timestamp = 0.0


# ── Internal helpers ──────────────────────────────────────────────────


def _fetch_models_dev() -> Optional[Dict[str, Any]]:
    """Fetch the full models catalog from models.dev."""
    try:
        req = urllib.request.Request(
            MODELS_DEV_URL,
            headers={"User-Agent": "ostwin-dashboard/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # Cache the raw catalog for fallback
            _write_json(
                CONFIGURED_MODELS_PATH.parent / "models_dev_raw.json",
                data,
            )
            logger.info("Fetched models.dev catalog: %d providers", len(data))
            return data
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to fetch models.dev/api.json: %s", exc)
        return None


def _read_cached_raw() -> Optional[Dict[str, Any]]:
    """Read the raw models.dev cache from disk."""
    raw_path = CONFIGURED_MODELS_PATH.parent / "models_dev_raw.json"
    if raw_path.exists():
        try:
            return json.loads(raw_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _read_configured_providers() -> Dict[str, Dict[str, Any]]:
    """Read auth.json + opencode.json to discover configured providers.

    Returns ``{provider_id: {type, key?, ...}}``.
    """
    providers: Dict[str, Dict[str, Any]] = {}

    # 1. auth.json -- native providers
    if AUTH_JSON_PATH.exists():
        try:
            auth_data = json.loads(AUTH_JSON_PATH.read_text())
            for provider_id, entry in auth_data.items():
                if isinstance(entry, dict) and entry.get("type") == "api":
                    providers[provider_id] = {
                        "type": "api",
                        "source": "auth.json",
                        "has_key": bool(entry.get("key")),
                    }
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read auth.json: %s", exc)

    # 2. opencode.json -- custom providers (provider block)
    if OPENCODE_CONFIG_PATH.exists():
        try:
            oc_data = json.loads(OPENCODE_CONFIG_PATH.read_text())
            for provider_id, entry in oc_data.get("provider", {}).items():
                if provider_id not in providers:
                    providers[provider_id] = {
                        "type": "custom",
                        "source": "opencode.json",
                        "has_key": bool(
                            entry.get("options", {}).get("apiKey")
                        ),
                    }
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read opencode.json: %s", exc)

    return providers


def _build_configured_models(
    raw_catalog: Dict[str, Any],
    configured_providers: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Build configured_models from models.dev + opencode.json custom models.

    Two sources are merged per provider:

    1. **models.dev catalog** -- rich metadata (cost, limits, modalities).
       Each model is tagged ``"source": "models.dev"``.
    2. **opencode.json provider block** -- custom / manually-added models.
       Each model is tagged ``"source": "custom"``.  These appear even
       when the provider doesn't exist in models.dev at all.

    Returns the structured configured_models.json content.
    """
    # Read the opencode.json provider block once
    custom_providers = _read_opencode_custom_providers()

    result: Dict[str, Any] = {
        "loaded_at": _iso_now(),
        "source": MODELS_DEV_URL,
        "configured_provider_ids": sorted(configured_providers.keys()),
        "providers": {},
    }

    for provider_id, provider_cfg in configured_providers.items():
        raw_provider = raw_catalog.get(provider_id)
        custom_block = custom_providers.get(provider_id)

        # Skip providers that exist in neither source
        if raw_provider is None and custom_block is None:
            logger.debug(
                "Provider '%s' configured in %s but not found in "
                "models.dev or opencode.json",
                provider_id,
                provider_cfg.get("source", "?"),
            )
            continue

        # Build provider metadata (prefer models.dev, fall back to custom)
        if raw_provider is not None:
            provider_entry: Dict[str, Any] = {
                "id": provider_id,
                "name": raw_provider.get("name", provider_id),
                "doc": raw_provider.get("doc", ""),
                "api": raw_provider.get("api", ""),
                "npm": raw_provider.get("npm", ""),
                "env": raw_provider.get("env", []),
                "logo_url": get_provider_logo_url(provider_id),
                "source": provider_cfg.get("source", ""),
                "models": {},
            }
        else:
            # Provider only exists in opencode.json
            base_url = (custom_block or {}).get("options", {}).get("baseURL", "")
            provider_entry = {
                "id": provider_id,
                "name": provider_id,
                "doc": "",
                "api": base_url,
                "npm": "",
                "env": [],
                "logo_url": get_provider_logo_url(provider_id),
                "source": "opencode.json",
                "models": {},
            }

        # ── 1) Ingest models.dev models ───────────────────────────
        if raw_provider is not None:
            for model_id, model_data in raw_provider.get("models", {}).items():
                provider_entry["models"][model_id] = {
                    "id": model_id,
                    "name": model_data.get("name", model_id),
                    "family": model_data.get("family", ""),
                    "reasoning": model_data.get("reasoning", False),
                    "tool_call": model_data.get("tool_call", False),
                    "attachment": model_data.get("attachment", False),
                    "temperature": model_data.get("temperature", True),
                    "cost": model_data.get("cost", {}),
                    "limit": model_data.get("limit", {}),
                    "modalities": model_data.get("modalities", {}),
                    "knowledge": model_data.get("knowledge", ""),
                    "release_date": model_data.get("release_date", ""),
                    "source": "models.dev",
                }

        # ── 2) Merge custom models from opencode.json ─────────────
        if custom_block is not None:
            for model_key, model_def in custom_block.get("models", {}).items():
                # The opencode model key is the short id (e.g. "seed-2-0-pro-260328").
                # Build the full model id the same way opencode does:
                #   name field like "byteplus:seed-2-0-pro-260328"
                oc_name = model_def.get("name", model_key)
                # If the model already came from models.dev, skip it
                if model_key in provider_entry["models"]:
                    continue
                provider_entry["models"][model_key] = {
                    "id": model_key,
                    "name": oc_name,
                    "family": "",
                    "reasoning": False,
                    "tool_call": False,
                    "attachment": False,
                    "temperature": True,
                    "cost": {},
                    "limit": {},
                    "modalities": {},
                    "knowledge": "",
                    "release_date": "",
                    "source": "custom",
                }

        if provider_entry["models"]:
            result["providers"][provider_id] = provider_entry

    return result


def _read_opencode_custom_providers() -> Dict[str, Any]:
    """Read the ``provider`` block from opencode.json.

    Returns ``{provider_id: {options, models}}``.
    """
    if not OPENCODE_CONFIG_PATH.exists():
        return {}
    try:
        data = json.loads(OPENCODE_CONFIG_PATH.read_text())
        return data.get("provider", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _format_context_window(ctx: int) -> str:
    """Format token count to human-readable string."""
    if ctx >= 1_000_000:
        val = ctx / 1_000_000
        return f"{val:g}M"
    elif ctx >= 1_000:
        val = ctx / 1_000
        return f"{val:g}K"
    return str(ctx)


def _classify_tier(model_data: dict) -> str:
    """Classify a model into a tier based on its properties."""
    if model_data.get("reasoning"):
        return "reasoning"
    cost = model_data.get("cost", {})
    input_cost = cost.get("input", 0)
    if input_cost >= 10:
        return "flagship"
    elif input_cost >= 1:
        return "balanced"
    elif input_cost > 0:
        return "fast"
    return "unknown"


def _iso_now() -> str:
    """Return current UTC time as ISO string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    """Atomically write a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, default=str) + "\n")
        os.replace(str(tmp), str(path))
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise
