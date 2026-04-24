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
        assert cfg.provider is None
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


# ── _get_api_key ───────────────────────────────────────────────────────────


class TestGetApiKey:
    def test_returns_google_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        from dashboard.master_agent import _get_api_key

        with patch("dashboard.master_agent._get_api_key") as mock_key:
            # Test env fallback path directly
            pass

        # Test the env path by mocking vault to fail
        with patch("dashboard.master_agent._get_api_key", wraps=_get_api_key) as wrapped:
            # Patch vault to raise so we fall through to env
            with patch("dashboard.lib.settings.vault.get_vault", side_effect=Exception("no vault")):
                result = _get_api_key("google")
                assert result == "gk-test"

    def test_returns_none_for_unknown_provider(self, monkeypatch):
        from dashboard.master_agent import _get_api_key

        with patch("dashboard.lib.settings.vault.get_vault", side_effect=Exception("no vault")):
            result = _get_api_key("nonexistent_provider_xyz")
            assert result is None

    def test_returns_openai_key_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        from dashboard.master_agent import _get_api_key

        with patch("dashboard.lib.settings.vault.get_vault", side_effect=Exception("no vault")):
            result = _get_api_key("openai")
            assert result == "sk-test-123"

    def test_vault_key_takes_precedence_over_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        from dashboard.master_agent import _get_api_key

        mock_vault = MagicMock()
        mock_vault.get.return_value = "vault-key"
        with patch("dashboard.lib.settings.vault.get_vault", return_value=mock_vault):
            result = _get_api_key("openai")
            assert result == "vault-key"


# ── create_master_client ───────────────────────────────────────────────────


class TestCreateMasterClient:
    def test_creates_openai_client(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from dashboard.master_agent import set_master_model, create_master_client
        from dashboard.llm_client import OpenAIClient

        set_master_model("gpt-4o", provider="openai")
        with patch("openai.AsyncOpenAI") as MockOAI:
            MockOAI.return_value = MagicMock()
            with patch("dashboard.lib.settings.vault.get_vault", side_effect=Exception("no vault")):
                client = create_master_client()
                assert isinstance(client, OpenAIClient)

    def test_creates_google_client(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        from dashboard.master_agent import set_master_model, create_master_client
        from dashboard.llm_client import GoogleClient

        mock_google_genai = MagicMock()
        import sys
        sys.modules.setdefault("google.genai", mock_google_genai)
        sys.modules.setdefault("google.genai.types", MagicMock())

        set_master_model("gemini-pro", provider="google")
        with patch.object(mock_google_genai, "Client", return_value=MagicMock()):
            with patch("dashboard.lib.settings.vault.get_vault", side_effect=Exception("no vault")):
                client = create_master_client()
                assert isinstance(client, GoogleClient)

    def test_creates_client_with_model_prefix(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from dashboard.master_agent import set_master_model, create_master_client
        from dashboard.llm_client import OpenAIClient

        set_master_model("anthropic/claude-3-opus")
        with patch("openai.AsyncOpenAI") as MockOAI:
            MockOAI.return_value = MagicMock()
            with patch("dashboard.lib.settings.vault.get_vault", side_effect=Exception("no vault")):
                client = create_master_client()
                # anthropic provider uses OpenAI-compat client
                assert isinstance(client, OpenAIClient)


# ── master_complete (async) ────────────────────────────────────────────────


class TestMasterComplete:
    @pytest.mark.asyncio
    async def test_master_complete_returns_content(self, monkeypatch):
        from dashboard.master_agent import master_complete

        mock_response = MagicMock()
        mock_response.content = "Summary here"

        with patch("dashboard.master_agent.create_master_client") as mock_factory:
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

        with patch("dashboard.master_agent.create_master_client") as mock_factory:
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

        with patch("dashboard.master_agent.create_master_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.chat = AsyncMock(return_value=mock_response)
            mock_factory.return_value = mock_client

            result = await master_complete("Empty response test")
            assert result == ""
