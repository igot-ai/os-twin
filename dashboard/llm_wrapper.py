"""Base LLM wrapper for domain-specific LLM services.

Provides the shared plumbing that ``MemoryLLM`` and ``KnowledgeLLM`` both
need — provider/model resolution, API-key resolution, client creation,
JSON extraction, graceful degradation, timeout handling, and empty-response
generation.

Provider resolution is delegated entirely to ``dashboard.llm_client``
via ``resolve_provider_and_model()``, which is the single source of truth
for parsing ``provider/model`` format strings, normalising aliases, and
deciding which transport to use (native provider vs. openai-compatible vs.
ollama).

Subclasses override ``_resolve_model_settings()`` and ``_complete()`` (or
just add domain-specific public methods on top of the base completion
primitive).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Optional

from dashboard.llm_client import (
    ChatMessage,
    LLMConfig,
    LLMError,
    _TRANSPORT_PROVIDERS,
    _resolve_transport_api_key,
    create_client,
    resolve_provider_and_model,
    run_sync,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60
_DEFAULT_MAX_TOKENS = 4096


class BaseLLMWrapper:
    """Base class for domain LLM wrappers backed by ``dashboard.llm_client``.

    Subclasses must set ``self.model``, ``self.provider``, and
    ``self._explicit_key`` in ``__init__`` (typically by calling
    ``super().__init__()`` then ``_resolve_model_settings()``).

    Provider resolution is delegated to ``llm_client.resolve_provider_and_model``
    so that ``provider/model`` format strings are handled consistently across
    the entire system.

    Designed for graceful degradation: when no model or API key is
    configured, every method returns a sensible empty/fallback value
    so callers don't have to special-case the missing-key path.
    """

    def __init__(
        self,
        model: str | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        *,
        timeout: int = _DEFAULT_TIMEOUT,
        base_url: str | None = None,
    ) -> None:
        self.model: str = model or ""
        self.provider: str | None = provider
        self._explicit_key: str | None = api_key
        self._explicit_base_url: str | None = base_url
        self._timeout = timeout
        self._resolved: tuple[str, str, Optional[str]] | None = None

    # -- Subclass hook ---------------------------------------------------

    def _resolve_model_settings(self) -> None:
        """Populate ``self.model`` and ``self.provider`` from settings / env.

        Subclasses override this to pull from their domain-specific config
        (e.g. MasterSettings.memory, MasterSettings.knowledge). Called once
        during ``__init__``.
        """

    # -- Provider / model resolution -------------------------------------

    def _get_resolved(self) -> tuple[str, str, Optional[str]]:
        """Return ``(effective_provider, clean_model, model_provider)``.

        Cached after first call.  Delegates to
        ``llm_client.resolve_provider_and_model``.
        """
        if self._resolved is None:
            self._resolved = resolve_provider_and_model(self.model, self.provider)
        return self._resolved

    def _effective_provider(self) -> str:
        """Return the effective provider after resolution."""
        return self._get_resolved()[0]

    def _clean_model(self) -> str:
        """Return the model identifier with provider prefix normalised."""
        return self._get_resolved()[1]

    def _model_provider(self) -> Optional[str]:
        """Return the provider embedded in the model string, if any."""
        return self._get_resolved()[2] or self._get_resolved()[0]

    # -- Capability ------------------------------------------------------

    def is_available(self) -> bool:
        """True iff a model is configured AND an API key can be resolved.

        Ollama and local-first providers don't require an API key by default.
        If a key is explicitly configured, it will be used; otherwise the
        local endpoint is assumed available without authentication.
        """
        if not self.model:
            return False
        key = self._resolve_api_key()
        if key:
            return True
        provider = self._effective_provider()
        if provider in ("ollama",):
            return True
        return False

    # -- API key resolution ----------------------------------------------

    def _resolve_api_key(self) -> Optional[str]:
        """Resolve an API key for the configured provider.

        Priority:
          1. Explicit key passed at construction
          2. Key for the *effective* (transport) provider via auth.json
          3. Key for the *model-embedded* provider — ONLY when the effective
             provider is a native provider (not a transport like
             ``openai-compatible`` or ``ollama``).
        """
        if self._explicit_key:
            return self._explicit_key

        effective = self._effective_provider()
        model_prov = self._model_provider()

        key = _resolve_transport_api_key(effective)
        if key:
            return key

        if model_prov and model_prov != effective and effective not in _TRANSPORT_PROVIDERS:
            key = _resolve_transport_api_key(model_prov)
            if key:
                return key

        return None

    # -- Client creation -------------------------------------------------

    def _get_client(self, max_tokens: int = None) -> Any:
        """Create the LLMClient via the unified factory.

        We do not cache this instance because it gets bound to the ephemeral
        event loop created by ``run_sync``. Reusing it across multiple
        ``run_sync`` calls would result in 'Event loop is closed' errors.

        When ``_explicit_base_url`` is set (e.g. from memory-specific
        compatible_url), it is passed to ``create_client`` so the
        openai-compatible transport uses the custom endpoint instead of
        the global provider default.
        """
        config = LLMConfig(max_tokens=max_tokens)
        kwargs: dict[str, Any] = dict(
            model=self._clean_model(),
            provider=self._model_provider(),
            config=config,
        )
        if self._explicit_base_url:
            kwargs["base_url"] = self._explicit_base_url
        # Pass the explicit API key when available (e.g. from memory-specific
        # compatible_key) so it overrides the global provider key.
        resolved_key = self._resolve_api_key()
        if resolved_key:
            kwargs["api_key"] = resolved_key
        return create_client(**kwargs)

    # -- JSON extraction -------------------------------------------------

    @staticmethod
    def _extract_json(text: str) -> Any:
        """Pull the first JSON object/array out of a text blob."""
        text = text.strip()
        fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                logger.debug("Failed to parse JSON from LLM response")
        return None

    # -- Core completion -------------------------------------------------

    def _complete(self, system: str, user: str, max_tokens: int = 2048) -> str:
        """Run a single LLM chat call via ``llm_client``. Returns the text content.

        Honours ``self._timeout`` (default 60s).
        On timeout, logs WARNING and returns empty string (graceful degradation).
        """
        t0 = time.perf_counter()

        client = self._get_client(max_tokens=max_tokens)

        messages = [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user),
        ]

        async def _call():
            return await asyncio.wait_for(
                client.chat(messages),
                timeout=self._timeout,
            )

        try:
            response = run_sync(_call())
            result_text = response.content or ""
            elapsed = time.perf_counter() - t0
            logger.debug(
                "%s call completed in %.2fs (model=%s)",
                type(self).__name__,
                elapsed,
                self.model,
            )
            return result_text
        except asyncio.TimeoutError:
            logger.warning(
                "%s timeout: LLM call timed out after %ss (model=%s, provider=%s)",
                type(self).__name__,
                self._timeout,
                self.model,
                self._effective_provider(),
            )
            return ""
        except Exception as exc:
            exc_name = type(exc).__name__
            if "Timeout" in exc_name or "timeout" in str(exc).lower():
                logger.warning(
                    "%s timeout: LLM call timed out after %ss (model=%s, provider=%s)",
                    type(self).__name__,
                    self._timeout,
                    self.model,
                    self._effective_provider(),
                )
                return ""
            logger.error(
                "%s call failed (provider=%s): %s",
                type(self).__name__,
                self._effective_provider(),
                exc,
            )
            return ""

    # -- Empty response generation ---------------------------------------

    @staticmethod
    def _generate_empty_value(schema_type: str, schema_items: dict | None = None) -> Any:
        """Generate empty value based on JSON schema type."""
        if schema_type == "array":
            return []
        elif schema_type == "string":
            return ""
        elif schema_type == "object":
            return {}
        elif schema_type in ("number", "integer"):
            return 0
        elif schema_type == "boolean":
            return False
        return None

    @staticmethod
    def _generate_empty_response(response_format: dict) -> dict:
        """Generate empty response matching the expected schema."""
        if "json_schema" not in response_format:
            return {}

        schema = response_format["json_schema"]["schema"]
        result = {}

        if "properties" in schema:
            for prop_name, prop_schema in schema["properties"].items():
                result[prop_name] = BaseLLMWrapper._generate_empty_value(
                    prop_schema["type"], prop_schema.get("items")
                )

        return result
