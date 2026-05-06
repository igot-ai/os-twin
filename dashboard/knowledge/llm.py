"""Multi-provider LLM wrapper for knowledge extraction, query planning, and answer aggregation.

Designed for graceful degradation: when no model or API key is configured, every method
returns a sensible empty / fallback value so callers don't have to special-case
the missing-key path.

Uses ``dashboard.llm_client`` (unified multi-provider abstraction) instead of
the legacy Anthropic SDK.  Providers are auto-detected from the model name or
can be set explicitly via ``provider`` (or ``OSTWIN_KNOWLEDGE_LLM_PROVIDER``).

EPIC-003 Hardening: LLM calls honour OSTWIN_KNOWLEDGE_LLM_TIMEOUT (default 60s).
On timeout, log WARNING and return graceful empty result.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any

from dashboard.knowledge.audit import LLM_TIMEOUT  # noqa: WPS433
from dashboard.knowledge.config import LLM_MODEL, LLM_PROVIDER
from dashboard.knowledge.metrics import get_metrics_registry  # noqa: WPS433

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt-service integration
# ---------------------------------------------------------------------------

# Keys in prompts/locales/*.yaml — used by _get_prompt() below.
_KEY_EXTRACT_SYSTEM = "knowledge.extract_system"
_KEY_EXTRACT_USER = "knowledge.extract_user"
_KEY_PLAN_SYSTEM = "knowledge.plan_system"
_KEY_PLAN_USER = "knowledge.plan_user"
_KEY_AGG_SYSTEM = "knowledge.aggregate_system"
_KEY_AGG_USER = "knowledge.aggregate_user"


def _get_prompt(key: str, lang_code: str, **kwargs) -> str | None:
    """Try to fetch a formatted prompt from the centralised prompt service.

    Returns ``None`` on any failure (missing key, missing language, import
    error) so the caller can fall back to the hardcoded template string.

    ``lang_code`` selects the locale (e.g. ``"English"``, ``"vi"``).
    ``**kwargs`` are forwarded as template variables (e.g. ``language=``,
    ``domain=``, ``query=``).
    """
    try:
        from dashboard.prompts import prompt_service  # noqa: WPS433

        return prompt_service.get(key, lang=lang_code, **kwargs)
    except Exception:  # noqa: BLE001
        return None


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
# Async event-loop runner (safe from both sync and async contexts)
# ---------------------------------------------------------------------------

def _run_sync(coro):
    """Execute an async coroutine from sync code.

    If an event loop is already running (e.g. called from asyncio.to_thread),
    we spin up a new loop in a thread. Otherwise we use asyncio.run().
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already inside a loop → use a thread-based loop
    import concurrent.futures
    def runner():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(runner).result()


# ---------------------------------------------------------------------------
# KnowledgeLLM
# ---------------------------------------------------------------------------


