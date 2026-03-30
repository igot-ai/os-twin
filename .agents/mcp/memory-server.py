#!/usr/bin/env python3
"""
Agent OS — MCP Memory Server

Shared memory layer for cross-room context sharing.
Thin MCP wrapper around memory-core.py functions.

Usage (via mcp-config.json):
    python3 .agents/mcp/memory-server.py

Environment:
    AGENT_OS_ROOT  Root of the agent-os repo (default: ".")
"""

import pathlib
from typing import Annotated, Literal, Optional

# Monkey patch pathlib to bypass macOS SIP PermissionError on .env files
original_is_file = pathlib.Path.is_file
def safe_is_file(self):
    try:
        return original_is_file(self)
    except PermissionError:
        return False
pathlib.Path.is_file = safe_is_file

from pydantic import Field
from mcp.server.fastmcp import FastMCP

import importlib.util, os, sys
_core_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory-core.py")
_spec = importlib.util.spec_from_file_location("memory_core", _core_path)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)

# ── MCP wiring ───────────────────────────────────────────────────────────────

MemoryKind = Literal["artifact", "decision", "interface", "convention", "warning", "code"]

mcp = FastMCP("ostwin-memory", log_level="CRITICAL")


@mcp.tool()
def publish(
    kind: Annotated[MemoryKind, Field(description="Memory kind: artifact | decision | interface | convention | warning")],
    summary: Annotated[str, Field(description="Concise summary of the memory entry (max 4KB). This is the primary content other agents will see.")],
    tags: Annotated[list[str], Field(description="Tags for discovery, e.g. ['auth', 'database', 'users-table']. Use lowercase, hyphenated.")],
    room_id: Annotated[str, Field(description="War-room ID that produced this memory, e.g. 'room-001'")],
    author_role: Annotated[str, Field(description="Role that is publishing: engineer | qa | architect | manager")],
    ref: Annotated[str, Field(description="Epic/task reference, e.g. 'EPIC-001'")],
    detail: Annotated[Optional[str], Field(description="Extended detail (max 16KB). Use for full schemas, API contracts, code snippets. Omit if summary is sufficient.")] = None,
    supersedes: Annotated[Optional[str], Field(description="ID of a previous memory entry this one replaces. The old entry will be excluded from queries.")] = None,
) -> str:
    """Publish a memory entry to the shared memory ledger.

    Use this when you have produced something other agents need to know about:
    - artifact: "I created/modified files X, Y, Z"
    - decision: "I chose approach A over B because..."
    - interface: "Module X exports function Y with signature Z"
    - convention: "All API endpoints use /api/v1/ prefix"
    - warning: "Don't modify file X, it has a known fragility"

    Returns the generated memory ID.
    """
    return core.publish(kind=kind, summary=summary, tags=tags, room_id=room_id,
                        author_role=author_role, ref=ref, detail=detail, supersedes=supersedes)


@mcp.tool()
def query(
    tags: Annotated[Optional[list[str]], Field(description="Filter by tags (OR match — entry must have at least one). Omit for all.")] = None,
    kind: Annotated[Optional[str], Field(description="Filter by kind: artifact | decision | interface | convention | warning. Omit for all.")] = None,
    ref: Annotated[Optional[str], Field(description="Filter by epic/task reference, e.g. 'EPIC-001'. Omit for all.")] = None,
    room_id: Annotated[Optional[str], Field(description="Filter by originating war-room. Omit for all rooms.")] = None,
    author_role: Annotated[Optional[str], Field(description="Filter by author role. Omit for all roles.")] = None,
    exclude_room: Annotated[Optional[str], Field(description="Exclude entries from this room (useful to get context from *other* rooms).")] = None,
    last_n: Annotated[Optional[int], Field(description="Return only the last N matching entries. Omit for all.", ge=1)] = None,
) -> str:
    """Query shared memory with optional filters.

    Returns a JSON array of matching memory entries (excluding superseded ones).
    All filters are optional and combinable. Use this to discover what other
    agents have built, decided, or established.
    """
    return core.query(tags=tags, kind=kind, ref=ref, room_id=room_id,
                      author_role=author_role, exclude_room=exclude_room, last_n=last_n)


@mcp.tool()
def search(
    text: Annotated[str, Field(description="Free-text search query. Matches against summary, tags, ref, and kind.")],
    kind: Annotated[Optional[str], Field(description="Optional kind filter to narrow results.")] = None,
    exclude_room: Annotated[Optional[str], Field(description="Exclude entries from this room.")] = None,
    max_results: Annotated[Optional[int], Field(description="Max results to return (default 10).", ge=1, le=50)] = 10,
) -> str:
    """Full-text search across shared memory.

    Tokenizes the query and scores entries by word overlap across summary,
    tags, ref, and kind fields. Returns results sorted by relevance (best first).
    Use this when you need fuzzy matching — e.g. "authentication flow" will
    match entries tagged with "auth" or summarizing login logic.
    """
    return core.search(text=text, kind=kind, exclude_room=exclude_room, max_results=max_results)


@mcp.tool()
def get_context(
    room_id: Annotated[str, Field(description="War-room ID to generate context for, e.g. 'room-001'")],
    brief_keywords: Annotated[Optional[list[str]], Field(description="Keywords from the room's brief.md to find relevant memories. If omitted, returns all memories from other rooms.")] = None,
    max_entries: Annotated[Optional[int], Field(description="Max memory entries to include (default 15).", ge=1, le=50)] = 15,
) -> str:
    """Generate a curated cross-room context summary for a specific war-room.

    Retrieves memories from ALL OTHER rooms (excludes the requesting room),
    optionally filtered by keywords from the room's brief. Returns a
    markdown-formatted context document ready to be injected into the agent's
    working context.

    Intended for the manager to call before spawning an agent, or for an agent
    to call at the start of its work to understand what other rooms have done.
    """
    return core.get_context(room_id=room_id, brief_keywords=brief_keywords, max_entries=max_entries)


@mcp.tool()
def list_memories(
    kind: Annotated[Optional[str], Field(description="Filter by kind. Omit for all.")] = None,
) -> str:
    """List all live memory entries (lightweight index view).

    Returns a JSON array of {id, ts, kind, room_id, ref, tags, summary_preview}
    objects. Does NOT include detail field — use query() with filters to get
    full entries. Useful for getting an overview of shared knowledge.
    """
    return core.list_memories(kind=kind)


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
