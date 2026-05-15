"""Unified completion — single function for all LLM text generation.

Uses ``dashboard.llm_client`` (native SDK abstraction) as the LLM backend.
Supports OpenAI, Google (Gemini / Vertex), Anthropic, and any
OpenAI-compatible endpoint via ``llm_client.create_client()``.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import get_config
from .errors import AIAuthError, AIError, AIQuotaError, AITimeoutError
from .retry import with_retry

logger = logging.getLogger(__name__)

# System prompt injected when the caller requests JSON output
_SYSTEM_JSON_PROMPT = "You must respond with a JSON object."


@dataclass
class CompletionResult:
    """Result from a completion call."""

    text: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Optional[Dict[str, int]] = None


# ---------------------------------------------------------------------------
# Async → Sync bridge
# ---------------------------------------------------------------------------


def _run_sync(coro):
    """Execute an async coroutine from sync code.

    If an event loop is already running (e.g. called from within an async
    framework like FastAPI's ``run_in_executor``), we spin up a new loop
    in a thread.  Otherwise we use ``asyncio.run()``.

    Mirrors the pattern used in ``knowledge.llm._run_sync()``.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Already inside a loop → use a thread-based loop
    def runner():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(runner).result()


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


def _map_llm_error(exc: Exception) -> AIError:
    """Map a ``LLMError`` (or generic exception) to the ``AIError`` hierarchy.

    ``llm_client.py`` raises a single ``LLMError`` type.  We heuristically
    classify it into auth / timeout / quota / generic based on the error
    message and any wrapped original exception.
    """
    msg = str(exc).lower()
    original = getattr(exc, "original_error", None)

    # Auth errors
    if any(kw in msg for kw in ("auth", "api key", "401", "403", "permission", "credentials")):
        return AIAuthError(str(exc))
    # Timeout errors
    if any(kw in msg for kw in ("timeout", "timed out", "deadline")):
        return AITimeoutError(str(exc))
    # Quota / rate-limit errors
    if any(kw in msg for kw in ("rate limit", "quota", "429", "resource_exhausted")):
        return AIQuotaError(str(exc))

    return AIError(str(exc))


# ---------------------------------------------------------------------------
# Main completion function
# ---------------------------------------------------------------------------


def complete(
    prompt: Optional[str] = None,
    *,
    messages: Optional[List[Dict[str, Any]]] = None,
    model: Optional[str] = None,
    purpose: Optional[str] = None,
    system: Optional[str] = None,
    response_format: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> CompletionResult:
    """Send a prompt (or messages), get text (or tool_calls) back.

    Supports two modes:

    1. **Simple** — pass ``prompt`` (and optionally ``system``).
    2. **Multi-turn / function-calling** — pass ``messages`` and ``tools``.
       The response may contain ``tool_calls`` instead of ``text``.  The
       caller executes them and sends results back in a follow-up call.

    Args:
        prompt:  User message (simple mode).
        messages:  Full message history (multi-turn mode).
        model:  Bare model name (e.g. ``"gemini-3-flash-preview"``).
            If ``None``, resolved from config + *purpose*.
        purpose:  Hint for per-purpose model override (``"knowledge"``, ``"memory"``).
        system:  System prompt.  Ignored when *messages* already contains one.
        response_format:  JSON schema for structured output (provider support varies).
        tools:  Function declarations (OpenAI format).  ``llm_client`` translates
            to each provider's native format automatically.
        max_tokens:  Maximum tokens in response.
        temperature:  Sampling temperature (0.0 = deterministic).

    Returns:
        ``CompletionResult`` with either ``.text`` or ``.tool_calls`` populated.
    """
    from dashboard.llm_client import (
        ChatMessage,
        LLMConfig,
        LLMError,
        create_client,
    )

    cfg = get_config()
    model = model or cfg.full_model(purpose)

    # Purpose-specific provider overrides.
    # When purpose="memory" and MemorySettings.llm_backend is set, use that
    # provider (and its companion URL/key) instead of the global AIConfig.
    # This mirrors how the embedding path already works via
    # _detect_embed_provider(purpose).
    from dashboard.ai import (
        _detect_completion_provider,
        _detect_completion_model,
        _detect_completion_compatible_url,
        _detect_completion_compatible_key,
    )

    purpose_provider = _detect_completion_provider(purpose)
    purpose_model = _detect_completion_model(purpose)
    purpose_base_url = _detect_completion_compatible_url(purpose)
    purpose_api_key = _detect_completion_compatible_key(purpose)

    effective_provider = purpose_provider or cfg.provider
    if purpose_model:
        model = purpose_model

    # Build ChatMessage list
    chat_messages: List[ChatMessage] = []
    if messages:
        for m in messages:
            chat_messages.append(
                ChatMessage(
                    role=m.get("role", "user"),
                    content=m.get("content"),
                    tool_call_id=m.get("tool_call_id"),
                    name=m.get("name"),
                )
            )
    else:
        if system:
            chat_messages.append(ChatMessage(role="system", content=system))
        elif response_format:
            # Encourage JSON output when structured format is requested
            chat_messages.append(ChatMessage(role="system", content=_SYSTEM_JSON_PROMPT))
        chat_messages.append(ChatMessage(role="user", content=prompt or ""))

    # Create client — pass purpose-specific overrides when available
    llm_config = LLMConfig(
        max_tokens=max_tokens,
        temperature=temperature,
    )
    client = create_client(
        model=model,
        provider=effective_provider,
        config=llm_config,
        base_url=purpose_base_url,
        api_key=purpose_api_key,
    )

    def _call() -> CompletionResult:
        from .monitor import record_completion
        import time as _time

        t0 = _time.time()
        try:

            async def _async_chat():
                return await asyncio.wait_for(
                    client.chat(chat_messages, tools=tools, response_format=response_format),
                    timeout=cfg.timeout,
                )

            response = _run_sync(_async_chat())
        except asyncio.TimeoutError as exc:
            latency_ms = (_time.time() - t0) * 1000
            record_completion(model, purpose, latency_ms, success=False, error="timeout")
            raise AITimeoutError(f"Request timed out after {cfg.timeout}s") from exc
        except LLMError as exc:
            latency_ms = (_time.time() - t0) * 1000
            record_completion(model, purpose, latency_ms, success=False, error=str(exc))
            raise _map_llm_error(exc) from exc
        except (AIAuthError, AITimeoutError, AIQuotaError):
            # Already mapped — re-raise
            raise
        except Exception as exc:
            latency_ms = (_time.time() - t0) * 1000
            record_completion(model, purpose, latency_ms, success=False, error=str(exc))
            raise AIError(str(exc)) from exc

        # --- Map response → CompletionResult ---
        content = (response.content or "").strip() or None

        # Tool calls
        result_tool_calls = None
        if response.tool_calls:
            result_tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else tc.arguments,
                    },
                }
                for tc in response.tool_calls
            ]

        # Usage — llm_client.ChatMessage doesn't carry usage data,
        # so we report None (monitor tracks latency separately).
        usage = None

        latency_ms = (_time.time() - t0) * 1000
        record_completion(model, purpose, latency_ms)

        return CompletionResult(text=content, tool_calls=result_tool_calls, usage=usage)

    return with_retry(_call, max_retries=cfg.max_retries)
