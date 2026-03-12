#!/usr/bin/env python3
"""
Agent OS Command Center — FastAPI Backend

Serves the dashboard and provides real-time war-room state via SSE.

Usage:
    pip install fastapi uvicorn
    python dashboard/api.py
"""

import asyncio
import glob
import json
import os
import signal
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# === Paths ===
# PROJECT_DIR is set via --project-dir flag (from dashboard.sh) or defaults to parent of dashboard/
PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = PROJECT_ROOT / ".agents"
# Default war-rooms location — overridden by --project-dir in __main__
WARROOMS_DIR = PROJECT_ROOT / ".war-rooms"
DEMO_DIR = Path(__file__).parent

# === zvec store (optional, graceful fallback) ===
store = None
try:
    from zvec_store import AgentOSStore
    _ZVEC_AVAILABLE = True
except ImportError:
    _ZVEC_AVAILABLE = False

app = FastAPI(title="Agent OS Command Center", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static assets
if (DEMO_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DEMO_DIR / "assets")), name="assets")


@app.on_event("startup")
async def startup_zvec():
    """Initialize zvec store on startup (non-blocking, graceful fallback)."""
    global store
    if not _ZVEC_AVAILABLE:
        print("  zvec: not available (pip install zvec sentence-transformers)")
        return
    try:
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        store = AgentOSStore(WARROOMS_DIR)
        store.ensure_collections()
        count = store.sync_from_disk()
        print(f"  zvec: synced {count} messages from disk")
    except Exception as e:
        print(f"  zvec: init failed ({e}), running without vector search")
        store = None


# === Models ===

class Room(BaseModel):
    room_id: str
    task_ref: str
    status: str
    retries: int
    message_count: int
    last_activity: str | None
    task_description: str | None


class Message(BaseModel):
    id: str
    ts: str
    from_: str
    to: str
    type: str
    ref: str
    body: str


class RunRequest(BaseModel):
    plan: str


# === Helpers ===

def read_room(room_dir: Path) -> dict:
    """Read war-room state from disk."""
    import re as _re

    room_id = room_dir.name
    status = (room_dir / "status").read_text().strip() if (room_dir / "status").exists() else "unknown"
    task_ref = (room_dir / "task-ref").read_text().strip() if (room_dir / "task-ref").exists() else None
    retries_str = (room_dir / "retries").read_text().strip() if (room_dir / "retries").exists() else "0"
    retries = int(retries_str) if retries_str.isdigit() else 0
    task_md = (room_dir / "brief.md").read_text() if (room_dir / "brief.md").exists() else None

    # Fallback: extract ref from TASKS.md header ("# Tasks for EPIC-XXX ..." or "# EPIC-XXX ...")
    if not task_ref:
        tasks_file = room_dir / "TASKS.md"
        if tasks_file.exists():
            header = tasks_file.read_text().split("\n", 1)[0]
            m = _re.search(r"(EPIC-\d+|TASK-\d+)", header)
            if m:
                task_ref = m.group(1)
    # Fallback: derive from room-id
    if not task_ref:
        m = _re.match(r"room-(\d+)", room_id)
        task_ref = f"EPIC-{m.group(1)}" if m else "UNKNOWN"

    # Fallback: use TASKS.md as description when brief.md is missing
    if not task_md and (room_dir / "TASKS.md").exists():
        task_md = (room_dir / "TASKS.md").read_text()

    channel_file = room_dir / "channel.jsonl"
    message_count = 0
    last_activity = None

    if channel_file.exists():
        lines = [l.strip() for l in channel_file.read_text().splitlines() if l.strip()]
        message_count = len(lines)
        if lines:
            try:
                last_msg = json.loads(lines[-1])
                last_activity = last_msg.get("ts")
            except json.JSONDecodeError:
                pass

    return {
        "room_id": room_id,
        "task_ref": task_ref,
        "status": status,
        "retries": retries,
        "message_count": message_count,
        "last_activity": last_activity,
        "task_description": task_md,
    }


