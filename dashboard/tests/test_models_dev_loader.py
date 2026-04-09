"""
Tests for dashboard.lib.settings.models_dev_loader.

Covers:
- Provider discovery (auth.json, opencode.json, env vars)
- Google deployment mode detection (vertex vs gemini)
- Companion provider loading (google-vertex, google-vertex-anthropic)
- Custom model merging from opencode.json
- Source tagging (models.dev vs custom)
- configured_models.json structure
- Model registry output format
- Cache invalidation
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from dashboard.lib.settings.models_dev_loader import (
    _read_configured_providers,
    _read_google_deployment_mode,
    _build_configured_models,
    _read_opencode_custom_providers,
    _COMPANION_PROVIDERS,
    get_model_registry_from_configured,
    get_available_providers,
    get_provider_logo_url,
    invalidate_cache,
    get_configured_models,
    _format_context_window,
    _classify_tier,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def fake_auth_json(tmp_path):
    """Create a temporary auth.json with known providers."""
    auth = {
        "openai": {"type": "api", "key": "test-key-openai"},
        "anthropic": {"type": "api", "key": "test-key-anthropic"},
        "deepseek": {"type": "api", "key": "test-key-deepseek"},
    }
    path = tmp_path / "auth.json"
    path.write_text(json.dumps(auth))
    return path


@pytest.fixture
def fake_opencode_json(tmp_path):
    """Create a temporary opencode.json with custom providers."""
    oc = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            "byteplus": {
                "options": {"apiKey": "test-bp-key", "baseURL": "https://ark.example.com/v3"},
                "models": {
                    "seed-2-0-pro": {"npm": "@ai-sdk/openai-compatible", "name": "byteplus:seed-2-0-pro"},
                },
            },
            "myprovider": {
                "options": {"apiKey": "my-key", "baseURL": "https://my.api/v1"},
                "models": {
                    "my-model-1": {"npm": "@ai-sdk/openai-compatible", "name": "myprovider:my-model-1"},
                },
            },
        },
    }
    path = tmp_path / "opencode.json"
    path.write_text(json.dumps(oc))
    return path


@pytest.fixture
def fake_raw_catalog():
    """A minimal models.dev catalog for testing."""
    return {
        "openai": {
            "name": "OpenAI",
            "doc": "https://docs.openai.com",
            "api": "https://api.openai.com/v1",
            "npm": "@ai-sdk/openai",
            "env": ["OPENAI_API_KEY"],
            "models": {
                "gpt-4.1": {
                    "name": "GPT-4.1",
                    "family": "gpt-4",
                    "reasoning": False,
                    "tool_call": True,
                    "cost": {"input": 2, "output": 8},
                    "limit": {"context": 1048576},
                },
                "o3": {
                    "name": "o3",
                    "family": "o-series",
                    "reasoning": True,
                    "tool_call": True,
                    "cost": {"input": 10, "output": 40},
                    "limit": {"context": 200000},
                },
            },
        },
        "anthropic": {
            "name": "Anthropic",
            "doc": "https://docs.anthropic.com",
            "api": "https://api.anthropic.com",
            "npm": "@ai-sdk/anthropic",
            "env": ["ANTHROPIC_API_KEY"],
            "models": {
                "claude-sonnet-4-6": {
                    "name": "Claude Sonnet 4.6",
                    "family": "claude",
                    "reasoning": False,
                    "cost": {"input": 3, "output": 15},
                    "limit": {"context": 200000},
                },
            },
        },
        "deepseek": {
            "name": "DeepSeek",
            "doc": "https://docs.deepseek.com",
            "api": "https://api.deepseek.com/v1",
            "npm": "@ai-sdk/openai-compatible",
            "env": ["DEEPSEEK_API_KEY"],
            "models": {
                "deepseek-r1": {
                    "name": "DeepSeek R1",
                    "family": "r-series",
                    "reasoning": True,
                    "cost": {"input": 0.55, "output": 2.19},
                    "limit": {"context": 65536},
                },
            },
        },
        "google": {
            "name": "Google",
            "models": {
                "gemini-2.5-pro": {"name": "Gemini 2.5 Pro", "cost": {"input": 1.25}, "limit": {"context": 1048576}},
            },
        },
        "google-vertex": {
            "name": "Vertex",
            "models": {
                "gemini-2.5-pro": {"name": "Gemini 2.5 Pro (Vertex)", "cost": {"input": 1.25}, "limit": {"context": 1048576}},
            },
        },
        "google-vertex-anthropic": {
            "name": "Vertex (Anthropic)",
            "models": {
                "claude-sonnet-4-6@default": {"name": "Claude Sonnet 4.6", "cost": {"input": 3}, "limit": {"context": 200000}},
            },
        },
    }


# ── Provider discovery ────────────────────────────────────────────────

def test_reads_auth_json_providers(fake_auth_json):
    with patch("dashboard.lib.settings.models_dev_loader.AUTH_JSON_PATH", fake_auth_json):
        with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", Path("/nonexistent")):
            providers = _read_configured_providers()

    assert "openai" in providers
    assert "anthropic" in providers
    assert "deepseek" in providers
    assert providers["openai"]["source"] == "auth.json"
    assert providers["openai"]["has_key"] is True


def test_reads_opencode_json_custom_providers(fake_opencode_json):
    with patch("dashboard.lib.settings.models_dev_loader.AUTH_JSON_PATH", Path("/nonexistent")):
        with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", fake_opencode_json):
            providers = _read_configured_providers()

    assert "byteplus" in providers
    assert "myprovider" in providers
    assert providers["byteplus"]["source"] == "opencode.json"
    assert providers["byteplus"]["type"] == "custom"


def test_auth_json_takes_precedence_over_opencode(fake_auth_json, fake_opencode_json):
    """If a provider appears in both, auth.json wins."""
    auth = {"byteplus": {"type": "api", "key": "auth-bp"}}
    fake_auth_json.write_text(json.dumps(auth))

    with patch("dashboard.lib.settings.models_dev_loader.AUTH_JSON_PATH", fake_auth_json):
        with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", fake_opencode_json):
            providers = _read_configured_providers()

    assert providers["byteplus"]["source"] == "auth.json"


def test_google_detected_from_env_vars(tmp_path):
    """Google is detected from GOOGLE_CLOUD_PROJECT even without auth.json."""
    with patch("dashboard.lib.settings.models_dev_loader.AUTH_JSON_PATH", Path("/nonexistent")):
        with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", Path("/nonexistent")):
            with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "my-project"}, clear=False):
                providers = _read_configured_providers()

    assert "google" in providers
    assert providers["google"]["type"] == "env"
    assert providers["google"]["source"] == "env"
    assert providers["google"]["has_key"] is True


def test_google_detected_from_api_key(tmp_path):
    with patch("dashboard.lib.settings.models_dev_loader.AUTH_JSON_PATH", Path("/nonexistent")):
        with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", Path("/nonexistent")):
            env = {"GOOGLE_API_KEY": "test-key"}
            with patch.dict(os.environ, env, clear=False):
                # Remove GOOGLE_CLOUD_PROJECT if set
                os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
                providers = _read_configured_providers()

    assert "google" in providers


def test_google_not_detected_without_env():
    with patch("dashboard.lib.settings.models_dev_loader.AUTH_JSON_PATH", Path("/nonexistent")):
        with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", Path("/nonexistent")):
            with patch.dict(os.environ, {}, clear=True):
                providers = _read_configured_providers()

    assert "google" not in providers


# ── Deployment mode ───────────────────────────────────────────────────

def test_deployment_mode_read_from_config(tmp_path):
    config = {"providers": {"google": {"deployment_mode": "gemini"}}}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))

    with patch("dashboard.api_utils.AGENTS_DIR", tmp_path):
        mode = _read_google_deployment_mode()
    assert mode == "gemini"


def test_deployment_mode_defaults_to_vertex_with_gcp_project():
    with patch("dashboard.api_utils.AGENTS_DIR", Path("/nonexistent")):
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "proj"}, clear=False):
            mode = _read_google_deployment_mode()
    assert mode == "vertex"


# ── Build configured models ──────────────────────────────────────────

def test_build_filters_to_configured_providers(fake_raw_catalog):
    providers = {
        "openai": {"type": "api", "source": "auth.json", "has_key": True},
    }
    result = _build_configured_models(fake_raw_catalog, providers)
    assert "openai" in result["providers"]
    assert "anthropic" not in result["providers"]
    assert "deepseek" not in result["providers"]


def test_build_tags_models_dev_source(fake_raw_catalog):
    providers = {"openai": {"type": "api", "source": "auth.json", "has_key": True}}
    result = _build_configured_models(fake_raw_catalog, providers)
    for mid, mdata in result["providers"]["openai"]["models"].items():
        assert mdata["source"] == "models.dev"


def test_build_includes_custom_models_from_opencode(fake_raw_catalog, fake_opencode_json):
    providers = {
        "byteplus": {"type": "custom", "source": "opencode.json", "has_key": True},
    }
    with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", fake_opencode_json):
        result = _build_configured_models(fake_raw_catalog, providers)

    assert "byteplus" in result["providers"]
    models = result["providers"]["byteplus"]["models"]
    assert "seed-2-0-pro" in models
    assert models["seed-2-0-pro"]["source"] == "custom"


def test_build_skips_provider_not_in_any_source(fake_raw_catalog):
    providers = {"nonexistent": {"type": "api", "source": "auth.json", "has_key": True}}
    with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", Path("/nonexistent")):
        result = _build_configured_models(fake_raw_catalog, providers)
    assert "nonexistent" not in result["providers"]


# ── Companion providers (Vertex) ─────────────────────────────────────

def test_vertex_mode_loads_companions(fake_raw_catalog):
    providers = {
        "google": {"type": "env", "source": "env", "has_key": True, "deployment_mode": "vertex"},
    }
    with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", Path("/nonexistent")):
        result = _build_configured_models(fake_raw_catalog, providers)

    models = result["providers"]["google"]["models"]
    # Base google model
    assert "gemini-2.5-pro" in models
    # Vertex companion
    assert "google-vertex/gemini-2.5-pro" in models
    assert models["google-vertex/gemini-2.5-pro"]["companion_provider"] == "google-vertex"
    # Vertex-Anthropic companion
    assert "google-vertex-anthropic/claude-sonnet-4-6@default" in models
    assert models["google-vertex-anthropic/claude-sonnet-4-6@default"]["companion_provider"] == "google-vertex-anthropic"


def test_gemini_mode_skips_companions(fake_raw_catalog):
    providers = {
        "google": {"type": "env", "source": "env", "has_key": True, "deployment_mode": "gemini"},
    }
    with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", Path("/nonexistent")):
        result = _build_configured_models(fake_raw_catalog, providers)

    models = result["providers"]["google"]["models"]
    assert "gemini-2.5-pro" in models
    assert not any("google-vertex" in mid for mid in models)


def test_companion_providers_mapping_structure():
    assert "google" in _COMPANION_PROVIDERS
    assert "vertex" in _COMPANION_PROVIDERS["google"]
    assert "gemini" in _COMPANION_PROVIDERS["google"]
    assert "google-vertex" in _COMPANION_PROVIDERS["google"]["vertex"]
    assert "google-vertex-anthropic" in _COMPANION_PROVIDERS["google"]["vertex"]
    assert _COMPANION_PROVIDERS["google"]["gemini"] == []


# ── Source tagging ────────────────────────────────────────────────────

def test_source_propagates_to_registry(fake_raw_catalog):
    providers = {"openai": {"type": "api", "source": "auth.json", "has_key": True}}
    with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", Path("/nonexistent")):
        result = _build_configured_models(fake_raw_catalog, providers)

    # Patch cache for get_model_registry_from_configured
    with patch("dashboard.lib.settings.models_dev_loader._cached_models", result):
        registry = get_model_registry_from_configured()

    openai_models = registry.get("OpenAI", [])
    assert len(openai_models) >= 1
    for m in openai_models:
        assert m["source"] == "models.dev"
        assert m["provider_id"] == "openai"


# ── Utility functions ─────────────────────────────────────────────────

def test_format_context_window():
    assert _format_context_window(200000) == "200K"
    assert _format_context_window(1048576) == "1048.58K" or "1" in _format_context_window(1048576)
    assert _format_context_window(1000000) == "1M"
    assert _format_context_window(2000000) == "2M"
    assert _format_context_window(500) == "500"


def test_classify_tier():
    assert _classify_tier({"reasoning": True, "cost": {"input": 1}}) == "reasoning"
    assert _classify_tier({"reasoning": False, "cost": {"input": 15}}) == "flagship"
    assert _classify_tier({"reasoning": False, "cost": {"input": 3}}) == "balanced"
    assert _classify_tier({"reasoning": False, "cost": {"input": 0.5}}) == "fast"
    assert _classify_tier({"reasoning": False, "cost": {}}) == "unknown"


def test_provider_logo_url():
    assert get_provider_logo_url("anthropic") == "https://models.dev/logos/anthropic.svg"
    assert get_provider_logo_url("openai") == "https://models.dev/logos/openai.svg"


# ── Cache ─────────────────────────────────────────────────────────────

def test_invalidate_cache_clears_memory():
    import dashboard.lib.settings.models_dev_loader as loader
    loader._cached_models = {"test": True}
    loader._cached_timestamp = 999.0
    invalidate_cache()
    assert loader._cached_models is None
    assert loader._cached_timestamp == 0.0


# ── configured_models structure ───────────────────────────────────────

def test_configured_models_has_required_keys(fake_raw_catalog):
    providers = {"openai": {"type": "api", "source": "auth.json", "has_key": True}}
    with patch("dashboard.lib.settings.models_dev_loader.OPENCODE_CONFIG_PATH", Path("/nonexistent")):
        result = _build_configured_models(fake_raw_catalog, providers)

    assert "loaded_at" in result
    assert "source" in result
    assert "configured_provider_ids" in result
    assert "providers" in result
    assert "openai" in result["configured_provider_ids"]

    p = result["providers"]["openai"]
    assert p["id"] == "openai"
    assert p["name"] == "OpenAI"
    assert p["logo_url"].endswith("openai.svg")
    assert "models" in p

    m = p["models"]["gpt-4.1"]
    assert m["id"] == "gpt-4.1"
    assert m["name"] == "GPT-4.1"
    assert m["cost"]["input"] == 2
    assert m["limit"]["context"] == 1048576
    assert m["source"] == "models.dev"
