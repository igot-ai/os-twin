"""
Tests for dashboard.lib.settings.models_registry.

Covers:
- Full catalog structure
- Filtering by provider enabled/disabled
- Google mode filtering (gemini vs vertex)
- OpenCode model building
"""

import pytest

from dashboard.lib.settings.models_registry import (
    ModelEntry,
    ProviderAuthType,
    get_full_catalog,
    get_model_registry,
    build_opencode_models,
    OPENCODE_PROVIDERS,
    AUTH_JSON_PROVIDERS,
)


# ── Full catalog ──────────────────────────────────────────────────────

def test_full_catalog_has_all_providers():
    catalog = get_full_catalog()
    assert set(catalog.keys()) == {"Claude", "GPT", "Gemini", "BytePlus"}


def test_full_catalog_entries_are_model_entries():
    catalog = get_full_catalog()
    for provider, entries in catalog.items():
        for entry in entries:
            assert isinstance(entry, ModelEntry)
            assert entry.id
            assert entry.label
            assert entry.tier


# ── Filtered registry ─────────────────────────────────────────────────

def test_registry_all_enabled():
    reg = get_model_registry(
        google_enabled=True, google_mode="vertex",
        byteplus_enabled=True, anthropic_enabled=True, openai_enabled=True,
    )
    assert "Claude" in reg
    assert "GPT" in reg
    assert "Gemini" in reg
    assert "BytePlus" in reg


def test_registry_google_disabled():
    reg = get_model_registry(google_enabled=False)
    assert "Gemini" not in reg


def test_registry_byteplus_disabled():
    reg = get_model_registry(byteplus_enabled=False)
    assert "BytePlus" not in reg


def test_registry_anthropic_disabled():
    reg = get_model_registry(anthropic_enabled=False)
    assert "Claude" not in reg


def test_registry_openai_disabled():
    reg = get_model_registry(openai_enabled=False)
    assert "GPT" not in reg


def test_registry_google_gemini_mode_only():
    """When google_mode='gemini', only gemini-mode models are returned."""
    reg = get_model_registry(google_enabled=True, google_mode="gemini")
    gemini_models = reg["Gemini"]
    for m in gemini_models:
        assert m.get("mode") == "gemini", f"Expected gemini mode, got {m}"
    # Should NOT include vertex models
    ids = {m["id"] for m in gemini_models}
    assert not any(mid.startswith("google-vertex") for mid in ids)


def test_registry_google_vertex_mode_only():
    """When google_mode='vertex', only vertex-mode models are returned."""
    reg = get_model_registry(google_enabled=True, google_mode="vertex")
    gemini_models = reg["Gemini"]
    for m in gemini_models:
        assert m.get("mode") == "vertex", f"Expected vertex mode, got {m}"
    # Should NOT include gemini-api models
    ids = {m["id"] for m in gemini_models}
    assert not any(mid.startswith("gemini/") for mid in ids)


def test_registry_dict_format():
    """Entries should be plain dicts with the expected keys."""
    reg = get_model_registry()
    for provider, models in reg.items():
        for m in models:
            assert isinstance(m, dict)
            assert "id" in m
            assert "label" in m
            assert "context_window" in m
            assert "tier" in m


# ── OpenCode model building ──────────────────────────────────────────

def test_build_opencode_models_gemini():
    pdef = OPENCODE_PROVIDERS["gemini"]
    models = build_opencode_models(pdef)

    # Should only contain gemini-mode models (not vertex)
    assert len(models) > 0
    for key, val in models.items():
        assert val["npm"] == "@ai-sdk/openai-compatible"
        assert val["name"].startswith("gemini:")
        # Key should be the short id (no prefix)
        assert "/" not in key


def test_build_opencode_models_byteplus():
    pdef = OPENCODE_PROVIDERS["byteplus"]
    models = build_opencode_models(pdef)

    assert len(models) > 0
    for key, val in models.items():
        assert val["npm"] == "@ai-sdk/openai-compatible"
        assert val["name"].startswith("byteplus:")


