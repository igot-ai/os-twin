"""
Master Agent Model Configuration.

Provides a global default LLM model that can be used across the dashboard
for plan refinement, brainstorming, and other AI operations.

The client is initialized once and reused across all requests.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from dashboard.llm_client import ChatMessage, LLMConfig, LLMClient, ToolCall, create_client

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.1-pro-preview"
DEFAULT_PROVIDER = "google-vertex"


@dataclass
class MasterAgentConfig:
    model: str = DEFAULT_MODEL
    provider: Optional[str] = DEFAULT_PROVIDER
    temperature: Optional[float] = None
    max_tokens: int = 8192
    is_explicit: bool = False

    def to_llm_config(self) -> LLMConfig:
        return LLMConfig(
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )


_master_config = MasterAgentConfig()
_master_client: Optional[LLMClient] = None


def init_master_from_config() -> None:
    """Load persisted settings from config.json on startup.

    Restores:
    - ``runtime.master_agent_model`` → in-memory ``_master_config``
    - ``memory.*`` → env vars (so subprocesses inherit config.json values)
    - ``knowledge.*`` → env vars (so subprocesses inherit config.json values)

    This ensures user choices made in the settings UI survive process
    restarts and are not silently overridden by .env.sh defaults.
    """
    try:
        from dashboard.lib.settings import get_settings_resolver

        resolver = get_settings_resolver()
        settings = resolver.get_master_settings()

        # ── Master agent model ──────────────────────────────────────────
        stored = settings.runtime.master_agent_model
        if stored:
            set_master_model(stored)
            logger.info(
                "[MASTER_AGENT] Restored from config.json: %s",
                stored,
            )

        # ── Memory settings → env vars for agent subprocesses ──────────
        mem = settings.memory
        if mem.llm_backend:
            os.environ.setdefault("MEMORY_LLM_BACKEND", mem.llm_backend)
        if mem.llm_model:
            os.environ.setdefault("MEMORY_LLM_MODEL", mem.llm_model)
        if mem.embedding_backend:
            os.environ.setdefault("MEMORY_EMBEDDING_BACKEND", mem.embedding_backend)
        if mem.embedding_model:
            os.environ.setdefault("MEMORY_EMBEDDING_MODEL", mem.embedding_model)
        logger.info(
            "[MASTER_AGENT] Memory settings from config.json: llm=%s/%s embed=%s/%s",
            mem.llm_backend, mem.llm_model,
            mem.embedding_backend, mem.embedding_model,
        )

        # ── Knowledge settings → env vars for agent subprocesses ───────
        know = settings.knowledge
        if know.knowledge_llm_backend:
            os.environ.setdefault("OSTWIN_KNOWLEDGE_LLM_PROVIDER", know.knowledge_llm_backend)
        if know.knowledge_llm_model:
            os.environ.setdefault("OSTWIN_KNOWLEDGE_LLM_MODEL", know.knowledge_llm_model)
        if know.knowledge_embedding_backend:
            os.environ.setdefault("OSTWIN_KNOWLEDGE_EMBED_PROVIDER", know.knowledge_embedding_backend)
        if know.knowledge_embedding_model:
            os.environ.setdefault("OSTWIN_KNOWLEDGE_EMBED_MODEL", know.knowledge_embedding_model)
        logger.info(
            "[MASTER_AGENT] Knowledge settings from config.json: llm=%s/%s embed=%s/%s",
            know.knowledge_llm_backend, know.knowledge_llm_model,
            know.knowledge_embedding_backend, know.knowledge_embedding_model,
        )
    except Exception as exc:
        logger.warning(
            "[MASTER_AGENT] Could not load settings from config.json: %s",
            exc,
        )


def is_master_model_explicit() -> bool:
    return _master_config.is_explicit


def get_master_model() -> str:
    return _master_config.model


def set_master_model(model: str, provider: Optional[str] = None) -> None:
    global _master_client
    if "/" in model:
        provider, model = model.split("/", 1)
    elif ":" in model:
        provider, model = model.split(":", 1)
    _master_config.model = model
    _master_config.provider = provider
    _master_config.is_explicit = True
    _master_client = None
    logger.info("[MASTER_AGENT] Model set to: %s (provider: %s)", model, provider)


def get_master_config() -> MasterAgentConfig:
    return MasterAgentConfig(
        model=_master_config.model,
        provider=_master_config.provider,
        temperature=_master_config.temperature,
        max_tokens=_master_config.max_tokens,
    )


def set_master_config(config: MasterAgentConfig) -> None:
    global _master_config, _master_client
    _master_config = config
    _master_client = None
    logger.info("[MASTER_AGENT] Config updated: model=%s, provider=%s", config.model, config.provider)


def get_api_key(provider: str) -> Optional[str]:
    from dashboard.lib.settings.vault import get_vault

    auth_path = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    if auth_path.exists():
        try:
            auth_data = json.loads(auth_path.read_text())
            entry = auth_data.get(provider)
            if isinstance(entry, dict) and entry.get("type") == "api":
                return entry.get("key")
        except Exception as e:
            logger.warning("[MASTER_AGENT] auth.json read failed: %s", e)

    try:
        vault = get_vault()
        key = vault.get("providers", provider)
        if key:
            return key
    except Exception as e:
        logger.warning("[MASTER_AGENT] Vault read failed: %s", e)

    return None


def create_client_for_model(model: str, provider: Optional[str] = None) -> LLMClient:
    if provider is None:
        if "/" in model:
            provider, model = model.split("/", 1)
        elif ":" in model:
            provider, model = model.split(":", 1)

    api_key = get_api_key(provider or "openai") if provider else None
    config = _master_config.to_llm_config()

    logger.debug("[MASTER_AGENT] Creating client for model: %s (provider: %s)", model, provider)
    return create_client(model, provider=provider, api_key=api_key, config=config)


def _build_client() -> LLMClient:
    model = _master_config.model
    provider = _master_config.provider

    if provider is None:
        if "/" in model:
            provider, model = model.split("/", 1)
        elif ":" in model:
            provider, model = model.split(":", 1)

    api_key = get_api_key(provider or "openai") if provider else None
    config = _master_config.to_llm_config()

    logger.info("[MASTER_AGENT] Building client: model=%s, provider=%s", model, provider)
    return create_client(model, provider=provider, api_key=api_key, config=config)


def get_master_client() -> LLMClient:
    global _master_client
    if _master_client is None:
        _master_client = _build_client()
    return _master_client


def reset_master_client() -> None:
    global _master_client
    _master_client = None
    logger.info("[MASTER_AGENT] Client reset, will rebuild on next use")


async def master_chat(
    messages: list[ChatMessage],
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[str] = None,
) -> ChatMessage:
    client = get_master_client()
    return await client.chat(messages, tools=tools, tool_choice=tool_choice)


async def master_chat_stream(
    messages: list[ChatMessage],
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[str] = None,
) -> AsyncIterator[str | ToolCall]:
    client = get_master_client()
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
