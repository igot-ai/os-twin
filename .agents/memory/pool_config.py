"""Configuration for the Memory Pool.

Loads defaults from the ``pool`` section of ``config.default.json``,
then lets environment variables override any value.

Env-var mapping (all prefixed with ``MEMORY_POOL_``):
    MEMORY_POOL_IDLE_TIMEOUT       → idle_timeout_s
    MEMORY_POOL_MAX_INSTANCES      → max_instances
    MEMORY_POOL_EVICTION           → eviction_policy
    MEMORY_POOL_ML_PRELOAD         → ml_preload
    MEMORY_POOL_ML_TIMEOUT         → ml_ready_timeout_s
    MEMORY_POOL_SYNC_INTERVAL      → sync_interval_s
    MEMORY_POOL_SYNC_ON_KILL       → sync_on_kill
    MEMORY_POOL_ALLOWED_PATHS      → allowed_paths  (comma-separated)
    MEMORY_POOL_SWEEP_INTERVAL     → sweep_interval_s
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


_CONFIG_DIR = Path(__file__).resolve().parent


def _env_str(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    return int(val) if val is not None else default


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes")


@dataclass
class PoolConfig:
    """Configuration for the MemoryPool."""

    # --- Instance lifecycle ---
    idle_timeout_s: int = 300
    """Kill an instance after this many seconds of inactivity.
    0 means never kill (instances live for the dashboard lifetime)."""

    max_instances: int = 10
    """Maximum number of concurrent AgenticMemorySystem instances."""

    eviction_policy: str = "lru"
    """Policy when max_instances is reached: 'lru', 'oldest', or 'none'.
    'none' rejects new connections when the pool is full."""

    # --- ML preload ---
    ml_preload: bool = True
    """Start loading heavy ML libraries (torch, transformers) on pool creation."""

    ml_ready_timeout_s: int = 30
    """Max seconds to wait for ML preload before failing a new slot creation."""

    # --- Per-instance sync ---
    sync_interval_s: int = 60
    """Auto-sync interval per memory instance (seconds)."""

    sync_on_kill: bool = True
    """Run a final sync_to_disk() before killing an idle instance."""

    # --- Security ---
    allowed_paths: Optional[List[str]] = None
    """Restrict persist_dir to paths starting with one of these prefixes.
    None means any path is accepted."""

    # --- Idle sweep ---
    sweep_interval_s: int = 30
    """How often the background sweep thread checks for idle slots (seconds)."""


def load_pool_config() -> PoolConfig:
    """Build a PoolConfig from config.default.json ``pool`` section + env vars."""
    config_path = _CONFIG_DIR / "config.default.json"
    pool_d: dict = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            pool_d = json.load(f).get("pool", {})

    allowed_env = os.getenv("MEMORY_POOL_ALLOWED_PATHS")
    if allowed_env is not None:
        allowed = [p.strip() for p in allowed_env.split(",") if p.strip()] or None
    elif "allowed_paths" in pool_d and pool_d["allowed_paths"] is not None:
        allowed = pool_d["allowed_paths"]
    else:
        allowed = None

    return PoolConfig(
        idle_timeout_s=_env_int(
            "MEMORY_POOL_IDLE_TIMEOUT",
            pool_d.get("idle_timeout_s", 300),
        ),
        max_instances=_env_int(
            "MEMORY_POOL_MAX_INSTANCES",
            pool_d.get("max_instances", 10),
        ),
        eviction_policy=_env_str(
            "MEMORY_POOL_EVICTION",
            pool_d.get("eviction_policy", "lru"),
        ),
        ml_preload=_env_bool(
            "MEMORY_POOL_ML_PRELOAD",
            pool_d.get("ml_preload", True),
        ),
        ml_ready_timeout_s=_env_int(
            "MEMORY_POOL_ML_TIMEOUT",
            pool_d.get("ml_ready_timeout_s", 30),
        ),
        sync_interval_s=_env_int(
            "MEMORY_POOL_SYNC_INTERVAL",
            pool_d.get("sync_interval_s", 60),
        ),
        sync_on_kill=_env_bool(
            "MEMORY_POOL_SYNC_ON_KILL",
            pool_d.get("sync_on_kill", True),
        ),
        allowed_paths=allowed,
        sweep_interval_s=_env_int(
            "MEMORY_POOL_SWEEP_INTERVAL",
            pool_d.get("sweep_interval_s", 30),
        ),
    )
