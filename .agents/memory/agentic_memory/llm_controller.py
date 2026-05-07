from typing import Dict, Optional, Literal, Any
import os
import json
from abc import ABC, abstractmethod
import requests

# Lazy import: litellm pulls in heavy ML deps at import time (~3s)
completion = None

_SYSTEM_JSON_PROMPT = "You must respond with a JSON object."


def _ensure_litellm():
    global completion
    if completion is None:
        from litellm import completion as _c

        completion = _c


class BaseLLMController(ABC):
    @abstractmethod
    def get_completion(
        self, prompt: str, response_format: dict = None, temperature: float = 1.0
    ) -> str:
        """Get completion from LLM"""

    def _generate_empty_value(self, schema_type: str, schema_items: dict = None) -> Any:
        """Generate empty value based on JSON schema type."""
        if schema_type == "array":
            return []
        elif schema_type == "string":
            return ""
        elif schema_type == "object":
            return {}
        elif schema_type == "number" or schema_type == "integer":
            return 0
        elif schema_type == "boolean":
            return False
        return None

    def _generate_empty_response(self, response_format: dict) -> dict:
        """Generate empty response matching the expected schema."""
        if "json_schema" not in response_format:
            return {}

        schema = response_format["json_schema"]["schema"]
        result = {}

        if "properties" in schema:
            for prop_name, prop_schema in schema["properties"].items():
                result[prop_name] = self._generate_empty_value(
                    prop_schema["type"], prop_schema.get("items")
                )

        return result


class OllamaController(BaseLLMController):
    def __init__(self, model: str = "llama2"):
        from ollama import chat

        if "/" in model and not model.startswith("hf.co/"):
            model = f"hf.co/{model}"
            
        self.model = model

    def get_completion(
        self, prompt: str, response_format: dict = None, temperature: float = 1.0
    ) -> str:
        try:
            _ensure_litellm()
            kwargs = {
                "model": "ollama_chat/{}".format(self.model),
                "messages": [
                    {
                        "role": "system",
                        "content": _SYSTEM_JSON_PROMPT,
                    },
                    {"role": "user", "content": prompt},
                ],
            }
            if response_format is not None:
                kwargs["response_format"] = response_format
            response = completion(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            # Bubbling up specific errors instead of silent failure
            error_str = str(e).lower()
            if "connection" in error_str or "refused" in error_str:
                raise RuntimeError("Ollama server is unreachable. Please ensure 'ollama serve' is running.") from e
            elif "not found" in error_str:
                raise RuntimeError(f"Model 'ollama_chat/{self.model}' not found. Please pull it using 'ollama pull hf.co/{self.model}'.") from e
            
            # If it's another kind of error, re-raise it
            raise RuntimeError(f"OllamaController completion error: {str(e)}") from e


class OpenAICompatibleController(BaseLLMController):
    """LLM controller for any OpenAI-compatible API server.

    Uses OPENAI_COMPATIBLE_BASE_URL and OPENAI_COMPATIBLE_API_KEY env vars.
    Falls back to http://localhost:8000 if not set.
    """

    def __init__(self, model: str = "default", api_key: Optional[str] = None, base_url: Optional[str] = None):
        try:
            from openai import OpenAI

            self.model = model
            self.base_url = base_url or os.getenv("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:8000")
            if api_key is None:
                api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY", "")
            self.client = OpenAI(api_key=api_key, base_url=self.base_url)
        except ImportError:
            raise ImportError(
                "OpenAI package not found. Install it with: pip install openai"
            )

    def get_completion(
        self,
        prompt: str,
        response_format: dict = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
    ) -> str:
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_JSON_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format

        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        try:
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("LLM returned None content")
            return content
        except Exception as e:
            # Re-raise the exception so it can be handled by the caller, rather than failing silently with an empty string
            raise RuntimeError(f"OpenAICompatibleController completion error: {str(e)}") from e


class LLMController:
    """LLM-based controller for memory metadata generation.

    Supports multiple backends: Ollama and OpenAI-compatible API servers.
    """

    def __init__(
        self,
        backend: Literal[
            "ollama", "openai-compatible"
        ] = "ollama",
        model: str = "llama3.2",
        compatible_url: Optional[str] = None,
        compatible_key: Optional[str] = None,
    ):
        if backend == "ollama":
            self.llm = OllamaController(model)
        elif backend == "openai-compatible":
            self.llm = OpenAICompatibleController(
                model,
                api_key=compatible_key,
                base_url=compatible_url
            )
        else:
            raise ValueError(
                "Unknown backend '" + str(backend) + "'. Backend must be one of: 'ollama', 'openai-compatible'"
            )

    def get_completion(
        self, prompt: str, response_format: dict = None, temperature: float = 1.0
    ) -> str:
        return self.llm.get_completion(prompt, response_format, temperature)
