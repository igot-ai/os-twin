import pytest
from unittest.mock import patch, MagicMock
import sys

# Mock ollama module before importing our code
mock_ollama = MagicMock()
sys.modules['ollama'] = mock_ollama

# Adjust imports based on the codebase structure
from agentic_memory.llm_controller import OllamaController
from agentic_memory.retrievers import OllamaEmbeddingFunction

class MockResponseError(Exception):
    def __init__(self, message, status_code):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

# Inject our MockResponseError into the mocked ollama module
mock_ollama.ResponseError = MockResponseError

def test_ollama_controller_connection_error():
    controller = OllamaController(model="llama3.2")
    
    with patch("agentic_memory.llm_controller.completion") as mock_completion:
        # Simulate connection error from litellm/requests
        import requests
        mock_completion.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        with pytest.raises(RuntimeError, match="Ollama server is unreachable"):
            controller.get_completion("Hello")

def test_ollama_controller_model_not_found():
    controller = OllamaController(model="llama3.2")
    
    with patch("agentic_memory.llm_controller.completion") as mock_completion:
        # Simulate LiteLLM passing through Ollama's 404
        # We'll use an exception that matches what LiteLLM throws
        class MockAPIError(Exception):
            pass
            
        mock_completion.side_effect = MockAPIError(
            "litellm.exceptions.APIError: ollama_chat/llama3.2 not found"
        )
        
        with pytest.raises(RuntimeError, match="Model 'ollama_chat/llama3.2' not found. Please pull it"):
            controller.get_completion("Hello")

def test_ollama_embedding_connection_error():
    embedder = OllamaEmbeddingFunction(model_name="harrier")
    
    with patch("ollama.embed") as mock_embed:
        import httpx
        mock_embed.side_effect = httpx.ConnectError("Connection refused")
        
        with pytest.raises(RuntimeError, match="Ollama server is unreachable"):
            embedder(["test document"])

def test_ollama_embedding_model_not_found():
    embedder = OllamaEmbeddingFunction(model_name="harrier")
    
    with patch("ollama.embed") as mock_embed:
        mock_embed.side_effect = MockResponseError("model 'harrier' not found", status_code=404)
        
        with pytest.raises(RuntimeError, match="Model 'harrier' not found. Please pull it"):
            embedder(["test document"])
