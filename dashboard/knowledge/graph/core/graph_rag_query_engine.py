"""Graph-RAG query engine — combines vector search with graph reasoning.

Refactor notes (EPIC-001):
- Removed dependency on llama-index ``LLM`` and DSPy adapters.
- ``llm`` and ``plan_llm`` attributes are now :class:`KnowledgeLLM` instances.
- Aggregation uses :meth:`KnowledgeLLM.aggregate_answers` directly.
- Removed ``run_async_in_thread`` (was an `app.utils` helper); use a small
  inline event-loop runner.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

from pydantic import PrivateAttr

import yaml
from llama_index.core import PropertyGraphIndex, StorageContext
from llama_index.core.graph_stores.types import KG_SOURCE_REL
from llama_index.core.query_engine import CustomQueryEngine
from llama_index.core.query_engine.custom import STR_OR_RESPONSE_TYPE
from llama_index.core.vector_stores.types import BasePydanticVectorStore

from dashboard.knowledge.config import PAGERANK_SCORE_THRESHOLD
from dashboard.knowledge.graph.core.graph_rag_extractor import GraphRAGExtractor
from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore
from dashboard.knowledge.graph.core.query_executioner import QueryExecutor
from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever
from dashboard.knowledge.llm import KnowledgeLLM

logger = logging.getLogger(__name__)

# Constants for file-metadata fields.
FILE_METADATA_FIELDS = ["file_path", "filename", "page_range", "page_number"]


def _run_async(coro):
    """Run an awaitable from sync code without disturbing the caller's loop.

    Uses ``asyncio.get_running_loop()`` (3.10+) to detect whether the caller is
    already inside an event loop. If so, executes the coroutine on a fresh loop
    in a worker thread. Otherwise drives a new loop via ``asyncio.run()``.

    The previous implementation called ``asyncio.get_event_loop()`` which is
    deprecated (DeprecationWarning in 3.12, removal scheduled for 3.14) and
    has surprising behaviour when no loop is set.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop in this thread → simplest path.
        return asyncio.run(coro)

    # We're already inside a running loop → must use a worker thread.
    import concurrent.futures

    def runner():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(runner).result()


