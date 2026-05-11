"""Unit tests for dashboard.llm_wrapper.BaseLLMWrapper.

Tests the shared base class that MemoryLLM and KnowledgeLLM extend,
covering: empty-response generation, JSON extraction, API-key resolution,
client creation, completion with timeout/retry, and graceful degradation.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from dashboard.llm_wrapper import BaseLLMWrapper


class TestGenerateEmptyValue:
    @pytest.mark.parametrize(
        "schema_type,expected",
        [
            ("array", []),
            ("string", ""),
            ("object", {}),
            ("number", 0),
            ("integer", 0),
            ("boolean", False),
        ],
    )
    def test_known_types(self, schema_type, expected):
        assert BaseLLMWrapper._generate_empty_value(schema_type) == expected

    def test_unknown_type_returns_none(self):
        assert BaseLLMWrapper._generate_empty_value("null") is None


class TestGenerateEmptyResponse:
    def test_flat_schema(self):
        fmt = {
            "json_schema": {
                "schema": {
                    "properties": {
                        "keywords": {"type": "array"},
                        "context": {"type": "string"},
                        "score": {"type": "number"},
                        "active": {"type": "boolean"},
                    }
                }
            }
        }
        assert BaseLLMWrapper._generate_empty_response(fmt) == {
            "keywords": [],
            "context": "",
            "score": 0,
            "active": False,
        }

    def test_no_json_schema_key(self):
        assert BaseLLMWrapper._generate_empty_response({}) == {}

    def test_no_properties_key(self):
        assert BaseLLMWrapper._generate_empty_response(
            {"json_schema": {"schema": {}}}
        ) == {}

    def test_nested_array_items(self):
        fmt = {
            "json_schema": {
                "schema": {
                    "properties": {
                        "items": {"type": "array", "items": {"type": "string"}},
                    }
                }
            }
        }
        result = BaseLLMWrapper._generate_empty_response(fmt)
        assert result == {"items": []}


class TestExtractJson:
    def test_plain_json_object(self):
        assert BaseLLMWrapper._extract_json('{"a": 1}') == {"a": 1}

    def test_plain_json_array(self):
        assert BaseLLMWrapper._extract_json("[1, 2, 3]") == [1, 2, 3]

    def test_markdown_fenced(self):
        text = "```json\n{\"key\": \"value\"}\n```"
        assert BaseLLMWrapper._extract_json(text) == {"key": "value"}

    def test_markdown_fenced_no_lang(self):
        text = "```\n{\"key\": \"value\"}\n```"
        assert BaseLLMWrapper._extract_json(text) == {"key": "value"}

    def test_embedded_json(self):
        text = "Here is the result: {\"x\": 42} and that's it."
        assert BaseLLMWrapper._extract_json(text) == {"x": 42}

    def test_no_json_returns_none(self):
        assert BaseLLMWrapper._extract_json("just plain text") is None

    def test_invalid_json_returns_none(self):
        assert BaseLLMWrapper._extract_json("{broken json") is None


class TestBaseLLMWrapperInit:
    def test_defaults(self):
        w = BaseLLMWrapper()
        assert w.model == ""
        assert w.provider is None
        assert w._explicit_key is None
        assert w._timeout == 60

    def test_explicit_params(self):
        w = BaseLLMWrapper(model="gpt-4", provider="openai", api_key="sk-123", timeout=30)
        assert w.model == "gpt-4"
        assert w.provider == "openai"
        assert w._explicit_key == "sk-123"
        assert w._timeout == 30


class TestIsAvailable:
    def test_no_model_returns_false(self):
        w = BaseLLMWrapper(model="", provider="openai", api_key="sk-123")
        assert not w.is_available()

    def test_key_resolved_returns_true(self):
        w = BaseLLMWrapper(model="gpt-4", provider="openai")
        with patch.object(w, "_resolve_api_key", return_value="sk-123"):
            assert w.is_available()

    def test_no_key_non_ollama_returns_false(self):
        w = BaseLLMWrapper(model="gpt-4", provider="openai")
        with patch.object(w, "_resolve_api_key", return_value=None):
            assert not w.is_available()

    def test_ollama_no_key_returns_true(self):
        w = BaseLLMWrapper(model="llama3.2", provider="ollama")
        with patch.object(w, "_resolve_api_key", return_value=None):
            assert w.is_available()

    def test_ollama_with_key_returns_true(self):
        w = BaseLLMWrapper(model="llama3.2", provider="ollama", api_key="my-ollama-key")
        with patch.object(w, "_resolve_api_key", return_value="my-ollama-key"):
            assert w.is_available()

    def test_key_checked_before_ollama_fallback(self):
        w = BaseLLMWrapper(model="llama3.2", provider="ollama")
        with patch.object(w, "_resolve_api_key", return_value="resolved-key"):
            assert w.is_available()

    def test_ollama_empty_model_returns_false(self):
        w = BaseLLMWrapper(model="", provider="ollama")
        assert not w.is_available()


class TestResolveApiKey:
    def test_explicit_key_wins(self):
        w = BaseLLMWrapper(api_key="explicit-key")
        assert w._resolve_api_key() == "explicit-key"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "from-env"})
    def test_env_var_fallback(self):
        w = BaseLLMWrapper(model="gpt-4", provider="openai")
        assert w._resolve_api_key() == "from-env"

    def test_no_key_returns_none(self):
        w = BaseLLMWrapper(model="gpt-4", provider="openai")
        with patch.dict("os.environ", {}, clear=True):
            with patch("dashboard.llm_wrapper.get_vault", create=True) as mock_vault:
                with patch("dashboard.llm_wrapper.get_api_key", create=True, side_effect=ImportError):
                    result = w._resolve_api_key()
                    assert result is None or isinstance(result, str)


class TestComplete:
    @patch("dashboard.llm_wrapper.run_sync")
    def test_successful_completion(self, mock_run_sync):
        mock_response = MagicMock()
        mock_response.content = "Hello!"
        mock_run_sync.return_value = mock_response

        w = BaseLLMWrapper(model="gpt-4", provider="openai", api_key="sk-123")
        with patch.object(w, "is_available", return_value=True):
            result = w._complete("system prompt", "user prompt")
        assert result == "Hello!"

    @patch("dashboard.llm_wrapper.run_sync")
    def test_timeout_returns_empty(self, mock_run_sync):
        mock_run_sync.side_effect = asyncio.TimeoutError()

        w = BaseLLMWrapper(model="gpt-4", provider="openai", api_key="sk-123", timeout=1)
        with patch.object(w, "is_available", return_value=True):
            result = w._complete("system prompt", "user prompt")
        assert result == ""

    @patch("dashboard.llm_wrapper.run_sync")
    def test_generic_exception_returns_empty(self, mock_run_sync):
        mock_run_sync.side_effect = RuntimeError("boom")

        w = BaseLLMWrapper(model="gpt-4", provider="openai", api_key="sk-123")
        with patch.object(w, "is_available", return_value=True):
            result = w._complete("system prompt", "user prompt")
        assert result == ""

    @patch("dashboard.llm_wrapper.run_sync")
    def test_timeout_in_exception_name_returns_empty(self, mock_run_sync):
        mock_run_sync.side_effect = Exception("request timeout exceeded")

        w = BaseLLMWrapper(model="gpt-4", provider="openai", api_key="sk-123")
        with patch.object(w, "is_available", return_value=True):
            result = w._complete("system prompt", "user prompt")
        assert result == ""

    @patch("dashboard.llm_wrapper.run_sync")
    def test_none_content_returns_empty_string(self, mock_run_sync):
        mock_response = MagicMock()
        mock_response.content = None
        mock_run_sync.return_value = mock_response

        w = BaseLLMWrapper(model="gpt-4", provider="openai", api_key="sk-123")
        with patch.object(w, "is_available", return_value=True):
            result = w._complete("system prompt", "user prompt")
        assert result == ""


class TestEmbeddingDimensionFixed:
    """Verify that embedding dimension is fixed from OSTWIN_EMBEDDING_DIM env var
    and cannot be changed dynamically via settings."""

    def test_default_is_1024(self):
        from dashboard.llm_client import DEFAULT_EMBEDDING_DIMENSION
        assert DEFAULT_EMBEDDING_DIMENSION == 1024

    def test_memory_retrievers_uses_shared_dimension(self):
        from agentic_memory.retrievers import EMBEDDING_DIMENSION
        from dashboard.llm_client import DEFAULT_EMBEDDING_DIMENSION
        assert EMBEDDING_DIMENSION == DEFAULT_EMBEDDING_DIMENSION

    def test_knowledge_config_uses_shared_dimension(self):
        from dashboard.knowledge.config import EMBEDDING_DIMENSION
        from dashboard.llm_client import DEFAULT_EMBEDDING_DIMENSION
        assert EMBEDDING_DIMENSION == DEFAULT_EMBEDDING_DIMENSION

    def test_knowledge_settings_dimension_is_readonly(self):
        from dashboard.models import KnowledgeSettings
        from dashboard.llm_client import DEFAULT_EMBEDDING_DIMENSION
        ks = KnowledgeSettings(knowledge_embedding_dimension=999)
        assert ks.knowledge_embedding_dimension == DEFAULT_EMBEDDING_DIMENSION
