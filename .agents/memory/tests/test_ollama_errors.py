"""Tests for Ollama error handling through the new MemoryLLM stack.

The old OllamaController and its litellm dependency are gone. Ollama errors
are now handled by dashboard.llm_client.OllamaClient with retry/timeout via
BaseLLMWrapper._complete(). This file verifies the new error paths.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agentic_memory.memory_llm import MemoryLLM
from dashboard.llm_wrapper import BaseLLMWrapper


class TestOllamaConnectionErrorThroughMemoryLLM:
    @patch("dashboard.llm_wrapper.run_sync")
    def test_connection_error_returns_empty_string(self, mock_run_sync):
        mock_run_sync.side_effect = ConnectionError("Connection refused")

        llm = MemoryLLM(model="llama3.2", provider="ollama", api_key="unused")
        with patch.object(llm, "is_available", return_value=True):
            result = llm.get_completion("Hello")
        assert result == ""


class TestOllamaEmbeddingConnectionError:
    def test_ollama_embedding_connection_error(self):
        from agentic_memory.retrievers import OllamaEmbeddingFunction

        embedder = OllamaEmbeddingFunction(model_name="harrier")

        with patch("ollama.embed") as mock_embed:
            import httpx
            mock_embed.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(RuntimeError, match="Ollama server is unreachable"):
                embedder(["test document"])

    def test_ollama_embedding_model_not_found(self):
        from agentic_memory.retrievers import OllamaEmbeddingFunction

        class MockResponseError(Exception):
            def __init__(self, message, status_code):
                self.status_code = status_code
                super().__init__(message)

        embedder = OllamaEmbeddingFunction(model_name="harrier")

        with patch("ollama.embed") as mock_embed:
            mock_embed.side_effect = MockResponseError("model 'harrier' not found", status_code=404)

            with pytest.raises(RuntimeError, match="Model 'harrier' not found"):
                embedder(["test document"])
