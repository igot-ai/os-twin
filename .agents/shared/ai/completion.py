"""Unified completion — single function for all LLM text generation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import get_config
from .errors import AIAuthError, AIError, AITimeoutError
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
        model:  Fully-qualified model ID (e.g. ``"vertex_ai/gemini-3-flash-preview"``).
            If ``None``, resolved from config + *purpose*.
        purpose:  Hint for per-purpose model override (``"knowledge"``, ``"memory"``).
        system:  System prompt.  Ignored when *messages* already contains one.
        response_format:  JSON schema for structured output.
        tools:  Function declarations (OpenAI format).  litellm translates
            to each provider's native format automatically.
        max_tokens:  Maximum tokens in response.
        temperature:  Sampling temperature (0.0 = deterministic).

    Returns:
        ``CompletionResult`` with either ``.text`` or ``.tool_calls`` populated.
    """
    import litellm

    cfg = get_config()
    model = model or cfg.full_model(purpose)

    # Build messages
    if messages:
        msg_list = [dict(m) for m in messages]
    else:
        msg_list = []
        if system:
            msg_list.append({"role": "system", "content": system})
        elif response_format:
            # Encourage JSON output when structured format is requested
            msg_list.append({"role": "system", "content": _SYSTEM_JSON_PROMPT})
        msg_list.append({"role": "user", "content": prompt or ""})

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": msg_list,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "timeout": cfg.timeout,
    }

    # Claude on Vertex Model Garden needs a specific region
    if "claude" in model.lower() and model.startswith("vertex_ai/"):
        kwargs["vertex_ai_location"] = cfg.vertex_claude_location

    if response_format:
        kwargs["response_format"] = response_format
    if tools:
        kwargs["tools"] = tools

    def _call() -> CompletionResult:
        from .monitor import record_completion
        import time as _time

        t0 = _time.time()
        try:
            response = litellm.completion(**kwargs)
        except litellm.AuthenticationError as exc:
            record_completion(
                model,
                purpose,
                (_time.time() - t0) * 1000,
                success=False,
                error=str(exc),
            )
            raise AIAuthError(str(exc)) from exc
        except litellm.Timeout as exc:
            record_completion(
                model,
                purpose,
                (_time.time() - t0) * 1000,
                success=False,
                error=str(exc),
            )
            raise AITimeoutError(str(exc)) from exc
        except Exception as exc:
            record_completion(
                model,
                purpose,
                (_time.time() - t0) * 1000,
                success=False,
                error=str(exc),
            )
            raise AIError(str(exc)) from exc

        choice = response.choices[0]
        content = (choice.message.content or "").strip() or None

        # Check for tool calls
        tool_calls = None
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        usage = None
        in_tok, out_tok = 0, 0
        if hasattr(response, "usage") and response.usage:
            in_tok = response.usage.prompt_tokens or 0
            out_tok = response.usage.completion_tokens or 0
            usage = {"input_tokens": in_tok, "output_tokens": out_tok}

        latency = (_time.time() - t0) * 1000
        record_completion(model, purpose, latency, in_tok, out_tok)

        return CompletionResult(text=content, tool_calls=tool_calls, usage=usage)

    return with_retry(_call, max_retries=cfg.max_retries)
