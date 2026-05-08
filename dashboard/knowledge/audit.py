"""Audit logging for knowledge operations (EPIC-003).

Provides structured, append-only audit logging with automatic rotation.
Disabled by ``OSTWIN_KNOWLEDGE_AUDIT=0``; reads can be included via
``OSTWIN_KNOWLEDGE_AUDIT_READS=1``.

The audit log is a newline-delimited JSON (JSONL) file:
    ~/.ostwin/knowledge/_audit.jsonl

Each line is a JSON object with the following schema:
    {
        "timestamp": "2026-04-19T12:34:56.789Z",
        "actor": "user@example.com" | "anonymous",
        "namespace": "my-namespace",
        "op": "create_namespace" | "delete_namespace" | "import" | ...,
        "args": {...},  // operation-specific arguments (sanitized)
        "result_status": "success" | "error",
        "latency_ms": 123.45
    }

Rotation: when the file exceeds 10 MB, it's gzipped to ``_audit.jsonl.1.gz``
(and older files are shifted up to ``.2.gz``, ..., ``.5.gz``; max 5 generations).
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Configuration via environment
AUDIT_ENABLED: bool = os.environ.get("OSTWIN_KNOWLEDGE_AUDIT", "1") == "1"
AUDIT_READS: bool = os.environ.get("OSTWIN_KNOWLEDGE_AUDIT_READS", "0") == "1"
MAX_NAMESPACES: int = int(os.environ.get("OSTWIN_KNOWLEDGE_MAX_NAMESPACES", "100"))
LLM_TIMEOUT: float = float(os.environ.get("OSTWIN_KNOWLEDGE_LLM_TIMEOUT", "60.0"))

# Audit log location
AUDIT_DIR: Path = Path.home() / ".ostwin" / "knowledge"
AUDIT_FILE: Path = AUDIT_DIR / "_audit.jsonl"
MAX_LOG_SIZE: int = 10 * 1024 * 1024  # 10 MB
MAX_GENERATIONS: int = 5

# Lock for thread-safe writes
_audit_lock = threading.Lock()

# Track active imports per namespace
_active_imports: dict[str, str] = {}  # namespace -> job_id
_active_imports_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ImportInProgressError(Exception):
    """Raised when an import is already in progress for a namespace."""

    def __init__(self, namespace: str, job_id: Optional[str] = None) -> None:
        self.namespace = namespace
        self.job_id = job_id
        msg = f"Import already in progress for namespace {namespace!r}"
        if job_id:
            msg += f" (job_id={job_id})"
        super().__init__(msg)


class MaxNamespacesReachedError(Exception):
    """Raised when the maximum number of namespaces has been reached."""

    def __init__(self, max_count: int = MAX_NAMESPACES) -> None:
        self.max_count = max_count
        super().__init__(f"Maximum number of namespaces ({max_count}) reached")


# ---------------------------------------------------------------------------
# Import tracking
# ---------------------------------------------------------------------------


def register_import(namespace: str, job_id: str) -> None:
    """Register an import as in-progress. Raises ImportInProgressError if one exists."""
    with _active_imports_lock:
        existing = _active_imports.get(namespace)
        if existing is not None:
            raise ImportInProgressError(namespace, existing)
        _active_imports[namespace] = job_id


def unregister_import(namespace: str) -> None:
    """Remove an in-progress import registration."""
    with _active_imports_lock:
        _active_imports.pop(namespace, None)


def is_import_in_progress(namespace: str) -> Optional[str]:
    """Return job_id if an import is in progress for namespace, else None."""
    with _active_imports_lock:
        return _active_imports.get(namespace)


# ---------------------------------------------------------------------------
# Structured call logging
# ---------------------------------------------------------------------------


def _log_call(
    namespace: str,
    op: str,
    result: str,
    latency_ms: float,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Emit a structured log line for a REST/MCP call.

    This is the centralized logging helper used by both REST routes
    and MCP tool wrappers. Logs at INFO level with a consistent format.
    Also writes an audit log entry to the JSONL file.

    Args:
        namespace: The namespace being operated on
        op: Operation name (e.g., "create_namespace", "import", "query")
        result: "success" or "error"
        latency_ms: Duration of the operation in milliseconds
        extra: Additional context (e.g., error message, query text, actor)
    """
    parts = [f"namespace={namespace}", f"op={op}", f"latency_ms={latency_ms:.2f}", f"result={result}"]
    if extra:
        for key, value in extra.items():
            # Sanitize: truncate long values, redact sensitive keys
            if key in ("api_key", "token", "password", "secret"):
                value = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 200:
                value = value[:200] + "..."
            parts.append(f"{key}={value}")
    logger.info(" ".join(parts))

    # Write audit log entry (EPIC-003 wiring fix)
    # Extract actor from extra, defaulting to "anonymous"
    actor = (extra or {}).get("actor", "anonymous")
    audit_event(
        actor=actor,
        namespace=namespace,
        op=op,
        args=extra or {},
        result_status=result,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


def _rotate_audit_log() -> None:
    """Rotate the audit log if it exceeds MAX_LOG_SIZE.

    Rotation strategy:
    1. Compress current file to _audit.jsonl.1.gz
    2. Shift existing .N.gz files up (.1.gz -> .2.gz, etc.)
    3. Delete files beyond MAX_GENERATIONS
    """
    if not AUDIT_FILE.exists():
        return

    if AUDIT_FILE.stat().st_size < MAX_LOG_SIZE:
        return

    try:
        # Shift existing compressed files
        for gen in range(MAX_GENERATIONS - 1, 0, -1):
            old_path = AUDIT_DIR / f"_audit.jsonl.{gen}.gz"
            new_path = AUDIT_DIR / f"_audit.jsonl.{gen + 1}.gz"
            if old_path.exists():
                if new_path.exists():
                    new_path.unlink()
                shutil.move(str(old_path), str(new_path))

        # Compress current file to .1.gz
        target_gz = AUDIT_DIR / "_audit.jsonl.1.gz"
        with open(AUDIT_FILE, "rb") as f_in:
            with gzip.open(target_gz, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Truncate the current file (or remove and recreate)
        AUDIT_FILE.unlink()
        logger.info("Rotated audit log to %s", target_gz)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to rotate audit log: %s", exc)


def audit_event(
    actor: str,
    namespace: str,
    op: str,
    args: dict[str, Any],
    result_status: str,
    latency_ms: float,
) -> None:
    """Write an audit log entry for a mutating operation.

    Args:
        actor: The user/agent performing the operation (email, username, or "anonymous")
        namespace: The namespace being operated on
        op: Operation name (create_namespace, delete_namespace, import, etc.)
        args: Operation arguments (will be sanitized)
        result_status: "success" or "error"
        latency_ms: Duration of the operation in milliseconds

    This function is a no-op if ``OSTWIN_KNOWLEDGE_AUDIT=0``.
    Read-only operations (query) are not logged unless
    ``OSTWIN_KNOWLEDGE_AUDIT_READS=1``.
    """
    if not AUDIT_ENABLED:
        return

    # Skip read operations unless explicitly enabled
    read_ops = {"query", "list_namespaces", "get_namespace", "list_jobs", "get_job"}
    if op in read_ops and not AUDIT_READS:
        return

    # Sanitize args (remove sensitive values, truncate)
    sanitized_args: dict[str, Any] = {}
    for key, value in args.items():
        if key in ("api_key", "token", "password", "secret", "authorization"):
            continue  # Skip entirely
        if isinstance(value, str) and len(value) > 500:
            value = value[:500] + "..."
        sanitized_args[key] = value

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor or "anonymous",
        "namespace": namespace,
        "op": op,
        "args": sanitized_args,
        "result_status": result_status,
        "latency_ms": round(latency_ms, 2),
    }

    with _audit_lock:
        try:
            # Ensure directory exists
            AUDIT_DIR.mkdir(parents=True, exist_ok=True)

            # Check rotation before writing
            _rotate_audit_log()

            # Append to log
            with open(AUDIT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")

        except Exception as exc:  # noqa: BLE001
            # Never crash the caller due to audit logging failure
            logger.warning("Failed to write audit log: %s", exc)


def get_audit_log_path() -> Path:
    """Return the path to the audit log file."""
    return AUDIT_FILE


def count_namespaces(base_dir: Path) -> int:
    """Count the number of existing namespaces under base_dir.

    Used by create_namespace to enforce the OSTWIN_KNOWLEDGE_MAX_NAMESPACES limit.
    """
    if not base_dir.exists():
        return 0
    count = 0
    for child in base_dir.iterdir():
        if child.is_dir() and (child / "manifest.json").exists():
            count += 1
    return count


# ---------------------------------------------------------------------------
# Context manager for timing operations
# ---------------------------------------------------------------------------


class AuditContext:
    """Context manager that records timing and writes audit log on exit.

    Usage:
        with AuditContext("user@example.com", "my-ns", "import", {"folder": "/data"}) as ctx:
            # ... do work ...
            ctx.result_status = "success"
    """

    def __init__(
        self,
        actor: str,
        namespace: str,
        op: str,
        args: Optional[dict[str, Any]] = None,
    ) -> None:
        self.actor = actor
        self.namespace = namespace
        self.op = op
        self.args = args or {}
        self.result_status = "error"  # Default to error; set to "success" on success
        self._start_time = time.perf_counter()

    def __enter__(self) -> "AuditContext":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        latency_ms = (time.perf_counter() - self._start_time) * 1000
        if exc_type is not None:
            self.result_status = "error"
            self.args["error"] = str(exc_val)
        audit_event(
            actor=self.actor,
            namespace=self.namespace,
            op=self.op,
            args=self.args,
            result_status=self.result_status,
            latency_ms=latency_ms,
        )


__all__ = [
    "AUDIT_ENABLED",
    "AUDIT_READS",
    "MAX_NAMESPACES",
    "LLM_TIMEOUT",
    "ImportInProgressError",
    "MaxNamespacesReachedError",
    "register_import",
    "unregister_import",
    "is_import_in_progress",
    "_log_call",
    "audit_event",
    "get_audit_log_path",
    "count_namespaces",
    "AuditContext",
]
