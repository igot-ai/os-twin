"""Per-namespace query engine — three retrieval modes (EPIC-004).

The :class:`KnowledgeQueryEngine` is the heart of EPIC-004. One engine
instance per namespace, constructed by :meth:`KnowledgeService._get_query_engine`
and cached for the lifetime of the service. The engine holds **references**
(not copies) to the centralised vector store, Kuzu graph, embedder and LLM
that live on the :class:`KnowledgeService` — which is why the service-level
cache is the single source of truth for those handles (architect's
ZVEC-LIVE-1 fix from the EPIC-003 review).

Three modes:

- ``raw``        — vector search via :class:`NamespaceVectorStore.search`
                   only. Sub-500ms p95 on small corpora; no graph, no LLM.
- ``graph``      — vector search + graph expansion (entities related to the
                   vector hits, ranked by personalised PageRank). Useful when
                   you want both the most-relevant chunks AND the entities
                   that connect them.
- ``summarized`` — graph mode + LLM-aggregated answer. Requires
                   ``ANTHROPIC_API_KEY``; without it the engine returns
                   chunks + entities + a ``warning`` field on the result and
                   ``answer=None``. Never crashes for missing-key reasons.

All three modes record ``latency_ms`` on the result. Per-step failures are
caught and accumulated as ``warnings`` on the result so a single bad
component (e.g. a Kuzu read error during graph expansion) doesn't kill the
entire query — the caller still gets the chunks that *did* come back.

Citations are populated from the vector hits' metadata. ``page`` is left
None because not every parser provides page numbers; future EPIC-007 work
can fill that in for PDF / DOCX once MarkItDown propagates page metadata
through the chunker.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from pydantic import BaseModel, Field

from dashboard.knowledge.metrics import get_metrics_registry

logger = logging.getLogger(__name__)


# Import bridge lazily to avoid circular imports
_bridge_index = None
_bridge_warned_unavailable = False  # Track if we've logged the "unavailable" warning


def _get_bridge_index():
    """Lazily import and get the bridge index singleton.
    
    Returns None if:
    - Bridge is disabled (OSTWIN_KNOWLEDGE_MEMORY_BRIDGE != "1")
    - Bridge module import fails
    - Memory server is unavailable
    
    Logs a warning ONCE when the bridge is unavailable.
    """
    global _bridge_index, _bridge_warned_unavailable
    
    if _bridge_index is None:
        try:
            from dashboard.knowledge.bridge import get_bridge_index, is_bridge_enabled
            if is_bridge_enabled():
                _bridge_index = get_bridge_index()
                if _bridge_index is None:
                    # Bridge enabled but not available
                    if not _bridge_warned_unavailable:
                        logger.warning(
                            "Memory-Knowledge bridge enabled but unavailable; "
                            "memory_links will be empty for all queries. "
                            "This warning will not repeat."
                        )
                        _bridge_warned_unavailable = True
            # If bridge is disabled, we silently return None (no warning needed)
        except ImportError:
            if not _bridge_warned_unavailable:
                logger.warning(
                    "Bridge module not available; memory_links will be empty. "
                    "This warning will not repeat."
                )
                _bridge_warned_unavailable = True
    return _bridge_index


# Hard ceiling on PageRank result count — even the most graph-heavy
# namespace shouldn't surface more than a handful of entities for a single
# query. EPIC-007 may make this configurable.
_MAX_ENTITIES_PER_QUERY = 20


# ---------------------------------------------------------------------------
# Result models (Pydantic — JSON-serialisable for EPIC-005 REST API)
# ---------------------------------------------------------------------------


class ChunkHit(BaseModel):
    """A single chunk returned from vector retrieval."""

    text: str
    score: float
    file_path: str = ""
    filename: str = ""
    chunk_index: int = 0
    total_chunks: int = 1
    file_hash: str = ""
    mime_type: Optional[str] = None
    category_id: Optional[str] = None
    memory_links: list[str] = Field(default_factory=list)


class EntityHit(BaseModel):
    """A single entity returned from graph expansion."""

    id: str
    name: str
    label: str = "entity"
    score: float = 0.0
    description: Optional[str] = None
    category_id: Optional[str] = None


class Citation(BaseModel):
    """A pointer back to the source document for a chunk hit.

    ``snippet_id`` is the zvec doc id. ``page`` is None for parsers that
    don't propagate page numbers (most of MarkItDown's path right now);
    EPIC-007 may extend this for PDF / DOCX.
    """

    file: str
    page: Optional[int] = None
    chunk_index: int = 0
    snippet_id: str = ""


class QueryResult(BaseModel):
    """Top-level result for a single query.

    Wired to the REST surface in EPIC-005 — keep this shape stable. Use
    ``model_dump(mode="json")`` when serialising via FastAPI to ensure the
    enum-like ``mode`` string and any future datetime fields render
    correctly.
    """

    query: str
    mode: str
    namespace: str
    chunks: list[ChunkHit] = Field(default_factory=list)
    entities: list[EntityHit] = Field(default_factory=list)
    answer: Optional[str] = None
    citations: list[Citation] = Field(default_factory=list)
    latency_ms: int = 0
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# KnowledgeQueryEngine
# ---------------------------------------------------------------------------


class KnowledgeQueryEngine:
    """Per-namespace query engine.

    Constructed once by :meth:`KnowledgeService._get_query_engine` and
    cached for the namespace's lifetime in the service. The engine itself
    is stateless beyond the references it holds; safe to call concurrently
    from multiple threads provided the underlying handles are thread-safe
    (zvec is, Kuzu reads are).

    Parameters
    ----------
    namespace:
        The namespace this engine queries against — informational only,
        used to populate :class:`QueryResult.namespace`.
    vector_store:
        A :class:`NamespaceVectorStore` instance (or duck-typed equivalent
        for tests). Reused across queries; never closed by the engine.
    kuzu_graph:
        A :class:`KuzuLabelledPropertyGraph` instance. Reused across
        queries; never closed by the engine.
    embedder:
        A :class:`KnowledgeEmbedder` (or duck-typed equivalent). The query
        text is embedded once per query via :meth:`embed_one`.
    llm:
        A :class:`KnowledgeLLM` (or duck-typed equivalent). Only invoked
        when ``mode="summarized"``; always checked via :meth:`is_available`
        first so a missing ANTHROPIC_API_KEY can't crash a query.
    """

    def __init__(
        self,
        namespace: str,
        vector_store: Any,
        kuzu_graph: Any,
        embedder: Any,
        llm: Any,
    ) -> None:
        self.namespace = namespace
        self.vs = vector_store
        self.kg = kuzu_graph
        self.embedder = embedder
        self.llm = llm

    # ---- Public entrypoint -----------------------------------------------

    def query(
        self,
        query: str,
        *,
        mode: str = "raw",
        top_k: int = 10,
        threshold: float = 0.5,
        category: Optional[str] = None,
        parameter: str = "",
    ) -> QueryResult:
        """Run a single query against this engine's namespace.

        See module docstring for ``mode`` semantics. ``threshold`` filters
        out vector hits with score < threshold (zvec returns COSINE
        similarity — higher is better). ``category`` scopes both the vector
        search and the graph expansion when set.

        ``parameter`` is reserved for future use (e.g. a domain hint for
        the LLM); it's accepted on the API surface so EPIC-005 doesn't
        need a follow-up signature change.
        """
        t0 = time.perf_counter()
        result = QueryResult(query=query, mode=mode, namespace=self.namespace)

        # Get metrics registry
        metrics = get_metrics_registry()
        metrics.counter("query_total").inc()

        # --- 1) Embed the query --------------------------------------
        try:
            q_embed = self.embedder.embed_one(query)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to embed query %r: %s", query, exc)
            result.warnings.append(f"embed_failed: {exc}")
            result.latency_ms = int((time.perf_counter() - t0) * 1000)
            metrics.counter("query_errors_total").inc()
            return result

        if not q_embed:
            # Embedder returned nothing — surface as a warning and bail.
            result.warnings.append("embed_returned_empty")
            result.latency_ms = int((time.perf_counter() - t0) * 1000)
            metrics.counter("query_errors_total").inc()
            return result

        # --- 2) Vector search ----------------------------------------
        try:
            hits = self.vs.search(q_embed, top_k=top_k, category_id=category)
        except Exception as exc:  # noqa: BLE001
            logger.error("Vector search failed for %r: %s", query, exc)
            result.warnings.append(f"vector_search_failed: {exc}")
            result.latency_ms = int((time.perf_counter() - t0) * 1000)
            metrics.counter("query_errors_total").inc()
            return result

        # Threshold filter (COSINE — higher is better).
        hits = [h for h in hits if float(h.score) >= float(threshold)]
        result.chunks = [self._to_chunk_hit(h) for h in hits]
        result.citations = [self._to_citation(h) for h in hits]

        # Enrich chunks with memory_links via bridge (if enabled)
        self._enrich_memory_links(result.chunks)

        if mode == "raw":
            result.latency_ms = int((time.perf_counter() - t0) * 1000)
            return result

        # --- 3) Graph expansion (graph + summarized modes) -----------
        try:
            entity_hits = self._graph_expand(hits, query, category=category)
            result.entities = entity_hits
        except Exception as exc:  # noqa: BLE001
            logger.warning("Graph expansion failed: %s", exc)
            result.warnings.append(f"graph_expansion_failed: {exc}")

        if mode == "graph":
            result.latency_ms = int((time.perf_counter() - t0) * 1000)
            return result

        # --- 4) LLM aggregation (summarized only) --------------------
        if mode == "summarized":
            llm_available = False
            try:
                llm_available = bool(self.llm.is_available())
            except Exception as exc:  # noqa: BLE001 — defensive
                logger.warning("llm.is_available() raised: %s", exc)
                llm_available = False

            if not llm_available:
                result.warnings.append(
                    "llm_unavailable: ANTHROPIC_API_KEY not set; "
                    "returning chunks without an aggregated answer"
                )
                result.latency_ms = int((time.perf_counter() - t0) * 1000)
                return result

            summaries = [h.text for h in hits if h.text]
            if not summaries:
                # Nothing to summarise — return empty string so callers can
                # still render "no answer" without a None check.
                result.answer = ""
            else:
                try:
                    result.answer = self.llm.aggregate_answers(summaries, query)
                except Exception as exc:  # noqa: BLE001
                    logger.error("LLM aggregation failed: %s", exc)
                    result.warnings.append(f"llm_aggregation_failed: {exc}")
                    result.answer = None

        result.latency_ms = int((time.perf_counter() - t0) * 1000)
        # Record query latency histogram (convert ms to seconds)
        metrics.histogram("query_latency_seconds").observe(result.latency_ms / 1000.0)
        return result

    # ---- Graph visualisation ---------------------------------------------

    def get_graph(self, *, limit: int = 200) -> dict:
        """Return ``{nodes, edges, stats}`` for visualization.

        ``limit`` caps the number of entity nodes returned (and therefore
        the maximum number of edges, since edges are filtered to those
        connecting two surviving nodes). Failures are caught and an
        ``error`` field is added to the response — never raises so the
        REST handler can return a 200 with an empty graph + diagnostic.
        """
        try:
            entities = self.kg.get_all_nodes(label_type="entity")
        except Exception as exc:  # noqa: BLE001
            logger.error("get_graph: get_all_nodes failed: %s", exc)
            return {
                "nodes": [],
                "edges": [],
                "stats": {"node_count": 0, "edge_count": 0},
                "error": str(exc),
            }

        # Bound the result before doing anything else expensive.
        if limit is not None and limit >= 0:
            entities = list(entities)[:limit]

        nodes = [
            {
                "id": getattr(e, "id", ""),
                "label": getattr(e, "label", "") or getattr(e, "id", ""),
                "name": getattr(e, "name", "") or getattr(e, "id", ""),
                "score": 1.0,
                "properties": getattr(e, "properties", {}) or {},
            }
            for e in entities
        ]
        entity_ids = {n["id"] for n in nodes if n["id"]}

        try:
            relations = self.kg.get_all_relations()
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_graph: get_all_relations failed: %s", exc)
            relations = []

        edges = [
            {
                "source": getattr(r, "source_id", ""),
                "target": getattr(r, "target_id", ""),
                "label": getattr(r, "label", "") or "RELATES",
            }
            for r in relations
            if getattr(r, "source_id", None) in entity_ids
            and getattr(r, "target_id", None) in entity_ids
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {"node_count": len(nodes), "edge_count": len(edges)},
        }

    # ---- Internals --------------------------------------------------------

    def _to_chunk_hit(self, vh: Any) -> ChunkHit:
        """Convert a :class:`VectorHit` (or duck-typed equivalent) to ChunkHit."""
        md = getattr(vh, "metadata", None) or {}
        return ChunkHit(
            text=getattr(vh, "text", "") or "",
            score=float(getattr(vh, "score", 0.0)),
            file_path=str(md.get("file_path") or ""),
            filename=str(md.get("filename") or ""),
            chunk_index=int(md.get("chunk_index") or 0),
            total_chunks=int(md.get("total_chunks") or 1),
            file_hash=str(md.get("file_hash") or ""),
            mime_type=md.get("mime_type"),
            category_id=md.get("category_id"),
        )

    def _enrich_memory_links(self, chunks: list[ChunkHit]) -> None:
        """Enrich chunks with memory_links from the bridge index.
        
        This is a no-op if the bridge is disabled or unavailable.
        Modifies chunks in-place.
        """
        bridge = _get_bridge_index()
        if bridge is None:
            return
        
        for chunk in chunks:
            if not chunk.file_hash:
                continue
            try:
                note_ids = bridge.lookup(
                    namespace=self.namespace,
                    file_hash=chunk.file_hash,
                    chunk_idx=chunk.chunk_index,
                )
                chunk.memory_links = note_ids
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Bridge lookup failed for %s/%s#%d: %s",
                    self.namespace,
                    chunk.file_hash,
                    chunk.chunk_index,
                    exc,
                )

    def _to_citation(self, vh: Any) -> Citation:
        md = getattr(vh, "metadata", None) or {}
        return Citation(
            file=str(md.get("file_path") or md.get("filename") or ""),
            page=None,
            chunk_index=int(md.get("chunk_index") or 0),
            snippet_id=str(getattr(vh, "id", "") or ""),
        )

    def _graph_expand(
        self,
        vector_hits: list[Any],
        query: str,
        *,
        category: Optional[str] = None,
    ) -> list[EntityHit]:
        """Use Kuzu PageRank to find entities related to the vector hits.

        For MVP: pull all entities for the namespace, run PageRank with a
        uniform personalisation vector. EPIC-007 can replace the
        personalisation with smarter heuristics (e.g. name-overlap with
        chunk text). Returns at most :data:`_MAX_ENTITIES_PER_QUERY`
        entities, sorted by PageRank score descending.

        Returns ``[]`` (not raise) when:

        - The Kuzu graph has no entities (e.g. ingest ran without a
          configured LLM, so no entities were extracted).
        - PageRank fails for any reason — the warning is captured by the
          caller via the surrounding try/except in :meth:`query`.
        """
        try:
            entities = self.kg.get_all_nodes(label_type="entity", category_id=category)
        except Exception as exc:  # noqa: BLE001
            logger.warning("_graph_expand: get_all_nodes failed: %s", exc)
            return []

        entities = list(entities or [])
        if not entities:
            return []

        # Uniform personalisation — every entity gets equal weight. Good
        # enough for MVP; EPIC-007 can swap in a hit-aware vector.
        weight = 1.0 / float(len(entities))
        personalize = {
            getattr(e, "id", str(i)): weight
            for i, e in enumerate(entities)
            if getattr(e, "id", None)
        }
        if not personalize:
            return []

        try:
            ranked = self.kg.pagerank(personalize, category_id=category)
        except Exception as exc:  # noqa: BLE001
            logger.warning("_graph_expand: pagerank failed: %s", exc)
            return []

        # ``ranked`` is List[(node_id, score)] sorted by score DESC.
        # Build an id → entity lookup so we can pull name / label / props.
        ent_by_id = {getattr(e, "id", None): e for e in entities}
        out: list[EntityHit] = []
        for item in (ranked or [])[:_MAX_ENTITIES_PER_QUERY]:
            try:
                ent_id, score = item[0], float(item[1])
            except (TypeError, IndexError, ValueError):
                continue
            ent = ent_by_id.get(ent_id)
            name = getattr(ent, "name", None) if ent is not None else None
            label = getattr(ent, "label", None) if ent is not None else None
            props = getattr(ent, "properties", None) if ent is not None else None
            description = None
            cat_id = None
            if isinstance(props, dict):
                description = props.get("description")
                cat_id = props.get("category_id")
            out.append(
                EntityHit(
                    id=str(ent_id),
                    name=str(name) if name else str(ent_id),
                    label=str(label) if label else "entity",
                    score=score,
                    description=str(description) if description else None,
                    category_id=str(cat_id) if cat_id else None,
                )
            )
        return out


__all__ = [
    "ChunkHit",
    "Citation",
    "EntityHit",
    "KnowledgeQueryEngine",
    "QueryResult",
]
