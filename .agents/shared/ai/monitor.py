"""AI Gateway traffic monitor — logs every call and tracks stats.

Two storage layers:
1. **In-memory** — per-process counters (fast, used for the dashboard's
   own calls like zvec_store).
2. **Shared file** — ``~/.ostwin/ai_monitor.jsonl`` (append-only, all
   processes write here). The dashboard reads this file to aggregate
   stats across all processes (MCP servers, dashboard, CLI).

Every call is also logged to the standard Python logger at INFO level.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CallRecord:
    """Single call record for logging."""

    timestamp: float
    call_type: str  # "completion" or "embedding"
    model: str
    purpose: Optional[str]
    caller: Optional[str]  # inferred from stack
    latency_ms: float
    input_tokens: int
    output_tokens: int
    text_count: int  # number of texts (for embedding)
    success: bool
    error: Optional[str]


@dataclass
class _Stats:
    """Aggregate counters — thread-safe via lock."""

    lock: threading.Lock = field(default_factory=threading.Lock)

    # Totals
    total_completions: int = 0
    total_embeddings: int = 0
    total_errors: int = 0

    # Per-model counters: {model: count}
    completions_by_model: dict = field(default_factory=lambda: defaultdict(int))
    embeddings_by_model: dict = field(default_factory=lambda: defaultdict(int))

    # Per-purpose counters: {purpose: count}
    completions_by_purpose: dict = field(default_factory=lambda: defaultdict(int))

    # Per-caller counters: {caller: count}
    calls_by_caller: dict = field(default_factory=lambda: defaultdict(int))

    # Latency tracking
    total_completion_latency_ms: float = 0.0
    total_embedding_latency_ms: float = 0.0

    # Token tracking
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Recent calls (ring buffer, last 50)
    recent: list = field(default_factory=list)
    max_recent: int = 50

    def to_dict(self) -> dict:
        with self.lock:
            avg_comp = (
                self.total_completion_latency_ms / self.total_completions
                if self.total_completions > 0
                else 0
            )
            avg_embed = (
                self.total_embedding_latency_ms / self.total_embeddings
                if self.total_embeddings > 0
                else 0
            )
            return {
                "total_completions": self.total_completions,
                "total_embeddings": self.total_embeddings,
                "total_errors": self.total_errors,
                "completions_by_model": dict(self.completions_by_model),
                "embeddings_by_model": dict(self.embeddings_by_model),
                "completions_by_purpose": dict(self.completions_by_purpose),
                "calls_by_caller": dict(self.calls_by_caller),
                "avg_completion_latency_ms": round(avg_comp, 1),
                "avg_embedding_latency_ms": round(avg_embed, 1),
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "recent_calls": [
                    {
                        "type": r.call_type,
                        "model": r.model,
                        "purpose": r.purpose,
                        "caller": r.caller,
                        "latency_ms": round(r.latency_ms, 1),
                        "success": r.success,
                        "timestamp": r.timestamp,
                    }
                    for r in self.recent
                ],
            }


# Singleton
_stats = _Stats()


def _infer_caller() -> str:
    """Walk the call stack to find the first caller outside shared.ai."""
    import inspect

    for frame_info in inspect.stack():
        module = frame_info.frame.f_globals.get("__name__", "")
        if module and not module.startswith("shared.ai"):
            filename = frame_info.filename.rsplit("/", 1)[-1]
            return f"{filename}:{frame_info.lineno}"
    return "unknown"


def record_completion(
    model: str,
    purpose: Optional[str],
    latency_ms: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """Record a completion call."""
    caller = _infer_caller()

    logger.info(
        "AI complete: model=%s purpose=%s caller=%s latency=%.0fms tokens=%d→%d %s",
        model,
        purpose or "-",
        caller,
        latency_ms,
        input_tokens,
        output_tokens,
        "OK" if success else f"FAIL: {error}",
    )

    record = CallRecord(
        timestamp=time.time(),
        call_type="completion",
        model=model,
        purpose=purpose,
        caller=caller,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        text_count=0,
        success=success,
        error=error,
    )

    with _stats.lock:
        _stats.total_completions += 1
        _stats.completions_by_model[model] += 1
        _stats.completions_by_purpose[purpose or "default"] += 1
        _stats.calls_by_caller[caller] += 1
        _stats.total_completion_latency_ms += latency_ms
        _stats.total_input_tokens += input_tokens
        _stats.total_output_tokens += output_tokens
        if not success:
            _stats.total_errors += 1
        _stats.recent.append(record)
        if len(_stats.recent) > _stats.max_recent:
            _stats.recent.pop(0)


def record_embedding(
    model: str,
    text_count: int,
    latency_ms: float,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """Record an embedding call."""
    caller = _infer_caller()

    logger.info(
        "AI embed: model=%s texts=%d caller=%s latency=%.0fms %s",
        model,
        text_count,
        caller,
        latency_ms,
        "OK" if success else f"FAIL: {error}",
    )

    record = CallRecord(
        timestamp=time.time(),
        call_type="embedding",
        model=model,
        purpose=None,
        caller=caller,
        latency_ms=latency_ms,
        input_tokens=0,
        output_tokens=0,
        text_count=text_count,
        success=success,
        error=error,
    )

    with _stats.lock:
        _stats.total_embeddings += 1
        _stats.embeddings_by_model[model] += 1
        _stats.calls_by_caller[caller] += 1
        _stats.total_embedding_latency_ms += latency_ms
        if not success:
            _stats.total_errors += 1
        _stats.recent.append(record)
        if len(_stats.recent) > _stats.max_recent:
            _stats.recent.pop(0)


def get_stats() -> dict:
    """Return current aggregate stats as a dict."""
    return _stats.to_dict()


def reset_stats() -> None:
    """Reset all counters (for testing)."""
    global _stats
    _stats = _Stats()
