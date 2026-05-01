"""Unit tests for dashboard/ai/config.py.

Covers:
  - AIConfig.full_model() — purpose routing, already-qualified models
  - AIConfig.full_cloud_embedding_model()
  - get_config() — singleton caching and settings-fallback-to-env
  - reset_config() — cache invalidation
  - _load_from_env() — env var mapping and defaults
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from dashboard.ai.config import AIConfig


# ---------------------------------------------------------------------------
# TestAIConfig — pure dataclass / method logic
# ---------------------------------------------------------------------------


class TestAIConfig:
    def test_full_model_default_purpose(self):
        """No purpose → completion_model prefixed with provider."""
        cfg = AIConfig(provider="vertex_ai", completion_model="gemini-3-flash-preview")
        assert cfg.full_model() == "vertex_ai/gemini-3-flash-preview"

    def test_full_model_knowledge_purpose_uses_override(self):
        cfg = AIConfig(
            provider="gemini",
            completion_model="flash",
            knowledge_model="claude-3-5-sonnet",
        )
        assert cfg.full_model("knowledge") == "gemini/claude-3-5-sonnet"

    def test_full_model_memory_purpose_uses_override(self):
        cfg = AIConfig(
            provider="vertex_ai",
            completion_model="flash",
            memory_model="gemini-3-flash-lite",
        )
        assert cfg.full_model("memory") == "vertex_ai/gemini-3-flash-lite"

    def test_full_model_falls_back_to_completion_when_no_override(self):
        """Unknown purpose (or None override) falls back to completion_model."""
        cfg = AIConfig(
            provider="gemini",
            completion_model="flash",
            knowledge_model=None,
        )
        assert cfg.full_model("knowledge") == "gemini/flash"

    def test_full_model_already_qualified_not_double_prefixed(self):
        """If model already contains '/', don't add provider prefix."""
        cfg = AIConfig(provider="vertex_ai", completion_model="vertex_ai/already-qualified")
        assert cfg.full_model() == "vertex_ai/already-qualified"

    def test_full_cloud_embedding_model_prefixes_provider(self):
        cfg = AIConfig(provider="vertex_ai", cloud_embedding_model="text-embedding-005")
        assert cfg.full_cloud_embedding_model() == "vertex_ai/text-embedding-005"

    def test_full_cloud_embedding_model_already_qualified(self):
        cfg = AIConfig(
            provider="vertex_ai",
            cloud_embedding_model="vertex_ai/text-embedding-005",
        )
        assert cfg.full_cloud_embedding_model() == "vertex_ai/text-embedding-005"


# ---------------------------------------------------------------------------
# TestGetConfig — singleton caching
# ---------------------------------------------------------------------------


class TestGetConfig:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        from dashboard.ai import config as cfg_mod
        cfg_mod._config = None
        yield
        cfg_mod._config = None

    def test_returns_same_instance_on_repeated_calls(self):
        from dashboard.ai.config import get_config, reset_config

        reset_config()
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_reset_config_forces_reload(self):
        from dashboard.ai.config import get_config, reset_config

        reset_config()
        c1 = get_config()
        reset_config()
        c2 = get_config()
        # After reset, a new object is created
        assert c1 is not c2

    def test_falls_back_to_env_when_settings_unavailable(self, monkeypatch):
        """When settings raise, env-based config is returned without crashing."""
        monkeypatch.setenv("LLM_MODEL", "gemini-test-model")
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        from dashboard.ai import config as cfg_mod
        cfg_mod._config = None

        with patch(
            "dashboard.ai.config._load_from_settings",
            side_effect=RuntimeError("settings DB unavailable"),
        ):
            cfg = cfg_mod.get_config()

        assert cfg.completion_model == "gemini-test-model"
        assert cfg.provider == "gemini"


# ---------------------------------------------------------------------------
# TestLoadFromEnv — env var mapping
# ---------------------------------------------------------------------------


class TestLoadFromEnv:
    def test_defaults_when_no_env_vars(self, monkeypatch):
        for key in (
            "GOOGLE_CLOUD_PROJECT",
            "LLM_MODEL",
            "LLM_CLOUD_EMBEDDING_MODEL",
            "LLM_LOCAL_EMBEDDING_MODEL",
            "VERTEX_LOCATION",
            "LLM_TIMEOUT",
            "LLM_MAX_RETRIES",
        ):
            monkeypatch.delenv(key, raising=False)

        from dashboard.ai.config import _load_from_env

        cfg = _load_from_env()
        assert cfg.provider == "gemini"
        assert cfg.completion_model == "gemini-3-flash-preview"
        assert cfg.cloud_embedding_model == "text-embedding-005"
        assert cfg.local_embedding_model == "all-MiniLM-L6-v2"
        assert cfg.timeout == 60
        assert cfg.max_retries == 2

    def test_vertex_detected_from_project_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-gcp-project")

        from dashboard.ai.config import _load_from_env

        cfg = _load_from_env()
        assert cfg.provider == "vertex_ai"
        assert cfg.vertex_project == "my-gcp-project"

    def test_custom_model_from_env(self, monkeypatch):
        monkeypatch.setenv("LLM_MODEL", "gemini-3-pro")
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        from dashboard.ai.config import _load_from_env

        cfg = _load_from_env()
        assert cfg.completion_model == "gemini-3-pro"

    def test_custom_timeout_and_retries_from_env(self, monkeypatch):
        monkeypatch.setenv("LLM_TIMEOUT", "120")
        monkeypatch.setenv("LLM_MAX_RETRIES", "5")

        from dashboard.ai.config import _load_from_env

        cfg = _load_from_env()
        assert cfg.timeout == 120
        assert cfg.max_retries == 5
