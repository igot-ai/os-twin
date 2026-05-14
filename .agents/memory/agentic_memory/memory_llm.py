"""Multi-provider LLM wrapper for the Agentic Memory system.

Delegates to the centralized ``dashboard.llm_wrapper.BaseLLMWrapper``
abstraction (shared with ``dashboard.knowledge.llm.KnowledgeLLM``),
providing:

- Multi-provider support (OpenAI, Anthropic, Google/Gemini, Ollama, OpenAI-compatible)
- Unified API key resolution (explicit → MasterSettings → env var → vault)
- Graceful degradation (returns empty values when no model/key configured)
- LLM call timeout (``MEMORY_LLM_TIMEOUT``, default 60s)
- JSON extraction from LLM responses

This replaces the old ``llm_controller.py`` which had 6 separate backend
classes with no timeout, no retry, and no shared key resolution.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dashboard.llm_wrapper import BaseLLMWrapper

logger = logging.getLogger(__name__)

LLM_TIMEOUT = int(os.environ.get("MEMORY_LLM_TIMEOUT", "60"))

_SYSTEM_JSON_PROMPT = "You must respond with a JSON object."


_UNSET = object()


class MemoryLLM(BaseLLMWrapper):
    """Multi-provider LLM helper backed by ``dashboard.llm_wrapper``.

    Designed for graceful degradation: when no model or API key is
    configured, every method returns a sensible empty/fallback value
    so callers don't have to special-case the missing-key path.

    Provider is auto-detected from the model name (e.g. ``claude-*`` → Anthropic,
    ``gpt-*`` → OpenAI, ``gemini-*`` → Google).  An explicit ``provider``
    parameter overrides auto-detection.

    When the provider is ``"openai-compatible"``, the ``compatible_url`` and
    ``compatible_key`` from ``MemorySettings`` are used to connect to the
    custom endpoint.

    Usage::

        llm = MemoryLLM(model="gemini-3-flash-preview", provider="google")
        result = llm.get_completion("Extract keywords from...")
    """

    def __init__(
        self,
        model: str | None = _UNSET,
        provider: str | None = _UNSET,
        api_key: str | None = None,
    ) -> None:
        self._explicit_model = model
        self._explicit_provider = provider
        # Pre-resolve compatible_url / compatible_key before super().__init__
        _base_url, _resolved_key = self._resolve_compatible_settings()
        super().__init__(
            model=model if model is not _UNSET and model is not None else "",
            provider=provider if provider is not _UNSET and provider is not None else None,
            api_key=api_key or _resolved_key,
            base_url=_base_url,
            timeout=LLM_TIMEOUT,
        )
        self._resolve_model_settings()

    @staticmethod
    def _resolve_compatible_settings() -> tuple[str | None, str | None]:
        """Resolve openai-compatible URL and key from MemorySettings."""
        try:
            from dashboard.lib.settings.resolver import get_settings_resolver
            resolver = get_settings_resolver()
            master = resolver.get_master_settings()
            if hasattr(master, "memory") and master.memory:
                mem = master.memory
                backend = getattr(mem, "llm_backend", "") or getattr(mem, "embedding_backend", "")
                if backend == "openai-compatible":
                    url = getattr(mem, "llm_compatible_url", "") or getattr(mem, "embedding_compatible_url", "")
                    key = getattr(mem, "llm_compatible_key", "") or getattr(mem, "embedding_compatible_key", "")
                    return (url or None, key or None)
        except Exception:
            pass
        return (None, None)

    def _resolve_model_settings(self) -> None:
        """Resolve model and provider from MasterSettings or env vars.

        Explicit values passed to __init__ (including None/empty string)
        always take precedence over settings/env resolution.
        """
        if self._explicit_model is _UNSET:
            self.model = self._resolve_model()
        if self._explicit_provider is _UNSET:
            self.provider = self._resolve_provider()

    @staticmethod
    def _resolve_model() -> str:
        try:
            from dashboard.lib.settings.resolver import get_settings_resolver
            resolver = get_settings_resolver()
            master = resolver.get_master_settings()
            if hasattr(master, 'memory') and master.memory:
                mem_cfg = master.memory
                if hasattr(mem_cfg, 'llm_model') and mem_cfg.llm_model:
                    return mem_cfg.llm_model
        except Exception:
            pass
        return os.environ.get("MEMORY_LLM_MODEL", "")

    @staticmethod
    def _resolve_provider() -> str | None:
        try:
            from dashboard.lib.settings.resolver import get_settings_resolver
            resolver = get_settings_resolver()
            master = resolver.get_master_settings()
            if hasattr(master, 'memory') and master.memory:
                mem_cfg = master.memory
                # Prefer llm_backend (new field name); fall back to embedding_provider (legacy alias)
                backend = getattr(mem_cfg, 'llm_backend', '') or getattr(mem_cfg, 'embedding_provider', '')
                if backend:
                    return backend
        except Exception:
            pass
        val = os.environ.get("MEMORY_LLM_BACKEND", "")
        return val if val else None

    def get_completion(
        self,
        prompt: str,
        response_format: dict | None = None,
        temperature: float = 1.0,
        max_tokens: int | None = None,
    ) -> str:
        """Get completion from LLM.

        When ``response_format`` is provided with a JSON schema, the system
        prompt requests JSON-only output and the response is validated.

        Args:
            prompt: The user prompt to send.
            response_format: Optional JSON schema dict.
            temperature: Sampling temperature (0.0–1.0).
            max_tokens: Override max output tokens.

        Returns:
            JSON string when ``response_format`` is set, raw text otherwise.
            Returns empty string on failure (graceful degradation).
        """
        if not self.is_available():
            if response_format:
                return json.dumps(self._generate_empty_response(response_format))
            return ""

        system = _SYSTEM_JSON_PROMPT if response_format else "You are a helpful assistant."

        if response_format:
            schema = response_format.get("json_schema", {}).get("schema", {})
            if schema:
                system += (
                    f"\n\nRespond with a JSON object matching this schema:\n"
                    f"{json.dumps(schema, indent=2)}\n"
                    f"Only return valid JSON, no prose, no markdown fences."
                )

        result = self._complete(system, prompt, max_tokens=max_tokens or 1024)

        if not result:
            if response_format:
                return json.dumps(self._generate_empty_response(response_format))
            return ""

        return result
