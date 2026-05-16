"""Tests for Ollama error handling through the new MemoryLLM stack.

The old OllamaController and its litellm dependency are gone. Ollama errors
are now handled by dashboard.llm_client.OllamaClient with retry/timeout via
BaseLLMWrapper._complete(). This file verifies the new error paths.
"""

from unittest.mock import patch

from dashboard.agentic_memory.memory_llm import MemoryLLM


class TestOllamaConnectionErrorThroughMemoryLLM:
    @patch("dashboard.llm_wrapper.run_sync")
    def test_connection_error_returns_empty_string(self, mock_run_sync):
        def raise_connection_error(coro):
            coro.close()
            raise ConnectionError("Connection refused")

        mock_run_sync.side_effect = raise_connection_error

        llm = MemoryLLM(model="llama3.2", provider="ollama", api_key="unused")
        with patch.object(llm, "is_available", return_value=True):
            result = llm.get_completion("Hello")
        assert result == ""


class TestOllamaEmbeddingConnectionError:
    def test_ollama_embedding_connection_error(self):
        from dashboard.llm_client import OllamaEmbeddingClient

        embedder = OllamaEmbeddingClient(model="harrier")

        with patch("ollama.embed") as mock_embed:
            import httpx
            mock_embed.side_effect = httpx.ConnectError("Connection refused")

            assert embedder.embed(["test document"]) == [[]]

    def test_ollama_embedding_model_not_found(self):
        from dashboard.llm_client import OllamaEmbeddingClient

        class MockResponseError(Exception):
            def __init__(self, message, status_code):
                self.status_code = status_code
                super().__init__(message)

        embedder = OllamaEmbeddingClient(model="harrier")

        with patch("ollama.embed") as mock_embed:
            mock_embed.side_effect = MockResponseError("model 'harrier' not found", status_code=404)

            assert embedder.embed(["test document"]) == [[]]
