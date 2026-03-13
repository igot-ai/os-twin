#!/usr/bin/env python3
# RESTART_TOKEN: 1
"""
Agent OS Command Center — FastAPI Backend

Serves the dashboard and provides real-time war-room state via SSE.

Usage:
    pip install fastapi uvicorn
    python dashboard/api.py
"""

import asyncio
import glob
import hashlib
import json
import os
import re as _re_mod
import signal
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, List, Optional, Dict
from pydantic import BaseModel, Field

import uvicorn
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles



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
async def startup_all():
    """Initialize zvec store and start background polling."""
    global store
    
    # 1. Start polling background task
    asyncio.create_task(poll_war_rooms())
    
    # 2. Init zvec
    if not _ZVEC_AVAILABLE:
        print("  zvec: not available (pip install zvec sentence-transformers)")
        return
    try:
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        store = AgentOSStore(WARROOMS_DIR, agents_dir=AGENTS_DIR)
        store.ensure_collections()
        count = store.sync_from_disk()
        print(f"  zvec: synced {count} messages from disk")
    except Exception as e:
        print(f"  zvec: init failed ({e}), running without vector search")
        store = None


async def poll_war_rooms():
    """Background task to poll war-room state and broadcast changes."""
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
                    await broadcaster.broadcast("room_created", {"room": room})
                    await process_notification("room_created", {"room": room})
                    if store:
                        store.upsert_room_metadata(room_id, room)
                elif (
                    prev["status"] != room["status"]
                    or prev["message_count"] != room["message_count"]
                ):
                    # Changed room — include latest channel messages
                    messages = read_channel(WARROOMS_DIR / room_id)
                    new_messages = messages[prev["message_count"]:]
                    event_data = {
                        "room": room,
                        "new_messages": new_messages,
                    }
                    await broadcaster.broadcast("room_updated", event_data)
                    await process_notification("room_updated", event_data)
                    # Index new messages and update metadata in zvec
                    if store:
                        store.index_messages_batch(room_id, new_messages)
                        store.upsert_room_metadata(room_id, room)
                        # Sync epic status if room status changed
                        if prev["status"] != room["status"]:
                            epic_ref = room.get("task_ref", "")
                            if epic_ref:
                                # Find plan_id from plans dir (latest launched)
                                try:
                                    plans_dir = AGENTS_DIR / "plans"
                                    if plans_dir.exists():
                                        latest = max(
                                            plans_dir.glob("agent-os-plan-*.md"),
                                            key=lambda p: p.stat().st_mtime,
                                            default=None,
                                        )
                                        if latest:
                                            store.update_epic_status(
                                                latest.stem, epic_ref, room["status"]
                                            )
                                except Exception:
                                    pass

            # Detect removed rooms
            for room_id in last_snapshot:
                if room_id != "__release__" and room_id not in current:
                    await broadcaster.broadcast("room_removed", {"room_id": room_id})

            # Check for release
            release_file = AGENTS_DIR / "RELEASE.md"
            if release_file.exists():
                prev_release = last_snapshot.get("__release__", {}).get("mtime", 0)
                curr_mtime = release_file.stat().st_mtime
                if curr_mtime != prev_release:
                    await broadcaster.broadcast("release", {
                        "content": release_file.read_text(),
                    })
                    current["__release__"] = {"mtime": curr_mtime}

            last_snapshot = current
            await asyncio.sleep(1)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"  poll_war_rooms: error ({e})")
            await asyncio.sleep(2)


# === Models ===

class Room(BaseModel):
    room_id: str
    task_ref: str
    status: str
    retries: int
    message_count: int
    last_activity: str | None
    task_description: str | None
    goal_total: int = 0
    goal_done: int = 0


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

class ReactionRequest(BaseModel):
    entity_id: str
    user_id: str
    reaction_type: str

class CommentRequest(BaseModel):
    entity_id: str
    user_id: str
    body: str
    parent_id: Optional[str] = None


# === Helpers ===

