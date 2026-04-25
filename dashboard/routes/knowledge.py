"""Dashboard route: Memory MCP over Streamable HTTP.

Mounts the Agentic Memory system as an MCP endpoint at ``/api/knowledge/mcp``
via FastMCP's Streamable HTTP transport.  A ``MemoryPool`` manages one
AgenticMemorySystem instance per unique ``persist_dir``.

Agents specify which memory store to use via a query parameter::

    POST /api/knowledge/mcp?persist_dir=/home/user/project/.memory

The stdio transport in ``mcp_server.py`` is **not** affected — it continues
to work for agents that prefer the legacy per-process model.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Optional
from urllib.parse import parse_qs

from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# sys.path setup — same candidates as amem.py
# ---------------------------------------------------------------------------
_MEMORY_PATH_CANDIDATES = [
    Path.home() / ".ostwin" / ".agents" / "memory",
    Path.home() / ".ostwin" / "A-mem-sys",
    Path(__file__).resolve().parent.parent.parent / ".agents" / "memory",
    Path(__file__).resolve().parent.parent.parent / "A-mem-sys",
]
for _p in _MEMORY_PATH_CANDIDATES:
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pool_config import PoolConfig, load_pool_config  # noqa: E402
from memory_pool import MemoryPool  # noqa: E402

# ---------------------------------------------------------------------------
# Context variable — set by ASGI middleware, read by tool functions
# ---------------------------------------------------------------------------
_current_persist_dir: ContextVar[Optional[str]] = ContextVar(
    "persist_dir", default=None
)

# ---------------------------------------------------------------------------
# Pool singleton — created once, lives for the dashboard process lifetime
# ---------------------------------------------------------------------------
_pool: Optional[MemoryPool] = None


def _get_pool() -> MemoryPool:
    global _pool
    if _pool is None:
        _pool = MemoryPool(config=load_pool_config())
        logger.info("Memory pool created")
    return _pool


def get_pool() -> MemoryPool:
    """Public accessor for the pool singleton (used by api.py shutdown hook)."""
    return _get_pool()


# ---------------------------------------------------------------------------
# Helper: resolve memory system for the current request
# ---------------------------------------------------------------------------
def _get_memory_for_request():
    """Return the AgenticMemorySystem for the current request's persist_dir.

    Raises RuntimeError if no persist_dir was set by the middleware.
    """
    persist_dir = _current_persist_dir.get()
    if not persist_dir:
        raise RuntimeError(
            "No persist_dir specified. Add ?persist_dir=<path> to the URL."
        )
    pool = _get_pool()
    slot = pool.get_or_create(persist_dir)
    pool.touch(persist_dir)
    return slot.system


# ---------------------------------------------------------------------------
# FastMCP instance — independent from mcp_server.py's stdio instance
# ---------------------------------------------------------------------------
from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP(
    "Agentic Memory",
    stateless_http=True,
    instructions=(
        "You have access to a persistent memory system that stores knowledge as "
        "interconnected notes organized in a directory tree. Use it to remember "
        "important information, decisions, context, and learnings across "
        "conversations."
    ),
)


# -- Tools -----------------------------------------------------------------
# Thin wrappers that route through the pool via _get_memory_for_request().
# The tool signatures and docstrings match mcp_server.py so agents see the
# same interface regardless of transport.


@mcp.tool()
def save_memory(
    content: str,
    name: Optional[str] = None,
    path: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> str:
    """Save a new memory note to the knowledge base.

    Write detailed, comprehensive memories -- not just brief notes. Include context,
    reasoning, examples, trade-offs, and lessons learned. The more detail you provide,
    the more useful the memory will be when retrieved later.

    Good memories are 3-10 sentences and capture:
    - WHAT happened or was decided
    - WHY it matters or was chosen over alternatives
    - HOW it works in practice, with specific details
    - GOTCHAS or edge cases discovered

    The system will automatically:
    - Generate a name and directory path if not provided
    - Extract keywords and tags for semantic search
    - Find and link related existing memories
    - Create a summary for long content (>150 words)

    Args:
        content: The memory content. Be detailed and thorough.
        name: Optional human-readable name (2-5 words). Auto-generated if not provided.
        path: Optional directory path (e.g. "backend/database").
            Auto-generated if not provided.
        tags: Optional list of tags. Auto-generated if not provided.

    Returns:
        JSON with the saved memory's id and status.
    """
    mem = _get_memory_for_request()
    memory_id = str(uuid.uuid4())

    kwargs: dict[str, Any] = {"id": memory_id}
    if name:
        kwargs["name"] = name
    if path:
        kwargs["path"] = path
    if tags:
        kwargs["tags"] = tags

    logger.info(
        "save_memory [HTTP]: id=%s persist_dir=%s content_len=%d",
        memory_id,
        _current_persist_dir.get(),
        len(content),
    )
    try:
        mem.add_note(content, **kwargs)
        logger.info("save_memory [HTTP]: completed id=%s", memory_id)
    except Exception:
        logger.exception("save_memory [HTTP]: failed id=%s", memory_id)
        return json.dumps(
            {"id": memory_id, "status": "error", "message": "Failed to save memory."},
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "id": memory_id,
            "status": "saved",
            "message": "Memory saved with full LLM analysis.",
        },
        ensure_ascii=False,
    )


@mcp.tool()
def search_memory(query: str, k: int = 5) -> str:
    """Search the knowledge base using natural language.

    Returns the most semantically relevant memories for the query.

    Args:
        query: Natural language search query. Be specific and descriptive.
        k: Maximum number of results to return (default: 5).

    Returns:
        JSON array of matching memories with content, tags, path, and links.
    """
    mem = _get_memory_for_request()
    logger.info("search_memory [HTTP]: query=%r k=%d", query, k)
    results = mem.search(query, k=k)

    output = []
    for r in results:
        note = mem.read(r["id"])
        output.append(
            {
                "id": r["id"],
                "name": note.name if note else None,
                "path": note.path if note else None,
                "content": r["content"],
                "tags": r.get("tags", []),
                "keywords": r.get("keywords", []),
                "links": note.links if note else [],
                "backlinks": note.backlinks if note else [],
            }
        )
    return json.dumps(output, ensure_ascii=False)


@mcp.tool()
def memory_tree() -> str:
    """Show the full directory tree of all memories.

    Returns:
        Tree-formatted string of the memory directory structure.
    """
    return _get_memory_for_request().tree()


@mcp.tool()
def grep_memory(pattern: str, flags: Optional[str] = None) -> str:
    """Search memory files using grep (full CLI grep).

    Runs grep on all markdown files in the memory notes directory.

    Examples:
        grep_memory("PostgreSQL")                    -- basic search
        grep_memory("oauth.*token", "-i")            -- case-insensitive regex
        grep_memory("TODO", "-l")                    -- list filenames only

    Args:
        pattern: Search pattern (string or regex depending on flags).
        flags: Optional grep flags as a single string.

    Returns:
        Grep output with paths relative to notes directory.
    """
    import subprocess

    mem = _get_memory_for_request()
    notes_dir = os.path.join(os.path.abspath(mem.persist_dir), "notes")
    os.makedirs(notes_dir, exist_ok=True)

    cmd = ["grep", "-r", "--include=*.md"]
    if flags:
        # Reuse mcp_server's sanitization logic if available, otherwise basic split
        cmd.extend(flags.split())
    cmd.extend(["-e", pattern, "--", notes_dir])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if not result.stdout and result.returncode == 1:
            return "No matches found."
        if result.returncode > 1:
            return f"Error: {result.stderr.strip()}"
        return result.stdout.replace(notes_dir + "/", "")
    except subprocess.TimeoutExpired:
        return "Error: grep timed out after 30 seconds."
    except FileNotFoundError:
        return "Error: grep command not found on this system."


@mcp.tool()
def find_memory(args: Optional[str] = None) -> str:
    """Search memory files using find (full CLI find).

    Runs find on the memory notes directory.

    Examples:
        find_memory()                                -- list all files
        find_memory("-name '*.md'")                  -- find by name pattern
        find_memory("-type d")                       -- list directories only

    Args:
        args: Optional find arguments as a single string.

    Returns:
        Find output with paths relative to notes directory.
    """
    import shlex
    import subprocess

    mem = _get_memory_for_request()
    notes_dir = os.path.join(os.path.abspath(mem.persist_dir), "notes")
    os.makedirs(notes_dir, exist_ok=True)

    cmd = ["find", notes_dir]
    if args:
        cmd.extend(shlex.split(args))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0 and result.stderr:
            return f"Error: {result.stderr.strip()}"
        if not result.stdout.strip():
            return "No results found."
        return result.stdout.replace(notes_dir + "/", "").replace(notes_dir, ".")
    except subprocess.TimeoutExpired:
        return "Error: find timed out after 30 seconds."
    except FileNotFoundError:
        return "Error: find command not found on this system."


# ---------------------------------------------------------------------------
# ASGI middleware — extracts persist_dir from query string
# ---------------------------------------------------------------------------
class _PersistDirMiddleware:
    """ASGI middleware that reads ``persist_dir`` from the query string and
    stores it in a ``ContextVar`` so tool functions can find it.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            qs = scope.get("query_string", b"").decode()
            params = parse_qs(qs)
            dirs = params.get("persist_dir")
            if dirs:
                _current_persist_dir.set(dirs[0])
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Build the ASGI app to be mounted by api.py
#
# We do NOT use mcp.streamable_http_app() because it creates a Starlette
# app whose lifespan (which starts the session manager's task group) does
# NOT fire when mounted inside FastAPI via app.mount().  Instead we:
#   1. Trigger session manager creation via streamable_http_app()
#   2. Build our own Starlette app with the ASGI handler, WITHOUT lifespan
#   3. Manage the session manager lifecycle from api.py startup/shutdown
# ---------------------------------------------------------------------------
from mcp.server.fastmcp.server import StreamableHTTPASGIApp  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.routing import Route  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402