def read_channel(room_dir: Path) -> list[dict]:
    """Read all messages from a channel file."""
    channel_file = room_dir / "channel.jsonl"
    if not channel_file.exists():
        return []
    messages = []
    for line in channel_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            messages.append(msg)
        except json.JSONDecodeError:
            pass
    return messages


# === Routes ===

@app.get("/")
async def index():
    index_file = DEMO_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>Agent OS Command Center</h1><p>index.html not found.</p>")


@app.get("/api/rooms")
async def list_rooms():
    """List all war-rooms with current status."""
    rooms = []
    if not WARROOMS_DIR.exists():
        return {"rooms": [], "summary": {}}

    for room_dir in sorted(WARROOMS_DIR.glob("room-*")):
        if room_dir.is_dir():
            rooms.append(read_room(room_dir))

    # Summary counts
    summary = {"total": len(rooms)}
    for status in ("pending", "engineering", "qa-review", "fixing", "passed", "failed-final"):
        summary[status.replace("-", "_")] = sum(1 for r in rooms if r["status"] == status)

    return {"rooms": rooms, "summary": summary}


@app.get("/api/rooms/{room_id}/channel")
async def get_channel(room_id: str):
    """Get messages for a specific war-room."""
    room_dir = WARROOMS_DIR / room_id
    if not room_dir.exists():
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    return {"messages": read_channel(room_dir)}


@app.get("/api/status")
async def get_status():
    """Get current manager run status."""
    pid_file = AGENTS_DIR / "manager.pid"
    running = False
    pid = None
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)  # signal 0 = check existence only
            running = True
        except (ValueError, ProcessLookupError, PermissionError):
            pid_file.unlink(missing_ok=True)
            pid = None
    return {"running": running, "pid": pid}


@app.post("/api/stop")
async def stop_run():
    """Kill the running manager loop."""
    pid_file = AGENTS_DIR / "manager.pid"
    if not pid_file.exists():
        return {"stopped": False, "reason": "no manager running"}
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink(missing_ok=True)
        return {"stopped": True, "pid": pid}
    except (ValueError, ProcessLookupError):
        pid_file.unlink(missing_ok=True)
        return {"stopped": False, "reason": "process not found"}


@app.get("/api/release")
async def get_release():
    """Get the release notes if they exist."""
    release_file = AGENTS_DIR / "RELEASE.md"
    if not release_file.exists():
        return {"available": False, "content": None}
    return {"available": True, "content": release_file.read_text()}


@app.get("/api/config")
async def get_config():
    """Get Agent OS configuration."""
    config_file = AGENTS_DIR / "config.json"
    if not config_file.exists():
        return {}
    return json.loads(config_file.read_text())


