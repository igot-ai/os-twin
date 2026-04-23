"""Unified AI gateway — two functions for all LLM and embedding calls.

Usage::

    from shared.ai import get_completion, get_embedding

    # Completion (prompt → text)
    text = get_completion("Extract keywords from this text...")

    # Completion with purpose-specific model
    text = get_completion(prompt, purpose="knowledge")  # uses Claude if configured

    # Completion with function calling
    result = complete(messages=msgs, tools=tool_defs)
    if result.tool_calls:
        ...  # handle tool calls

    # Embedding (text → vector)
    vectors = get_embedding(["some text"], model="local/all-MiniLM-L6-v2")
"""

from .completion import complete, CompletionResult
from .embedding import embed
from .config import get_config, reset_config, AIConfig
from .errors import AIError, AIAuthError, AITimeoutError, AIQuotaError


def get_completion(
    prompt: str,
    **kwargs,
) -> str:
    """Simple prompt → text.  For callers that don't need tool_calls.

    Accepts the same keyword arguments as :func:`complete`.
    """
    result = complete(prompt, **kwargs)
    return result.text or ""


def get_embedding(
    texts: list[str],
    **kwargs,
) -> list[list[float]]:
    """Texts → vectors.  Routes to cloud or local based on model prefix.

    Accepts the same keyword arguments as :func:`embed`.
    """
    return embed(texts, **kwargs)


__all__ = [
    "get_completion",
    "get_embedding",
    "complete",
    "CompletionResult",
    "embed",
    "get_config",
    "reset_config",
    "AIConfig",
    "AIError",
    "AIAuthError",
    "AITimeoutError",
    "AIQuotaError",
]
