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


class OpenAIController(BaseLLMController):
    def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None):
        try:
            from openai import OpenAI

            self.model = model
            if api_key is None:
                api_key = os.getenv("OPENAI_API_KEY")
            if api_key is None:
                raise ValueError(
                    "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
                )
            self.client = OpenAI(api_key=api_key)
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
        # Build kwargs dynamically based on model type
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

        # GPT-5 and newer reasoning models use max_completion_tokens
        if max_tokens is not None:
            if (
                "gpt-5" in self.model.lower()
                or "o1" in self.model.lower()
                or "o3" in self.model.lower()
            ):
                kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["max_tokens"] = max_tokens

        response = self.client.chat.completions.create(**kwargs)
        if not response.choices:
            raise ValueError("LLM returned empty choices array")
        return response.choices[0].message.content or ""


class OllamaController(BaseLLMController):
    def __init__(self, model: str = "llama2"):
        from ollama import chat

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
        except Exception:
            empty_response = self._generate_empty_response(response_format or {})
            return json.dumps(empty_response)


class SGLangController(BaseLLMController):
    """LLM controller for SGLang server using HTTP requests.

    SGLang provides fast local inference with RadixAttention for efficient KV cache reuse.
    This controller communicates with a SGLang server via HTTP.

    Args:
        model: Model identifier (e.g., "meta-llama/Llama-3.1-8B-Instruct")
        sglang_host: SGLang server host URL (default: "http://localhost")
        sglang_port: SGLang server port (default: 30000)
    """

    def __init__(
        self,
        model: str = "llama2",
        sglang_host: str = "http://localhost",
        sglang_port: int = 30000,
    ):
        self.model = model
        self.sglang_host = sglang_host
        self.sglang_port = sglang_port
        self.base_url = f"{sglang_host}:{sglang_port}"

    def get_completion(
        self, prompt: str, response_format: dict = None, temperature: float = 1.0
    ) -> str:
        fmt = response_format or {}
        try:
            json_schema = fmt.get("json_schema", {}).get("schema", {})
            json_schema_str = json.dumps(json_schema)

            payload = {
                "text": prompt,
                "sampling_params": {
                    "temperature": temperature,
                    "max_new_tokens": 1000,
                    "json_schema": json_schema_str,
                },
            }

            response = requests.post(
                f"{self.base_url}/generate",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )

            if response.status_code == 200:
                result = response.json()
                generated_text = result.get("text", "")
                return generated_text

            print(
                f"SGLang server returned status {response.status_code}: {response.text}"
            )
            raise RuntimeError(f"SGLang server error: {response.status_code}")

        except Exception as e:
            print(f"SGLang completion error: {e}")
            empty_response = self._generate_empty_response(fmt)
            return json.dumps(empty_response)


class OpenRouterController(BaseLLMController):
    """LLM controller for OpenRouter API using litellm.

    OpenRouter provides access to multiple LLM providers through a unified API.
    This controller uses litellm to interface with OpenRouter, supporting any model
    available on the OpenRouter platform.

    Args:
        model: Model identifier (e.g., "openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet").
               The "openrouter/" prefix is automatically added if not present.
        api_key: OpenRouter API key. If None, reads from OPENROUTER_API_KEY env variable.

    Raises:
        ValueError: If API key is not provided and not found in environment.

    Examples:
        >>> controller = OpenRouterController("openai/gpt-4o-mini", api_key="your-key")
        >>> controller = OpenRouterController("google/gemini-3.1-flash-lite-preview-001:free")
    """

    def __init__(
        self, model: str = "openai/gpt-4o-mini", api_key: Optional[str] = None
    ):
        # For litellm, prepend "openrouter/" if not already present
        if not model.startswith("openrouter/"):
            self.model = f"openrouter/{model}"
        else:
            self.model = model

        if api_key is None:
            api_key = os.getenv("OPENROUTER_API_KEY")
        if api_key is None:
            raise ValueError(
                "OpenRouter API key not found. Set OPENROUTER_API_KEY environment variable."
            )

        # Set the environment variable for litellm to use
        os.environ["OPENROUTER_API_KEY"] = api_key
        self.api_key = api_key

    def get_completion(
        self, prompt: str, response_format: dict = None, temperature: float = 1.0
    ) -> str:
        """Get completion from OpenRouter API.

        Args:
            prompt: The prompt to send to the LLM.
            response_format: JSON schema specifying the expected response format.
            temperature: Sampling temperature (0.0 to 1.0).

        Returns:
            JSON string containing the LLM response.
        """
        try:
            _ensure_litellm()
            kwargs = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": _SYSTEM_JSON_PROMPT,
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format
            response = completion(**kwargs)
            return response.choices[0].message.content
        except Exception:
            # Silently fall back to empty response on error
            empty_response = self._generate_empty_response(response_format or {})
            return json.dumps(empty_response)


