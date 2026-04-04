#!/usr/bin/env python3
"""
Compatibility shim for importing `memory-core.py` as `memory_core`.

This executes the hyphenated implementation file into the current module
namespace so module-level state like `AGENT_OS_ROOT` behaves exactly as tests
and helper scripts expect.
"""

from __future__ import annotations

import os

_CORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory-core.py")

with open(_CORE_PATH, "r", encoding="utf-8") as _f:
    _source = _f.read()

exec(compile(_source, _CORE_PATH, "exec"), globals(), globals())
