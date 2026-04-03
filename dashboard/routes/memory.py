"""Dashboard API routes for shared memory — thin wrapper around memory-core.py."""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
import json
import sys
import os
import importlib.util

from dashboard.api_utils import SYSTEM_MCP_DIR
from dashboard.auth import get_current_user

# Import memory-core.py (same source of truth as MCP server and CLI)
_core_path = os.path.join(str(SYSTEM_MCP_DIR), "memory-core.py")
if not os.path.exists(_core_path):
    raise RuntimeError(f"Could not find memory-core.py at {_core_path}")

_spec = importlib.util.spec_from_file_location("memory_core", _core_path)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

router = APIRouter(tags=["memory"])


@router.get("/api/memory")
async def list_memories(
    kind: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """List all live memory entries (index view)."""
    result = json.loads(_core.list_memories(kind=kind))
    return {"count": len(result), "entries": result}


@router.get("/api/memory/query/search")
async def search_memory(
    text: str = Query(..., description="Search query"),
    kind: Optional[str] = None,
    exclude_room: Optional[str] = None,
    max_results: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    """Full-text search across shared memory (BM25 + time decay)."""
    result = json.loads(
        _core.search(text=text, kind=kind, exclude_room=exclude_room, max_results=max_results)
    )
    return {"results": result}


@router.get("/api/memory/context/{room_id}")
async def get_room_context(
    room_id: str,
    keywords: Optional[str] = Query(None, description="Comma-separated keywords"),
    max_entries: int = Query(15, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    """Generate cross-room context for a war-room."""
    brief_keywords = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else None
    entries_json = _core.query(exclude_room=room_id)
    entries = json.loads(entries_json)

    if brief_keywords:
        # Use get_context for keyword-filtered markdown, but return structured data
        bm25_results = _core._bm25_rank(" ".join(brief_keywords), entries)
        ref_ts = _core._newest_ts(entries)
        scored_raw = [(rel, _core._time_decay(e, ref_ts), e) for rel, e in bm25_results]
        scored = _core._compute_scores(scored_raw)
        entries = [e for _, e in scored[:max_entries]]
    else:
        entries = entries[-max_entries:]

    return {
        "room_id": room_id,
        "context_entries": len(entries),
        "entries": entries,
    }


@router.get("/api/memory/{memory_id}")
async def get_memory(memory_id: str, user: dict = Depends(get_current_user)):
    """Get a single memory entry by ID (includes detail)."""
    all_entries = json.loads(_core.query())
    for entry in all_entries:
        if entry["id"] == memory_id:
            return entry
    raise HTTPException(status_code=404, detail="Memory entry not found")


@router.post("/api/memory")
async def publish_memory(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """Publish a new memory entry from the dashboard."""
    kind = body.get("kind")
    if kind not in _core.VALID_KINDS:
        raise HTTPException(400, f"Invalid kind '{kind}'. Must be one of: {sorted(_core.VALID_KINDS)}")

    result = _core.publish(
        kind=kind,
        summary=body.get("summary", ""),
        tags=body.get("tags", []),
        room_id=body.get("room_id", "dashboard"),
        author_role=body.get("author_role", "human"),
        ref=body.get("ref", ""),
        detail=body.get("detail"),
        supersedes=body.get("supersedes"),
    )

    if result.startswith("error:"):
        raise HTTPException(400, result)

    mem_id = result.replace("published:", "")
    return {"id": mem_id, "status": "published"}


@router.get("/api/memory/stats")
async def memory_stats(user: dict = Depends(get_current_user)):
    """Aggregate statistics about shared memory."""
    entries = json.loads(_core.query())
    by_kind: dict[str, int] = {}
    by_room: dict[str, int] = {}
    for e in entries:
        k = e.get("kind", "unknown")
        r = e.get("room_id", "unknown")
        by_kind[k] = by_kind.get(k, 0) + 1
        by_room[r] = by_room.get(r, 0) + 1

    return {
        "total": len(entries),
        "by_kind": by_kind,
        "by_room": by_room,
    }