def read_room(room_dir: Path) -> dict:
    """Read war-room state from disk."""
    import re as _re
    if (room_dir / "run_pytest_now").exists():
        import subprocess
        try:
            result = subprocess.run(["pytest"], capture_output=True, text=True, cwd=str(PROJECT_ROOT))
            (room_dir / "pytest_results.txt").write_text(f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nCODE: {result.returncode}")
        except Exception as e:
            (room_dir / "pytest_results.txt").write_text(f"ERROR running pytest: {e}")
        (room_dir / "run_pytest_now").unlink()

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
    tasks_file = room_dir / "TASKS.md"
    if not task_md and tasks_file.exists():
        task_md = tasks_file.read_text()

    # Parse TASKS.md for goal completion
    goal_total = 0
    goal_done = 0
    if tasks_file.exists():
        tasks_content = tasks_file.read_text()
        goal_total = len(_re.findall(r"- \[[ xX]\]", tasks_content))
        goal_done = len(_re.findall(r"- \[[xX]\]", tasks_content))

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
        "goal_total": goal_total,
        "goal_done": goal_done,
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

# === Real-Time Event Gateway ===

async def process_notification(event_type: str, data: dict):
    """Asynchronously process notifications (e.g., log to file or send to external service)."""
    # Simulate processing delay
    await asyncio.sleep(0.1)
    
    # Persist notification to a log file
    notifications_file = PROJECT_ROOT / ".data" / "notifications.log"
    notifications_file.parent.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = json.dumps({"ts": timestamp, "event": event_type, "data": data})
    
    with open(notifications_file, "a") as f:
        f.write(log_entry + "\n")

class Broadcaster:
    def __init__(self):
        self.sse_clients: List[asyncio.Queue] = []
        self.ws_clients: List[WebSocket] = []

    async def subscribe_sse(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.sse_clients.append(queue)
        return queue

    def unsubscribe_sse(self, queue: asyncio.Queue):
        if queue in self.sse_clients:
            self.sse_clients.remove(queue)

    async def connect_ws(self, websocket: WebSocket):
        await websocket.accept()
        self.ws_clients.append(websocket)

    def disconnect_ws(self, websocket: WebSocket):
        if websocket in self.ws_clients:
            self.ws_clients.remove(websocket)

    async def broadcast(self, event_type: str, data: dict):
        event_dict = {"event": event_type, **data}
        json_event = json.dumps(event_dict)
        
        # SSE format
        sse_event = f"data: {json_event}\n\n"
        for queue in list(self.sse_clients):
            await queue.put(sse_event)
            
        # WebSocket format (just JSON)
        for ws in list(self.ws_clients):
            try:
                await ws.send_text(json_event)
            except Exception:
                self.disconnect_ws(ws)

broadcaster = Broadcaster()


# === Engagement Routes ===

@app.get("/api/engagement/{entity_id}")
async def get_engagement(entity_id: str):
    """Retrieve all reactions and comments for an entity."""
    return load_engagement(entity_id)

@app.post("/api/engagement/reactions")
async def post_reaction(req: ReactionRequest, background_tasks: BackgroundTasks):
    """Toggle a reaction on an entity."""
    state = toggle_reaction(req.entity_id, req.user_id, req.reaction_type)
    event_data = {
        "entity_id": req.entity_id,
        "user_id": req.user_id,
        "reaction_type": req.reaction_type,
        "state": state.model_dump()
    }
    await broadcaster.broadcast("reaction_toggled", event_data)
    background_tasks.add_task(process_notification, "reaction_toggled", event_data)
    return state

@app.post("/api/engagement/comments")
async def post_comment(req: CommentRequest, background_tasks: BackgroundTasks):
    """Post a hierarchical comment."""
    state, new_comment = add_comment(req.entity_id, req.user_id, req.body, req.parent_id)
    event_data = {
        "entity_id": req.entity_id,
        "comment": new_comment.model_dump(),
        "state": state.model_dump()
    }
    await broadcaster.broadcast("comment_published", event_data)
    background_tasks.add_task(process_notification, "comment_published", event_data)
    return {"state": state, "new_comment": new_comment}


@app.get("/api/engagement/events")
async def engagement_events():
    """Real-time event gateway for engagement."""
    async def event_generator() -> AsyncIterator[str]:
        queue = await broadcaster.subscribe_sse()
        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe_sse(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await broadcaster.connect_ws(websocket)
    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "ts": datetime.now(timezone.utc).isoformat()}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        broadcaster.disconnect_ws(websocket)
    except Exception:
        broadcaster.disconnect_ws(websocket)


@app.get("/api/test_ws")
async def run_ws_test():
    import subprocess
    cmd = ["python3", "/Users/paulaan/PycharmProjects/agent-os/test_ws.py"]
    process = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "stdout": process.stdout,
        "stderr": process.stderr,
        "returncode": process.returncode
    }

@app.get("/api/notifications")
async def get_notifications(room_id: str | None = None, limit: int = 100):
    """Retrieve filtered notifications from the log."""
    notifications_file = PROJECT_ROOT / ".data" / "notifications.log"
    if not notifications_file.exists():
        return {"notifications": []}
    
    results = []
    with open(notifications_file, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if room_id:
                    # Filter by room_id in data if present
                    data = entry.get("data", {})
                    if data.get("room_id") == room_id or data.get("entity_id") == room_id:
                        results.append(entry)
                    elif "room" in data and isinstance(data["room"], dict) and data["room"].get("room_id") == room_id:
                        results.append(entry)
                else:
                    results.append(entry)
            except json.JSONDecodeError:
                continue
    
    return {"notifications": results[-limit:]}


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

    return {"rooms": rooms, "summary": summary, "debug": {"project_root": str(PROJECT_ROOT), "agents_dir": str(AGENTS_DIR)}}


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
    plan = request.plan.strip()
    if not plan:
        raise HTTPException(status_code=422, detail="Plan content is empty")

    # Quick pre-flight: must contain at least one ## Epic: or ## Task: section
    if not _re_mod.search(r"^## (Epic|Task):", plan, _re_mod.MULTILINE):
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

    plan_filename = os.path.basename(plan_path)
    plan_id = Path(plan_path).stem

    # Index plan + epics into zvec
    if store:
        try:
            from zvec_store import AgentOSStore
            # Extract title
            title_match = _re_mod.search(r"^# Plan:\s*(.+)", plan, _re_mod.MULTILINE)
            title = title_match.group(1).strip() if title_match else plan_id
            # Parse epics
            epics = AgentOSStore._parse_plan_epics(plan, plan_id)
            now = datetime.now(timezone.utc).isoformat()
            store.index_plan(
                plan_id=plan_id, title=title, content=plan,
                epic_count=len(epics), filename=plan_filename,
                status="launched", created_at=now,
            )
            for epic in epics:
                store.index_epic(
                    epic_ref=epic["task_ref"], plan_id=plan_id,
                    title=epic["title"], body=epic["body"],
                    room_id=epic["room_id"],
                    working_dir=epic.get("working_dir", "."),
                    status="pending",
                )
        except Exception as e:
            print(f"  zvec: plan indexing failed ({e}), continuing without")

    # Spawn Agent OS in background (run.sh will kill any existing manager itself)
    subprocess.Popen(
        [str(run_sh), plan_path],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return {"status": "launched", "plan_file": plan_filename, "plan_id": plan_id}


@app.get("/api/events")
async def sse_events():
    """
    Server-Sent Events stream.
    Now backed by the central Broadcaster.
    """
    async def event_generator() -> AsyncIterator[str]:
        queue = await broadcaster.subscribe_sse()
        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe_sse(queue)

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


# === Plan & Epic Endpoints ===

@app.get("/api/plans")
async def list_plans():
    """List all stored plans (from zvec, with file fallback)."""
    if store:
        plans = store.get_all_plans()
        if plans:
            # Check for completed status based on epics
            for p in plans:
                epics = store.get_epics_for_plan(p["plan_id"])
                if epics and all(e.get("status") == "passed" for e in epics):
                    p["status"] = "completed"
            return {"plans": plans, "count": len(plans)}

    # Fallback: read from disk
    plans_dir = AGENTS_DIR / "plans"
    if not plans_dir.exists():
        return {"plans": [], "count": 0}

    plans = []
    for f in sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.stem == "PLAN.template":
            continue
        content = f.read_text()
        if not content.strip():
            continue
        title_match = _re_mod.search(r"^# Plan:\s*(.+)", content, _re_mod.MULTILINE)
        title = title_match.group(1).strip() if title_match else f.stem

        # Count epics/tasks
        epics_found = _re_mod.findall(r"^## (Epic|Task):\s*(\S+)", content, _re_mod.MULTILINE)
        epic_count = len(epics_found)

        status = "stored"
        # If we have store, try to determine if completed
        if store:
            plan_meta = store.get_plan(f.stem)
            if plan_meta:
                status = plan_meta.get("status", "stored")
                epics = store.get_epics_for_plan(f.stem)
                if epics and all(e.get("status") == "passed" for e in epics):
                    status = "completed"

        plans.append({
            "plan_id": f.stem,
            "title": title,
            "content": content,
            "status": status,
            "epic_count": epic_count,
            "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            "filename": f.name,
        })

    return {"plans": plans, "count": len(plans)}


@app.get("/api/plans/{plan_id}")
async def get_plan(plan_id: str):
    """Get a specific plan with its epics."""
    plan = None
    epics = []

    if store:
        plan = store.get_plan(plan_id)
        epics = store.get_epics_for_plan(plan_id)

    # Fallback: read from disk
    if not plan:
        plans_dir = AGENTS_DIR / "plans"
        plan_file = plans_dir / f"{plan_id}.md"
        if not plan_file.exists():
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
        content = plan_file.read_text()
        title_match = _re_mod.search(r"^# Plan:\s*(.+)", content, _re_mod.MULTILINE)
        title = title_match.group(1).strip() if title_match else plan_id
        epic_count = len(_re_mod.findall(r"^## (Epic|Task):", content, _re_mod.MULTILINE))
        plan = {
            "plan_id": plan_id,
            "title": title,
            "content": content,
            "status": "stored",
            "epic_count": epic_count,
            "created_at": datetime.fromtimestamp(
                plan_file.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
            "filename": plan_file.name,
        }

    return {"plan": plan, "epics": epics}


@app.get("/api/plans/{plan_id}/epics")
async def get_plan_epics(plan_id: str):
    """Get epics for a specific plan."""
    if store:
        epics = store.get_epics_for_plan(plan_id)
        if epics:
            return {"epics": epics, "count": len(epics)}

    # Fallback: parse from disk
    plans_dir = AGENTS_DIR / "plans"
    plan_file = plans_dir / f"{plan_id}.md"
    if not plan_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    content = plan_file.read_text()
    if store:
        from zvec_store import AgentOSStore
        epics_raw = AgentOSStore._parse_plan_epics(content, plan_id)
    else:
        epics_raw = []

    return {"epics": epics_raw, "count": len(epics_raw)}


@app.get("/api/search/plans")
async def search_plans(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
):
    """Semantic search across plans."""
    if not store:
        raise HTTPException(status_code=503, detail="Vector search not available")
    results = store.search_plans(q, limit=limit)
    return {"results": results, "count": len(results)}


@app.get("/api/search/epics")
async def search_epics(
    q: str = Query(..., min_length=1),
    plan_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Semantic search across epics."""
    if not store:
        raise HTTPException(status_code=503, detail="Vector search not available")
    results = store.search_epics(q, plan_id=plan_id, limit=limit)
    return {"results": results, "count": len(results)}


@app.post("/api/rooms/{room_id}/action")
async def room_action(room_id: str, background_tasks: BackgroundTasks, action: str = Query(...)):
    """Perform an action on a room (stop, pause, resume)."""
    room_dir = WARROOMS_DIR / room_id
    if not room_dir.exists():
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    status_file = room_dir / "status"
    if action == "stop":
        status_file.write_text("failed-final")
    elif action == "pause":
        status_file.write_text("paused")
    elif action == "resume" or action == "start":
        status_file.write_text("pending")
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    background_tasks.add_task(process_notification, "room_action", {"room_id": room_id, "action": action})
    return {"status": "ok", "action": action, "room_id": room_id}


@app.post("/api/shell")
async def shell_command(command: str):
    import subprocess
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}



@app.get("/api/pytest")
async def run_pytest():
    import subprocess
    result = subprocess.run(["pytest"], capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

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
