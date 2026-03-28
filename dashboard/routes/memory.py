from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
import json
import fcntl
import time
import re
import os

from dashboard.api_utils import AGENTS_DIR, PROJECT_ROOT
from dashboard.auth import get_current_user

router = APIRouter(tags=["memory"])

VALID_KINDS = {"artifact", "decision", "interface", "convention", "warning"}
MAX_SUMMARY_BYTES = 4096
MAX_DETAIL_BYTES = 16384

# ── Helpers ──────────────────────────────────────────────────────────────────

def _memory_dir() -> Path:
    d = AGENTS_DIR / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ledger_path() -> Path:
    return _memory_dir() / "ledger.jsonl"


def _read_ledger() -> list[dict]:
    path = _ledger_path()
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _live_entries(entries: list[dict]) -> list[dict]:
    """Filter out superseded entries."""
    superseded = {e["supersedes"] for e in entries if e.get("supersedes")}
    return [e for e in entries if e["id"] not in superseded]


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_-]+", text.lower()))


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/api/memory")
async def list_memories(
    kind: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """List all live memory entries (index view)."""
    entries = _live_entries(_read_ledger())
    if kind:
        entries = [e for e in entries if e.get("kind") == kind]
    return {
        "count": len(entries),
        "entries": [
            {
                "id": e["id"],
                "ts": e.get("ts"),
                "kind": e.get("kind"),
                "room_id": e.get("room_id"),
                "ref": e.get("ref"),
                "tags": e.get("tags", []),
                "author_role": e.get("author_role"),
                "summary_preview": e.get("summary", "")[:200],
            }
            for e in entries
        ],
    }


@router.get("/api/memory/{memory_id}")
async def get_memory(memory_id: str, user: dict = Depends(get_current_user)):
    """Get a single memory entry by ID (includes detail)."""
    for entry in _live_entries(_read_ledger()):
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
    if kind not in VALID_KINDS:
        raise HTTPException(400, f"Invalid kind '{kind}'. Must be one of: {sorted(VALID_KINDS)}")

    summary = body.get("summary", "")
    if len(summary.encode()) > MAX_SUMMARY_BYTES:
        summary = summary[:MAX_SUMMARY_BYTES] + "\n[TRUNCATED]"

    detail = body.get("detail")
    if detail and len(detail.encode()) > MAX_DETAIL_BYTES:
        detail = detail[:MAX_DETAIL_BYTES] + "\n[TRUNCATED]"

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mem_id = f"mem-{kind[:3]}-{time.time_ns()}-{os.getpid()}"

    entry = {
        "id": mem_id,
        "ts": ts,
        "kind": kind,
        "room_id": body.get("room_id", "dashboard"),
        "author_role": body.get("author_role", "human"),
        "ref": body.get("ref", ""),
        "tags": [t.lower().strip() for t in body.get("tags", [])],
        "summary": summary,
    }
    if detail:
        entry["detail"] = detail
    if body.get("supersedes"):
        entry["supersedes"] = body["supersedes"]

    ledger = _ledger_path()
    with open(ledger, "a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry) + "\n")
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return {"id": mem_id, "status": "published"}


@router.get("/api/memory/query/search")
async def search_memory(
    text: str = Query(..., description="Search query"),
    kind: Optional[str] = None,
    exclude_room: Optional[str] = None,
    max_results: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    """Full-text search across shared memory."""
    live = _live_entries(_read_ledger())
    query_tokens = _tokenize(text)
    if not query_tokens:
        return {"results": []}

    scored = []
    for entry in live:
        if kind and entry.get("kind") != kind:
            continue
        if exclude_room and entry.get("room_id") == exclude_room:
            continue

        searchable = " ".join([
            entry.get("summary", ""),
            " ".join(entry.get("tags", [])),
            entry.get("ref", ""),
            entry.get("kind", ""),
            entry.get("detail", ""),
        ])
        entry_tokens = _tokenize(searchable)
        score = len(query_tokens & entry_tokens)
        for qt in query_tokens:
            for et in entry_tokens:
                if qt in et and qt not in (query_tokens & entry_tokens):
                    score += 0.5
                    break
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return {"results": [e for _, e in scored[:max_results]]}


@router.get("/api/memory/context/{room_id}")
async def get_room_context(
    room_id: str,
    keywords: Optional[str] = Query(None, description="Comma-separated keywords"),
    max_entries: int = Query(15, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    """Generate cross-room context for a war-room."""
    live = _live_entries(_read_ledger())
    candidates = [e for e in live if e.get("room_id") != room_id]

    if keywords:
        kw_tokens = set(k.strip().lower() for k in keywords.split(",") if k.strip())
        scored = []
        for entry in candidates:
            searchable = " ".join([
                entry.get("summary", ""),
                " ".join(entry.get("tags", [])),
                entry.get("ref", ""),
                entry.get("detail", ""),
            ])
            entry_tokens = _tokenize(searchable)
            score = len(kw_tokens & entry_tokens)
            for qt in kw_tokens:
                for et in entry_tokens:
                    if qt in et and qt not in (kw_tokens & entry_tokens):
                        score += 0.5
                        break
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        candidates = [e for _, e in scored[:max_entries]]
    else:
        candidates = candidates[-max_entries:]

    return {
        "room_id": room_id,
        "context_entries": len(candidates),
        "entries": candidates,
    }


@router.get("/api/memory/stats")
async def memory_stats(user: dict = Depends(get_current_user)):
    """Aggregate statistics about shared memory."""
    live = _live_entries(_read_ledger())
    by_kind = {}
    by_room = {}
    for e in live:
        k = e.get("kind", "unknown")
        r = e.get("room_id", "unknown")
        by_kind[k] = by_kind.get(k, 0) + 1
        by_room[r] = by_room.get(r, 0) + 1

    return {
        "total": len(live),
        "by_kind": by_kind,
        "by_room": by_room,
    }
