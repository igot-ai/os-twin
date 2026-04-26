"""Knowledge-graph extractor — wraps a :class:`KnowledgeLLM` to extract
entities and relationships from text chunks.

Refactor notes (EPIC-001):
- Removed DSPy + DspyLlamaIndexAdapter (not available in dashboard).
- Now takes a :class:`KnowledgeLLM` instance directly. The LLM call goes
  through ``KnowledgeLLM.extract_entities``.
- Removed the `_create_extraction_prompt` machinery — prompts are baked into
  ``KnowledgeLLM`` so callers only need to pass language + domain.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional

from llama_index.core.async_utils import run_jobs
from llama_index.core.graph_stores.types import (
    KG_NODES_KEY,
    KG_RELATIONS_KEY,
    EntityNode,
    Relation,
)
from llama_index.core.schema import BaseNode, TransformComponent

from dashboard.knowledge.embeddings import KnowledgeEmbedder
from dashboard.knowledge.llm import KnowledgeLLM

logger = logging.getLogger(__name__)


class ExtractionStatus(Enum):
    """Status of graph extraction process."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class ExtractionConfig:
    """Configuration for graph extraction."""

    max_retries: int = 3
    retry_delay: float = 1.0
    timeout_seconds: float = 240.0
    min_entity_length: int = 2
    max_entity_length: int = 100
    min_entities_per_chunk: int = 0
    max_entities_per_chunk: int = 50
    enable_validation: bool = True
    enable_performance_monitoring: bool = True
    batch_size: int = 10


@dataclass
class ExtractionMetrics:
    """Aggregate metrics for an extraction batch."""

    total_nodes: int = 0
    successful_extractions: int = 0
    failed_extractions: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    average_processing_time: float = 0.0
    errors: List[str] = field(default_factory=list)


