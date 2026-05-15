"""Backward-compat shim: import from dashboard.agentic_memory.pool_config instead."""
import sys as _sys
from pathlib import Path as _Path

_project_root = _Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in _sys.path:
    _sys.path.insert(0, str(_project_root))

from dashboard.agentic_memory.pool_config import *  # noqa: F401,F403
from dashboard.agentic_memory.pool_config import PoolConfig, load_pool_config  # noqa: F401
