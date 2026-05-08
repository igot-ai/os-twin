"""
Multi-provider LLM client abstraction.

Supports: OpenAI, Anthropic (via OpenAI-compatible API), Google (Gemini), and OpenAI-compatible endpoints.
Uses provider_urls.json for base URLs.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Literal, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

PROVIDER_URLS_PATH = Path(__file__).parent.parent / "provider_urls.json"

Role = Literal["user", "assistant", "system", "tool"]

MAX_RETRIES = 3
RETRY_DELAY = 1.0
REQUEST_TIMEOUT = 120.0


def load_provider_urls() -> dict:
    if not PROVIDER_URLS_PATH.exists():
        logger.warning(f"provider_urls.json not found at {PROVIDER_URLS_PATH}")
        return {}
    with open(PROVIDER_URLS_PATH) as f:
        return json.load(f)


PROVIDER_URLS = load_provider_urls()


def _detect_mime_type(url: str) -> str:
    """Detect mime type from URL or data URI."""
    if url.startswith("data:"):
        mime_end = url.find(";")
        if mime_end > 5:
            return url[5:mime_end]
        return "image/jpeg"

    parsed = urlparse(url)
    path = parsed.path.lower()
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type or "image/jpeg"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)
    thought_signature: Optional[str] = None

    def __repr__(self) -> str:
        return f"ToolCall(id={self.id!r}, name={self.name!r})"


@dataclass
class ChatMessage:
    role: Role
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    thought_signature: Optional[str] = None
    images: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        preview = self.content[:50] if self.content else None
        return f"ChatMessage(role={self.role!r}, content={preview}...)"


@dataclass
class LLMConfig:
    max_tokens: int = 4096
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop: Optional[list[str]] = None


class LLMError(Exception):
    def __init__(self, message: str, provider: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.provider = provider
        self.original_error = original_error


class LLMClient(ABC):
    def __init__(self, model: str, config: Optional[LLMConfig] = None):
        self.model = model
        self.config = config or LLMConfig()

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> ChatMessage:
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> AsyncIterator[str | ToolCall]:
        pass

    async def _retry_with_backoff(self, coro, *args, **kwargs):
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await coro(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (2**attempt)
                    logger.warning(
                        f"LLM request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
        raise LLMError(f"LLM request failed after {MAX_RETRIES} retries", original_error=last_error)


def _get_base_url(provider: str) -> Optional[str]:
    if provider in PROVIDER_URLS:
        return PROVIDER_URLS[provider].get("base")
    return None


class OpenAIClient(LLMClient):
    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        config: Optional[LLMConfig] = None,
    ):
        super().__init__(model, config)
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=REQUEST_TIMEOUT)
        self.base_url = base_url

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict]:
        result = []
        for msg in messages:
            if msg.role == "tool":
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content or "",
                    }
                )
            elif msg.tool_calls:
                result.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                            }
                            for tc in msg.tool_calls
                        ],
                    }
                )
            elif msg.images:
                content_parts = []
                if msg.content:
                    content_parts.append({"type": "text", "text": msg.content})
                for img_url in msg.images:
                    content_parts.append({"type": "image_url", "image_url": {"url": img_url}})
                result.append({"role": msg.role, "content": content_parts})
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def _convert_tools(self, tools: Optional[list[dict]]) -> Optional[list[dict]]:
        if not tools:
            return None
        return [{"type": "function", "function": t} for t in tools]

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> ChatMessage:
        async def _make_request():
            kwargs: dict = {
                "model": self.model,
                "messages": self._convert_messages(messages),
                "max_tokens": self.config.max_tokens,
            }
            if tools:
                kwargs["tools"] = self._convert_tools(tools)
            if tool_choice:
                kwargs["tool_choice"] = tool_choice
            if response_format:
                kwargs["response_format"] = response_format
            if self.config.temperature is not None:
                kwargs["temperature"] = self.config.temperature

            response = await self._client.chat.completions.create(**kwargs)
            choice = response.choices[0]

            tool_calls = []
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append(
                        ToolCall(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=json.loads(tc.function.arguments),
                        )
                    )

            return ChatMessage(
                role=choice.message.role or "assistant",
                content=choice.message.content,
                tool_calls=tool_calls,
            )

        try:
            return await self._retry_with_backoff(_make_request)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"OpenAI API error: {e}", provider="openai", original_error=e)

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> AsyncIterator[str | ToolCall]:
        kwargs: dict = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        if response_format:
            kwargs["response_format"] = response_format
        if self.config.temperature is not None:
            kwargs["temperature"] = self.config.temperature

        tool_calls_accumulator: dict[str, dict] = {}

        try:
            stream = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                if delta.content:
                    yield delta.content

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.id and tc.id not in tool_calls_accumulator:
                            tool_calls_accumulator[tc.id] = {"id": tc.id, "name": "", "arguments": ""}

                        if tc.function:
                            key = tc.id or list(tool_calls_accumulator.keys())[-1] if tool_calls_accumulator else None
                            if key and key in tool_calls_accumulator:
                                if tc.function.name:
                                    tool_calls_accumulator[key]["name"] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls_accumulator[key]["arguments"] += tc.function.arguments

            for tc_data in tool_calls_accumulator.values():
                try:
                    args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                yield ToolCall(id=tc_data["id"], name=tc_data["name"], arguments=args)
        except Exception as e:
            raise LLMError(f"OpenAI streaming error: {e}", provider="openai", original_error=e)


class GoogleClient(LLMClient):
    # Gemini AI (consumer) OpenAI-compatible endpoint.
    # Vertex AI uses a separate region-scoped URL resolved by create_client.
    _GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        config: Optional[LLMConfig] = None,
        vertexai: bool = False,
    ):
        super().__init__(model, config)
        from google.genai import Client
        import os as _os

        # Support model strings like "models/gemini-3.1-pro-preview" or plain "gemini-3.1-pro-preview".
        # The genai SDK expects only the bare model ID (last segment after "/").
        self.model_id = model.split("/")[-1]

        if vertexai:
            project = _os.environ.get("GOOGLE_CLOUD_PROJECT")
            location = _os.environ.get("VERTEX_LOCATION")
            self._client = Client(vertexai=True, project=project, location=location)
        else:
            self._client = Client(api_key=api_key)

        self.base_url = base_url or self._GEMINI_OPENAI_BASE

    def _convert_messages(self, messages: list[ChatMessage]) -> list:
        from google.genai import types

        result = []
        for msg in messages:
            if msg.role == "system":
                result.append(types.Content(role="user", parts=[types.Part(text=msg.content or "")]))
            elif msg.role == "tool":
                tool_name = msg.name or (msg.tool_call_id.replace("fc_", "") if msg.tool_call_id else "unknown_tool")
                func_response = types.Part.from_function_response(
                    name=tool_name, response={"result": msg.content or ""}
                )
                if msg.thought_signature:
                    func_response.thought_signature = msg.thought_signature
                result.append(types.Content(role="tool", parts=[func_response]))
            else:
                role = "user" if msg.role == "user" else "model"
                parts = []
                if msg.content:
                    parts.append(types.Part(text=msg.content))
                for img_url in msg.images:
                    mime_type = _detect_mime_type(img_url)
                    if img_url.startswith("data:"):
                        base64_data = img_url.split(",", 1)[-1] if "," in img_url else img_url
                        parts.append(types.Part.from_bytes(data=base64.b64decode(base64_data), mime_type=mime_type))
                    else:
                        parts.append(types.Part.from_uri(file_uri=img_url, mime_type=mime_type))
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        func_call_part = types.Part.from_function_call(name=tc.name, args=tc.arguments)
                        if tc.thought_signature:
                            func_call_part.thought_signature = tc.thought_signature
                        parts.append(func_call_part)
                if parts:
                    result.append(types.Content(role=role, parts=parts))
        return result

    def _convert_tools(self, tools: Optional[list[dict]]) -> Optional[list]:
        if not tools:
            return None
        from google.genai import types

        declarations = []
        for t in tools:
            declarations.append(
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("parameters", {}),
                )
            )
        return [types.Tool(function_declarations=declarations)]

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> ChatMessage:
        async def _make_request():
            from google.genai import types

            converted = self._convert_messages(messages)
            kwargs: dict = {"model": self.model_id, "contents": converted}
            converted_tools = self._convert_tools(tools)

            # Build GenerateContentConfig with tools and/or structured output
            config_kwargs: dict = {}
            if converted_tools:
                config_kwargs["tools"] = converted_tools
            if response_format:
                # Convert OpenAI-style response_format to Gemini's native format
                schema = response_format.get("json_schema", {}).get("schema", {})
                config_kwargs["response_mime_type"] = "application/json"
                if schema:
                    config_kwargs["response_schema"] = schema
            if config_kwargs:
                kwargs["config"] = types.GenerateContentConfig(**config_kwargs)

            response = await self._client.aio.models.generate_content(**kwargs)

            tool_calls = []
            text_content = None
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        tool_calls.append(
                            ToolCall(
                                id=f"fc_{uuid.uuid4().hex[:8]}",
                                name=part.function_call.name,
                                arguments=dict(part.function_call.args) if part.function_call.args else {},
                                thought_signature=getattr(part, "thought_signature", None),
                            )
                        )
                    elif part.text:
                        text_content = (text_content or "") + part.text

            return ChatMessage(role="assistant", content=text_content, tool_calls=tool_calls)

        try:
            return await self._retry_with_backoff(_make_request)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Google API error: {e}", provider="google", original_error=e)

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> AsyncIterator[str | ToolCall]:
        from google.genai import types

        converted = self._convert_messages(messages)
        kwargs: dict = {"model": self.model_id, "contents": converted}
        converted_tools = self._convert_tools(tools)

        config_kwargs: dict = {}
        if converted_tools:
            config_kwargs["tools"] = converted_tools
        if response_format:
            schema = response_format.get("json_schema", {}).get("schema", {})
            config_kwargs["response_mime_type"] = "application/json"
            if schema:
                config_kwargs["response_schema"] = schema
        if config_kwargs:
            kwargs["config"] = types.GenerateContentConfig(**config_kwargs)

        try:
            async for chunk in await self._client.aio.models.generate_content_stream(**kwargs):
                if chunk.text:
                    yield chunk.text
                if chunk.candidates and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        if part.function_call:
                            yield ToolCall(
                                id=f"fc_{uuid.uuid4().hex[:8]}",
                                name=part.function_call.name,
                                arguments=dict(part.function_call.args) if part.function_call.args else {},
                                thought_signature=getattr(part, "thought_signature", None),
                            )
        except Exception as e:
            raise LLMError(f"Google streaming error: {e}", provider="google", original_error=e)




class OllamaClient(LLMClient):
    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        config: Optional[LLMConfig] = None,
    ):
        super().__init__(model, config)
        from ollama import AsyncClient
        
        # Ollama supports host directly in AsyncClient
        self._client = AsyncClient(host=base_url)
        self.base_url = base_url

    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict]:
        result = []
        for msg in messages:
            if msg.role == "tool":
                # Ollama maps function responses using role="tool"
                result.append({
                    "role": "tool",
                    "content": msg.content or "",
                })
            elif msg.tool_calls:
                tool_calls = [
                    {
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments
                        }
                    }
                    for tc in msg.tool_calls
                ]
                result.append({
                    "role": msg.role,
                    "content": msg.content or "",
                    "tool_calls": tool_calls,
                })
            elif msg.images:
                images = []
                for img_url in msg.images:
                    if img_url.startswith("data:"):
                        b64 = img_url.split(",", 1)[-1]
                        images.append(b64)
                    else:
                        images.append(img_url)
                
                result.append({
                    "role": msg.role,
                    "content": msg.content or "",
                    "images": images
                })
            else:
                result.append({
                    "role": msg.role,
                    "content": msg.content or ""
                })
        return result

    def _convert_tools(self, tools: Optional[list[dict]]) -> Optional[list[dict]]:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {}),
                }
            }
            for t in tools
        ]

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> ChatMessage:
        async def _make_request():
            kwargs: dict = {
                "model": self.model,
                "messages": self._convert_messages(messages),
            }
            
            options = {}
            if self.config.temperature is not None:
                options["temperature"] = self.config.temperature
            if self.config.top_p is not None:
                options["top_p"] = self.config.top_p
            if self.config.stop is not None:
                options["stop"] = self.config.stop
                
            if options:
                kwargs["options"] = options

            if tools:
                kwargs["tools"] = self._convert_tools(tools)

            response = await self._client.chat(**kwargs)
            message = response.get("message", {})
            
            tool_calls = []
            if "tool_calls" in message and message["tool_calls"]:
                for tc in message["tool_calls"]:
                    func = tc.get("function", {})
                    if func:
                        tool_calls.append(
                            ToolCall(
                                id=f"call_{uuid.uuid4().hex}",
                                name=func.get("name", ""),
                                arguments=func.get("arguments", {}),
                            )
                        )

            return ChatMessage(
                role=message.get("role", "assistant"),
                content=message.get("content", ""),
                tool_calls=tool_calls,
            )

        try:
            return await self._retry_with_backoff(_make_request)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Ollama API error: {e}", provider="ollama", original_error=e)

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> AsyncIterator[str | ToolCall]:
        kwargs: dict = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "stream": True,
        }
        
        options = {}
        if self.config.temperature is not None:
            options["temperature"] = self.config.temperature
        if self.config.top_p is not None:
            options["top_p"] = self.config.top_p
        if self.config.stop is not None:
            options["stop"] = self.config.stop
            
        if options:
            kwargs["options"] = options

        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        try:
            async for chunk in await self._client.chat(**kwargs):
                message = chunk.get("message", {})
                
                if "tool_calls" in message and message["tool_calls"]:
                    for tc in message["tool_calls"]:
                        func = tc.get("function", {})
                        if func:
                            yield ToolCall(
                                id=f"call_{uuid.uuid4().hex}",
                                name=func.get("name", ""),
                                arguments=func.get("arguments", {}),
                            )
                
                content = message.get("content", "")
                if content:
                    yield content
        except Exception as e:
            raise LLMError(f"Ollama streaming error: {e}", provider="ollama", original_error=e)

PROVIDER_API_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "google-genai": "GOOGLE_API_KEY",
    "google-vertex": "GOOGLE_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "groq": "GROQ_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "together": "TOGETHER_API_KEY",
    "togetherai": "TOGETHER_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "xai": "XAI_API_KEY",
    "cohere": "CO_API_KEY",
    "openai-compatible": "OPENAI_COMPATIBLE_API_KEY",
}


def _detect_provider_from_model(model: str) -> str:
    model_lower = model.lower()
    if any(x in model_lower for x in ["gpt-", "o1-", "o3-", "o4-", "chatgpt"]):
        return "openai"
    elif "claude" in model_lower:
        return "anthropic"
    elif "gemini" in model_lower or "google" in model_lower:
        if "vertex" in model_lower:
            return "google-vertex"
        return "google"
    elif "deepseek" in model_lower:
        return "deepseek"
    elif "mistral" in model_lower or "mixtral" in model_lower:
        return "mistral"
    elif "llama" in model_lower:
        if "meta" in model_lower or "facebook" in model_lower:
            return "together"
        for provider in ["together", "fireworks", "groq", "deepinfra"]:
            if provider in PROVIDER_URLS:
                return provider
        return "together"
    elif "qwen" in model_lower:
        return "alibaba"
    elif "grok" in model_lower:
        return "xai"
    return "openai"


def create_client(
    model: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    config: Optional[LLMConfig] = None,
) -> LLMClient:
    import os as _os

    if provider is None:
        provider = _detect_provider_from_model(model)

    # Resolve custom configurations from settings if available
    try:
        from dashboard.lib.settings.resolver import get_settings_resolver
        resolver = get_settings_resolver()
        master_settings = resolver.get_master_settings()
        providers = master_settings.providers if master_settings else None
    except Exception:
        providers = None

    if provider in ("google", "google-genai", "google_gemini", "google-vertex"):
        base_url = _get_base_url(provider)
        is_vertex = provider == "google-vertex"
        if is_vertex and base_url:
            region = _os.environ.get("VERTEX_LOCATION", "global")
            project = _os.environ.get("GOOGLE_CLOUD_PROJECT", "")
            base_url = base_url.replace("{region}", region).replace("{project}", project)
        api_key = api_key or _os.environ.get("GEMINI_API_KEY") or _os.environ.get("OSTWIN_API_KEY") or _os.environ.get("GOOGLE_API_KEY")
        return GoogleClient(model=model, api_key=api_key, base_url=base_url, config=config, vertexai=is_vertex)

    if provider == "openai-compatible":
        cfg = providers.openai_compatible if providers else None
        base_url = (cfg.base_url if cfg and cfg.base_url else _os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:8000"))
        api_key = api_key or _os.environ.get("OPENAI_COMPATIBLE_API_KEY", "")
        return OpenAIClient(model=model, api_key=api_key, base_url=base_url, config=config)

    if provider == "ollama":
        cfg = providers.ollama if providers else None
        base_url = (cfg.base_url if cfg and cfg.base_url else _os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
        return OllamaClient(model=model, base_url=base_url, config=config)

    base_url = _get_base_url(provider)
    return OpenAIClient(model=model, api_key=api_key, base_url=base_url, config=config)