@app.post("/api/run")
async def run_plan(request: RunRequest):
    """Launch Agent OS with the provided plan content."""
    import re

    plan = request.plan.strip()
    if not plan:
        raise HTTPException(status_code=422, detail="Plan content is empty")

    # Quick pre-flight: must contain at least one ## Epic: or ## Task: section
    if not re.search(r"^## (Epic|Task):", plan, re.MULTILINE):
        raise HTTPException(status_code=400, detail="Plan contains no epics or tasks. Add at least one '## Epic: EPIC-XXX — Title' section.")

    run_sh = AGENTS_DIR / "run.sh"
    if not run_sh.exists():
        raise HTTPException(status_code=500, detail="Agent OS run.sh not found")

    plans_dir = AGENTS_DIR / "plans"
    plans_dir.mkdir(exist_ok=True)

    # Write plan to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", prefix="agent-os-plan-",
        dir=str(plans_dir), delete=False
    ) as f:
        f.write(plan)
        plan_path = f.name

    # Spawn Agent OS in background (run.sh will kill any existing manager itself)
    subprocess.Popen(
        [str(run_sh), plan_path],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return {"status": "launched", "plan_file": os.path.basename(plan_path)}


@app.get("/api/events")
async def sse_events():
    """
    Server-Sent Events stream.
    Polls war-room state every second and emits changes.
    """
    async def event_generator() -> AsyncIterator[str]:
        last_snapshot: dict[str, dict] = {}

        while True:
            try:
                current: dict[str, dict] = {}

                if WARROOMS_DIR.exists():
                    for room_dir in sorted(WARROOMS_DIR.glob("room-*")):
                        if room_dir.is_dir():
                            room = read_room(room_dir)
                            current[room["room_id"]] = room

                # Detect changes: new rooms, status changes, new messages
                for room_id, room in current.items():
                    prev = last_snapshot.get(room_id)
                    if prev is None:
                        # New room
                        event = json.dumps({"event": "room_created", "room": room})
                        yield f"data: {event}\n\n"
                        # Index new room in zvec
                        if store:
                            store.upsert_room_metadata(room_id, room)
                    elif (
                        prev["status"] != room["status"]
                        or prev["message_count"] != room["message_count"]
                    ):
                        # Changed room — include latest channel messages
                        messages = read_channel(WARROOMS_DIR / room_id)
                        new_messages = messages[prev["message_count"]:]
                        event = json.dumps({
                            "event": "room_updated",
                            "room": room,
                            "new_messages": new_messages,
                        })
                        yield f"data: {event}\n\n"
                        # Index new messages and update metadata in zvec
                        if store:
                            store.index_messages_batch(room_id, new_messages)
                            store.upsert_room_metadata(room_id, room)

                # Detect removed rooms
                for room_id in last_snapshot:
                    if room_id not in current:
                        event = json.dumps({"event": "room_removed", "room_id": room_id})
                        yield f"data: {event}\n\n"

                # Check for release
                release_file = AGENTS_DIR / "RELEASE.md"
                if release_file.exists():
                    prev_release = last_snapshot.get("__release__", {}).get("mtime", 0)
                    curr_mtime = release_file.stat().st_mtime
                    if curr_mtime != prev_release:
                        event = json.dumps({
                            "event": "release",
                            "content": release_file.read_text(),
                        })
                        yield f"data: {event}\n\n"
                        current["__release__"] = {"mtime": curr_mtime}

                last_snapshot = current
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# === Vector Search Endpoints ===

@app.get("/api/search")
async def search_messages(
    q: str = Query(..., min_length=1, description="Search query"),
    room_id: str | None = Query(None, description="Filter by room"),
    type: str | None = Query(None, description="Filter by message type"),
    limit: int = Query(20, ge=1, le=100),
):
    """Semantic vector search across all indexed messages."""
    if not store:
        raise HTTPException(status_code=503, detail="Vector search not available (zvec not initialized)")
    results = store.search(q, room_id=room_id, msg_type=type, limit=limit)
    return {"results": results, "count": len(results)}


@app.get("/api/rooms/{room_id}/context")
async def search_room_context(
    room_id: str,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
):
    """Semantic search scoped to a single room."""
    if not store:
        raise HTTPException(status_code=503, detail="Vector search not available")
    results = store.search(q, room_id=room_id, limit=limit)
    return {"results": results, "count": len(results)}


@app.get("/api/rooms/{room_id}/state")
async def get_room_state(room_id: str):
    """Get room metadata from zvec (fast, no file I/O) with file fallback."""
    if store:
        meta = store.get_room_metadata(room_id)
        if meta:
            return meta
    # Fallback to file-based read
    room_dir = WARROOMS_DIR / room_id
    if not room_dir.exists():
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    return read_room(room_dir)


if __name__ == "__main__":
    import argparse as _ap

    _parser = _ap.ArgumentParser(description="Ostwin Dashboard")
    _parser.add_argument("--port", type=int, default=9000, help="Port to listen on")
    _parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    _parser.add_argument("--project-dir", default=None, help="Project directory to monitor")
    _args = _parser.parse_args()

    # Override global WARROOMS_DIR if project-dir provided
    if _args.project_dir:
        WARROOMS_DIR = Path(_args.project_dir) / ".war-rooms"

    print("⬡ Agent OS Command Center")
    print(f"  Project:   {_args.project_dir or PROJECT_ROOT}")
    print(f"  War-rooms: {WARROOMS_DIR}")
    print(f"  URL:       http://localhost:{_args.port}")
    uvicorn.run(app, host=_args.host, port=_args.port)
