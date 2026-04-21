"""Per-namespace storage layout & lifecycle (EPIC-002).

Each namespace is a self-contained directory under ``KNOWLEDGE_DIR``::

    {KNOWLEDGE_DIR}/{namespace}/
        graph.db          # Kuzu single-file DB (created lazily by the indexer)
        chroma/           # ChromaDB persistent dir (created lazily by the indexer)
        manifest.json     # NamespaceMeta (this module owns it)
        jobs/             # JobManager event logs (created in EPIC-003)

Manifest writes are atomic: a temp file is written then ``os.replace``'d into
position. Crashes mid-write leave the previous manifest intact.

Manifest schema (NamespaceMeta serialized as JSON, ``schema_version=1``)::

    {
        "schema_version": 1,
        "name": "my-corpus",
        "created_at": "2026-04-19T12:34:56+00:00",
        "updated_at": "2026-04-19T12:34:56+00:00",
        "language": "English",
        "description": "...",
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "embedding_dimension": 384,
        "stats": {
            "files_indexed": 0,
            "chunks": 0,
            "entities": 0,
            "relations": 0,
            "vectors": 0,
            "bytes_on_disk": 0
        },
        "imports": []
    }

Heavy deps (``kuzu``) are imported lazily inside ``delete()`` only when needed
to drop a cached DB handle, so importing this module is cheap.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from dashboard.knowledge.config import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    KNOWLEDGE_DIR,
)

logger = logging.getLogger(__name__)

# ADR-12: filesystem-safe, URL-safe, Kuzu-table-safe namespace IDs.
NAMESPACE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

# Bounded import history — prevents the manifest from growing without limit
# when a namespace is re-indexed many times. EPIC-007 may make this configurable.
MAX_IMPORTS_PER_MANIFEST = 100


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class NamespaceError(Exception):
    """Base class for namespace-management errors."""


class NamespaceNotFoundError(NamespaceError):
    """Raised when an operation targets a namespace that doesn't exist."""


class NamespaceExistsError(NamespaceError):
    """Raised when ``create()`` is called for an already-existing namespace."""


class InvalidNamespaceIdError(NamespaceError, ValueError):
    """Raised when a namespace identifier doesn't match the ADR-12 regex."""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class NamespaceStats(BaseModel):
    """Aggregate counters for a namespace's content.

    All counters default to 0 and are updated by the ingestor / query layer.
    ``bytes_on_disk`` is computed lazily (e.g. by ``Ingestor`` after a run).
    """

    files_indexed: int = 0
    chunks: int = 0
    entities: int = 0
    relations: int = 0
    vectors: int = 0
    bytes_on_disk: int = 0


class ImportRecord(BaseModel):
    """A single import event appended to the manifest's ``imports`` list."""

    folder_path: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str  # "running" | "completed" | "failed" | "interrupted"
    file_count: int = 0
    error_count: int = 0
    job_id: Optional[str] = None