class KnowledgeLLM:
    """Multi-provider LLM helper backed by ``dashboard.llm_client``.

    Methods gracefully degrade to empty results when no model or API key is
    configured.  The user must explicitly set a model — there is no hardcoded
    default.

    Provider is auto-detected from the model name (e.g. ``claude-*`` → Anthropic,
    ``gpt-*`` → OpenAI, ``gemini-*`` → Google).  An explicit ``provider``
    parameter overrides the auto-detection.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> None:
        # Load from MasterSettings if not explicitly provided
        from dashboard.lib.settings.resolver import get_settings_resolver

        resolver = get_settings_resolver()
        master = resolver.get_master_settings()
        knowledge_cfg = master.knowledge if master.knowledge else None

        if provider is None:
            provider = (
                knowledge_cfg.knowledge_llm_backend
                if knowledge_cfg and knowledge_cfg.knowledge_llm_backend
                else LLM_PROVIDER
            )
            
        if model is None:
            model = (
                knowledge_cfg.knowledge_llm_model
                if knowledge_cfg and knowledge_cfg.knowledge_llm_model
                else LLM_MODEL
            )
            
        self.openai_compatible_url = (
            knowledge_cfg.knowledge_llm_compatible_url
            if knowledge_cfg and getattr(knowledge_cfg, "knowledge_llm_compatible_url", "")
            else ""
        )
        
        self.openai_compatible_key = (
            knowledge_cfg.knowledge_llm_compatible_key
            if knowledge_cfg and getattr(knowledge_cfg, "knowledge_llm_compatible_key", "")
            else ""
        )

        # Resolve model: explicit > config (env / MasterSettings)
        self.model: str = model or ""
        # Resolve provider: explicit > config env > auto-detect
        self.provider: str | None = provider or None
        # Resolve API key: explicit > resolved from master_agent
        self._explicit_key: str | None = api_key
        self._client: Any | None = None  # cached LLMClient instance

    # -- Capability -----------------------------------------------------

    def is_available(self) -> bool:
        """True iff a model is configured AND an API key can be resolved.

        This is checked before every LLM call site; returning False triggers
        graceful degradation (empty results, no crash).
        """
        if not self.model:
            return False
        return bool(self._resolve_api_key())

    # -- Internals ------------------------------------------------------

    def _resolve_api_key(self) -> str | None:
        """Resolve an API key for the configured provider.

        Priority: explicit key > env var > Settings vault (providers) > master_agent vault.
        """
        if self._explicit_key:
            return self._explicit_key

        # Detect provider for key lookup
        provider = self._effective_provider()

        if provider == "openai-compatible" and getattr(self, "openai_compatible_key", ""):
            return self.openai_compatible_key

        # 1. Try standard env vars first (fast path, no imports)
        from dashboard.llm_client import PROVIDER_API_KEYS  # noqa: WPS433
        env_name = PROVIDER_API_KEYS.get(provider)
        if env_name:
            val = os.environ.get(env_name)
            if val:
                return val

        # 2. Settings vault — the Settings UI stores provider API keys here
        #    (scope="providers", key=provider_name). This is the binding to
        #    the master agent's provider configuration.
        try:
            from dashboard.lib.settings.vault import get_vault  # noqa: WPS433
            key = get_vault().get("providers", provider)
            if key:
                return key
        except Exception as exc:  # noqa: BLE001
            logger.debug("vault.get('providers', %s) failed: %s", provider, exc)

        # 3. Fall back to master_agent.get_api_key (auth.json + vault)
        try:
            from dashboard.master_agent import get_api_key  # noqa: WPS433
            key = get_api_key(provider)
            if key:
                return key
        except Exception as exc:  # noqa: BLE001
            logger.debug("master_agent.get_api_key(%s) failed: %s", provider, exc)

        return None

    def _effective_provider(self) -> str:
        """Return the provider name (explicit or auto-detected from model)."""
        from dashboard.llm_client import _detect_provider_from_model  # noqa: WPS433
        return _detect_provider_from_model(self.model)

    def _get_client(self) -> Any:
        """Lazy-create the LLMClient via the unified factory."""
        if self._client is not None:
            return self._client
        from dashboard.llm_client import LLMConfig, create_client  # noqa: WPS433

        api_key = self._resolve_api_key()
        config = LLMConfig(max_tokens=4096)
        
        provider = self._effective_provider()
        base_url = None
        if provider == "openai-compatible" and getattr(self, "openai_compatible_url", ""):
            base_url = self.openai_compatible_url
            
        self._client = create_client(
            model=self.model,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            config=config,
        )
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
        """Run a single LLM chat call via ``llm_client``. Returns the text content.

        EPIC-003: Honours OSTWIN_KNOWLEDGE_LLM_TIMEOUT (default 60s).
        On timeout, logs WARNING and returns empty string (graceful degradation).
        """
        metrics = get_metrics_registry()
        metrics.counter("llm_calls_total").inc()
        t0 = time.perf_counter()

        from dashboard.llm_client import ChatMessage as CM  # noqa: WPS433

        client = self._get_client()
        # Override max_tokens for this call if different from default
        client.config.max_tokens = max_tokens

        messages = [
            CM(role="system", content=system),
            CM(role="user", content=user),
        ]

        async def _call():
            return await asyncio.wait_for(
                client.chat(messages),
                timeout=LLM_TIMEOUT,
            )

        try:
            response = _run_sync(_call())
            result_text = response.content or ""
            elapsed = time.perf_counter() - t0
            metrics.histogram("llm_latency_seconds").observe(elapsed)
            return result_text
        except TimeoutError:
            metrics.counter("llm_errors_total").inc()
            logger.warning(
                "llm_timeout: LLM call timed out after %ss (model=%s, provider=%s)",
                LLM_TIMEOUT,
                self.model,
                self._effective_provider(),
            )
            return ""
        except Exception as exc:  # noqa: BLE001
            metrics.counter("llm_errors_total").inc()
            exc_name = type(exc).__name__
            if "Timeout" in exc_name or "timeout" in str(exc).lower():
                logger.warning(
                    "llm_timeout: LLM call timed out after %ss (model=%s, provider=%s)",
                    LLM_TIMEOUT,
                    self.model,
                    self._effective_provider(),
                )
                return ""
            logger.error("LLM call failed (provider=%s): %s", self._effective_provider(), exc)
            return ""

    # -- Public API -----------------------------------------------------

    def extract_entities(
        self, text: str, language: str = "English", domain: str = ""
    ) -> tuple[list[dict], list[dict]]:
        """Extract entities and relationships from `text`.

        Returns ([entity_dict], [relationship_dict]). When unavailable: ([], []).
        """
        system = _get_prompt(
            _KEY_EXTRACT_SYSTEM, language, language=language, domain=domain or "general",
        ) or _EXTRACT_SYSTEM.format(language=language, domain=domain or "general")
        user = _get_prompt(
            _KEY_EXTRACT_USER, language, text=text,
        ) or _EXTRACT_USER.format(text=text)
        raw = self._complete(system, user, max_tokens=8192)
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
        system = _get_prompt(
            _KEY_PLAN_SYSTEM, language,
            knowledge_summary=knowledge_summary or "(no summary provided)",
            language=language,
            max_steps=max_steps,
        ) or _PLAN_SYSTEM.format(
            knowledge_summary=knowledge_summary or "(no summary provided)",
            language=language,
            max_steps=max_steps,
        )
        user = _get_prompt(
            _KEY_PLAN_USER, language, query=query,
        ) or _PLAN_USER.format(query=query)
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
        system = _get_prompt(
            _KEY_AGG_SYSTEM, language, language=language,
        ) or _AGG_SYSTEM.format(language=language)
        user = _get_prompt(
            _KEY_AGG_USER, language, query=query, summaries="\n---\n".join(snippets),
        ) or _AGG_USER.format(query=query, summaries="\n---\n".join(snippets))
        raw = self._complete(system, user, max_tokens=2048)
        if not raw:
            return "\n\n".join(snippets)
        return raw.strip()
