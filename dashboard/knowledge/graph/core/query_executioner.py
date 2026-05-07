"""Plan + execute multi-step queries against a graph-RAG engine.

Refactor notes (EPIC-001):
- Replaced ``app.models.LLMChatMessage`` with a local Pydantic ``ChatMessage``.
- ``self.llm`` is a :class:`KnowledgeLLM`. We call its ``plan_query`` and
  ``aggregate_answers`` methods directly instead of crafting custom messages.
- The Vietnamese-locked legacy prompts in ``prompt.py`` are no longer used by
  this module — they remain in the file for back-compat with downstream
  consumers but the planner here goes through ``KnowledgeLLM.plan_query``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel

from dashboard.knowledge.graph.utils import filter_metadata_fields

logger = logging.getLogger(__name__)

METADATA_FIELDS = ["entity_description", "filename", "file_path", "page_range", "page_number"]
FILE_METADATA_FIELDS = ["file_path", "filename", "page_range", "page_number"]


class ChatMessage(BaseModel):
    """Minimal chat-message model (replaces app.models.LLMChatMessage)."""

    role: str
    content: str


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
        # Cache for citation metadata lookups.
        self._uuid_metadata_cache: dict[str, Any] = {}

    # -- Citation helpers ----------------------------------------------

    def _filter_citation(self, metadata):
        try:
            if not metadata or not isinstance(metadata, dict):
                return {}
            if "target_id" in metadata and "source_id" in metadata:
                target_id = metadata.get("target_id", "")
                source_id = metadata.get("source_id", "")
                if target_id:
                    meta_citation = self.engine.create_citation(metadata)
                    if meta_citation:
                        return meta_citation
                    candidates = []
                    if self._is_uuid_format(target_id):
                        candidates.append(target_id)
                    if self._is_uuid_format(source_id) and source_id != target_id:
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
        if not isinstance(value, str):
            return False
        try:
            obj = uuid.UUID(value)
        except ValueError:
            return False
        return str(obj) == value.lower()

    @staticmethod
    def _extract_file_metadata(properties):
        if not properties or not any(key in properties for key in FILE_METADATA_FIELDS):
            return None
        return {
            "file_path": properties.get("file_path", ""),
            "filename": properties.get("filename", ""),
            "page_range": properties.get("page_range", ""),
            "page_number": properties.get("page_number", ""),
            "entity_description": properties.get("entity_description", ""),
        }

    def _get_document_metadata_by_uuid(self, key: str):
        if key in self._uuid_metadata_cache:
            return self._uuid_metadata_cache[key]
        try:
            result = self._get_metadata_from_property_graph(key)
            self._uuid_metadata_cache[key] = result
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error("Error looking up document metadata for %s: %s", key, exc)
            self._uuid_metadata_cache[key] = None
            return None

    def _get_metadata_from_property_graph(self, key: str):
        if not (hasattr(self.engine, "index") and hasattr(self.engine.index, "property_graph_store")):
            return None
        try:
            nodes = self.engine.index.property_graph_store.get(ids=[key])
            for node in nodes:
                return self._extract_file_metadata(node.properties or {})
        except Exception as exc:  # noqa: BLE001
            logger.error("Error getting node by ID %s: %s", key, exc)
        return None

    # -- Planning + execution ------------------------------------------

    def generate_plans(
        self,
        query,
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
            plans.append({"is_query": False, "term": f"{query} {context}"})
        return plans, ""

    async def execute_plans(
        self,
        plans: list[dict],
        context,
        llm=None,
        query=None,
        stream_handler=None,
        is_memory: bool = False,
        **kwargs,
    ):
        if llm is None:
            llm = self.llm
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
                    context = f"{plan.get('term')}. {graph}. ({query})"
                    answer = await self.engine.aggregate_answers(
                        list(citation.values()), context, llm
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Error in plan execution: %s", exc)
                    continue
        return answer, nodes_collected
