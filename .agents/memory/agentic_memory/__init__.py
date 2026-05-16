"""Backward-compat shim: all implementation has moved to dashboard.agentic_memory.

This package re-exports every public name so that existing code using
``from agentic_memory.X import Y`` continues to work.
"""

import sys as _sys
from pathlib import Path as _Path

# Ensure the project root (containing dashboard/) is on sys.path
_project_root = _Path(__file__).resolve().parent.parent.parent.parent
if str(_project_root) not in _sys.path:
    _sys.path.insert(0, str(_project_root))

from dashboard.agentic_memory import *  # noqa: F401,F403
from dashboard.agentic_memory.config import *  # noqa: F401,F403
from dashboard.agentic_memory.memory_note import *  # noqa: F401,F403
from dashboard.agentic_memory.memory_system import *  # noqa: F401,F403
from dashboard.agentic_memory.memory_llm import *  # noqa: F401,F403
from dashboard.agentic_memory.retrievers import *  # noqa: F401,F403
from dashboard.agentic_memory.knowledge_link import *  # noqa: F401,F403
