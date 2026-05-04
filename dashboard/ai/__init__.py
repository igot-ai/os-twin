"""Unified AI gateway for the dashboard.

Provides completion via :mod:`dashboard.llm_client` (multi-provider native
SDK abstraction), and embedding via
:class:`~dashboard.knowledge.embeddings.KnowledgeEmbedder`.

Usage::

    from dashboard.ai import get_completion, get_embedding

    # Completion (prompt → text)
    text = get_completion("Extract keywords from this text...")

    # Completion with purpose-specific model
    text = get_completion(prompt, purpose="knowledge")

    # Completion with function calling
    result = complete(messages=msgs, tools=tool_defs)
    if result.tool_calls:
        ...  # handle tool calls

    # Embedding (text → vector)
    vectors = get_embedding(["some text"])
"""

from .completion import complete, CompletionResult
from .config import get_config, reset_config, AIConfig
from .errors import AIError, AIAuthError, AITimeoutError, AIQuotaError


# Lazy singleton — avoids circular import with dashboard.knowledge
_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from dashboard.knowledge.embeddings import KnowledgeEmbedder
        _embedder = KnowledgeEmbedder()
    return _embedder


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
    """Texts → vectors via KnowledgeEmbedder.

    Every call is recorded in the AI Monitor for observability.
    """
    import time as _time
    from .monitor import record_embedding

    embedder = _get_embedder()
    t0 = _time.time()
    try:
        result = embedder.embed(texts)
        latency_ms = (_time.time() - t0) * 1000
        record_embedding(
            model=f"{embedder.provider}/{embedder.model_name}",
            text_count=len(texts),
            latency_ms=latency_ms,
        )
        return result
    except Exception as exc:
        latency_ms = (_time.time() - t0) * 1000
        record_embedding(
            model=f"{embedder.provider}/{embedder.model_name}",
            text_count=len(texts),
            latency_ms=latency_ms,
            success=False,
            error=str(exc),
        )
        raise


def embed(
    texts: list[str],
    **kwargs,
) -> list[list[float]]:
    """Alias for ``get_embedding`` — backward compatibility."""
    return get_embedding(texts, **kwargs)


def get_stats():
    """Return AI usage statistics."""
    from .monitor import get_stats as _get_stats
    return _get_stats()


def reset_stats():
    """Reset AI usage statistics."""
    from .monitor import reset_stats as _reset_stats
    return _reset_stats()


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
    "get_stats",
    "reset_stats",
]
