"""Plan + execute multi-step queries against a graph-RAG engine.

Refactor notes (EPIC-001):
- Replaced ``app.models.LLMChatMessage`` with a local Pydantic ``ChatMessage``.
- ``self.llm`` is a :class:`KnowledgeLLM`. We call its ``plan_query`` and
  ``aggregate_answers`` methods directly instead of crafting custom messages.
- The Vietnamese-locked legacy prompts in ``prompt.py`` are no longer used by
  this module — they remain in the file for back-compat with downstream
  consumers but the planner here goes through ``KnowledgeLLM.plan_query``.

Shared citation utilities are now imported from
:mod:`dashboard.knowledge.graph.core.citation` — the old names
(``_is_uuid_format``, ``FILE_METADATA_FIELDS``, etc.) are re-exported here
for backward compatibility.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from dashboard.knowledge.graph.core.citation import (
    FILE_METADATA_FIELDS,
    build_citation_dict,
    extract_file_metadata,
    is_uuid,
    resolve_chunk_metadata,
)
from dashboard.knowledge.graph.utils import filter_metadata_fields

logger = logging.getLogger(__name__)

METADATA_FIELDS = ["entity_description", "filename", "file_path", "page_range", "page_number"]

# Backward-compat alias — existing code that imports this still works.
_is_uuid_format = is_uuid


class QueryExecutor:
    """Plan and execute multi-step queries.

    The ``llm`` parameter is a :class:`dashboard.knowledge.llm.KnowledgeLLM`
    instance. Per EPIC-001 it owns its own prompt templates; we just call
    ``plan_query`` and ``aggregate_answers``.
    """

    def __init__(self, engine, llm, language: str) -> None:
        self.engine = engine
        self.llm = llm
        self.language = language
        self._uuid_metadata_cache: dict[str, Any] = {}

    # -- Citation helpers ----------------------------------------------

    def _filter_citation(self, metadata) -> dict[str, Any]:
        try:
            if not metadata or not isinstance(metadata, dict):
                return {}
            if "target_id" in metadata and "source_id" in metadata:
                target_id = metadata.get("target_id", "")
                if target_id:
                    index = getattr(self.engine, "index", None)
                    meta_citation = build_citation_dict(metadata, index)
                    if meta_citation:
                        return meta_citation
                    candidates = []
                    if is_uuid(target_id):
                        candidates.append(target_id)
                    source_id = metadata.get("source_id", "")
                    if is_uuid(source_id) and source_id != target_id:
                        candidates.append(source_id)
                    result: dict[str, Any] = {}
                    for uuid_val in candidates:
                        meta = self._get_document_metadata_by_uuid(uuid_val)
                        if meta:
                            result[uuid_val] = meta
                    return result
                return {}
            return filter_metadata_fields(metadata, METADATA_FIELDS)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error in _filter_citation: %s", exc)
            return {}

    @staticmethod
    def _is_uuid_format(value) -> bool:
        """Backward-compat wrapper around :func:`is_uuid`."""
        return is_uuid(value)

    @staticmethod
    def _extract_file_metadata(properties) -> Optional[dict]:
        """Backward-compat wrapper around :func:`extract_file_metadata`."""
        return extract_file_metadata(properties)

    def _get_document_metadata_by_uuid(self, key: str) -> Optional[dict]:
        if key in self._uuid_metadata_cache:
            return self._uuid_metadata_cache[key]
        try:
            index = getattr(self.engine, "index", None)
            result = resolve_chunk_metadata(index, key)
            if result is not None:
                self._uuid_metadata_cache[key] = result
            else:
                self._uuid_metadata_cache[key] = None
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error("Error looking up document metadata for %s: %s", key, exc)
            self._uuid_metadata_cache[key] = None
            return None

    def _get_metadata_from_property_graph(self, key: str) -> Optional[dict]:
        """Backward-compat wrapper around :func:`resolve_chunk_metadata`."""
        index = getattr(self.engine, "index", None)
        return resolve_chunk_metadata(index, key)

    # -- Planning + execution ------------------------------------------

    def generate_plans(
        self,
        query: str,
        max_queries: int = 5,
        instruction: str = "",
        knowledge=None,
        context=None,
    ):
        """Use ``KnowledgeLLM.plan_query`` to generate a multi-step plan."""
        knowledge_summary = ""
        if knowledge:
            knowledge_summary = str(knowledge)[:2000]
        plans = self.llm.plan_query(
            query=query,
            knowledge_summary=knowledge_summary,
            max_steps=max_queries,
            language=self.language,
        )
        if plans and not any(not p.get("is_query", True) for p in plans):
            safe_query = query or ""
            safe_context = context or ""
            plans.append({"is_query": False, "term": f"Synthesize data for: {safe_query} {safe_context}"})
        return plans, ""

    async def execute_plans(
        self,
        plans: list[dict],
        context,
        llm=None,
        query: str | None = None,
        stream_handler=None,
        is_memory: bool = False,
        **kwargs,
    ):
        if llm is None:
            llm = self.llm
        safe_query = query or ""
        nodes_collected: list = []
        answer = ""
        community_answers = [context]
        citation: dict[str, Any] = {}

        for plan in plans:
            if plan.get("is_query", False):
                if stream_handler:
                    stream_handler(f"THINKING: {plan.get('term')}")
                if plan.get("category_id"):
                    kwargs.update({"category_id": plan["category_id"]})
                items = self.engine.get_nodes(plan.get("term"), **kwargs)
                for n in items:
                    try:
                        cit = self._filter_citation(n.node.metadata)
                        if cit and isinstance(cit, dict):
                            citation.update(cit)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Error processing node citation: %s", exc)
                        continue
                if is_memory:
                    return ".".join(community_answers), nodes_collected
                if stream_handler:
                    stream_handler(f"FOUND: {len(items)}")
            else:
                try:
                    graph = self.engine.graph_result()
                    synthesis_context = f"{plan.get('term')}. {graph}. ({safe_query})"
                    answer = await self.engine.aggregate_answers(
                        list(citation.values()), synthesis_context, llm
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Error in plan execution: %s", exc)
                    continue
        return answer, nodes_collected
