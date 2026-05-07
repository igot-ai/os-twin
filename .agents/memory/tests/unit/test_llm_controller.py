import json
import unittest
from unittest.mock import Mock, patch

from agentic_memory.llm_controller import (
    BaseLLMController,
    LLMController,
    OllamaController,
    OpenAICompatibleController,
)


class DummyLLMController(BaseLLMController):
    def get_completion(
        self, prompt: str, response_format: dict = None, temperature: float = 1.0
    ) -> str:
        del prompt, response_format, temperature
        return "{}"


class TestBaseLLMController(unittest.TestCase):
    def setUp(self):
        self.controller = DummyLLMController()

    def test_generate_empty_response_matches_schema(self):
        response_format = {
            "json_schema": {
                "schema": {
                    "properties": {
                        "keywords": {"type": "array"},
                        "context": {"type": "string"},
                        "score": {"type": "number"},
                        "enabled": {"type": "boolean"},
                    }
                }
            }
        }

        self.assertEqual(
            self.controller._generate_empty_response(response_format),
            {
                "keywords": [],
                "context": "",
                "score": 0,
                "enabled": False,
            },
        )


class TestLLMControllerDispatch(unittest.TestCase):
    def test_ollama_backend_selection_is_patchable(self):
        with patch.object(OllamaController, "__init__", return_value=None):
            controller = LLMController(backend="ollama", model="llama3.2")

        self.assertIsInstance(controller.llm, OllamaController)

    def test_openai_compatible_backend_selection_is_patchable(self):
        with patch.object(OpenAICompatibleController, "__init__", return_value=None):
            controller = LLMController(
                backend="openai-compatible",
                model="qwen/qwen3-7b",
                compatible_url="https://api.example.com/v1",
                compatible_key="test-key",
            )

        self.assertIsInstance(controller.llm, OpenAICompatibleController)

    def test_invalid_backend_raises(self):
        with self.assertRaises(ValueError):
            LLMController(backend="invalid")