class GraphRAGQueryEngine(CustomQueryEngine):
    """Query engine combining vector search and graph-based reasoning."""

    graph_store: GraphRAGStore
    index: PropertyGraphIndex
    vector_store: BasePydanticVectorStore
    storage_context: StorageContext
    kg_extractor: GraphRAGExtractor
    llm: Any  # KnowledgeLLM
    plan_llm: Any  # KnowledgeLLM
    similarity_top_k: int = 20
    similarity_score: float = 0.2
    data_instruction: str = ""
    language: str = "English"
    node_id: str
    include_graph: bool = False
    stream_handler: Optional[Callable] = None
    max_queries: int = 3
    _tracking: Any = PrivateAttr(default=None)

    @property
    def tracking(self):
        if self._tracking is None:
            self._tracking = TrackVectorRetriever(
                engine=self,
                graph_store=self.index.property_graph_store,
                vector_store=self.index.vector_store,
                include_text=False,
                embed_model=self.index._embed_model,
            )
        return self._tracking

    # -- Citation helpers -----------------------------------------------

    def _create_citation(self, metadata: dict, uuid: str) -> str:
        file_path = metadata.get("file_path", "")
        file_name = metadata.get("filename", "")
        page_range = metadata.get("page_range", "")
        page_number = metadata.get("page_number", "")

        file_identifier = file_name or file_path
        page_info = page_range or page_number

        if not file_identifier:
            return f"`{uuid}`"

        page_suffix = f"({page_info})" if page_info else ""
        return f"[{file_identifier}{page_suffix}]{{uuid:{uuid}}}"

    # -- Graph snapshot -------------------------------------------------

    def graph_result(self):
        graph = self.tracking.graph
        nodes: list[dict] = []
        for node_id, node_data in graph.nodes(data=True):
            try:
                score = node_data.get("score", 0.0)
                properties = node_data.get("properties", {})
                citation = self._create_citation(properties, node_id)
                nodes.append(
                    {
                        "id": node_id,
                        "citation": citation,
                        "label": node_data.get("label", node_id),
                        "score": score,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Error processing node %s: %s", node_id, exc)
                nodes.append(
                    {
                        "id": node_id,
                        "citation": f"`{node_id}`",
                        "label": node_data.get("label", node_id),
                        "score": node_data.get("score", 0.0),
                    }
                )
        nodes.sort(key=lambda x: x["score"], reverse=True)

        edges: list[dict] = []
        for source_id, target_id, edge_data in graph.edges(data=True):
            relationship_label = edge_data.get("label", "RELATED")
            relationship_desc = edge_data.get("relationship_description", "")
            edges.append(
                {"source": source_id, "target": target_id, "**": f"{relationship_label}: {relationship_desc}"}
            )
        return yaml.dump(
            {
                "knowledge": yaml.dump(nodes, allow_unicode=True),
                "context": yaml.dump(edges, allow_unicode=True),
            },
            allow_unicode=True,
        )

    # -- CustomQueryEngine surface --------------------------------------

    async def acustom_query(self, query_str: str, **kwargs) -> STR_OR_RESPONSE_TYPE:
        return await self._acustom_query(query_str, **kwargs)

    def custom_query(self, query_str: str, **kwargs) -> str:
        return _run_async(self._acustom_query(query_str, **kwargs))

    async def _acustom_query(self, query_str: str, **kwargs) -> str:
        context_query = kwargs.get("parameter", "")
        answer, _ = await self._query_plan(
            query_str, context=context_query, include_graph=self.include_graph, **kwargs
        )
        return answer

    async def _query_plan(self, query, context=None, include_graph=True, **kwargs):
        knowledge: list[dict] = []
        if include_graph:
            for node in self.graph_store.graph.get_all_nodes(
                label_type="entity",
                context=f"{context}. {query}. {self.data_instruction}",
                category_id=kwargs.get("category_id"),
            ):
                if node.label == "text_chunk":
                    continue
                if len(node.name) < 100:
                    knowledge.append(
                        {
                            node.label: node.id,
                            "name": node.properties.get("entity_description"),
                            "category_id": node.properties.get("category_id"),
                        }
                    )
        logger.info("Query: %s with knowledge: %s", query, knowledge)

        executor = QueryExecutor(self, llm=self.plan_llm, language=self.language)
        if self.max_queries == 1:
            plans = [{"is_query": True, "term": query}]
        else:
            plans, _ = executor.generate_plans(
                query,
                max_queries=self.max_queries,
                instruction=self.data_instruction,
                knowledge=yaml.dump(knowledge, allow_unicode=True),
                context=context if context is not None else "",
            )
        if plans is None:
            return "", []

        is_memory = self.max_queries == 1
        return await executor.execute_plans(
            plans,
            yaml.dump(knowledge, allow_unicode=True),
            llm=self.llm,
            stream_handler=self.stream_handler,
            is_memory=is_memory,
            **kwargs,
        )

    def get_nodes(self, query_str, similarity_top_k=40, similarity_score=0.5, **kwargs):
        sub_retrievers = [self.tracking]
        return self.index.as_retriever(
            similarity_top_k=similarity_top_k,
            similarity_score=similarity_score,
            sub_retrievers=sub_retrievers,
        ).retrieve(query_str)

    def compute_page_rank(self, personalize_matrix, **kwargs):
        score = self.graph_store.pagerank(personalize_matrix, **kwargs)
        if score is not None:
            return [(_id, s) for _id, s in score if s > PAGERANK_SCORE_THRESHOLD]
        return [(v, _i) for _i, v in enumerate(personalize_matrix)]

    def get_community_relations(self, ids):
        kg_ids = self.index.property_graph_store.get(ids=ids)
        return self.index.property_graph_store.get_rel_map(kg_ids, depth=3, ignore_rels=[KG_SOURCE_REL])

    async def aggregate_answers(self, community_answers, query, llm=None, citation=None):
        """Aggregate community answers via :meth:`KnowledgeLLM.aggregate_answers`.

        The ``citation`` parameter is preserved in the API for back-compat;
        post-processing of UUID -> file citations is left to the caller in v1.
        """
        active_llm: KnowledgeLLM = llm if llm is not None else self.llm

        # Normalise community_answers into list[str].
        if isinstance(community_answers, str):
            snippets = [community_answers]
        elif isinstance(community_answers, (list, tuple)):
            snippets = [str(s) for s in community_answers]
        else:
            snippets = [str(community_answers)]

        try:
            return await asyncio.to_thread(
                active_llm.aggregate_answers, snippets, query, self.language
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("aggregate_answers failed: %s", exc)
            return f"Error: {exc}"