class NamespaceMeta(BaseModel):
    """Manifest metadata for a single namespace."""

    schema_version: int = 1
    name: str
    created_at: datetime
    updated_at: datetime
    language: str = "English"
    description: Optional[str] = None
    # Frozen at create time; changing models post-creation would corrupt the
    # vector index — so we record what was used.
    embedding_model: str = EMBEDDING_MODEL
    embedding_dimension: int = EMBEDDING_DIMENSION
    stats: NamespaceStats = Field(default_factory=NamespaceStats)
    imports: list[ImportRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# NamespaceManager
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Return current UTC time as a tz-aware datetime."""
    return datetime.now(timezone.utc)


class NamespaceManager:
    """Lifecycle manager for knowledge namespaces.

    Thread-safe: ``create``, ``delete`` and ``update_stats`` / ``append_import``
    take an internal ``threading.Lock``. Read-only ``get`` / ``list`` operations
    do not lock (they may briefly observe a half-written ``imports[]`` if
    interleaved with an append, but the manifest itself is never partially
    written thanks to the temp-file + ``os.replace`` pattern).

    Construction is cheap — no I/O beyond ``mkdir(parents=True, exist_ok=True)``
    on the base directory.
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base = Path(base_dir) if base_dir is not None else KNOWLEDGE_DIR
        self._base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # ---- ID validation ---------------------------------------------------

    @staticmethod
    def validate_id(namespace: Any) -> bool:
        """Return True iff ``namespace`` matches the ADR-12 regex."""
        if not isinstance(namespace, str):
            return False
        return NAMESPACE_ID_RE.match(namespace) is not None

    @classmethod
    def _require_valid_id(cls, namespace: Any) -> None:
        if not cls.validate_id(namespace):
            raise InvalidNamespaceIdError(
                f"Invalid namespace id {namespace!r}: must match {NAMESPACE_ID_RE.pattern}"
            )

    # ---- Path helpers ----------------------------------------------------
    #
    # Public instance methods that respect ``self._base`` — these are the
    # canonical way for the rest of the package (``ingestion.py``,
    # ``service.py`` and EPIC-004 query code) to compute per-namespace paths.
    # The module-level helpers in ``config.py`` are deprecated and only safe
    # for the default ``KNOWLEDGE_DIR`` case (see QA report Defect 1).

    def path_for(self, namespace: str) -> Path:
        """Return the on-disk directory for a namespace (may not exist).

        Identical to :meth:`namespace_dir`; kept for back-compat.
        """
        return self._base / namespace

    def namespace_dir(self, namespace: str) -> Path:
        """Return ``base_dir / namespace`` — the namespace's root directory."""
        return self._base / namespace

    def manifest_path(self, namespace: str) -> Path:
        """Return ``base_dir / namespace / manifest.json``."""
        return self.namespace_dir(namespace) / "manifest.json"

    def kuzu_db_path(self, namespace: str) -> Path:
        """Return ``base_dir / namespace / graph.db`` — the Kuzu single-file DB."""
        return self.namespace_dir(namespace) / "graph.db"

    def vector_dir(self, namespace: str) -> Path:
        """Return ``base_dir / namespace / vectors`` — the zvec collection directory."""
        return self.namespace_dir(namespace) / "vectors"

    # Internal aliases preserved for back-compat with the EPIC-002 codebase.
    def _manifest_path_for(self, namespace: str) -> Path:
        return self.manifest_path(namespace)

    def _kuzu_db_path_for(self, namespace: str) -> Path:
        return self.kuzu_db_path(namespace)

    def _vector_dir_for(self, namespace: str) -> Path:
        return self.vector_dir(namespace)

    # ---- CRUD ------------------------------------------------------------

    def create(
        self,
        namespace: str,
        language: str = "English",
        description: Optional[str] = None,
    ) -> NamespaceMeta:
        """Create a fresh namespace. Raises if it already exists.

        - Validates the namespace id (ADR-12).
        - Creates ``{base}/{namespace}/`` (makedirs).
        - Writes ``manifest.json`` atomically.
        - Does NOT eagerly create ``graph.db`` or ``chroma/`` — those come up
          lazily on first ingestion.
        """
        self._require_valid_id(namespace)
        with self._lock:
            ns_path = self.path_for(namespace)
            if ns_path.exists():
                raise NamespaceExistsError(f"Namespace {namespace!r} already exists")
            ns_path.mkdir(parents=True, exist_ok=False)
            now = _utcnow()
            meta = NamespaceMeta(
                name=namespace,
                created_at=now,
                updated_at=now,
                language=language,
                description=description,
            )
            self.write_manifest(namespace, meta)
            logger.info("Created namespace %r at %s", namespace, ns_path)
            return meta

    def get(self, namespace: str) -> Optional[NamespaceMeta]:
        """Return the manifest for a namespace, or None if it doesn't exist."""
        if not self.validate_id(namespace):
            return None
        return self._read_manifest(namespace)

    def list(self) -> list[NamespaceMeta]:
        """Return manifests for every namespace under ``base_dir``.

        Sub-directories without a readable ``manifest.json`` (e.g. partially
        deleted, or unrelated dirs) are skipped with a warning.
        """
        out: list[NamespaceMeta] = []
        if not self._base.exists():
            return out
        for child in sorted(self._base.iterdir()):
            if not child.is_dir():
                continue
            if not self.validate_id(child.name):
                # Unrelated dir (e.g. user dropped something in KNOWLEDGE_DIR).
                continue
            meta = self._read_manifest(child.name)
            if meta is not None:
                out.append(meta)
            else:
                logger.warning(
                    "Skipping %s: directory exists but manifest.json is missing/unreadable",
                    child,
                )
        return out

    def delete(self, namespace: str) -> bool:
        """Delete a namespace's directory and drop any cached Kuzu handle.

        Returns True if the namespace existed and was removed, False otherwise.
        Idempotent: deleting a missing namespace is not an error.

        IMPORTANT: this also evicts the per-DB entry from
        ``KuzuLabelledPropertyGraph.kuzu_database_cache`` so an immediate
        re-create of the same namespace doesn't reuse a stale file handle on
        the now-deleted ``graph.db``.
        """
        if not self.validate_id(namespace):
            # Caller asked to delete an obviously-invalid name → not an error.
            return False
        with self._lock:
            ns_path = self.path_for(namespace)
            if not ns_path.exists():
                return False

            # Drop any cached Kuzu handle BEFORE rmtree so the file is closed.
            self._evict_kuzu_cache_inst(namespace)

            try:
                shutil.rmtree(ns_path)
            except OSError as exc:
                logger.error("Failed to remove %s: %s", ns_path, exc)
                raise

            logger.info("Deleted namespace %r (%s)", namespace, ns_path)
            return True

    def _evict_kuzu_cache_inst(self, namespace: str) -> None:
        """Best-effort: pop the namespace's DB path out of the Kuzu cache.

        Imported lazily so this module stays free of ``kuzu``-related deps at
        import time. Uses :meth:`kuzu_db_path` on ``self`` so ``base_dir``
        overrides are honoured.
        """
        try:
            from dashboard.knowledge.graph.index.kuzudb import (  # noqa: WPS433
                KuzuLabelledPropertyGraph,
            )
        except Exception as exc:  # pragma: no cover — only if import broke
            logger.warning("Could not import KuzuLabelledPropertyGraph for cache eviction: %s", exc)
            return

        try:
            db_path = str(self.kuzu_db_path(namespace).resolve())
        except Exception as exc:  # pragma: no cover — should not happen
            logger.warning("Could not resolve Kuzu db path for %r: %s", namespace, exc)
            return

        cache = getattr(KuzuLabelledPropertyGraph, "kuzu_database_cache", None)
        if not isinstance(cache, dict):
            return
        # Pop both the resolved path and any matching unresolved variant —
        # the cache key is the resolved path, but be defensive.
        cache.pop(db_path, None)

    # Module-level back-compat shim. EPIC-002 callers (if any) used the
    # static method name; keep it but route through the instance method on
    # a temp manager rooted at the default KNOWLEDGE_DIR.
    @staticmethod
    def _evict_kuzu_cache(namespace: str) -> None:
        """Deprecated; only safe when no custom base_dir is in use.

        See :meth:`_evict_kuzu_cache_inst` for the corrected version.
        """
        NamespaceManager()._evict_kuzu_cache_inst(namespace)

    # ---- Stats / imports -------------------------------------------------

    def update_stats(self, namespace: str, **stats_delta: int) -> NamespaceMeta:
        """Apply integer deltas to the namespace's ``stats`` block.

        Example::

            nm.update_stats("docs", chunks=42, entities=10)

        Held under the manager lock so concurrent ingestion threads can't lose
        increments. Read-modify-write — slow but correct.
        """
        self._require_valid_id(namespace)
        with self._lock:
            meta = self._read_manifest(namespace)
            if meta is None:
                raise NamespaceNotFoundError(namespace)
            stats = meta.stats.model_dump()
            for key, delta in stats_delta.items():
                if key not in stats:
                    raise ValueError(f"Unknown stats field: {key!r}")
                stats[key] = stats[key] + int(delta)
            meta.stats = NamespaceStats(**stats)
            meta.updated_at = _utcnow()
            self.write_manifest(namespace, meta)
            return meta

    def append_import(self, namespace: str, record: ImportRecord) -> NamespaceMeta:
        """Append an :class:`ImportRecord` to the manifest, capped at ``MAX_IMPORTS_PER_MANIFEST``."""
        self._require_valid_id(namespace)
        with self._lock:
            meta = self._read_manifest(namespace)
            if meta is None:
                raise NamespaceNotFoundError(namespace)
            meta.imports.append(record)
            # Trim oldest entries if we exceed the cap.
            if len(meta.imports) > MAX_IMPORTS_PER_MANIFEST:
                drop = len(meta.imports) - MAX_IMPORTS_PER_MANIFEST
                meta.imports = meta.imports[drop:]
            meta.updated_at = _utcnow()
            self.write_manifest(namespace, meta)
            return meta

    # ---- Manifest I/O ----------------------------------------------------

    def write_manifest(self, namespace: str, meta: NamespaceMeta) -> None:
        """Atomically write the manifest for ``namespace``.

        Strategy: write to a sibling ``.manifest.<rand>.tmp`` file, fsync via
        ``os.replace`` (atomic on POSIX and on modern Windows). On any error
        the temp file is unlinked.
        """
        target = self._manifest_path_for(namespace)
        target.parent.mkdir(parents=True, exist_ok=True)
        # tempfile in the SAME directory so os.replace stays on one filesystem.
        fd, tmp_path = tempfile.mkstemp(
            prefix=".manifest.",
            suffix=".tmp",
            dir=str(target.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                # mode="json" makes Pydantic emit ISO strings for datetime,
                # plus stringify any other non-JSON-native types.
                json.dump(meta.model_dump(mode="json"), fh, indent=2, default=str)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, target)
        except Exception:
            # Clean up the temp file; never leave dotfiles behind.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _read_manifest(self, namespace: str) -> Optional[NamespaceMeta]:
        """Read & validate the manifest for ``namespace``.

        Returns None if the directory doesn't exist, the manifest is missing,
        or the JSON is unreadable / invalid. Logs a warning on parse failure
        so corruption isn't silently masked as "namespace doesn't exist".
        """
        path = self._manifest_path_for(namespace)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read manifest for %r at %s: %s", namespace, path, exc)
            return None
        try:
            return NamespaceMeta.model_validate(raw)
        except Exception as exc:  # pydantic.ValidationError, etc.
            logger.warning("Manifest at %s failed validation: %s", path, exc)
            return None


__all__ = [
    "NAMESPACE_ID_RE",
    "MAX_IMPORTS_PER_MANIFEST",
    "ImportRecord",
    "InvalidNamespaceIdError",
    "NamespaceError",
    "NamespaceExistsError",
    "NamespaceManager",
    "NamespaceMeta",
    "NamespaceNotFoundError",
    "NamespaceStats",
]