class HuggingFaceController(BaseLLMController):
    """LLM controller for local HuggingFace models via transformers.

    Loads a causal-LM model and tokenizer from the HuggingFace Hub (or a local
    path) and runs inference entirely on the local machine. No API keys or
    network calls are needed after the initial model download.

    The controller applies the tokenizer's chat template when available
    (system + user messages) and extracts JSON from the generated text.

    Args:
        model: HuggingFace model identifier or local path
            (e.g. "LiquidAI/LFM2-1.2B-Extract", "mistralai/Mistral-7B-Instruct-v0.3").
        device: Compute device — "cpu", "cuda", "mps", or None for auto-detect.
        max_new_tokens: Maximum tokens to generate per call (default: 1024).
        torch_dtype: Data type for model weights — "auto", "float32", "float16",
            "bfloat16". Default "auto" uses float16 on GPU/MPS and float32 on CPU.
    """

    def __init__(
        self,
        model: str,
        device: Optional[str] = None,
        max_new_tokens: int = 1024,
        torch_dtype: str = "auto",
    ):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_name = model
        self.max_new_tokens = max_new_tokens

        # Auto-detect device
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device = device

        # Resolve dtype
        if torch_dtype == "auto":
            self._torch_dtype = torch.float32 if device == "cpu" else torch.float16
        else:
            self._torch_dtype = getattr(torch, torch_dtype)

        self.tokenizer = AutoTokenizer.from_pretrained(
            model, trust_remote_code=True
        )
        # transformers >=5.x renamed torch_dtype -> dtype
        dtype_kwarg = {"dtype": self._torch_dtype}
        self.model = AutoModelForCausalLM.from_pretrained(
            model,
            trust_remote_code=True,
            **dtype_kwarg,
        ).to(device)
        self.model.eval()

    def get_completion(
        self, prompt: str, response_format: dict = None, temperature: float = 1.0
    ) -> str:
        """Generate a JSON completion from a local HuggingFace model.

        Applies the chat template, generates tokens, extracts JSON from the
        output. Falls back to a schema-conforming empty response on failure.
        """
        import torch
        import re

        input_text = self._build_input(prompt)
        inputs = self.tokenizer(input_text, return_tensors="pt").to(self.device)

        gen_kwargs = {
            "max_new_tokens": self.max_new_tokens,
            "pad_token_id": self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
        }
        # temperature=0 → greedy; >0 → sampling
        if temperature <= 0.01:
            gen_kwargs["do_sample"] = False
        else:
            gen_kwargs["do_sample"] = True
            gen_kwargs["temperature"] = temperature
            gen_kwargs["top_p"] = 0.9

        with torch.no_grad():
            outputs = self.model.generate(**inputs, **gen_kwargs)

        # Decode only the newly generated tokens
        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        raw_text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)

        # Try to extract valid JSON
        extracted = self._extract_json(raw_text)
        if extracted is not None:
            # Small models often wrap their response in an extra key like
            # {"analysis": {"name": ..., "keywords": ...}}.  Unwrap it so
            # callers (e.g. analyze_content) see the inner dict directly.
            extracted = self._unwrap_single_key(extracted)
            return extracted

        # Fallback: return a schema-conforming empty response
        if response_format:
            return json.dumps(self._generate_empty_response(response_format))
        return "{}"

    def _build_input(self, prompt: str) -> str:
        """Build the full input string using the tokenizer's chat template."""
        messages = [
            {"role": "system", "content": _SYSTEM_JSON_PROMPT},
            {"role": "user", "content": prompt},
        ]
        try:
            return self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            # Fallback for tokenizers without a chat template
            return (
                f"System: {_SYSTEM_JSON_PROMPT}\n\n"
                f"User: {prompt}\n\nAssistant:"
            )

    @staticmethod
    def _unwrap_single_key(text: str) -> str:
        """Unwrap {"wrapper": {actual_payload}} → {actual_payload}.

        Small models frequently nest the real response inside an extra key
        like "analysis", "result", or "response".  If the parsed JSON has
        exactly one key whose value is itself a dict, return the inner dict
        as a JSON string instead.
        """
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and len(obj) == 1:
                inner = next(iter(obj.values()))
                if isinstance(inner, dict):
                    return json.dumps(inner, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            pass
        return text

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """Extract the first valid JSON object from generated text.

        Handles raw JSON, markdown code fences, and nested braces.
        """
        import re

        # Strip markdown code fences if present
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            try:
                json.loads(fenced.group(1))
                return fenced.group(1)
            except (json.JSONDecodeError, ValueError):
                pass

        # Walk through the text looking for balanced braces
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except (json.JSONDecodeError, ValueError):
                        # Reset and keep searching after this failed candidate
                        depth = 0
                        start = text.find("{", i + 1)
                        if start == -1:
                            return None
        return None


class GeminiController(BaseLLMController):
    """LLM controller for Google Gemini API using litellm.

    Args:
        model: Gemini model identifier (e.g., "gemini-3.1-flash-lite-preview", "gemini-1.5-pro").
               The "gemini/" prefix is automatically added if not present.
        api_key: Google API key. If None, reads from GOOGLE_API_KEY env variable.
    """

    def __init__(self, model: str = "gemini-3.1-flash-lite-preview", api_key: Optional[str] = None):
        if not model.startswith("gemini/"):
            self.model = f"gemini/{model}"
        else:
            self.model = model

        if api_key is None:
            api_key = os.getenv("GOOGLE_API_KEY")
        if api_key is None:
            raise ValueError(
                "Google API key not found. Set GOOGLE_API_KEY environment variable."
            )

        os.environ["GEMINI_API_KEY"] = api_key
        self.api_key = api_key

    def get_completion(
        self, prompt: str, response_format: dict = None, temperature: float = 1.0
    ) -> str:
        try:
            _ensure_litellm()
            kwargs = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": _SYSTEM_JSON_PROMPT,
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format
            response = completion(**kwargs)
            return response.choices[0].message.content
        except Exception:
            empty_response = self._generate_empty_response(response_format or {})
            return json.dumps(empty_response)


class LLMController:
    """LLM-based controller for memory metadata generation.

    Supports multiple backends: OpenAI, Ollama, SGLang, OpenRouter, Gemini,
    and HuggingFace (local inference).
    """

    def __init__(
        self,
        backend: Literal[
            "openai", "ollama", "sglang", "openrouter", "gemini", "huggingface"
        ] = "openai",
        model: str = "gpt-4",
        api_key: Optional[str] = None,
        sglang_host: str = "http://localhost",
        sglang_port: int = 30000,
        hf_device: Optional[str] = None,
        hf_max_new_tokens: int = 1024,
        hf_torch_dtype: str = "auto",
    ):
        if backend == "openai":
            self.llm = OpenAIController(model, api_key)
        elif backend == "ollama":
            self.llm = OllamaController(model)
        elif backend == "sglang":
            self.llm = SGLangController(model, sglang_host, sglang_port)
        elif backend == "openrouter":
            self.llm = OpenRouterController(model, api_key)
        elif backend == "gemini":
            self.llm = GeminiController(model, api_key)
        elif backend == "huggingface":
            self.llm = HuggingFaceController(
                model,
                device=hf_device,
                max_new_tokens=hf_max_new_tokens,
                torch_dtype=hf_torch_dtype,
            )
        else:
            raise ValueError(
                "Backend must be one of: 'openai', 'ollama', 'sglang', "
                "'openrouter', 'gemini', 'huggingface'"
            )

    def get_completion(
        self, prompt: str, response_format: dict = None, temperature: float = 1.0
    ) -> str:
        return self.llm.get_completion(prompt, response_format, temperature)
