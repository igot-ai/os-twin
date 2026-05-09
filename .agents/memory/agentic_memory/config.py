"""Centralized configuration for the Agentic Memory system.

Loads defaults from ``config.default.json`` (shipped with the package),
then lets environment variables override any value.

Env-var mapping (all prefixed with ``MEMORY_``):
    MEMORY_LLM_BACKEND         → config.llm.backend
    MEMORY_LLM_MODEL           → config.llm.model
    MEMORY_EMBEDDING_BACKEND   → config.embedding.backend
    MEMORY_EMBEDDING_MODEL     → config.embedding.model
    MEMORY_VECTOR_BACKEND      → config.vector.backend
    MEMORY_SIMILARITY_WEIGHT   → config.search.similarity_weight
    MEMORY_DECAY_HALF_LIFE     → config.search.decay_half_life_days
    MEMORY_MAX_LINKS           → config.evolution.max_links
    MEMORY_CONTEXT_AWARE       → config.evolution.context_aware
    MEMORY_CONTEXT_AWARE_TREE  → config.evolution.context_aware_tree
    MEMORY_AUTO_SYNC           → config.sync.auto_sync
    MEMORY_AUTO_SYNC_INTERVAL  → config.sync.auto_sync_interval
    MEMORY_DISABLED_TOOLS      → config.disabled_tools (comma-separated)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

_CONFIG_DIR = Path(__file__).resolve().parent.parent


def _ostwin_home() -> Path:
    configured = os.environ.get("OSTWIN_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".ostwin"


@dataclass
class LLMConfig:
    backend: str = "ollama"
    model: str = "llama3.2"


@dataclass
class EmbeddingConfig:
    """Embedding configuration.

    Valid backends: ``"ollama"``, ``"gemini"``, ``"openai-compatible"``,
    ``"vertex"``.
    """

    backend: str = "ollama"
    model: str = "leoipulsar/harrier-0.6b"


@dataclass
class VectorConfig:
    backend: str = "zvec"


@dataclass
class SearchConfig:
    similarity_weight: float = 0.8
    decay_half_life_days: float = 30.0


@dataclass
class EvolutionConfig:
    max_links: int = 3
    context_aware: bool = True
    context_aware_tree: bool = False


@dataclass
class SyncConfig:
    auto_sync: bool = True
    auto_sync_interval: int = 60  # seconds
    conflict_resolution: str = "last_modified"  # "last_modified" or "llm"


@dataclass
class MemoryConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    vector: VectorConfig = field(default_factory=VectorConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    evolution: EvolutionConfig = field(default_factory=EvolutionConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    disabled_tools: List[str] = field(default_factory=list)


def _load_json_defaults() -> dict:
    """Load defaults from config.default.json if it exists."""
    config_path = _CONFIG_DIR / "config.default.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _env_str(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_float(key: str, default: float) -> float:
    val = os.getenv(key)
    return float(val) if val is not None else default


def _env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    return int(val) if val is not None else default


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes")


def _load_system_settings() -> dict:
    """Load memory settings from the dashboard's system config.

    The dashboard writes user-configured memory settings (backend, model, etc.)
    into ``~/.ostwin/.agents/config.json`` under the ``memory`` key using a
    **flat** schema::

        { "memory": { "llm_backend": "ollama", "llm_model": "...", ... } }

    This function reads that file fresh on every call so the MCP server always
    reflects the latest dashboard settings without a restart.

    Returns a nested dict matching the shape of ``config.default.json`` so it
    can be merged directly into the defaults dict.
    """
    config_path = _ostwin_home() / ".agents" / "config.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

    flat = raw.get("memory", {})
    if not isinstance(flat, dict) or not flat:
        return {}

    # Map the flat dashboard keys → nested config.default.json shape.
    result: dict = {}
    if flat.get("llm_backend") or flat.get("llm_model"):
        result["llm"] = {}
        if flat.get("llm_backend"):
            result["llm"]["backend"] = flat["llm_backend"]
        if flat.get("llm_model"):
            result["llm"]["model"] = flat["llm_model"]

    if flat.get("embedding_backend") or flat.get("embedding_model"):
        result["embedding"] = {}
        if flat.get("embedding_backend"):
            result["embedding"]["backend"] = flat["embedding_backend"]
        if flat.get("embedding_model"):
            result["embedding"]["model"] = flat["embedding_model"]

    if flat.get("vector_backend"):
        result["vector"] = {"backend": flat["vector_backend"]}

    if "context_aware" in flat:
        result.setdefault("evolution", {})["context_aware"] = flat["context_aware"]
    if "auto_sync" in flat:
        result.setdefault("sync", {})["auto_sync"] = flat["auto_sync"]
    if "auto_sync_interval" in flat:
        result.setdefault("sync", {})["auto_sync_interval"] = flat["auto_sync_interval"]
    if "ttl_days" in flat:
        result.setdefault("search", {})["decay_half_life_days"] = float(flat["ttl_days"])

    return result


def load_config() -> MemoryConfig:
    """Build a MemoryConfig by merging: defaults file → system settings → env vars.

    Resolution order (later wins):
      1. ``config.default.json``  — bundled package defaults
      2. ``~/.ostwin/.agents/config.json``  — dashboard / UI settings
      3. ``MEMORY_*`` environment variables  — explicit overrides

    The system settings file is re-read on every call so the MCP server always
    reflects the latest dashboard configuration.
    """
    d = _load_json_defaults()

    # Layer 2: merge dashboard system settings on top of defaults
    sys_settings = _load_system_settings()
    for section_key in ("llm", "embedding", "vector", "search", "evolution", "sync"):
        if section_key in sys_settings:
            d.setdefault(section_key, {}).update(sys_settings[section_key])

    llm_d = d.get("llm", {})
    embedding_d = d.get("embedding", {})
    vector_d = d.get("vector", {})
    search_d = d.get("search", {})
    evo_d = d.get("evolution", {})
    sync_d = d.get("sync", {})

    config = MemoryConfig(
        llm=LLMConfig(
            backend=_env_str("MEMORY_LLM_BACKEND", llm_d.get("backend", "ollama")),
            model=_env_str(
                "MEMORY_LLM_MODEL", llm_d.get("model", "llama3.2")
            ),
        ),
        embedding=EmbeddingConfig(
            backend=_env_str(
                "MEMORY_EMBEDDING_BACKEND", embedding_d.get("backend", "ollama")
            ),
            model=_env_str(
                "MEMORY_EMBEDDING_MODEL",
                embedding_d.get("model", "leoipulsar/harrier-0.6b"),
            ),
        ),
        vector=VectorConfig(
            backend=_env_str("MEMORY_VECTOR_BACKEND", vector_d.get("backend", "zvec")),
        ),
        search=SearchConfig(
            similarity_weight=_env_float(
                "MEMORY_SIMILARITY_WEIGHT",
                search_d.get("similarity_weight", 0.8),
            ),
            decay_half_life_days=_env_float(
                "MEMORY_DECAY_HALF_LIFE",
                search_d.get("decay_half_life_days", 30.0),
            ),
        ),
        evolution=EvolutionConfig(
            max_links=_env_int(
                "MEMORY_MAX_LINKS",
                evo_d.get("max_links", 3),
            ),
            context_aware=_env_bool(
                "MEMORY_CONTEXT_AWARE",
                evo_d.get("context_aware", True),
            ),
            context_aware_tree=_env_bool(
                "MEMORY_CONTEXT_AWARE_TREE",
                evo_d.get("context_aware_tree", False),
            ),
        ),
        sync=SyncConfig(
            auto_sync=_env_bool(
                "MEMORY_AUTO_SYNC",
                sync_d.get("auto_sync", True),
            ),
            auto_sync_interval=_env_int(
                "MEMORY_AUTO_SYNC_INTERVAL",
                sync_d.get("auto_sync_interval", 60),
            ),
            conflict_resolution=_env_str(
                "MEMORY_CONFLICT_RESOLUTION",
                sync_d.get("conflict_resolution", "last_modified"),
            ),
        ),
        disabled_tools=_parse_disabled_tools(d),
    )
    return config


def _parse_disabled_tools(d: dict) -> List[str]:
    """Parse disabled tools from env var (comma-separated) or JSON default."""
    env_val = os.getenv("MEMORY_DISABLED_TOOLS")
    if env_val is not None:
        return [t.strip() for t in env_val.split(",") if t.strip()]
    return d.get("disabled_tools", [])