# Trigger lazy creation of the session manager
mcp.streamable_http_app()

# Build the ASGI handler from the session manager directly
_mcp_handler = StreamableHTTPASGIApp(mcp.session_manager)


async def _health_endpoint(request):
    """Pool health endpoint at /api/knowledge/health."""
    pool = _get_pool()
    return JSONResponse(pool.stats())


_starlette_app = Starlette(
    routes=[
        Route("/mcp", endpoint=_mcp_handler),
        Route("/health", endpoint=_health_endpoint, methods=["GET"]),
    ],
    # NO lifespan — we manage session_manager lifecycle from api.py
)

knowledge_mcp_app = _PersistDirMiddleware(_starlette_app)


# ---------------------------------------------------------------------------
# Session manager lifecycle — called by api.py startup/shutdown
# ---------------------------------------------------------------------------
_session_cm = None


async def startup_knowledge():
    """Start the MCP session manager's task group.  Call from api.py startup."""
    global _session_cm
    _session_cm = mcp.session_manager.run()
    await _session_cm.__aenter__()
    logger.info("Knowledge MCP session manager started")


async def shutdown_knowledge():
    """Stop the MCP session manager's task group.  Call from api.py shutdown."""
    global _session_cm
    if _session_cm:
        try:
            await _session_cm.__aexit__(None, None, None)
        except Exception:
            logger.exception("Error stopping knowledge session manager")
        _session_cm = None
    # Kill all pool slots
    try:
        pool = _get_pool()
        pool.kill_all()
    except Exception:
        pass
    logger.info("Knowledge MCP shut down")
