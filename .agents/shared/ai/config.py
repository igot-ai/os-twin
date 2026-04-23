"""AI Gateway configuration.

Reads from the dashboard settings system (``MasterSettings``) when
available. Falls back to environment variables when running standalone
(e.g. the memory MCP server without the dashboard).

Config is cached after first load.  Call ``reset_config()`` to force
a re-read (done automatically when ``PUT /api/settings/providers``
or ``PUT /api/settings/ai`` is called on the dashboard).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AIConfig:
    """Resolved AI gateway configuration."""

    # Provider prefix for litellm (e.g. "vertex_ai", "gemini")
    provider: str = "vertex_ai"

    # Completion models
    completion_model: str = "gemini-3-flash-preview"
    knowledge_model: Optional[str] = None  # for knowledge graph (e.g. Claude)
    memory_model: Optional[str] = None  # for memory analysis

    # Embedding models
    cloud_embedding_model: str = "text-embedding-005"
    local_embedding_model: str = "all-MiniLM-L6-v2"

    # Vertex AI specifics
    vertex_project: Optional[str] = None
    vertex_location: str = "global"
    vertex_auth_mode: str = "oauth"
    vertex_claude_location: str = "us-east5"

    # Runtime
    timeout: int = 60
    max_retries: int = 2

    def full_model(self, purpose: Optional[str] = None) -> str:
        """Return the fully-qualified model ID for litellm.

        Args:
            purpose: Optional purpose hint (``"knowledge"``, ``"memory"``).
                Selects a per-purpose model override if configured.
        """
        if purpose == "knowledge" and self.knowledge_model:
            model = self.knowledge_model
        elif purpose == "memory" and self.memory_model:
            model = self.memory_model
        else:
            model = self.completion_model

        # Already fully qualified (e.g. "vertex_ai/gemini-3-flash-preview")
        if "/" in model:
            return model
        return f"{self.provider}/{model}"

    def full_cloud_embedding_model(self) -> str:
        """Return the fully-qualified cloud embedding model ID."""
        m = self.cloud_embedding_model
        if "/" in m:
            return m
        return f"{self.provider}/{m}"


# ---------------------------------------------------------------------------
# Singleton cache
# ---------------------------------------------------------------------------

_config: Optional[AIConfig] = None


def get_config() -> AIConfig:
    """Load config from settings system (or env fallback).  Cached."""
    global _config
    if _config is not None:
        return _config

    try:
        _config = _load_from_settings()
        logger.info("AI config loaded from settings system")
    except Exception as exc:
        logger.info("Settings system unavailable (%s), falling back to env vars", exc)
        _config = _load_from_env()

    return _config


def reset_config() -> None:
    """Invalidate cached config.  Next ``get_config()`` re-reads."""
    global _config
    _config = None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_from_settings() -> AIConfig:
    """Read from ``MasterSettings.providers`` + ``MasterSettings.ai``."""
    from dashboard.lib.settings import SettingsResolver

    resolver = SettingsResolver()
    settings = resolver.load()

    # --- providers.google ---
    google = settings.providers.google if settings.providers else None
    if not google or not google.enabled:
        raise ValueError("Google provider not configured or disabled in settings")

    is_vertex = (google.deployment_mode or "").lower() == "vertex"
    provider = "vertex_ai" if is_vertex else "gemini"

    # --- providers.anthropic ---
    anthropic = settings.providers.anthropic if settings.providers else None
    vertex_claude_location = "us-east5"
    if anthropic and hasattr(anthropic, "vertex_claude_location"):
        vertex_claude_location = anthropic.vertex_claude_location or "us-east5"

    # --- ai namespace ---
    ai_ns = getattr(settings, "ai", None)

    completion_model = (
        (ai_ns.completion_model if ai_ns and ai_ns.completion_model else None)
        or google.default_model
        or "gemini-3-flash-preview"
    )
    knowledge_model = ai_ns.knowledge_model if ai_ns else None
    memory_model = ai_ns.memory_model if ai_ns else None
    cloud_embedding = (
        (ai_ns.cloud_embedding_model if ai_ns and ai_ns.cloud_embedding_model else None)
        or (google.embedding_model if hasattr(google, "embedding_model") else None)
        or "text-embedding-005"
    )
    local_embedding = (
        ai_ns.local_embedding_model if ai_ns else None
    ) or "all-MiniLM-L6-v2"
    timeout = (
        ai_ns.timeout_seconds if ai_ns and hasattr(ai_ns, "timeout_seconds") else 60
    )
    max_retries = ai_ns.max_retries if ai_ns and hasattr(ai_ns, "max_retries") else 2

    return AIConfig(
        provider=provider,
        completion_model=completion_model,
        knowledge_model=knowledge_model,
        memory_model=memory_model,
        cloud_embedding_model=cloud_embedding,
        local_embedding_model=local_embedding,
        vertex_project=google.project_id,
        vertex_location=google.vertex_location or "global",
        vertex_auth_mode=google.vertex_auth_mode or "oauth",
        vertex_claude_location=vertex_claude_location,
        timeout=timeout,
        max_retries=max_retries,
    )


def _load_from_env() -> AIConfig:
    """Fallback: read from environment variables.

    These are typically set by ``_sync_vertex_env()`` in the settings route,
    so even without the dashboard the values are correct.
    """
    is_vertex = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))
    provider = "vertex_ai" if is_vertex else "gemini"

    return AIConfig(
        provider=provider,
        completion_model=os.environ.get("LLM_MODEL", "gemini-3-flash-preview"),
        cloud_embedding_model=os.environ.get(
            "LLM_CLOUD_EMBEDDING_MODEL", "text-embedding-005"
        ),
        local_embedding_model=os.environ.get(
            "LLM_LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
        ),
        vertex_project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        vertex_location=os.environ.get("VERTEX_LOCATION", "global"),
        timeout=int(os.environ.get("LLM_TIMEOUT", "60")),
        max_retries=int(os.environ.get("LLM_MAX_RETRIES", "2")),
    )
