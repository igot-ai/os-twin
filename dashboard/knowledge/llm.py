"""Thin Anthropic wrapper for knowledge extraction, query planning, and answer aggregation.

Designed for graceful degradation: when no API key is provided, every method
returns a sensible empty / fallback value so callers don't have to special-case
the missing-key path.

Heavy `anthropic` SDK is imported lazily inside methods to keep package import
time fast.

EPIC-003 Hardening: LLM calls honour OSTWIN_KNOWLEDGE_LLM_TIMEOUT (default 60s).
On timeout, log WARNING and return graceful empty result.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from dashboard.knowledge.config import LLM_MODEL
from dashboard.knowledge.audit import LLM_TIMEOUT  # noqa: WPS433
from dashboard.knowledge.metrics import get_metrics_registry  # noqa: WPS433

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
        # Resolve key (constructor wins over env)
        self.api_key: str | None = api_key if api_key is not None else os.environ.get(
            "ANTHROPIC_API_KEY"
        )
        self.model: str = model or LLM_MODEL
        self._client: Any | None = None  # cached anthropic.Anthropic instance

    # -- Capability -----------------------------------------------------

    def is_available(self) -> bool:
        """True iff an API key is configured (constructor or env)."""
        return bool(self.api_key)

    # -- Internals ------------------------------------------------------

    def _get_client(self) -> Any:
        """Lazy-import anthropic and cache the client."""
        if self._client is not None:
            return self._client
        # Lazy import — keeps `import dashboard.knowledge` fast.
        import anthropic  # noqa: WPS433

        self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

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
        """Run a single Anthropic Messages call. Returns the text content.

        EPIC-003: Honours OSTWIN_KNOWLEDGE_LLM_TIMEOUT (default 60s).
        On timeout, logs WARNING and returns empty string (graceful degradation).
        """
        metrics = get_metrics_registry()
        metrics.counter("llm_calls_total").inc()
        t0 = time.perf_counter()
        
        client = self._get_client()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                timeout=LLM_TIMEOUT,
            )
            # Anthropic response: content is list of blocks; pick text blocks.
            parts = []
            for block in response.content:
                # Block can be TextBlock or other; both have .text on TextBlock.
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
            result_text = "".join(parts)
            # Record successful latency
            elapsed = time.perf_counter() - t0
            metrics.histogram("llm_latency_seconds").observe(elapsed)
            return result_text
        except Exception as exc:  # noqa: BLE001
            metrics.counter("llm_errors_total").inc()
            # Check for timeout specifically
            exc_name = type(exc).__name__
            if "Timeout" in exc_name or "timeout" in str(exc).lower():
                logger.warning(
                    "llm_timeout: Anthropic call timed out after %ss (model=%s)",
                    LLM_TIMEOUT,
                    self.model,
                )
                return ""
            logger.error("Anthropic call failed: %s", exc)
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
