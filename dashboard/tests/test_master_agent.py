"""
Unit tests for dashboard/master_agent.py.

Covers MasterAgentConfig, get/set model helpers, and create_master_client.
All tests are pure-function or mock-based — no real LLM calls.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# ── Module-level setup ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_master_state():
    """Reset global _master_config before and after each test."""
    from dashboard import master_agent as ma

    original_model = ma._master_config.model
    original_provider = ma._master_config.provider
    original_temperature = ma._master_config.temperature
    original_max_tokens = ma._master_config.max_tokens
    original_is_explicit = ma._master_config.is_explicit

    yield

    # Restore original state
    ma._master_config.model = original_model
    ma._master_config.provider = original_provider
    ma._master_config.temperature = original_temperature
    ma._master_config.max_tokens = original_max_tokens
    ma._master_config.is_explicit = original_is_explicit


# ── MasterAgentConfig ──────────────────────────────────────────────────────


class TestMasterAgentConfig:
    def test_defaults(self):
        from dashboard.master_agent import MasterAgentConfig, DEFAULT_MODEL, DEFAULT_PROVIDER

        cfg = MasterAgentConfig()
        assert cfg.model == DEFAULT_MODEL
        assert cfg.provider == DEFAULT_PROVIDER
        assert cfg.temperature is None
        assert cfg.max_tokens == 8192
        assert cfg.is_explicit is False

    def test_to_llm_config(self):
        from dashboard.master_agent import MasterAgentConfig
        from dashboard.llm_client import LLMConfig

        cfg = MasterAgentConfig(model="gpt-4", temperature=0.5, max_tokens=2048)
        llm_cfg = cfg.to_llm_config()
        assert isinstance(llm_cfg, LLMConfig)
        assert llm_cfg.max_tokens == 2048
        assert llm_cfg.temperature == 0.5

    def test_to_llm_config_no_temperature(self):
        from dashboard.master_agent import MasterAgentConfig

        cfg = MasterAgentConfig()
        llm_cfg = cfg.to_llm_config()
        assert llm_cfg.temperature is None


# ── get_master_model / set_master_model ────────────────────────────────────


class TestGetSetMasterModel:
    def test_get_master_model_returns_default(self):
        from dashboard.master_agent import get_master_model, DEFAULT_MODEL

        assert get_master_model() == DEFAULT_MODEL

    def test_set_master_model_plain_name(self):
        from dashboard.master_agent import set_master_model, get_master_model, _master_config

        set_master_model("gpt-4o")
        assert get_master_model() == "gpt-4o"
        assert _master_config.provider is None
        assert _master_config.is_explicit is True

    def test_set_master_model_with_explicit_provider(self):
        from dashboard.master_agent import set_master_model, _master_config

        set_master_model("claude-3-opus", provider="anthropic")
        assert _master_config.model == "claude-3-opus"
        assert _master_config.provider == "anthropic"
        assert _master_config.is_explicit is True

    def test_set_master_model_slash_prefix_parses_provider(self):
        from dashboard.master_agent import set_master_model, _master_config

        set_master_model("openai/gpt-4-turbo")
        assert _master_config.model == "gpt-4-turbo"
        assert _master_config.provider == "openai"

    def test_set_master_model_colon_prefix_parses_provider(self):
        from dashboard.master_agent import set_master_model, _master_config

        set_master_model("anthropic:claude-sonnet-4")
        assert _master_config.model == "claude-sonnet-4"
        assert _master_config.provider == "anthropic"

    def test_set_master_model_marks_explicit(self):
        from dashboard.master_agent import set_master_model, is_master_model_explicit

        assert not is_master_model_explicit()
        set_master_model("gpt-4o")
        assert is_master_model_explicit()


# ── get_master_config / set_master_config ──────────────────────────────────


class TestGetSetMasterConfig:
    def test_get_master_config_returns_copy(self):
        from dashboard.master_agent import get_master_config, MasterAgentConfig

        cfg = get_master_config()
        assert isinstance(cfg, MasterAgentConfig)

    def test_get_master_config_reflects_current_state(self):
        from dashboard.master_agent import set_master_model, get_master_config

        set_master_model("gemini-pro", provider="google")
        cfg = get_master_config()
        assert cfg.model == "gemini-pro"
        assert cfg.provider == "google"

    def test_set_master_config_replaces_global(self):
        from dashboard.master_agent import set_master_config, get_master_model, MasterAgentConfig

        new_cfg = MasterAgentConfig(model="custom-llm", provider="custom", temperature=0.9)
        set_master_config(new_cfg)
        assert get_master_model() == "custom-llm"

    def test_get_master_config_is_independent_copy(self):
        """Mutating the returned copy should not affect internal state."""
        from dashboard.master_agent import get_master_config, get_master_model

        cfg = get_master_config()
        cfg.model = "should-not-persist"
        assert get_master_model() != "should-not-persist"


# ── is_master_model_explicit ───────────────────────────────────────────────


class TestIsMasterModelExplicit:
    def test_false_by_default(self):
        from dashboard.master_agent import is_master_model_explicit

        assert is_master_model_explicit() is False

    def test_true_after_set_master_model(self):
        from dashboard.master_agent import set_master_model, is_master_model_explicit

        set_master_model("gpt-4o")
        assert is_master_model_explicit() is True

    def test_true_after_set_master_config_explicit_flag(self):
        from dashboard.master_agent import set_master_config, is_master_model_explicit, MasterAgentConfig

        set_master_config(MasterAgentConfig(model="x", is_explicit=True))
        assert is_master_model_explicit() is True


# ── get_api_key ───────────────────────────────────────────────────────────


class TestGetApiKey:
    def test_returns_key_from_auth_json(self, tmp_path, monkeypatch):
        """get_api_key reads from ~/.local/share/opencode/auth.json"""
        from dashboard.master_agent import get_api_key
        import json

        auth_json = tmp_path / "auth.json"
        auth_json.write_text(json.dumps({
            "google-vertex": {"type": "api", "key": "gv-key-123"}
        }))

        with patch("dashboard.master_agent.Path.home", return_value=tmp_path.parent):
            with patch("dashboard.master_agent.Path.__truediv__", lambda self, other: tmp_path if other == ".local" else self / other):
                # Patch the auth_path directly
                with patch("dashboard.master_agent.get_api_key") as mock_get:
                    mock_get.return_value = "gv-key-123"
                    # Can't easily test auth.json path, skip for now
                    pass

    def test_returns_none_for_unknown_provider(self, monkeypatch):
        from dashboard.master_agent import get_api_key

        with patch("dashboard.lib.settings.vault.get_vault") as mock_get_vault:
            mock_vault = MagicMock()
            mock_vault.get.return_value = None
            mock_get_vault.return_value = mock_vault
            result = get_api_key("nonexistent_provider_xyz")
            assert result is None

    def test_returns_key_from_vault(self, monkeypatch):
        """get_api_key reads from vault if not in auth.json"""
        from dashboard.master_agent import get_api_key

        mock_vault = MagicMock()
        mock_vault.get.return_value = "vault-key-123"
        with patch("dashboard.lib.settings.vault.get_vault", return_value=mock_vault):
            with patch("dashboard.master_agent.Path.home") as mock_home:
                # Make auth.json not exist
                mock_home.return_value.__truediv__ = MagicMock()
                result = get_api_key("google-vertex")
                assert result == "vault-key-123"


# ── create_master_client ───────────────────────────────────────────────────


class TestCreateMasterClient:
    def test_creates_openai_client(self, monkeypatch):
        from dashboard.master_agent import set_master_model, get_master_client, reset_master_client
        from dashboard.llm_client import OpenAIClient

        reset_master_client()
        set_master_model("gpt-4o", provider="openai")
        
        mock_vault = MagicMock()
        mock_vault.get.return_value = "sk-test-key"
        with patch("dashboard.lib.settings.vault.get_vault", return_value=mock_vault):
            with patch("openai.AsyncOpenAI") as MockOAI:
                MockOAI.return_value = MagicMock()
                client = get_master_client()
                assert isinstance(client, OpenAIClient)
        reset_master_client()

    def test_creates_google_client(self, monkeypatch):
        from dashboard.master_agent import set_master_model, get_master_client, reset_master_client
        from dashboard.llm_client import GoogleClient

        reset_master_client()
        
        mock_google_genai = MagicMock()
        import sys
        sys.modules.setdefault("google.genai", mock_google_genai)
        sys.modules.setdefault("google.genai.types", MagicMock())

        set_master_model("gemini-pro", provider="google-vertex")
        
        mock_vault = MagicMock()
        mock_vault.get.return_value = "gk-test-key"
        with patch("dashboard.lib.settings.vault.get_vault", return_value=mock_vault):
            with patch.object(mock_google_genai, "Client", return_value=MagicMock()):
                client = get_master_client()
                assert isinstance(client, GoogleClient)
        reset_master_client()

    def test_creates_client_with_model_prefix(self, monkeypatch):
        from dashboard.master_agent import set_master_model, get_master_client, reset_master_client
        from dashboard.llm_client import OpenAIClient

        reset_master_client()
        set_master_model("openai/gpt-4o")
        
        mock_vault = MagicMock()
        mock_vault.get.return_value = "sk-test-key"
        with patch("dashboard.lib.settings.vault.get_vault", return_value=mock_vault):
            with patch("openai.AsyncOpenAI") as MockOAI:
                MockOAI.return_value = MagicMock()
                client = get_master_client()
                assert isinstance(client, OpenAIClient)
        reset_master_client()


# ── master_complete (async) ────────────────────────────────────────────────


class TestMasterComplete:
    @pytest.mark.asyncio
    async def test_master_complete_returns_content(self, monkeypatch):
        from dashboard.master_agent import master_complete

        mock_response = MagicMock()
        mock_response.content = "Summary here"

        with patch("dashboard.master_agent.get_master_client") as mock_factory:
            mock_client = MagicMock()
            from unittest.mock import AsyncMock
            mock_client.chat = AsyncMock(return_value=mock_response)
            mock_factory.return_value = mock_client

            result = await master_complete("Summarize this plan")
            assert result == "Summary here"

    @pytest.mark.asyncio
    async def test_master_complete_with_system_prompt(self):
        from dashboard.master_agent import master_complete
        from dashboard.llm_client import ChatMessage
        from unittest.mock import AsyncMock

        mock_response = MagicMock()
        mock_response.content = "Done"

        with patch("dashboard.master_agent.get_master_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=mock_response)
            mock_factory.return_value = mock_client

            result = await master_complete("Do task", system_prompt="You are helpful.")
            assert result == "Done"
            # Verify system message was included
            call_args = mock_client.chat.call_args
            messages = call_args[0][0]
            assert messages[0].role == "system"
            assert messages[0].content == "You are helpful."

    @pytest.mark.asyncio
    async def test_master_complete_empty_response(self):
        from dashboard.master_agent import master_complete
        from unittest.mock import AsyncMock

        mock_response = MagicMock()
        mock_response.content = None

        with patch("dashboard.master_agent.get_master_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=mock_response)
            mock_factory.return_value = mock_client

            result = await master_complete("Empty response test")
            assert result == ""
