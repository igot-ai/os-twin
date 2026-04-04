#!/usr/bin/env python3
"""
Thin CLI wrapper around memory-core tool functions.
Used by Pester tests to invoke memory tools from PowerShell.
"""

import json
import sys
import os
import importlib.util

# Load memory-core.py (no MCP dependency)
_core_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory-core.py")
_spec = importlib.util.spec_from_file_location("memory_core", _core_path)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)


def main():
    if len(sys.argv) < 2:
        print("Usage: memory-cli.py <command> [json_args]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    dispatch = {
        "publish": core.publish,
        "query": core.query,
        "search": core.search,
        "get_context": core.get_context,
        "list": core.list_memories,
        "distill": core.distill,
        "knowledge_add": core.knowledge_add,
        "knowledge_list": core.knowledge_list,
        "knowledge_search": core.knowledge_search,
    }

    fn = dispatch.get(cmd)
    if not fn:
        print(f"Unknown command: {cmd}. Valid: {', '.join(dispatch)}", file=sys.stderr)
        sys.exit(1)

    print(fn(**args))


if __name__ == "__main__":
    main()
