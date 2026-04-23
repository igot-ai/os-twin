"""Knowledge LLM — entity extraction, query planning, and answer aggregation.

Routes all LLM calls through shared.ai gateway (Vertex AI / litellm).
Designed for graceful degradation: when no AI config is available, every
method returns a sensible empty / fallback value.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from dashboard.knowledge.config import LLM_MODEL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt templates (English; language-parameterized at call site)
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM = """You are an expert knowledge-graph engineer. Given a chunk of text,
extract the entities and relationships that appear in it. Respond with strict JSON only.

Reply in {language} for entity descriptions and relationship descriptions.

Output schema:
{{
  "entities": [
    {{"name": "<canonical name>", "type": "<category>", "description": "<short description>"}}
  ],
  "relationships": [
    {{"source": "<entity name>", "target": "<entity name>", "relation": "<verb-phrase>", "description": "<short description>"}}
  ]
}}

Rules:
- Only return JSON, no prose, no markdown fences.
- Entity names must match exactly between the entities list and the relationships list.
- Keep descriptions under 200 characters.
- Domain context (if any): {domain}
"""

_EXTRACT_USER = "Extract entities and relationships from the following text:\n\n{text}"


_PLAN_SYSTEM = """You are a query-planning expert. Break a user question down into a small
sequence of sub-queries that can be executed against a knowledge graph + vector store.

Knowledge available (summary):
{knowledge_summary}

Reply in {language}.

Respond with strict JSON: a list of step objects. Each step has:
  - "term": str  — the sub-query text
  - "is_query": bool — True if this step retrieves data, False if it synthesises
  - "category_id": str (optional) — category to scope the retrieval

Cap the plan at {max_steps} steps. Last step should typically be a synthesis (is_query=false).
"""

_PLAN_USER = "User question: {query}\n\nReturn JSON only."


_AGG_SYSTEM = """You are a senior research-assistant. You will be given a list of community-summary
snippets retrieved from a knowledge graph plus the user's question. Synthesise a single,
coherent answer in {language}, citing the snippets where appropriate.

Rules:
- Only use facts that appear in the provided snippets.
- If the snippets don't answer the question, say so.
- Keep the answer focused and under 500 words unless the question asks for detail.
"""

_AGG_USER = (
    "User question: {query}\n\n"
    "Community summaries:\n{summaries}\n\n"
    "Write the final answer."
)


# ---------------------------------------------------------------------------
# KnowledgeLLM
# ---------------------------------------------------------------------------


class KnowledgeLLM:
    """Lightweight Anthropic-backed helper.

    Methods gracefully degrade to empty results when no API key is configured.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.model: str = model or LLM_MODEL
        # api_key kept for is_available() — actual auth goes through shared.ai (ADC)
        self.api_key: str | None = (
            api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY")
        )

    # -- Capability -----------------------------------------------------

    def is_available(self) -> bool:
        """True iff an API key or ADC is configured."""
        if self.api_key:
            return True
        # Check if shared.ai can load config (ADC / Vertex)
        try:
            from shared.ai.config import get_config

            get_config()
            return True
        except Exception:
            return False

    @staticmethod
    def _extract_json(text: str) -> Any:
        """Pull the first JSON object/array out of a text blob."""
        text = text.strip()
        # Strip markdown fences if present
        fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        # Try the whole thing first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Find first {...} or [...]
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                logger.debug("Failed to parse JSON from LLM response")
        return None

    def _complete(self, system: str, user: str, max_tokens: int = 2048) -> str:
        """Run a completion via shared.ai gateway. Returns the text content."""
        try:
            from shared.ai import get_completion

            return get_completion(
                user,
                system=system,
                purpose="knowledge",
                model=self.model if "/" in self.model else None,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Knowledge LLM call failed: %s", exc)
            return ""

    # -- Public API -----------------------------------------------------

    def extract_entities(
        self, text: str, language: str = "English", domain: str = ""
    ) -> tuple[list[dict], list[dict]]:
        """Extract entities and relationships from `text`.

        Returns ([entity_dict], [relationship_dict]). When unavailable: ([], []).
        """
        if not self.is_available():
            return [], []
        system = _EXTRACT_SYSTEM.format(language=language, domain=domain or "general")
        user = _EXTRACT_USER.format(text=text)
        raw = self._complete(system, user, max_tokens=4096)
        if not raw:
            return [], []
        parsed = self._extract_json(raw)
        if not isinstance(parsed, dict):
            return [], []
        entities = parsed.get("entities", []) or []
        relations = parsed.get("relationships", []) or []
        # Defensive: filter out non-dict items
        entities = [e for e in entities if isinstance(e, dict)]
        relations = [r for r in relations if isinstance(r, dict)]
        return entities, relations

    def plan_query(
        self,
        query: str,
        knowledge_summary: str = "",
        max_steps: int = 3,
        language: str = "English",
    ) -> list[dict]:
        """Decompose `query` into a list of step dicts.

        Returns [{term, is_query, category_id?}]. When unavailable, returns a
        single retrieval step with the verbatim query.
        """
        if not self.is_available():
            return [{"term": query, "is_query": True}]
        system = _PLAN_SYSTEM.format(
            knowledge_summary=knowledge_summary or "(no summary provided)",
            language=language,
            max_steps=max_steps,
        )
        user = _PLAN_USER.format(query=query)
        raw = self._complete(system, user, max_tokens=2048)
        if not raw:
            return [{"term": query, "is_query": True}]
        parsed = self._extract_json(raw)
        if not isinstance(parsed, list) or not parsed:
            return [{"term": query, "is_query": True}]
        # Normalise step shape
        steps: list[dict] = []
        for step in parsed:
            if not isinstance(step, dict):
                continue
            term = step.get("term")
            if not isinstance(term, str) or not term:
                continue
            normalised = {"term": term, "is_query": bool(step.get("is_query", True))}
            if "category_id" in step and step["category_id"]:
                normalised["category_id"] = str(step["category_id"])
            steps.append(normalised)
        if not steps:
            return [{"term": query, "is_query": True}]
        return steps

    def aggregate_answers(
        self,
        community_summaries: list[str],
        query: str,
        language: str = "English",
    ) -> str:
        """Aggregate per-community answers into a single response.

        When unavailable: returns "\\n\\n".join(community_summaries).
        """
        snippets = [s for s in community_summaries if isinstance(s, str) and s.strip()]
        if not self.is_available():
            return "\n\n".join(snippets)
        if not snippets:
            return ""
        system = _AGG_SYSTEM.format(language=language)
        user = _AGG_USER.format(query=query, summaries="\n---\n".join(snippets))
        raw = self._complete(system, user, max_tokens=2048)
        if not raw:
            return "\n\n".join(snippets)
        return raw.strip()
