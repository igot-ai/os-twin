"""Backward-compat shim: import from dashboard.agentic_memory.memory_pool instead."""
import sys as _sys
from pathlib import Path as _Path

_project_root = _Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in _sys.path:
    _sys.path.insert(0, str(_project_root))

from dashboard.agentic_memory.memory_pool import *  # noqa: F401,F403
from dashboard.agentic_memory.memory_pool import MemoryPool, MemorySlot  # noqa: F401