# ── enabled_models allowlist ──────────────────────────────────────────

def test_registry_enabled_models_filters_claude():
    """Only listed model IDs should appear when enabled_models is set."""
    reg = get_model_registry(
        anthropic_models=["claude-sonnet-4-6"],
    )
    assert len(reg["Claude"]) == 1
    assert reg["Claude"][0]["id"] == "claude-sonnet-4-6"


def test_registry_enabled_models_filters_gpt():
    reg = get_model_registry(
        openai_models=["gpt-4.1", "o3"],
    )
    assert len(reg["GPT"]) == 2
    ids = {m["id"] for m in reg["GPT"]}
    assert ids == {"gpt-4.1", "o3"}


def test_registry_enabled_models_filters_gemini():
    """enabled_models should apply on top of mode filtering."""
    reg = get_model_registry(
        google_enabled=True,
        google_mode="gemini",
        google_models=["gemini/gemini-3-flash-preview"],
    )
    assert len(reg["Gemini"]) == 1
    assert reg["Gemini"][0]["id"] == "gemini/gemini-3-flash-preview"


def test_registry_enabled_models_filters_byteplus():
    reg = get_model_registry(
        byteplus_models=["byteplus/seed-2-0-pro-260328"],
    )
    assert len(reg["BytePlus"]) == 1


def test_registry_empty_enabled_models_means_all():
    """Empty list should be treated as 'all models'."""
    reg_all = get_model_registry(anthropic_models=None)
    reg_empty = get_model_registry(anthropic_models=[])
    assert len(reg_all["Claude"]) == len(reg_empty["Claude"])


def test_registry_nonexistent_model_id_filtered_out():
    """Model IDs not in the catalog should result in empty provider."""
    reg = get_model_registry(
        anthropic_models=["nonexistent-model"],
    )
    assert "Claude" not in reg


def test_build_opencode_models_with_allowlist():
    pdef = OPENCODE_PROVIDERS["gemini"]
    models = build_opencode_models(pdef, enabled_models=["gemini/gemini-3-flash-preview"])
    assert len(models) == 1
    assert "gemini-3-flash-preview" in models


def test_build_opencode_models_empty_allowlist_means_all():
    pdef = OPENCODE_PROVIDERS["gemini"]
    all_models = build_opencode_models(pdef)
    empty_list = build_opencode_models(pdef, enabled_models=[])
    assert len(all_models) == len(empty_list)


def test_opencode_providers_have_required_fields():
    for name, pdef in OPENCODE_PROVIDERS.items():
        assert pdef.opencode_key == name
        assert pdef.vault_scope
        assert pdef.vault_key
        assert pdef.base_url.startswith("https://")
        assert pdef.registry_filter_provider in get_full_catalog()


# ── AUTH_JSON_PROVIDERS ──────────────────────────────────────────────

def test_auth_json_providers_have_required_fields():
    for name, adef in AUTH_JSON_PROVIDERS.items():
        assert adef.auth_json_key == name
        assert adef.vault_scope == "providers"
        assert adef.vault_key
        assert ProviderAuthType.AUTH_JSON in adef.auth_types


def test_auth_json_providers_cover_known_set():
    expected = {"anthropic", "openai", "azure", "xai", "deepseek", "openrouter", "moonshotai", "lmstudio", "zai"}
    assert set(AUTH_JSON_PROVIDERS.keys()) == expected


def test_azure_has_dual_auth():
    azure = AUTH_JSON_PROVIDERS["azure"]
    assert ProviderAuthType.AUTH_JSON in azure.auth_types
    assert ProviderAuthType.ENV in azure.auth_types


def test_no_overlap_between_openai_compatible_and_auth_json():
    """A provider should not appear in both registries."""
    oc_keys = set(OPENCODE_PROVIDERS.keys())
    aj_keys = set(AUTH_JSON_PROVIDERS.keys())
    assert oc_keys.isdisjoint(aj_keys), f"Overlap: {oc_keys & aj_keys}"
