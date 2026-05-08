"""Background-job manager for the knowledge package (EPIC-003).

A ``JobManager`` runs jobs on a small ``ThreadPoolExecutor`` and persists every
status transition to ``{base_dir}/{namespace}/jobs/{job_id}.jsonl`` (one event
per line). On startup the manager scans for jobs whose last event was
``RUNNING`` and appends a final ``INTERRUPTED`` event — that's the dashboard
restart story (ADR-08).

Jobs are submitted via :meth:`JobManager.submit`, which returns a ``job_id``
synchronously after writing a ``PENDING`` event. The supplied callable
``fn(emit) -> dict`` runs in the worker thread; it receives a single ``emit``
callback for progress updates and returns a result dict on success.

This module imports nothing heavy — Pydantic + stdlib only. Safe to
``from dashboard.knowledge.jobs import JobManager`` at any point.
"""

from __future__ import annotations

import json
import logging
import threading
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models / enums
# ---------------------------------------------------------------------------


class JobState(str, Enum):
    """Lifecycle states for a job. Persisted to jsonl as the string value."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


# A job is "terminal" when no further work will happen on it.
TERMINAL_STATES: frozenset[JobState] = frozenset(
    {JobState.COMPLETED, JobState.FAILED, JobState.INTERRUPTED, JobState.CANCELLED}
)


class JobEvent(BaseModel):
    """One line in ``jobs/{job_id}.jsonl``.

    ``detail`` is an open-ended dict — callers can stash per-file status,
    counter snapshots, etc. The ``message`` field is a human-readable summary.
    """

    timestamp: datetime
    state: JobState
    message: str = ""
    progress_current: int = 0
    progress_total: int = 0
    detail: dict = Field(default_factory=dict)


class JobStatus(BaseModel):
    """Aggregate view of a single job, reconstructable from its event log.

    ``result`` is populated on COMPLETED state with the dict returned by ``fn``.
    ``errors`` is a free-form list of strings the worker can append to.
    """

    job_id: str
    namespace: str
    operation: str  # e.g. "import_folder"
    state: JobState
    submitted_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    progress_current: int = 0
    progress_total: int = 0
    message: str = ""
    errors: list[str] = Field(default_factory=list)
    result: Optional[dict] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_to_dt(s: Any) -> Optional[datetime]:
    """Best-effort ISO-8601 → datetime; returns None on garbage."""
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# JobManager
# ---------------------------------------------------------------------------


class JobManager:
    """In-process job tracker with on-disk persistence per namespace.

    Construction is cheap — only filesystem scanning happens (and only for
    ``running`` jobs that need ``interrupted`` recovery).

    Thread-safety: an internal ``RLock`` protects the in-memory dicts and the
    per-job append-event sequence. The disk format (jsonl, append-only) is
    tolerant of concurrent appends from a single process.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        max_workers: int = 2,
        completed_job_ttl: int = 3600,
    ) -> None:
        # Lazy import: keep this module import-cheap. config has no heavy deps,
        # but importing it inside __init__ avoids a static dependency loop with
        # the rest of the package.
        if base_dir is None:
            from dashboard.knowledge.config import KNOWLEDGE_DIR  # noqa: WPS433

            base_dir = KNOWLEDGE_DIR
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._exec = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="kb-job"
        )
        self._jobs: dict[str, JobStatus] = {}
        self._futures: dict[str, Future] = {}
        # cancel flags polled by long-running fns
        self._cancel_flags: dict[str, threading.Event] = {}
        self._lock = threading.RLock()
        self._completed_job_ttl = completed_job_ttl
        # Recovery: scan running jobs and mark interrupted (ADR-08).
        self._recover_interrupted()

    # ---- Path helpers --------------------------------------------------

    def _ns_dir(self, namespace: str) -> Path:
        return self._base / namespace

    def _jobs_dir(self, namespace: str) -> Path:
        return self._ns_dir(namespace) / "jobs"

    def _job_log_path(self, namespace: str, job_id: str) -> Path:
        return self._jobs_dir(namespace) / f"{job_id}.jsonl"

    # ---- Disk I/O ------------------------------------------------------

    def _append_event(self, namespace: str, job_id: str, event: JobEvent) -> None:
        """Append one JobEvent line to the namespace's per-job log file."""
        path = self._job_log_path(namespace, job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        # mode="json" so datetimes serialize as ISO strings.
        line = event.model_dump_json()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _load_events(self, path: Path) -> list[JobEvent]:
        """Read & parse a job log; tolerates partial / blank lines."""
        events: list[JobEvent] = []
        if not path.exists():
            return events
        try:
            with path.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        events.append(JobEvent.model_validate_json(raw))
                    except Exception as exc:  # pydantic.ValidationError, etc.
                        logger.debug("Skipping malformed job event line in %s: %s", path, exc)
        except OSError as exc:
            logger.warning("Could not read job log %s: %s", path, exc)
        return events

    def _load_status_from_log(
        self, namespace: str, job_id: str, *, operation_hint: str = ""
    ) -> Optional[JobStatus]:
        """Replay events from the on-disk log to reconstruct latest status.

        Returns None if the log doesn't exist or contains no events.
        """
        path = self._job_log_path(namespace, job_id)
        events = self._load_events(path)
        if not events:
            return None

        first = events[0]
        last = events[-1]
        operation = operation_hint
        submitted_at = first.timestamp
        started_at: Optional[datetime] = None
        finished_at: Optional[datetime] = None
        result: Optional[dict] = None
        errors: list[str] = []

        for ev in events:
            # Operation lives in the first PENDING event's detail.
            if not operation and ev.state == JobState.PENDING:
                op = ev.detail.get("operation") if isinstance(ev.detail, dict) else None
                if isinstance(op, str):
                    operation = op
            if ev.state == JobState.RUNNING and started_at is None:
                started_at = ev.timestamp
            if ev.state in TERMINAL_STATES:
                finished_at = ev.timestamp
            # Result + errors live in the terminal event's detail.
            if isinstance(ev.detail, dict):
                if ev.state == JobState.COMPLETED:
                    res = ev.detail.get("result")
                    if isinstance(res, dict):
                        result = res
                if "errors" in ev.detail and isinstance(ev.detail["errors"], list):
                    errors = [str(e) for e in ev.detail["errors"]]

        return JobStatus(
            job_id=job_id,
            namespace=namespace,
            operation=operation or "unknown",
            state=last.state,
            submitted_at=submitted_at,
            started_at=started_at,
            finished_at=finished_at,
            progress_current=last.progress_current,
            progress_total=last.progress_total,
            message=last.message,
            errors=errors,
            result=result,
        )

    # ---- Recovery ------------------------------------------------------

    def _recover_interrupted(self) -> None:
        """Scan all known job logs; any whose last event is RUNNING is marked INTERRUPTED.

        Best-effort: failures here don't block JobManager construction.
        """
        if not self._base.exists():
            return
        for ns_dir in self._base.iterdir():
            if not ns_dir.is_dir():
                continue
            jobs_dir = ns_dir / "jobs"
            if not jobs_dir.is_dir():
                continue
            for log in jobs_dir.glob("*.jsonl"):
                events = self._load_events(log)
                if not events:
                    continue
                last = events[-1]
                if last.state != JobState.RUNNING:
                    continue
                # Append a final INTERRUPTED event.
                interrupted = JobEvent(
                    timestamp=_utcnow(),
                    state=JobState.INTERRUPTED,
                    message="Process restart detected; job marked interrupted",
                    progress_current=last.progress_current,
                    progress_total=last.progress_total,
                    detail={
                        "errors": [
                            "Job was running when the process exited; recovered as interrupted."
                        ]
                    },
                )
                try:
                    with log.open("a", encoding="utf-8") as fh:
                        fh.write(interrupted.model_dump_json() + "\n")
                    logger.info(
                        "Marked previously-running job %s in namespace %s as interrupted",
                        log.stem,
                        ns_dir.name,
                    )
                except OSError as exc:
                    logger.warning("Could not append interrupted event to %s: %s", log, exc)

    # ---- Public API ----------------------------------------------------

    def submit(
        self,
        namespace: str,
        operation: str,
        fn: Callable[[Callable[[JobEvent], None]], dict],
        message: str = "",
    ) -> str:
        """Submit a background job and return its ``job_id``.

        ``fn`` will be called with a single ``emit(event: JobEvent)`` callback
        and must return a dict on success (stored as the job's ``result``).
        Exceptions raised inside ``fn`` are caught, the job is marked FAILED
        and the traceback recorded in ``errors``.

        Returns the ``job_id`` immediately — DOES NOT wait for ``fn`` to start.
        """
        # Evict stale completed jobs to prevent unbounded memory growth
        self._evict_completed()

        job_id = uuid.uuid4().hex
        now = _utcnow()
        status = JobStatus(
            job_id=job_id,
            namespace=namespace,
            operation=operation,
            state=JobState.PENDING,
            submitted_at=now,
            message=message,
        )

        with self._lock:
            self._jobs[job_id] = status
            self._cancel_flags[job_id] = threading.Event()

        # Persist the PENDING event immediately so a crash before the worker
        # picks it up still leaves a footprint on disk.
        try:
            self._append_event(
                namespace,
                job_id,
                JobEvent(
                    timestamp=now,
                    state=JobState.PENDING,
                    message=message,
                    detail={"operation": operation},
                ),
            )
        except OSError as exc:
            # Filesystem failure isn't fatal — we can still run in-memory.
            logger.error("Could not write PENDING event for job %s: %s", job_id, exc)

        future = self._exec.submit(self._run_job, job_id, fn)
        with self._lock:
            self._futures[job_id] = future

        return job_id

    def get(self, job_id: str) -> Optional[JobStatus]:
        """Return a job's current status, or None if unknown.

        Looks in the in-memory dict first; falls back to replaying the on-disk
        jsonl so jobs survive process restart.
        """
        with self._lock:
            cached = self._jobs.get(job_id)
        if cached is not None:
            return cached
        # Fallback: scan all namespaces' jobs/ dirs for the file.
        if not self._base.exists():
            return None
        for ns_dir in self._base.iterdir():
            if not ns_dir.is_dir():
                continue
            log = ns_dir / "jobs" / f"{job_id}.jsonl"
            if log.exists():
                return self._load_status_from_log(ns_dir.name, job_id)
        return None

    def list_for_namespace(self, namespace: str) -> list[JobStatus]:
        """List all jobs for a namespace, sorted by submitted_at desc.

        Combines in-memory state with on-disk replay so post-restart jobs
        still appear.
        """
        out: dict[str, JobStatus] = {}
        # Disk-resident first.
        jobs_dir = self._jobs_dir(namespace)
        if jobs_dir.is_dir():
            for log in jobs_dir.glob("*.jsonl"):
                status = self._load_status_from_log(namespace, log.stem)
                if status is not None:
                    out[status.job_id] = status
        # In-memory wins (more up-to-date counters).
        with self._lock:
            for job_id, status in self._jobs.items():
                if status.namespace == namespace:
                    out[job_id] = status
        return sorted(out.values(), key=lambda s: s.submitted_at, reverse=True)

    def cancel(self, job_id: str) -> bool:
        """Best-effort cancellation. Sets a flag the running fn should poll.

        Returns True if the job exists and is not already terminal.
        Does NOT hard-kill threads — that's risky and platform-dependent.
        """
        with self._lock:
            status = self._jobs.get(job_id)
            if status is None:
                return False
            if status.state in TERMINAL_STATES:
                return False
            flag = self._cancel_flags.get(job_id)
        if flag is not None:
            flag.set()
        return True

    def is_cancelled(self, job_id: str) -> bool:
        """True iff cancel() has been called for this job (and it's still alive)."""
        with self._lock:
            flag = self._cancel_flags.get(job_id)
        return flag is not None and flag.is_set()

    def shutdown(self, wait: bool = False) -> None:
        """Stop accepting new work; optionally wait for in-flight jobs."""
        self._exec.shutdown(wait=wait)

    def _evict_completed(self) -> int:
        """Evict terminal jobs older than ``_completed_job_ttl`` seconds.

        Prevents unbounded growth of the in-memory ``_jobs`` dict during
        long-running sessions with many knowledge imports.  Disk logs
        are untouched — the ``get()`` fallback can still replay them.

        Returns the number of evicted entries.
        """
        now = _utcnow()
        evicted = 0
        with self._lock:
            expired = [
                jid
                for jid, status in self._jobs.items()
                if status.state in TERMINAL_STATES
                and status.finished_at
                and (now - status.finished_at).total_seconds() > self._completed_job_ttl
            ]
            for jid in expired:
                del self._jobs[jid]
                self._futures.pop(jid, None)
                self._cancel_flags.pop(jid, None)
                evicted += 1
        if evicted:
            logger.debug("Evicted %d completed jobs from in-memory cache", evicted)
        return evicted

    # ---- Worker --------------------------------------------------------

    def _run_job(
        self,
        job_id: str,
        fn: Callable[[Callable[[JobEvent], None]], dict],
    ) -> None:
        """Worker entry point; runs in a ThreadPoolExecutor thread."""
        with self._lock:
            status = self._jobs[job_id]
            namespace = status.namespace

        # Transition: PENDING → RUNNING
        running_event = JobEvent(
            timestamp=_utcnow(),
            state=JobState.RUNNING,
            message=f"Started {status.operation}",
        )
        with self._lock:
            status.state = JobState.RUNNING
            status.started_at = running_event.timestamp
            status.message = running_event.message
        try:
            self._append_event(namespace, job_id, running_event)
        except OSError as exc:
            logger.error("Could not write RUNNING event for job %s: %s", job_id, exc)

        # Build the emit callback — closes over status + dispatches to disk.
        def emit(event: JobEvent) -> None:
            with self._lock:
                status.state = event.state
                status.message = event.message
                status.progress_current = event.progress_current
                status.progress_total = event.progress_total
                if isinstance(event.detail, dict):
                    err = event.detail.get("error")
                    if isinstance(err, str):
                        status.errors.append(err)
            try:
                self._append_event(namespace, job_id, event)
            except OSError as exc:
                logger.error("Could not append job event for %s: %s", job_id, exc)

        # Run the function and capture outcome.
        try:
            result = fn(emit)
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            logger.exception("Job %s (operation=%s) failed", job_id, status.operation)
            done_event = JobEvent(
                timestamp=_utcnow(),
                state=JobState.FAILED,
                message=f"Failed: {exc}",
                progress_current=status.progress_current,
                progress_total=status.progress_total,
                detail={"errors": [*status.errors, str(exc), tb]},
            )
            with self._lock:
                status.state = JobState.FAILED
                status.finished_at = done_event.timestamp
                status.message = done_event.message
                status.errors.append(str(exc))
            try:
                self._append_event(namespace, job_id, done_event)
            except OSError as os_exc:
                logger.error("Could not write FAILED event for job %s: %s", job_id, os_exc)
            return

        # Normal completion: COMPLETED with the result dict.
        if not isinstance(result, dict):
            result = {"result": result}
        done_event = JobEvent(
            timestamp=_utcnow(),
            state=JobState.COMPLETED,
            message=f"Completed {status.operation}",
            progress_current=status.progress_current or status.progress_total,
            progress_total=status.progress_total,
            detail={"result": result, "errors": list(status.errors)},
        )
        with self._lock:
            status.state = JobState.COMPLETED
            status.finished_at = done_event.timestamp
            status.message = done_event.message
            status.result = result
            if status.progress_total and not status.progress_current:
                status.progress_current = status.progress_total
        try:
            self._append_event(namespace, job_id, done_event)
        except OSError as exc:
            logger.error("Could not write COMPLETED event for job %s: %s", job_id, exc)


__all__ = [
    "JobEvent",
    "JobManager",
    "JobState",
    "JobStatus",
    "TERMINAL_STATES",
]