class GraphRAGExtractor(TransformComponent):
    """Knowledge-graph extractor backed by ``KnowledgeLLM``.

    Implements the LlamaIndex ``TransformComponent`` interface so it can be
    plugged into ``PropertyGraphIndex.from_existing(...)``.
    """

    # Pydantic-friendly field declarations
    llm: Optional[Any] = None
    embedder: Optional[Any] = None
    config: Optional[ExtractionConfig] = None
    metrics: Optional[Any] = None
    domain_prompt: str = ""
    language: str = "English"
    max_paths_per_chunk: int = 10
    num_workers: int = 1

    def __init__(
        self,
        llm: KnowledgeLLM,
        domain_prompt: str = "",
        language: str = "English",
        max_paths_per_chunk: int = 10,
        num_workers: int = 1,
        config: Optional[ExtractionConfig] = None,
        embedder: Optional[KnowledgeEmbedder] = None,
        # Legacy kwargs accepted for back-compat; ignored.
        extract_prompt: Any = None,
        sys_prompt: Any = None,
        parse_fn: Any = None,
        **_: Any,
    ) -> None:
        super().__init__()
        self.llm = llm
        self.embedder = embedder or KnowledgeEmbedder()
        self.config = config or ExtractionConfig()
        self.metrics = ExtractionMetrics()
        self.domain_prompt = domain_prompt or ""
        self.language = language or "English"
        self.max_paths_per_chunk = max_paths_per_chunk
        self.num_workers = num_workers

    # -- Sync entrypoint ------------------------------------------------

    def __call__(self, nodes: List[BaseNode], show_progress: bool = False, **kwargs: Any) -> List[BaseNode]:
        """Run the async pipeline in a fresh event loop on a worker thread."""
        try:
            import concurrent.futures

            def runner():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.acall(nodes, show_progress=show_progress, **kwargs))
                finally:
                    loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(runner)
                return future.result(timeout=self.config.timeout_seconds + 60)
        except Exception as exc:  # noqa: BLE001
            logger.error("GraphRAGExtractor sync run failed: %s", exc)
            for node in nodes:
                node.metadata[KG_NODES_KEY] = []
                node.metadata[KG_RELATIONS_KEY] = []
            return nodes

    # -- Async pipeline -------------------------------------------------

    async def acall(self, nodes: List[BaseNode], show_progress: bool = False, **kwargs: Any) -> List[BaseNode]:
        if not nodes:
            return []
        logger.info("Starting graph extraction for %d nodes", len(nodes))
        self.metrics = ExtractionMetrics()
        jobs = [self._extract_with_retry(node) for node in nodes]
        try:
            results = await run_jobs(
                jobs,
                workers=min(self.num_workers, len(nodes)),
                show_progress=show_progress,
                desc="Extracting knowledge graphs",
            )
            logger.info("Graph extraction completed for %s nodes", str(results))
            return results
        except Exception as exc:  # noqa: BLE001
            logger.error("Batch extraction failed: %s", exc)
            for node in nodes:
                node.metadata[KG_NODES_KEY] = []
                node.metadata[KG_RELATIONS_KEY] = []
            return nodes

    async def _extract_with_retry(self, node: BaseNode) -> BaseNode:
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                if attempt > 0:
                    await asyncio.sleep(self.config.retry_delay * attempt)
                return await self._aextract_single(node)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.error("Extraction attempt %d failed for %s: %s", attempt + 1, node.id_, exc)
        return self._create_empty_extraction_result(node, str(last_error))

    async def _aextract_single(self, node: BaseNode) -> BaseNode:
        if not hasattr(node, "text"):
            return self._create_empty_extraction_result(node, "node missing .text")
        text = node.get_content(metadata_mode="llm")
        try:
            entities, relations = await asyncio.wait_for(
                asyncio.to_thread(
                    self.llm.extract_entities,
                    text,
                    self.language,
                    self.domain_prompt,
                ),
                timeout=self.config.timeout_seconds,
            )
            return self._create_extraction_result(node, entities, relations)
        except asyncio.TimeoutError:
            raise ValueError(f"Extraction timeout for node {node.id_}")

    # -- Result builders ------------------------------------------------

    def _create_extraction_result(
        self,
        node: BaseNode,
        entities: list,
        entities_relationship: list,
    ) -> BaseNode:
        existing_nodes = node.metadata.pop(KG_NODES_KEY, [])
        existing_relations = node.metadata.pop(KG_RELATIONS_KEY, [])
        entity_metadata = node.metadata.copy()

        if entities:
            entity_texts: list[str] = []
            for entity in entities:
                if isinstance(entity, dict):
                    name = entity.get("name", "")
                    etype = entity.get("type", "")
                    desc = entity.get("description", "")
                else:
                    name, etype, desc = entity
                entity_texts.append(".".join([str(name), str(etype), str(desc)]))
            try:
                embeddings = self.embedder.embed(entity_texts)
                logger.info("Batch embedding completed for %s entities", len(entities))
            except Exception as exc:  # noqa: BLE001
                logger.error("Batch embedding failed (%s); falling back to per-text", exc)
                embeddings = [self.embedder.embed_one(t) for t in entity_texts]
        else:
            embeddings = []

        for entity, embedding in zip(entities, embeddings):
            if isinstance(entity, dict):
                name = entity.get("name", "")
                etype = entity.get("type", "")
                desc = entity.get("description", "")
            else:
                name, etype, desc = entity
            entity_metadata["entity_description"] = desc
            entity_metadata["node_id"] = str(node.id_)
            existing_nodes.append(
                EntityNode(
                    name=name,
                    label=etype,
                    properties=dict(entity_metadata),
                    embedding=embedding,
                )
            )

        relation_metadata = node.metadata.copy()
        for rel in entities_relationship:
            if isinstance(rel, dict):
                subj = rel.get("source", "")
                obj = rel.get("target", "")
                rlabel = rel.get("relation", "")
                desc = rel.get("description", "")
            else:
                subj, obj, rlabel, desc = rel
            relation_metadata["relationship_description"] = desc
            relation_metadata["node_id"] = str(node.id_)
            existing_relations.append(
                Relation(
                    label=rlabel,
                    source_id=subj,
                    target_id=obj,
                    properties=dict(relation_metadata),
                )
            )

        node.metadata[KG_NODES_KEY] = existing_nodes
        node.metadata[KG_RELATIONS_KEY] = existing_relations

        # Ensure the source node (ChunkNode) also carries an embedding so it
        # can be found via KuzuDB's QUERY_VECTOR_INDEX. If the node already
        # has an embedding (e.g. from the PropertyGraphIndex embed_model) we
        # leave it alone; otherwise we generate one from its text content.
        if not getattr(node, "embedding", None):
            try:
                text_for_embed = node.get_content(metadata_mode="none")
                if text_for_embed and text_for_embed.strip():
                    node.embedding = self.embedder.embed_one(text_for_embed)
                    logger.debug("Embedded source ChunkNode %s (%d chars)", node.id_, len(text_for_embed))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to embed source ChunkNode %s: %s", node.id_, exc)

        logger.info(
            "Extraction: %d entities, %d relations",
            len(existing_nodes),
            len(existing_relations),
        )
        return node

    def _create_empty_extraction_result(self, node: BaseNode, error_msg: str) -> BaseNode:
        node.metadata[KG_NODES_KEY] = []
        node.metadata[KG_RELATIONS_KEY] = []
        node.metadata["extraction_error"] = error_msg
        node.metadata["extraction_status"] = ExtractionStatus.FAILED.value
        return node

    def get_metrics(self) -> ExtractionMetrics:
        return self.metrics
