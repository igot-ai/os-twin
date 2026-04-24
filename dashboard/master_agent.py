"""
Master Agent Model Configuration.

Provides a global default LLM model that can be used across the dashboard
for plan refinement, brainstorming, and other AI operations.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from dashboard.llm_client import ChatMessage, LLMConfig, LLMClient, ToolCall, create_client

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.1-pro-preview"
DEFAULT_PROVIDER = "google"


@dataclass
class MasterAgentConfig:
    model: str = DEFAULT_MODEL
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: int = 8192
    is_explicit: bool = False

    def to_llm_config(self) -> LLMConfig:
        return LLMConfig(
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )


_master_config = MasterAgentConfig()


def is_master_model_explicit() -> bool:
    return _master_config.is_explicit


def get_master_model() -> str:
    return _master_config.model


def set_master_model(model: str, provider: Optional[str] = None) -> None:
    if "/" in model:
        provider, model = model.split("/", 1)
    elif ":" in model:
        provider, model = model.split(":", 1)
    _master_config.model = model
    _master_config.provider = provider
    _master_config.is_explicit = True
    logger.info("[MASTER_AGENT] Model set to: %s (provider: %s)", model, provider)


def get_master_config() -> MasterAgentConfig:
    return MasterAgentConfig(
        model=_master_config.model,
        provider=_master_config.provider,
        temperature=_master_config.temperature,
        max_tokens=_master_config.max_tokens,
    )


def set_master_config(config: MasterAgentConfig) -> None:
    global _master_config
    _master_config = config
    logger.info("[MASTER_AGENT] Config updated: model=%s, provider=%s", config.model, config.provider)


def _get_api_key(provider: str) -> Optional[str]:
    from dashboard.lib.settings.vault import get_vault

    key_map = {
        "openai": "openai",
        "anthropic": "anthropic",
        "google": "google",
        "google-genai": "google",
        "deepseek": "deepseek",
        "mistral": "mistral",
    }
    vault_key = key_map.get(provider)
    if vault_key:
        try:
            vault = get_vault()
            return vault.get("providers", vault_key)
        except Exception as e:
            logger.warning("[MASTER_AGENT] Failed to get API key from vault: %s", e)

    env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "google-genai": "GOOGLE_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }
    env_var = env_map.get(provider)
    if env_var:
        return os.environ.get(env_var)

    return None


def create_master_client() -> LLMClient:
    model = _master_config.model
    provider = _master_config.provider

    if provider is None:
        if "/" in model:
            provider, model = model.split("/", 1)
        elif ":" in model:
            provider, model = model.split(":", 1)

    api_key = _get_api_key(provider or "openai") if provider else None
    config = _master_config.to_llm_config()

    logger.debug("[MASTER_AGENT] Creating client: model=%s, provider=%s", model, provider)
    return create_client(model, provider=provider, api_key=api_key, config=config)


async def master_chat(
    messages: list[ChatMessage],
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[str] = None,
) -> ChatMessage:
    client = create_master_client()
    return await client.chat(messages, tools=tools, tool_choice=tool_choice)


async def master_chat_stream(
    messages: list[ChatMessage],
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[str] = None,
) -> AsyncIterator[str | ToolCall]:
    client = create_master_client()
    async for chunk in client.chat_stream(messages, tools=tools, tool_choice=tool_choice):
        yield chunk


async def master_complete(
    prompt: str,
    system_prompt: Optional[str] = None,
) -> str:
    messages = []
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    messages.append(ChatMessage(role="user", content=prompt))

    response = await master_chat(messages)
    return response.content or ""


async def master_complete_stream(
    prompt: str,
    system_prompt: Optional[str] = None,
) -> AsyncIterator[str]:
    messages = []
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    messages.append(ChatMessage(role="user", content=prompt))

    async for chunk in master_chat_stream(messages):
        if isinstance(chunk, str):
            yield chunk
