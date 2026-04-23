"""Top-level :class:`KnowledgeService` facade.

EPIC-002: namespace lifecycle is fully wired (delegates to
:class:`NamespaceManager`).
EPIC-003: ``import_folder``, ``get_job``, ``list_jobs`` are wired through a
:class:`JobManager` + :class:`Ingestor`.
EPIC-004: ``query``, ``get_graph`` and a centralized ``_vector_stores`` /
``_kuzu_graphs`` / ``_query_engines`` cache (architect's ZVEC-LIVE-1 fix).
Both the ingestor and the query engine pull their per-namespace handles from
this single service-level cache, so a single zvec collection / Kuzu DB is
shared across ingestion + retrieval (no duplicate handles, no lock contention).
EPIC-003 Hardening: concurrent import protection, namespace quotas, and
audit logging integration.
EPIC-004 Lifecycle: backup/restore, retention sweeper, refresh.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from dashboard.knowledge.namespace import (
    ImportRecord,  # noqa: F401 — re-exported convenience
    InvalidNamespaceIdError,  # noqa: F401
    NamespaceExistsError,  # noqa: F401
    NamespaceManager,
    NamespaceMeta,
    NamespaceNotFoundError,
    RetentionPolicy,  # noqa: F401 — EPIC-004
)
from dashboard.knowledge.audit import (  # noqa: WPS433 — EPIC-003 policies
    ImportInProgressError,
    MaxNamespacesReachedError,
    MAX_NAMESPACES,
    register_import,
    unregister_import,
    is_import_in_progress,
    _log_call,
    count_namespaces,
)
from dashboard.knowledge.stats import get_stats_computer  # noqa: WPS433 — EPIC-005
from dashboard.knowledge.metrics import get_metrics_registry  # noqa: WPS433 — EPIC-005

if TYPE_CHECKING:  # pragma: no cover
    from dashboard.knowledge.query import KnowledgeQueryEngine, QueryResult
    from dashboard.knowledge.vector_store import NamespaceVectorStore

logger = logging.getLogger(__name__)

# Default sweep interval for retention (hours)
DEFAULT_SWEEP_INTERVAL_HOURS = 6


class RetentionSweeper(threading.Thread):
    """Background thread that purges expired imports based on TTL policy.

    Started by :meth:`KnowledgeService.start_background` on dashboard startup.
    Runs every ``OSTWIN_KNOWLEDGE_SWEEP_INTERVAL_HOURS`` (default 6 hours).

    For each namespace with ``retention.policy == "ttl_days"``:
        1. Delete import records older than ``ttl_days``
        2. If all imports purged and ``auto_delete_when_empty == True``,
           delete the namespace itself
    """

    def __init__(
        self,
        service: "KnowledgeService",
        interval_hours: Optional[float] = None,
    ) -> None:
        super().__init__(daemon=True, name="RetentionSweeper")
        self._service = service
        self._interval_hours = interval_hours or float(
            os.environ.get("OSTWIN_KNOWLEDGE_SWEEP_INTERVAL_HOURS", DEFAULT_SWEEP_INTERVAL_HOURS)
        )
        self._stop_event = threading.Event()

    def run(self) -> None:
        """Main sweep loop."""
        logger.info("RetentionSweeper started (interval: %.1f hours)", self._interval_hours)
        while not self._stop_event.wait(timeout=self._interval_hours * 3600):
            try:
                self._sweep_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("RetentionSweeper error: %s", exc)

    def stop(self) -> None:
        """Signal the sweeper to stop."""
        self._stop_event.set()

    def _sweep_once(self) -> None:
        """Run a single sweep pass."""
        from datetime import datetime, timezone, timedelta
        
        now = datetime.now(timezone.utc)
        namespaces = self._service.list_namespaces()
        
        for meta in namespaces:
            if meta.retention.policy != "ttl_days":
                continue
            if meta.retention.ttl_days is None:
                continue
            
            ttl_days = meta.retention.ttl_days
            cutoff = now - timedelta(days=ttl_days)
            
            # Find expired imports
            expired = [
                imp for imp in meta.imports
                if imp.finished_at and imp.finished_at < cutoff
            ]
            
            # Update last_swept_at regardless of whether we have expired imports
            meta.retention.last_swept_at = now
            meta.updated_at = now
            
            if not expired:
                # Just save the updated timestamp
                self._service._nm.write_manifest(meta.name, meta)  # noqa: SLF001
                continue
            
            logger.info(
                "Sweeping %d expired imports from namespace %r (TTL: %d days)",
                len(expired), meta.name, ttl_days
            )
            
            # Remove expired imports from manifest
            remaining = [imp for imp in meta.imports if imp not in expired]
            meta.imports = remaining
            
            # Check if namespace should be deleted
            if not remaining and meta.retention.auto_delete_when_empty:
                logger.info("Deleting empty namespace %r (auto_delete_when_empty=True)", meta.name)
                self._service.delete_namespace(meta.name, actor="retention_sweeper")
            else:
                # Save updated manifest
                self._service._nm.write_manifest(meta.name, meta)  # noqa: SLF001


class KnowledgeService:
    """Sync façade composing :class:`NamespaceManager` + ingestion + query.

    All methods are sync; route handlers should wrap calls in
    ``asyncio.to_thread(...)`` per the cross-cutting concern in the plan.

    The ``namespace_manager``, ``job_manager`` and ``ingestor`` ctor args are
    optional injection points used by tests. When omitted they're constructed
    on-demand against ``KNOWLEDGE_DIR`` and shared across all calls.

    EPIC-004 architecture: this service owns the canonical per-namespace
    caches for vector stores, Kuzu graphs and query engines. Both the
    Ingestor and the query path resolve handles through
    :meth:`get_vector_store` / :meth:`get_kuzu_graph`, so there is exactly
    one live zvec handle and one Kuzu connection per namespace per process.
    Call :meth:`shutdown` before process exit (or in test teardown) to
    release them cleanly.
    """

    def __init__(
        self,
        namespace_manager: Optional[NamespaceManager] = None,
        job_manager: Optional[Any] = None,
        ingestor: Optional[Any] = None,
        embedder: Optional[Any] = None,
        llm: Optional[Any] = None,
    ) -> None:
        self._nm = namespace_manager or NamespaceManager()
        # Lazy: only construct JobManager / Ingestor on first use, so that
        # `KnowledgeService()` itself stays cheap.
        self._jm_override = job_manager
        self._ingestor_override = ingestor
        # Pass-throughs to the Ingestor when it's constructed lazily; tests
        # use these to inject fake embedder / LLM without having to also
        # build their own Ingestor.
        self._embedder_override = embedder
        self._llm_override = llm
        self._jm: Any = None
        self._ingestor: Any = None
        # Lazy-instantiated long-lived embedder / llm shared between the
        # ingestor and the query engine. Constructed on first use through
        # the relevant getter so a fresh `KnowledgeService()` stays cheap.
        self._embedder: Any = None
        self._llm: Any = None
        # Centralised caches — survive across ingestion + query and are the
        # ONLY source of truth for per-namespace handles. Architect's
        # ZVEC-LIVE-1 fix from the EPIC-003 review.
        self._vector_stores: dict[str, "NamespaceVectorStore"] = {}
        self._kuzu_graphs: dict[str, Any] = {}
        self._query_engines: dict[str, "KnowledgeQueryEngine"] = {}
        self._cache_lock = threading.RLock()
        # Background retention sweeper (EPIC-004)
        self._sweeper: Optional[RetentionSweeper] = None

    # ---- Shared embedder / LLM (lazy) -----------------------------------

    @staticmethod
    def _resolve_settings_overrides() -> tuple[str, str]:
        """Return ``(llm_model, embedding_model)`` overrides from MasterSettings.

        Empty strings mean "no override; use env-var / hardcoded default".
        Settings-resolver failures (config missing, vault offline, etc.)
        are logged at DEBUG and treated as "no override" — knowledge work
        must never crash because settings IO failed (ADR-15 graceful path).
        """
        try:
            from dashboard.lib.settings import get_settings_resolver  # noqa: WPS433

            ms = get_settings_resolver().get_master_settings()
            ks = getattr(ms, "knowledge", None)
            if ks is None:
                return "", ""
            return (ks.llm_model or ""), (ks.embedding_model or "")
        except Exception as exc:  # noqa: BLE001
            logger.debug("settings resolver unavailable: %s; using env defaults", exc)
            return "", ""

    def _get_embedder(self) -> Any:
        """Lazily construct (or return the injected) embedder, shared service-wide.

        The Ingestor and the query engine both go through this so a single
        SentenceTransformer model load is amortised across ingestion + every
        subsequent query.

        Effective model resolution (ADR-15): ``MasterSettings.knowledge.embedding_model``
        > ``OSTWIN_KNOWLEDGE_EMBED_MODEL`` env var > hardcoded ``EMBEDDING_MODEL``.
        """
        if self._embedder is not None:
            return self._embedder
        with self._cache_lock:
            if self._embedder is not None:
                return self._embedder
            if self._embedder_override is not None:
                self._embedder = self._embedder_override
            else:
                from dashboard.knowledge.config import EMBEDDING_MODEL as _DEFAULT_EMBED  # noqa: WPS433
                from dashboard.knowledge.embeddings import KnowledgeEmbedder  # noqa: WPS433

                _, settings_embed = self._resolve_settings_overrides()
                effective = settings_embed or _DEFAULT_EMBED
                self._embedder = KnowledgeEmbedder(model_name=effective)
            return self._embedder

    def _get_llm(self) -> Any:
        """Lazily construct (or return the injected) LLM, shared service-wide.

        Effective model resolution (ADR-15): ``MasterSettings.knowledge.llm_model``
        > ``OSTWIN_KNOWLEDGE_LLM_MODEL`` env var > hardcoded ``LLM_MODEL``.
        """
        if self._llm is not None:
            return self._llm
        with self._cache_lock:
            if self._llm is not None:
                return self._llm
            if self._llm_override is not None:
                self._llm = self._llm_override
            else:
                from dashboard.knowledge.config import LLM_MODEL as _DEFAULT_LLM  # noqa: WPS433
                from dashboard.knowledge.llm import KnowledgeLLM  # noqa: WPS433

                settings_llm, _ = self._resolve_settings_overrides()
                effective = settings_llm or _DEFAULT_LLM
                self._llm = KnowledgeLLM(model=effective)
            return self._llm

    # ---- Centralised per-namespace handle cache (EPIC-004) --------------

    def get_vector_store(self, namespace: str) -> "NamespaceVectorStore":
        """Get-or-create the cached vector store for ``namespace``.

        BOTH the ingestor AND the query engine MUST go through this method
        — the architect's ZVEC-LIVE-1 fix from the EPIC-003 review. zvec
        rejects opening the same collection from two live handles in the
        same process; centralising the cache here is the only correct
        solution.
        """
        with self._cache_lock:
            existing = self._vector_stores.get(namespace)
            if existing is not None:
                return existing
            from dashboard.knowledge.vector_store import NamespaceVectorStore  # noqa: WPS433

            vs = NamespaceVectorStore(
                vector_path=self._nm.vector_dir(namespace),
                dimension=int(self._get_embedder().dimension()),
                schema_name=f"knowledge_{namespace}",
            )
            self._vector_stores[namespace] = vs
            return vs

    def get_kuzu_graph(self, namespace: str) -> Any:
        """Get-or-create the cached Kuzu graph for ``namespace``.

        Uses :meth:`NamespaceManager.kuzu_db_path` so a custom ``base_dir``
        is honoured — never falls back to the module-level
        ``config.kuzu_db_path`` helper.
        """
        with self._cache_lock:
            existing = self._kuzu_graphs.get(namespace)
            if existing is not None:
                return existing
            from dashboard.knowledge.graph.index.kuzudb import (  # noqa: WPS433
                KuzuLabelledPropertyGraph,
            )

            db_path = str(self._nm.kuzu_db_path(namespace))
            kg = KuzuLabelledPropertyGraph(
                index=namespace,
                ws_id=namespace,
                database_path=db_path,
            )
            self._kuzu_graphs[namespace] = kg
            return kg

    def _get_query_engine(self, namespace: str) -> "KnowledgeQueryEngine":
        """Cached per-namespace query engine.

        The engine holds references to the cached vector store, Kuzu graph,
        embedder and LLM — building one is cheap (sub-ms) so this cache
        primarily exists so repeated queries against the same namespace
        don't reconstruct the wrapper.
        """
        with self._cache_lock:
            existing = self._query_engines.get(namespace)
            if existing is not None:
                return existing
            from dashboard.knowledge.query import KnowledgeQueryEngine  # noqa: WPS433

            engine = KnowledgeQueryEngine(
                namespace=namespace,
                vector_store=self.get_vector_store(namespace),
                kuzu_graph=self.get_kuzu_graph(namespace),
                embedder=self._get_embedder(),
                llm=self._get_llm(),
            )
            self._query_engines[namespace] = engine
            return engine

    def shutdown(self) -> None:
        """Release every cached handle. Call before process exit / test teardown.

        Order matters: query engines (which hold refs to the others) are
        cleared first, then vector stores, then Kuzu graphs, then the job
        manager. Each ``close`` is best-effort; a single failure is logged
        but does not abort the rest of the shutdown.
        """
        with self._cache_lock:
            # Drop query engine refs first (they only hold weak-ish refs to
            # the underlying handles, but clearing them ensures a future
            # call doesn't accidentally hold an old handle alive).
            self._query_engines.clear()

            for ns, vs in list(self._vector_stores.items()):
                try:
                    vs.close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Error closing vector store for %r: %s", ns, exc)
            self._vector_stores.clear()

            for ns, kg in list(self._kuzu_graphs.items()):
                try:
                    kg.close_connection()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Error closing kuzu graph for %r: %s", ns, exc)
            self._kuzu_graphs.clear()

        # Tell the JobManager to stop accepting new work and tear down its
        # ThreadPoolExecutor. ``wait=False`` so callers (especially test
        # teardown) don't block on a long-running ingest.
        if self._jm is not None:
            try:
                self._jm.shutdown(wait=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error shutting down job manager: %s", exc)
        
        # Stop the retention sweeper (EPIC-004)
        if self._sweeper is not None:
            try:
                self._sweeper.stop()
                self._sweeper.join(timeout=5.0)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error stopping retention sweeper: %s", exc)

    def start_background(self) -> None:
        """Start background services (retention sweeper).

        Called by the FastAPI lifespan in ``api.py`` on startup.
        """
        if self._sweeper is None:
            self._sweeper = RetentionSweeper(self)
            self._sweeper.start()
            logger.info("Started retention sweeper background thread")


    def _evict_namespace_caches(self, namespace: str) -> None:
        """Drop all cached handles for ``namespace`` (used by delete_namespace)."""
        with self._cache_lock:
            self._query_engines.pop(namespace, None)
            vs = self._vector_stores.pop(namespace, None)
            if vs is not None:
                try:
                    vs.close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Error closing vector store for %r during eviction: %s",
                        namespace,
                        exc,
                    )
            kg = self._kuzu_graphs.pop(namespace, None)
            if kg is not None:
                try:
                    kg.close_connection()
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Error closing kuzu graph for %r during eviction: %s",
                        namespace,
                        exc,
                    )

    # ---- Lazy job manager / ingestor ------------------------------------

    def _get_job_manager(self) -> Any:
        if self._jm is not None:
            return self._jm
        if self._jm_override is not None:
            self._jm = self._jm_override
            return self._jm
        from dashboard.knowledge.jobs import JobManager  # noqa: WPS433

        self._jm = JobManager(base_dir=self._nm._base)  # noqa: SLF001
        return self._jm

    def _get_ingestor(self) -> Any:
        if self._ingestor is not None:
            return self._ingestor
        if self._ingestor_override is not None:
            self._ingestor = self._ingestor_override
            return self._ingestor
        from dashboard.knowledge.ingestion import Ingestor  # noqa: WPS433

        # Pass the cache-aware factories so the ingestor pulls from the
        # service's centralised caches instead of constructing its own
        # per-namespace handles. This is the architect's ZVEC-LIVE-1 fix.
        self._ingestor = Ingestor(
            namespace_manager=self._nm,
            embedder=self._get_embedder(),
            llm=self._get_llm(),
            vector_store_factory=self.get_vector_store,
            kuzu_factory=self.get_kuzu_graph,
        )
        return self._ingestor

    # ---- Namespace lifecycle (EPIC-002 — wired) --------------------------

    def list_namespaces(self) -> list[NamespaceMeta]:
        """Return manifests for every existing namespace (possibly empty)."""
        return self._nm.list()

    def get_namespace(self, namespace: str) -> Optional[NamespaceMeta]:
        """Return the manifest for ``namespace``, or None if missing/invalid."""
        return self._nm.get(namespace)

    def get_namespace_stats(self, namespace: str) -> Optional[dict[str, Any]]:
        """Return enriched stats for a namespace (EPIC-005).

        Computes and caches:
        - disk_bytes: Actual disk usage
        - query_count_24h: Queries in last 24 hours
        - ingest_count_24h: Ingestions in last 24 hours

        Returns None if the namespace doesn't exist.
        """
        meta = self._nm.get(namespace)
        if meta is None:
            return None

        # Get computed stats from stats computer
        stats_computer = get_stats_computer()
        namespace_dir = self._nm.namespace_dir(namespace)
        computed = stats_computer.get_stats(namespace, namespace_dir)

        # Merge with manifest stats
        base_stats = meta.stats.model_dump()
        base_stats.update(computed)
        return base_stats

    def _update_namespace_gauges(self) -> None:
        """Update Prometheus gauges for namespace counts (EPIC-005).

        Called after namespace create/delete operations and periodically.
        """
        metrics = get_metrics_registry()
        namespaces = self._nm.list()
        
        # Total namespace count
        metrics.gauge("namespaces_total").set(len(namespaces))
        
        # Per-namespace gauges
        for meta in namespaces:
            ns = meta.name
            labels = {"namespace": ns}
            
            # Vector count
            metrics.gauge("vector_count_per_namespace").set(meta.stats.vectors, labels=labels)
            
            # Entity count
            metrics.gauge("entity_count_per_namespace").set(meta.stats.entities, labels=labels)
            
            # Disk bytes (use computed value if available)
            stats_computer = get_stats_computer()
            namespace_dir = self._nm.namespace_dir(ns)
            computed = stats_computer.get_stats(ns, namespace_dir)
            metrics.gauge("disk_bytes_per_namespace").set(computed.get("disk_bytes", 0), labels=labels)

    def create_namespace(
        self,
        namespace: str,
        language: str = "English",
        description: Optional[str] = None,
        actor: str = "anonymous",
    ) -> NamespaceMeta:
        """Create a fresh namespace.

        Raises :class:`InvalidNamespaceIdError` for bad ids,
        :class:`NamespaceExistsError` for duplicates, and
        :class:`MaxNamespacesReachedError` when the quota is exceeded.
        """
        start_time = time.perf_counter()
        try:
            # Check namespace quota before attempting creation
            current_count = count_namespaces(self._nm._base)  # noqa: SLF001
            if current_count >= MAX_NAMESPACES:
                raise MaxNamespacesReachedError(MAX_NAMESPACES)

            meta = self._nm.create(namespace, language=language, description=description)
            latency_ms = (time.perf_counter() - start_time) * 1000
            _log_call(namespace, "create_namespace", "success", latency_ms, {"actor": actor})
            # EPIC-005: Update namespace gauges
            self._update_namespace_gauges()
            return meta
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            result = "error"
            if isinstance(exc, (InvalidNamespaceIdError, NamespaceExistsError, MaxNamespacesReachedError)):
                result = type(exc).__name__
            _log_call(namespace, "create_namespace", result, latency_ms, {"actor": actor, "error": str(exc)})
            raise

    def delete_namespace(self, namespace: str, actor: str = "anonymous") -> bool:
        """Delete a namespace; returns True if it existed, False otherwise.

        EPIC-004: evicts the namespace's entries from all centralised
        caches BEFORE the directory is removed. Without this, the cached
        zvec handle would keep a file lock on the now-deleted directory
        and a subsequent re-create would fail.
        """
        start_time = time.perf_counter()
        try:
            # Evict cached handles FIRST so files can be removed cleanly.
            self._evict_namespace_caches(namespace)
            deleted = self._nm.delete(namespace)
            latency_ms = (time.perf_counter() - start_time) * 1000
            _log_call(namespace, "delete_namespace", "success", latency_ms, {"actor": actor, "deleted": deleted})
            # EPIC-005: Update namespace gauges
            self._update_namespace_gauges()
            return deleted
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            _log_call(namespace, "delete_namespace", "error", latency_ms, {"actor": actor, "error": str(exc)})
            raise

    # ---- Ingestion (EPIC-003 — wired) -----------------------------------

    def import_folder(
        self,
        namespace: str,
        folder_path: str,
        options: Optional[dict[str, Any]] = None,
        actor: str = "anonymous",
    ) -> str:
        """Submit a folder for background ingestion; return the ``job_id``.

        - **Auto-creates the namespace** when it doesn't already exist
          (decision recorded in EPIC-003 done report — chosen over 404
          because the alternative forces a clumsy two-step API for
          first-time imports).
        - Validates that ``folder_path`` exists and is a directory; raises
          :class:`FileNotFoundError` / :class:`NotADirectoryError` otherwise.
        - Returns within milliseconds — actual work runs on the JobManager's
          ThreadPoolExecutor.
        - **Concurrent import protection**: raises :class:`ImportInProgressError`
          if another import is already running for the same namespace.

        Raises:
            ImportInProgressError: When an import is already in progress for
                the same namespace.
        """
        from dashboard.knowledge.ingestion import IngestOptions  # noqa: WPS433

        start_time = time.perf_counter()

        # Check for concurrent import BEFORE any other work
        existing_job = is_import_in_progress(namespace)
        if existing_job is not None:
            raise ImportInProgressError(namespace, existing_job)

        try:
            # Auto-create namespace if missing.
            if self._nm.get(namespace) is None:
                self._nm.create(namespace)

            # Validate folder path BEFORE submitting — surface the error to the caller.
            p = Path(folder_path)
            if not p.exists():
                raise FileNotFoundError(folder_path)
            if not p.is_dir():
                raise NotADirectoryError(folder_path)

            opts = IngestOptions(**(options or {}))
            ingestor = self._get_ingestor()
            jm = self._get_job_manager()

            # The JobManager calls runner(emit) in a worker thread.
            def runner(emit):
                try:
                    return ingestor.run(namespace, folder_path, opts, emit=emit)
                finally:
                    # Always unregister the import when done (success or failure)
                    unregister_import(namespace)

            job_id = jm.submit(
                namespace=namespace,
                operation="import_folder",
                fn=runner,
                message=f"Importing {folder_path}",
            )

            # Register the import as in-progress
            register_import(namespace, job_id)

            latency_ms = (time.perf_counter() - start_time) * 1000
            _log_call(namespace, "import_folder", "success", latency_ms, {"actor": actor, "job_id": job_id})
            return job_id

        except ImportInProgressError:
            # Re-raise as-is (don't log as regular error)
            latency_ms = (time.perf_counter() - start_time) * 1000
            _log_call(namespace, "import_folder", "import_in_progress", latency_ms, {"actor": actor})
            raise
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            _log_call(namespace, "import_folder", "error", latency_ms, {"actor": actor, "error": str(exc)})
            raise

    def get_job(self, job_id: str) -> Any:
        """Return the :class:`JobStatus` for ``job_id`` (or None if unknown)."""
        return self._get_job_manager().get(job_id)

    def list_jobs(self, namespace: str) -> Any:
        """List jobs for ``namespace`` (newest first)."""
        return self._get_job_manager().list_for_namespace(namespace)

    # ---- Retrieval (EPIC-004) -------------------------------------------

    def query(
        self,
        namespace: str,
        query: str,
        *,
        mode: str = "raw",
        top_k: int = 10,
        threshold: float = 0.5,
        category: Optional[str] = None,
        parameter: str = "",
        actor: str = "anonymous",
    ) -> "QueryResult":
        """Run a retrieval against ``namespace``.

        Modes:

        - ``raw``        — vector search only. Fast (< 500ms p95 on small
          corpora). No graph, no LLM.
        - ``graph``      — vector search + graph expansion + PageRank
          rerank. Returns chunks AND entities. No LLM aggregation.
        - ``summarized`` — graph mode + LLM-aggregated answer. Requires
          ``ANTHROPIC_API_KEY``; without it, returns chunks + a warning
          (no crash, no answer).

        Raises :class:`NamespaceNotFoundError` if the namespace doesn't
        exist, and :class:`ValueError` for an unknown mode.
        """
        start_time = time.perf_counter()
        try:
            if self._nm.get(namespace) is None:
                raise NamespaceNotFoundError(namespace)
            if mode not in ("raw", "graph", "summarized"):
                raise ValueError(f"unknown mode: {mode!r}")
            engine = self._get_query_engine(namespace)
            result = engine.query(
                query,
                mode=mode,
                top_k=top_k,
                threshold=threshold,
                category=category,
                parameter=parameter,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000
            _log_call(namespace, "query", "success", latency_ms, {"actor": actor, "mode": mode})
            # EPIC-005: Update last_query_at in stats
            try:
                from datetime import datetime, timezone  # noqa: WPS433

                self._nm.update_stats(namespace, last_query_at=datetime.now(timezone.utc))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to update last_query_at: %s", exc)
            return result
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            _log_call(namespace, "query", "error", latency_ms, {"actor": actor, "error": str(exc)})
            raise



__all__ = ["KnowledgeService"]
