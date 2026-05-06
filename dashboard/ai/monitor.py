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
    """Walk the call stack to find the first caller outside dashboard.ai."""
    import inspect

    for frame_info in inspect.stack():
        module = frame_info.frame.f_globals.get("__name__", "")
        if module and not module.startswith("dashboard.ai"):
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

    _append_to_file(record)

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

    _append_to_file(record)

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


# ---------------------------------------------------------------------------
# Shared file persistence — all processes append here
# ---------------------------------------------------------------------------

_MONITOR_FILE = os.path.join(
    os.environ.get("OSTWIN_HOME", os.path.join(os.path.expanduser("~"), ".ostwin")),
    "ai_monitor.jsonl",
)
_file_lock = threading.Lock()


def _lock_file(f) -> None:
    """Acquire an exclusive file lock (cross-platform)."""
    try:
        import fcntl
        fcntl.flock(f, fcntl.LOCK_EX)
    except ImportError:
        # Windows fallback
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)


def _unlock_file(f) -> None:
    """Release the file lock (cross-platform)."""
    try:
        import fcntl
        fcntl.flock(f, fcntl.LOCK_UN)
    except ImportError:
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def _append_to_file(record: CallRecord) -> None:
    """Append a record to the shared JSONL file with file locking."""
    try:
        entry = {
            "ts": record.timestamp,
            "type": record.call_type,
            "model": record.model,
            "purpose": record.purpose,
            "caller": record.caller,
            "latency_ms": round(record.latency_ms, 1),
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "text_count": record.text_count,
            "success": record.success,
            "error": record.error,
            "pid": os.getpid(),
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"

        with _file_lock:
            os.makedirs(os.path.dirname(_MONITOR_FILE), exist_ok=True)
            with open(_MONITOR_FILE, "a", encoding="utf-8") as f:
                _lock_file(f)
                f.write(line)
                _unlock_file(f)
    except Exception as exc:
        logger.debug("Failed to append AI monitor record: %s", exc)


def _read_from_file(max_age_seconds: int = 3600) -> list[dict]:
    """Read records from the shared JSONL file, filtered by age."""
    records = []
    cutoff = time.time() - max_age_seconds
    try:
        with open(_MONITOR_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("ts", 0) >= cutoff:
                        records.append(rec)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return records


def get_stats(include_file: bool = True, max_age_seconds: int = 3600) -> dict:
    """Return aggregate stats from in-memory + shared file.

    Args:
        include_file: If True, also reads from the shared JSONL file
            to include stats from other processes (MCP servers, CLI).
        max_age_seconds: Only include file records from the last N seconds.
    """
    if not include_file:
        return _stats.to_dict()

    # Aggregate from file (cross-process)
    records = _read_from_file(max_age_seconds)

    total_completions = 0
    total_embeddings = 0
    total_errors = 0
    completions_by_model: dict = defaultdict(int)
    embeddings_by_model: dict = defaultdict(int)
    completions_by_purpose: dict = defaultdict(int)
    calls_by_caller: dict = defaultdict(int)
    total_completion_latency = 0.0
    total_embedding_latency = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    recent: list = []

    for rec in records:
        call_type = rec.get("type", "")
        model = rec.get("model", "unknown")
        caller = rec.get("caller", "unknown")
        latency = rec.get("latency_ms", 0)
        success = rec.get("success", True)

        if call_type == "completion":
            total_completions += 1
            completions_by_model[model] += 1
            completions_by_purpose[rec.get("purpose") or "default"] += 1
            total_completion_latency += latency
            total_input_tokens += rec.get("input_tokens", 0)
            total_output_tokens += rec.get("output_tokens", 0)
        elif call_type == "embedding":
            total_embeddings += 1
            embeddings_by_model[model] += 1
            total_embedding_latency += latency

        calls_by_caller[caller] += 1
        if not success:
            total_errors += 1

        recent.append(
            {
                "type": call_type,
                "model": model,
                "purpose": rec.get("purpose"),
                "caller": caller,
                "latency_ms": round(latency, 1),
                "success": success,
                "timestamp": rec.get("ts", 0),
            }
        )

    # Keep last 50
    recent = recent[-50:]

    avg_comp = (
        (total_completion_latency / total_completions) if total_completions > 0 else 0
    )
    avg_embed = (
        (total_embedding_latency / total_embeddings) if total_embeddings > 0 else 0
    )

    return {
        "total_completions": total_completions,
        "total_embeddings": total_embeddings,
        "total_errors": total_errors,
        "completions_by_model": dict(completions_by_model),
        "embeddings_by_model": dict(embeddings_by_model),
        "completions_by_purpose": dict(completions_by_purpose),
        "calls_by_caller": dict(calls_by_caller),
        "avg_completion_latency_ms": round(avg_comp, 1),
        "avg_embedding_latency_ms": round(avg_embed, 1),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "recent_calls": recent,
    }


def reset_stats() -> None:
    """Reset in-memory counters and truncate the shared file."""
    global _stats
    _stats = _Stats()
    try:
        with open(_MONITOR_FILE, "w") as f:
            f.truncate(0)
    except Exception as exc:
        logger.debug("Failed to truncate AI monitor file: %s", exc)
