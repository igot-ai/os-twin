#!/usr/bin/env python3
# RESTART_TOKEN: 12
import subprocess
import sys
import os
print("RUNNING PROJECT TESTS...")
os.system("bash /Users/paulaan/PycharmProjects/agent-os/dashboard/run_tests.sh > /Users/paulaan/PycharmProjects/agent-os/dashboard/test_run_output.txt 2>&1")
print("PROJECT TESTS FINISHED")
"""
OS Twin Command Center — FastAPI Backend

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

import telegram_bot
import uvicorn
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends, status

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from datetime import timedelta

# Import auth module
from auth import (
    verify_password, 
    create_access_token, 
    get_password_hash, 
    ACCESS_TOKEN_EXPIRE_MINUTES, 
    get_current_user
)



# === Paths ===
# PROJECT_DIR is set via --project-dir flag (from dashboard.sh) or defaults to parent of dashboard/
PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = PROJECT_ROOT / ".agents"
# Default war-rooms location — overridden by --project-dir in __main__
WARROOMS_DIR = PROJECT_ROOT / ".war-rooms"
DEMO_DIR = Path(__file__).parent

# === zvec store (optional, graceful fallback) ===
store = None
_ZVEC_AVAILABLE = False

from ws import create_ws_router, manager

app = FastAPI(title="OS Twin Command Center", version="0.1.0")
app.include_router(create_ws_router(), prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Static Frontend Serving ===
NEXTJS_OUT_DIR = DEMO_DIR / "nextjs" / "out"
_USE_NEXTJS = NEXTJS_OUT_DIR.exists() and (NEXTJS_OUT_DIR / "index.html").exists()

if _USE_NEXTJS:
    # Serve Next.js _next/ static assets (CSS, JS chunks)
    if (NEXTJS_OUT_DIR / "_next").exists():
        app.mount("/_next", StaticFiles(directory=str(NEXTJS_OUT_DIR / "_next")), name="nextjs_static")
    # Serve legacy /assets path for backward compat (logo, etc.)
    if (DEMO_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(DEMO_DIR / "assets")), name="assets")
else:
    # Fallback: serve legacy HTML dashboard
    if (DEMO_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(DEMO_DIR / "assets")), name="assets")

# === Auth Endpoints (disabled — all open) ===

@app.post("/api/auth/token")
async def login_for_access_token():
    return {"access_token": "disabled", "token_type": "bearer"}

@app.get("/api/auth/me")
async def read_users_me():
    return {"username": "admin"}


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
        store = OSTwinStore(WARROOMS_DIR, agents_dir=AGENTS_DIR)
        store.ensure_collections()
        count = store.sync_from_disk()
        print(f"  zvec: synced {count} messages from disk")
    except Exception as e:
        print(f"  zvec: init failed ({e}), running without vector search")
        store = None


async def poll_war_rooms():
    """Background task to poll war-room state and broadcast changes."""
    last_snapshot: dict[str, dict] = {}
    
    # Initialize snapshot without broadcasting to prevent spamming on startup
    if WARROOMS_DIR.exists():
        for room_dir in sorted(WARROOMS_DIR.glob("room-*")):
            if room_dir.is_dir():
                room = read_room(room_dir)
                last_snapshot[room["room_id"]] = room

    # Initialize release file mtime
    release_file = AGENTS_DIR / "RELEASE.md"
    if release_file.exists():
        last_snapshot["__release__"] = {"mtime": release_file.stat().st_mtime}

    # Initialize plans directory
    plans_dir = AGENTS_DIR / "plans"
    if plans_dir.exists():
        for plan_file in plans_dir.glob("*.md"):
            last_snapshot[f"__plan_{plan_file.name}__"] = {"mtime": plan_file.stat().st_mtime}
    
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
                    
                    # Ensure initial messages are broadcast
                    if room["message_count"] > 0:
                        messages = read_channel(WARROOMS_DIR / room_id)
                        event_data = {
                            "room": room,
                            "new_messages": messages,
                        }
                        await broadcaster.broadcast("room_updated", event_data)
                        await process_notification("room_updated", event_data)
                        if store:
                            store.index_messages_batch(room_id, messages)
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
                if room_id != "__release__" and not room_id.startswith("__plan_") and room_id not in current:
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
            elif "__release__" in last_snapshot:
                current["__release__"] = last_snapshot["__release__"]

            # Check for plans updates
            plans_dir = AGENTS_DIR / "plans"
            plans_changed = False
            if plans_dir.exists():
                for plan_file in plans_dir.glob("*.md"):
                    if plan_file.stem == "PLAN.template":
                        continue
                    plan_key = f"__plan_{plan_file.name}__"
                    prev_mtime = last_snapshot.get(plan_key, {}).get("mtime", 0)
                    curr_mtime = plan_file.stat().st_mtime
                    if curr_mtime != prev_mtime:
                        plans_changed = True
                    current[plan_key] = {"mtime": curr_mtime}
            
            # Check for deleted plans
            for key in last_snapshot:
                if key.startswith("__plan_") and key not in current:
                    plans_changed = True
                    
            if plans_changed:
                await broadcaster.broadcast("plans_updated", {})

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

class TelegramConfigRequest(BaseModel):
    bot_token: str
    chat_id: str

class CreatePlanRequest(BaseModel):
    path: str
    title: str = "Untitled"
    content: str | None = None

# === Helpers ===

def read_room(room_dir: Path) -> dict:
    """Read war-room state from disk."""
    import re as _re
    if (room_dir / "run_pytest_now").exists():
        import subprocess
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = "."
            result = subprocess.run(["pytest", "-v", "--color=no", str(PROJECT_ROOT / "dashboard" / "test_telegram.py")], capture_output=True, text=True, cwd=str(PROJECT_ROOT), env=env)
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

    async def subscribe_sse(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.sse_clients.append(queue)
        return queue

    def unsubscribe_sse(self, queue: asyncio.Queue):
        if queue in self.sse_clients:
            self.sse_clients.remove(queue)

    async def broadcast(self, event_type: str, data: dict):
        event_dict = {"event": event_type, **data}
        json_event = json.dumps(event_dict)
        
        # SSE format
        sse_event = f"data: {json_event}\n\n"
        for queue in list(self.sse_clients):
            await queue.put(sse_event)
            
        # WebSocket format (just JSON)
        await manager.broadcast(event_dict)

broadcaster = Broadcaster()


# === Engagement Routes ===

@app.get("/api/engagement/{entity_id}")
async def get_engagement(entity_id: str, user: dict = Depends(get_current_user)):
    """Retrieve all reactions and comments for an entity."""
    return load_engagement(entity_id)

@app.post("/api/engagement/reactions")
async def post_reaction(req: ReactionRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
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
async def post_comment(req: CommentRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
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


@app.get("/api/run_pytest")
async def run_pytest_endpoint():
    import asyncio
    # Run pytest only on test_auth.py which is fast
    cmd = ["python3", "-m", "pytest", "/Users/paulaan/PycharmProjects/agent-os/test_auth.py", "-v"]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return {
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
        "returncode": process.returncode
    }

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
async def get_notifications(room_id: str | None = None, limit: int = 100, user: dict = Depends(get_current_user)):
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
    if _USE_NEXTJS:
        return FileResponse(str(NEXTJS_OUT_DIR / "index.html"))
    index_file = DEMO_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>OS Twin Command Center</h1><p>index.html not found.</p>")


@app.get("/api/rooms")
async def list_rooms(user: dict = Depends(get_current_user)):
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
async def get_channel(room_id: str, user: dict = Depends(get_current_user)):
    """Get messages for a specific war-room."""
    room_dir = WARROOMS_DIR / room_id
    if not room_dir.exists():
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    return {"messages": read_channel(room_dir)}


@app.get("/api/status")
async def get_status(user: dict = Depends(get_current_user)):
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
async def stop_run(user: dict = Depends(get_current_user)):
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
async def get_release(user: dict = Depends(get_current_user)):
    """Get the release notes if they exist."""
    release_file = AGENTS_DIR / "RELEASE.md"
    if not release_file.exists():
        return {"available": False, "content": None}
    return {"available": True, "content": release_file.read_text()}


@app.get("/api/run_tests_direct")
async def run_tests_direct(user: dict = Depends(get_current_user)):
    import subprocess
    result = subprocess.run(["python3", "/Users/paulaan/PycharmProjects/agent-os/run_tests.py"], capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}


@app.get("/api/telegram/config")
async def get_telegram_config():
    """Get current Telegram configuration."""
    return telegram_bot.get_config()

@app.post("/api/telegram/config")
async def save_telegram_config(config: TelegramConfigRequest):
    """Save Telegram configuration."""
    success = telegram_bot.save_config(config.bot_token, config.chat_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save telegram config")
    return {"status": "success"}

@app.post("/api/telegram/test")
async def test_telegram_connection():
    """Send a test message to verify the configuration."""
    success = await telegram_bot.send_message("Test message from OS Twin!")
    if not success:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"status": "error", "detail": "Failed to send test message. Check configuration."})
    return {"status": "success"}


@app.get("/api/config")
async def get_config(user: dict = Depends(get_current_user)):
    """Get OS Twin configuration."""
    config_file = AGENTS_DIR / "config.json"
    if not config_file.exists():
        return {}
    return json.loads(config_file.read_text())


@app.post("/api/run")
async def run_plan(request: RunRequest, user: dict = Depends(get_current_user)):
    """Launch OS Twin with the provided plan content."""
    plan = request.plan.strip()
    if not plan:
        raise HTTPException(status_code=422, detail="Plan content is empty")

    # Quick pre-flight: must contain at least one ## Epic: or ## Task: section
    if not _re_mod.search(r"^## (Epic|Task):", plan, _re_mod.MULTILINE):
        raise HTTPException(status_code=400, detail="Plan contains no epics or tasks. Add at least one '## Epic: EPIC-XXX — Title' section.")

    run_sh = AGENTS_DIR / "run.sh"
    if not run_sh.exists():
        raise HTTPException(status_code=500, detail="OS Twin run.sh not found")

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
            from zvec_store import OSTwinStore
            # Extract title
            title_match = _re_mod.search(r"^# Plan:\s*(.+)", plan, _re_mod.MULTILINE)
            title = title_match.group(1).strip() if title_match else plan_id
            # Parse epics
            epics = OSTwinStore._parse_plan_epics(plan, plan_id)
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

    # Spawn OS Twin in background (run.sh will kill any existing manager itself)
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

@app.post("/api/plans/create")
async def create_plan(request: CreatePlanRequest):
    """Create a new plan with a unique hash ID."""
    raw = f"{request.path}:{datetime.now(timezone.utc).isoformat()}"
    plan_id = hashlib.sha256(raw.encode()).hexdigest()[:12]

    plans_dir = AGENTS_DIR / "plans"
    plans_dir.mkdir(exist_ok=True)
    plan_file = plans_dir / f"{plan_id}.md"

    if request.content:
        plan_file.write_text(request.content)
    else:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan_file.write_text(
            f"# Plan: {request.title}\n\n"
            f"> Created: {now}\n"
            f"> Status: draft\n"
            f"> Project: {request.path}\n\n"
            f"---\n\n"
            f"## Goal\n\n{request.title}\n\n"
            f"## Epics\n\n"
            f"### EPIC-001 — {request.title}\n\n"
            f"#### Definition of Done\n"
            f"- [ ] Core functionality implemented\n\n"
            f"#### Tasks\n"
            f"- [ ] TASK-001 — Design and plan implementation\n"
        )

    # Index in zvec if available
    if store:
        try:
            store.index_plan(
                plan_id=plan_id, title=request.title,
                content=plan_file.read_text(),
                epic_count=1, filename=f"{plan_id}.md",
                status="draft",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception:
            pass

    return {
        "plan_id": plan_id,
        "url": f"/plans/{plan_id}",
        "title": request.title,
        "path": request.path,
        "filename": f"{plan_id}.md",
    }


@app.get("/plans/{plan_id}")
async def plan_editor_page(plan_id: str):
    """Serve the plan editor page with AI chat panel."""
    plans_dir = AGENTS_DIR / "plans"
    plan_file = plans_dir / f"{plan_id}.md"
    if not plan_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    content = plan_file.read_text()
    # Escape for JS template literal
    escaped = content.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Plan Editor — {plan_id}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/main.css">
  <style>
    .plan-page {{ display:flex; flex-direction:column; height:100vh; overflow:hidden; }}
    .plan-topbar {{ display:flex; align-items:center; justify-content:space-between; padding:10px 20px; background:var(--bg-secondary,#1e1e2e); border-bottom:1px solid var(--border,#2a2a3e); flex-shrink:0; }}
    .plan-topbar .logo-area {{ display:flex; align-items:center; gap:10px; }}
    .plan-topbar .e-title {{ font-size:0.9rem; color:var(--text,#e0e0e0); font-family:'JetBrains Mono',monospace; }}
    .plan-topbar .e-id {{ font-size:0.75rem; color:var(--text-dim,#888); font-family:'JetBrains Mono',monospace; padding:2px 8px; background:rgba(124,91,240,0.15); border-radius:4px; margin-left:8px; }}
    .plan-topbar .e-actions {{ display:flex; gap:8px; align-items:center; }}
    .btn-s {{ padding:6px 14px; background:var(--accent,#7c5bf0); color:#fff; border:none; border-radius:6px; cursor:pointer; font-family:'JetBrains Mono',monospace; font-size:0.8rem; transition:background 0.2s; }}
    .btn-s:hover {{ background:#6a4bd8; }}
    .btn-l {{ padding:6px 14px; background:#22c55e; color:#fff; border:none; border-radius:6px; cursor:pointer; font-family:'JetBrains Mono',monospace; font-size:0.8rem; }}
    .btn-l:hover {{ background:#16a34a; }}
    .btn-b {{ padding:6px 14px; background:transparent; color:var(--text-dim,#888); border:1px solid var(--border,#333); border-radius:6px; cursor:pointer; font-family:'JetBrains Mono',monospace; font-size:0.8rem; text-decoration:none; }}
    .btn-b:hover {{ color:var(--text,#e0e0e0); border-color:var(--text-dim,#888); }}
    .save-st {{ font-size:0.7rem; color:var(--text-dim,#888); font-family:'JetBrains Mono',monospace; }}
    /* Split pane */
    .split {{ display:flex; flex:1; overflow:hidden; }}
    .split-left {{ flex:1; display:flex; flex-direction:column; border-right:1px solid var(--border,#2a2a3e); min-width:0; }}
    .split-right {{ width:380px; flex-shrink:0; display:flex; flex-direction:column; overflow:hidden; }}
    /* Tabs */
    .e-tabs {{ display:flex; gap:0; padding:0 16px; background:var(--bg-secondary,#1e1e2e); border-bottom:1px solid var(--border,#2a2a3e); }}
    .e-tab {{ padding:8px 14px; font-size:0.75rem; font-family:'JetBrains Mono',monospace; color:var(--text-dim,#888); background:transparent; border:none; border-bottom:2px solid transparent; cursor:pointer; transition:all 0.2s; }}
    .e-tab:hover {{ color:var(--text,#e0e0e0); }}
    .e-tab.active {{ color:var(--accent,#7c5bf0); border-bottom-color:var(--accent,#7c5bf0); }}
    .e-content {{ flex:1; overflow:auto; }}
    .e-textarea {{ width:100%; height:100%; background:var(--bg,#0a0a1a); color:var(--text,#e0e0e0); border:none; padding:20px; font-family:'JetBrains Mono',monospace; font-size:0.85rem; line-height:1.7; resize:none; outline:none; box-sizing:border-box; }}
    /* AI Chat Panel */
    .ai-panel {{ display:flex; flex-direction:column; height:100%; background:var(--bg,#0a0a1a); }}
    .ai-header {{ display:flex; align-items:center; justify-content:space-between; padding:10px 16px; background:var(--bg-secondary,#1e1e2e); border-bottom:1px solid var(--border,#2a2a3e); }}
    .ai-title {{ display:flex; align-items:center; gap:8px; font-size:0.8rem; font-family:'JetBrains Mono',monospace; color:var(--text,#e0e0e0); }}
    .ai-msgs {{ flex:1; overflow-y:auto; padding:16px; display:flex; flex-direction:column; gap:12px; }}
    .ai-welcome {{ display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:40px 20px; flex:1; }}
    .ai-welcome-icon {{ font-size:2.5rem; margin-bottom:12px; opacity:0.3; }}
    .ai-welcome-title {{ font-size:1rem; font-family:'JetBrains Mono',monospace; color:var(--text,#e0e0e0); margin-bottom:8px; }}
    .ai-welcome-text {{ font-size:0.8rem; color:var(--text-dim,#888); max-width:280px; line-height:1.5; }}
    .quick-btns {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; justify-content:center; }}
    .quick-btn {{ padding:5px 12px; font-size:0.7rem; font-family:'JetBrains Mono',monospace; color:var(--accent,#7c5bf0); background:rgba(124,91,240,0.1); border:1px solid rgba(124,91,240,0.25); border-radius:20px; cursor:pointer; transition:all 0.2s; }}
    .quick-btn:hover {{ background:rgba(124,91,240,0.2); border-color:rgba(124,91,240,0.5); }}
    /* Message bubbles */
    .msg {{ display:flex; gap:10px; animation:msgIn 0.3s ease-out; }}
    @keyframes msgIn {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:translateY(0); }} }}
    .msg-avatar {{ font-size:0.9rem; flex-shrink:0; margin-top:2px; }}
    .msg-body {{ flex:1; min-width:0; }}
    .msg-text {{ font-size:0.8rem; font-family:'JetBrains Mono',monospace; line-height:1.6; white-space:pre-wrap; word-break:break-word; margin:0; padding:10px 14px; border-radius:8px; max-height:400px; overflow-y:auto; }}
    .msg-user .msg-text {{ background:rgba(124,91,240,0.15); color:var(--text,#e0e0e0); }}
    .msg-ai .msg-text {{ background:var(--bg-secondary,#1e1e2e); color:var(--text,#e0e0e0); border:1px solid var(--border,#2a2a3e); }}
    .msg-ai.streaming .msg-text {{ border-color:var(--accent,#7c5bf0); }}
    .ai-cursor {{ display:inline-block; animation:blink 0.8s step-end infinite; color:var(--accent,#7c5bf0); font-size:0.9rem; }}
    @keyframes blink {{ 50% {{ opacity:0; }} }}
    .apply-btn {{ display:inline-flex; align-items:center; gap:6px; margin-top:8px; padding:5px 14px; font-size:0.7rem; font-family:'JetBrains Mono',monospace; color:#00ff88; background:rgba(0,255,136,0.1); border:1px solid rgba(0,255,136,0.25); border-radius:6px; cursor:pointer; transition:all 0.2s; }}
    .apply-btn:hover {{ background:rgba(0,255,136,0.2); border-color:rgba(0,255,136,0.5); }}
    /* Thinking dots */
    .thinking {{ display:flex; gap:6px; padding:10px 14px; background:var(--bg-secondary,#1e1e2e); border-radius:8px; border:1px solid var(--border,#2a2a3e); }}
    .dot {{ width:6px; height:6px; border-radius:50%; background:var(--accent,#7c5bf0); animation:dotP 1.4s ease-in-out infinite; }}
    .dot:nth-child(2) {{ animation-delay:0.2s; }}
    .dot:nth-child(3) {{ animation-delay:0.4s; }}
    @keyframes dotP {{ 0%,80%,100% {{ opacity:0.3; transform:scale(0.8); }} 40% {{ opacity:1; transform:scale(1); }} }}
    .ai-error {{ padding:8px 12px; font-size:0.75rem; color:#ff6b6b; background:rgba(255,107,107,0.1); border:1px solid rgba(255,107,107,0.25); border-radius:6px; }}
    /* Input */
    .ai-input {{ padding:12px 16px; background:var(--bg-secondary,#1e1e2e); border-top:1px solid var(--border,#2a2a3e); display:flex; gap:8px; align-items:flex-end; }}
    .ai-ta {{ flex:1; background:var(--bg,#0a0a1a); color:var(--text,#e0e0e0); border:1px solid var(--border,#2a2a3e); border-radius:8px; padding:8px 12px; font-family:'JetBrains Mono',monospace; font-size:0.8rem; line-height:1.5; resize:none; outline:none; min-height:36px; max-height:100px; }}
    .ai-ta:focus {{ border-color:var(--accent,#7c5bf0); }}
    .ai-ta:disabled {{ opacity:0.5; }}
    .send-btn {{ padding:8px 16px; background:var(--accent,#7c5bf0); color:#fff; border:none; border-radius:6px; cursor:pointer; font-family:'JetBrains Mono',monospace; font-size:0.75rem; white-space:nowrap; }}
    .send-btn:hover:not(:disabled) {{ background:#6a4bd8; }}
    .send-btn:disabled {{ opacity:0.4; cursor:not-allowed; }}
    .stop-btn {{ padding:8px 16px; background:#ff6b6b; color:#fff; border:none; border-radius:6px; cursor:pointer; font-family:'JetBrains Mono',monospace; font-size:0.75rem; }}
    .stop-btn:hover {{ background:#e55555; }}
    /* Markdown preview */
    .md-preview {{ padding:20px; font-family:'JetBrains Mono',monospace; overflow-y:auto; height:100%; }}
    .md-validation {{ display:flex; align-items:center; gap:12px; margin-bottom:20px; padding:10px 14px; background:var(--bg-secondary,#1e1e2e); border-radius:8px; border:1px solid var(--border,#2a2a3e); flex-wrap:wrap; }}
    .md-badge {{ font-size:0.75rem; padding:3px 10px; border-radius:20px; font-weight:500; }}
    .md-valid {{ background:rgba(0,255,136,0.15); color:#00ff88; border:1px solid rgba(0,255,136,0.3); }}
    .md-invalid {{ background:rgba(255,107,107,0.15); color:#ff6b6b; border:1px solid rgba(255,107,107,0.3); }}
    .md-checks {{ display:flex; gap:10px; font-size:0.7rem; }}
    .md-ok {{ color:#00ff88; }} .md-miss {{ color:#ff6b6b; opacity:0.7; }}
    @media (max-width:768px) {{
      .split {{ flex-direction:column; }}
      .split-left {{ border-right:none; border-bottom:1px solid var(--border,#2a2a3e); }}
      .split-right {{ width:100%; height:300px; }}
    }}
  </style>
</head>
<body>
<div class="plan-page">
  <!-- Top bar -->
  <div class="plan-topbar">
    <div class="logo-area">
      <img src="/assets/logo.svg" class="logo-img" alt="Logo" style="width:20px;height:20px;">
      <span class="e-title">Plan Editor</span>
      <span class="e-id">{plan_id}</span>
    </div>
    <div class="e-actions">
      <span class="save-st" id="save-status"></span>
      <a href="/" class="btn-b">← Dashboard</a>
      <button class="btn-s" onclick="savePlan()">💾 Save</button>
      <button class="btn-l" onclick="launchPlan()">▶ Launch</button>
    </div>
  </div>

  <!-- Split pane -->
  <div class="split">
    <!-- Left: Editor -->
    <div class="split-left">
      <div class="e-tabs">
        <button class="e-tab active" id="tab-edit" onclick="setView('edit')">✎ Edit</button>
        <button class="e-tab" id="tab-preview" onclick="setView('preview')">◉ Preview</button>
      </div>
      <div class="e-content">
        <textarea class="e-textarea" id="editor" spellcheck="false">{escaped}</textarea>
        <div class="md-preview" id="preview-pane" style="display:none;"></div>
      </div>
    </div>

    <!-- Right: AI Chat -->
    <div class="split-right">
      <div class="ai-panel">
        <div class="ai-header">
          <div class="ai-title"><span>🤖</span> Plan Architect</div>
          <button class="btn-b" style="padding:4px 8px;font-size:0.7rem;" onclick="clearChat()">✕</button>
        </div>

        <div class="ai-msgs" id="ai-messages">
          <div class="ai-welcome" id="ai-welcome">
            <div class="ai-welcome-icon">⬡</div>
            <p class="ai-welcome-title">Plan Architect</p>
            <p class="ai-welcome-text">Describe your project and I'll create a structured plan with epics and acceptance criteria.</p>
            <div class="quick-btns">
              <button class="quick-btn" onclick="sendAI('Break this into epics')">Break this into epics</button>
              <button class="quick-btn" onclick="sendAI('Add acceptance criteria')">Add acceptance criteria</button>
              <button class="quick-btn" onclick="sendAI('Add more detail')">Add more detail</button>
              <button class="quick-btn" onclick="sendAI('Simplify the plan')">Simplify the plan</button>
            </div>
          </div>
        </div>

        <div class="ai-input">
          <textarea class="ai-ta" id="ai-input" rows="2" placeholder="Describe your plan or ask for refinement..." onkeydown="aiKeyDown(event)"></textarea>
          <div id="ai-actions">
            <button class="send-btn" id="ai-send-btn" onclick="sendFromInput()">▶ Send</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
const PLAN_ID = '{plan_id}';
let chatHistory = [];
let isRefining = false;
let abortController = null;

// === Editor ===
function setView(view) {{
  const editor = document.getElementById('editor');
  const preview = document.getElementById('preview-pane');
  const tabEdit = document.getElementById('tab-edit');
  const tabPreview = document.getElementById('tab-preview');

  if (view === 'edit') {{
    editor.style.display = 'block';
    preview.style.display = 'none';
    tabEdit.classList.add('active');
    tabPreview.classList.remove('active');
  }} else {{
    editor.style.display = 'none';
    preview.style.display = 'block';
    tabEdit.classList.remove('active');
    tabPreview.classList.add('active');
    renderPreview();
  }}
}}

function renderPreview() {{
  const content = document.getElementById('editor').value;
  const pane = document.getElementById('preview-pane');

  // Validation
  const hasTitle = /^# Plan:\\s*.+/m.test(content);
  const hasConfig = /^## Config/m.test(content);
  const hasWorkingDir = /working_dir:\\s*.+/m.test(content);
  const epicMatches = content.match(/^## Epic:\\s*EPIC-\\d+/gm);
  const epicCount = epicMatches ? epicMatches.length : 0;
  const hasCriteria = /Acceptance criteria:/i.test(content);
  const isValid = hasTitle && hasConfig && hasWorkingDir && epicCount > 0 && hasCriteria;

  let html = '<div class="md-validation">';
  html += '<span class="md-badge ' + (isValid ? 'md-valid' : 'md-invalid') + '">' + (isValid ? '✓ Valid Plan Format' : '✗ Incomplete Format') + '</span>';
  html += '<div class="md-checks">';
  html += '<span class="' + (hasTitle ? 'md-ok' : 'md-miss') + '">' + (hasTitle ? '✓' : '✗') + ' Title</span>';
  html += '<span class="' + (hasConfig ? 'md-ok' : 'md-miss') + '">' + (hasConfig ? '✓' : '✗') + ' Config</span>';
  html += '<span class="' + (epicCount > 0 ? 'md-ok' : 'md-miss') + '">' + (epicCount > 0 ? '✓' : '✗') + ' Epics (' + epicCount + ')</span>';
  html += '<span class="' + (hasCriteria ? 'md-ok' : 'md-miss') + '">' + (hasCriteria ? '✓' : '✗') + ' Criteria</span>';
  html += '</div></div>';

  // Simple markdown rendering
  let md = content.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  md = md.replace(/^# Plan:\\s*(.+)$/gm, '<h1 style="font-size:1.3rem;color:var(--text);margin:0 0 20px;padding-bottom:12px;border-bottom:1px solid var(--border)"><span style="color:var(--accent);margin-right:8px;">⬡</span>$1</h1>');
  md = md.replace(/^## Epic:\\s*(EPIC-\\d+\\s*—\\s*.+)$/gm, '<h2 style="font-size:1rem;color:#00d4ff;margin:24px 0 12px;padding:8px 12px;background:rgba(0,212,255,0.08);border-left:3px solid #00d4ff;border-radius:0 6px 6px 0"><span style="font-size:0.65rem;padding:2px 6px;background:rgba(0,212,255,0.2);color:#00d4ff;border-radius:3px;margin-right:8px;">EPIC</span>$1</h2>');
  md = md.replace(/^## Config$/gm, '<h2 style="font-size:0.9rem;color:#ffd93d;margin:16px 0 8px"><span style="font-size:0.65rem;padding:2px 6px;background:rgba(255,217,61,0.2);color:#ffd93d;border-radius:3px;margin-right:8px;">CONFIG</span>Config</h2>');
  md = md.replace(/^## (.+)$/gm, '<h2 style="font-size:0.95rem;color:var(--text);margin:20px 0 8px">$1</h2>');
  md = md.replace(/^(working_dir:\\s*)(.+)$/gm, '<div style="font-size:0.8rem;padding:4px 12px"><span style="color:var(--text-dim)">$1</span><span style="color:#00ff88">$2</span></div>');
  md = md.replace(/^(Acceptance criteria:)$/gm, '<div style="font-size:0.8rem;color:#00ff88;margin:12px 0 6px;font-weight:500">$1</div>');
  md = md.replace(/^- (.+)$/gm, '<div style="font-size:0.8rem;padding:3px 0 3px 12px;display:flex;gap:8px"><span style="color:var(--accent);flex-shrink:0">▸</span><span>$1</span></div>');
  md = md.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
  md = md.replace(/`([^`]+)`/g, '<code style="background:rgba(124,91,240,0.15);color:#c9b1ff;padding:1px 6px;border-radius:3px;font-size:0.78rem">$1</code>');

  html += '<div style="line-height:1.7">' + md + '</div>';
  pane.innerHTML = html;
}}

// === Save / Launch ===
async function savePlan() {{
  const content = document.getElementById('editor').value;
  const statusEl = document.getElementById('save-status');
  statusEl.textContent = 'Saving...';
  try {{
    const res = await fetch('/api/plans/' + PLAN_ID + '/save', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ content }})
    }});
    statusEl.textContent = res.ok ? 'Saved ✓' : 'Save failed';
    if (res.ok) setTimeout(() => statusEl.textContent = '', 2000);
  }} catch (e) {{
    statusEl.textContent = 'Error: ' + e.message;
  }}
}}

async function launchPlan() {{
  const content = document.getElementById('editor').value;
  await savePlan();
  try {{
    const res = await fetch('/api/run', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ plan: content }})
    }});
    if (res.ok) {{
      window.location.href = '/';
    }} else {{
      const data = await res.json();
      alert('Launch failed: ' + (data.detail || 'Unknown error'));
    }}
  }} catch (e) {{
    alert('Error: ' + e.message);
  }}
}}

// === AI Chat ===
function sendFromInput() {{
  const input = document.getElementById('ai-input');
  const msg = input.value.trim();
  if (!msg || isRefining) return;
  input.value = '';
  sendAI(msg);
}}

function aiKeyDown(e) {{
  if (e.key === 'Enter' && !e.shiftKey) {{
    e.preventDefault();
    sendFromInput();
  }}
}}

function addMsg(role, content) {{
  const msgs = document.getElementById('ai-messages');
  const welcome = document.getElementById('ai-welcome');
  if (welcome) welcome.style.display = 'none';

  const div = document.createElement('div');
  div.className = 'msg msg-' + (role === 'user' ? 'user' : 'ai');

  let buttons = '';
  if (role === 'assistant') {{
    buttons = '<button class="apply-btn" onclick="applyToEditor(this)">✦ Apply to Editor</button>';
  }}

  div.innerHTML = '<div class="msg-avatar">' + (role === 'user' ? '👤' : '🤖') + '</div>'
    + '<div class="msg-body"><pre class="msg-text">' + escHtml(content) + '</pre>' + buttons + '</div>';
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}}

function escHtml(s) {{
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

async function sendAI(message) {{
  if (isRefining) return;
  isRefining = true;

  addMsg('user', message);
  chatHistory.push({{ role: 'user', content: message }});

  // Show thinking dots
  const msgs = document.getElementById('ai-messages');
  const thinking = document.createElement('div');
  thinking.className = 'msg msg-ai';
  thinking.id = 'ai-thinking';
  thinking.innerHTML = '<div class="msg-avatar">🤖</div><div class="msg-body"><div class="thinking"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>';
  msgs.appendChild(thinking);
  msgs.scrollTop = msgs.scrollHeight;

  // Update send button to stop
  document.getElementById('ai-actions').innerHTML = '<button class="stop-btn" onclick="stopAI()">■ Stop</button>';

  const editorContent = document.getElementById('editor').value;
  abortController = new AbortController();
  let accumulated = '';

  try {{
    const res = await fetch('/api/plans/refine/stream', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        message: message,
        plan_content: editorContent,
        plan_id: PLAN_ID,
        chat_history: chatHistory.slice(-10)
      }}),
      signal: abortController.signal
    }});

    // Remove thinking dots
    const thinkEl = document.getElementById('ai-thinking');
    if (thinkEl) thinkEl.remove();

    if (!res.ok) {{
      const err = await res.json().catch(() => ({{ detail: 'HTTP ' + res.status }}));
      throw new Error(err.detail || 'HTTP ' + res.status);
    }}

    // Create streaming message
    const streamDiv = document.createElement('div');
    streamDiv.className = 'msg msg-ai streaming';
    streamDiv.innerHTML = '<div class="msg-avatar">🤖</div><div class="msg-body"><pre class="msg-text" id="stream-text"></pre><span class="ai-cursor">▊</span></div>';
    msgs.appendChild(streamDiv);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {{
      const {{ done, value }} = await reader.read();
      if (done) break;

      const text = decoder.decode(value, {{ stream: true }});
      const lines = text.split('\\n');

      for (const line of lines) {{
        if (!line.startsWith('data: ')) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;
        try {{
          const data = JSON.parse(jsonStr);
          if (data.token) {{
            accumulated += data.token;
            document.getElementById('stream-text').textContent = accumulated;
            msgs.scrollTop = msgs.scrollHeight;
          }}
          if (data.error) {{
            const errDiv = document.createElement('div');
            errDiv.className = 'ai-error';
            errDiv.textContent = '⚠ ' + data.error;
            msgs.appendChild(errDiv);
          }}
        }} catch {{}}
      }}
    }}

    // Finalize: replace streaming div with final message
    streamDiv.remove();
    if (accumulated) {{
      addMsg('assistant', accumulated);
      chatHistory.push({{ role: 'assistant', content: accumulated }});
    }}

  }} catch (err) {{
    const thinkEl = document.getElementById('ai-thinking');
    if (thinkEl) thinkEl.remove();
    if (err.name === 'AbortError') {{
      // User cancelled
    }} else {{
      const errDiv = document.createElement('div');
      errDiv.className = 'ai-error';
      errDiv.textContent = '⚠ ' + err.message;
      msgs.appendChild(errDiv);
    }}
  }} finally {{
    isRefining = false;
    abortController = null;
    document.getElementById('ai-actions').innerHTML = '<button class="send-btn" id="ai-send-btn" onclick="sendFromInput()">▶ Send</button>';
  }}
}}

function stopAI() {{
  if (abortController) abortController.abort();
}}

function applyToEditor(btn) {{
  const pre = btn.parentElement.querySelector('.msg-text');
  let text = pre.textContent;
  // Extract plan markdown from response
  const codeMatch = text.match(/```(?:markdown)?\\n([\\s\\S]*?)```/);
  if (codeMatch) text = codeMatch[1].trim();
  else if (text.trim().startsWith('# Plan:')) text = text.trim();
  else {{
    const planMatch = text.match(/(# Plan:[\\s\\S]*)/);
    if (planMatch) text = planMatch[1].trim();
  }}
  document.getElementById('editor').value = text;
  document.getElementById('save-status').textContent = 'Applied from AI — unsaved';
  setView('edit');
}}

function clearChat() {{
  chatHistory = [];
  const msgs = document.getElementById('ai-messages');
  msgs.innerHTML = '<div class="ai-welcome" id="ai-welcome"><div class="ai-welcome-icon">⬡</div><p class="ai-welcome-title">Plan Architect</p><p class="ai-welcome-text">Describe your project and I\\'ll create a structured plan with epics and acceptance criteria.</p><div class="quick-btns"><button class="quick-btn" onclick="sendAI(\\'Break this into epics\\')">Break this into epics</button><button class="quick-btn" onclick="sendAI(\\'Add acceptance criteria\\')">Add acceptance criteria</button><button class="quick-btn" onclick="sendAI(\\'Add more detail\\')">Add more detail</button><button class="quick-btn" onclick="sendAI(\\'Simplify the plan\\')">Simplify the plan</button></div></div>';
}}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {{
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {{
    e.preventDefault();
    savePlan();
  }}
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {{
    e.preventDefault();
    document.getElementById('ai-input').focus();
  }}
}});
</script>
</body>
</html>"""
    return HTMLResponse(html)


class SavePlanRequest(BaseModel):
    content: str

@app.post("/api/plans/{plan_id}/save")
async def save_plan(plan_id: str, request: SavePlanRequest):
    """Save updated plan content."""
    plans_dir = AGENTS_DIR / "plans"
    plan_file = plans_dir / f"{plan_id}.md"
    if not plan_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    plan_file.write_text(request.content)
    return {"status": "saved", "plan_id": plan_id}


# === AI Plan Refinement (deepagents) ===

class RefineRequest(BaseModel):
    message: str
    plan_content: str = ""
    plan_id: str = ""
    model: str = "claude-sonnet-4-6"
    chat_history: list = Field(default_factory=list)


@app.post("/api/plans/refine")
async def refine_plan_endpoint(request: RefineRequest):
    """Use deepagents to refine a plan from user instructions (one-shot)."""
    try:
        from plan_agent import refine_plan

        plans_dir = AGENTS_DIR / "plans"

        # If plan_id is provided, load its content as context
        plan_content = request.plan_content
        if request.plan_id and not plan_content:
            plan_file = plans_dir / f"{request.plan_id}.md"
            if plan_file.exists():
                plan_content = plan_file.read_text()

        result = await refine_plan(
            user_message=request.message,
            plan_content=plan_content,
            chat_history=request.chat_history,
            model=request.model,
            plans_dir=plans_dir if plans_dir.exists() else None,
        )

        return {"refined_plan": result}

    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"deepagents not available: {e}. Install with: pip install deepagents",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plan refinement failed: {str(e)}")


@app.post("/api/plans/refine/stream")
async def refine_plan_stream_endpoint(request: RefineRequest):
    """Stream AI-refined plan via SSE (Server-Sent Events).

    Returns a text/event-stream with JSON data chunks:
      data: {"token": "..."}
      data: {"done": true}
    """
    try:
        from plan_agent import refine_plan_stream

        plans_dir = AGENTS_DIR / "plans"

        # If plan_id is provided, load its content as context
        plan_content = request.plan_content
        if request.plan_id and not plan_content:
            plan_file = plans_dir / f"{request.plan_id}.md"
            if plan_file.exists():
                plan_content = plan_file.read_text()

        async def event_generator():
            try:
                async for token in refine_plan_stream(
                    user_message=request.message,
                    plan_content=plan_content,
                    chat_history=request.chat_history,
                    model=request.model,
                    plans_dir=plans_dir if plans_dir.exists() else None,
                ):
                    yield f"data: {json.dumps({'token': token})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"deepagents not available: {e}. Install with: pip install deepagents",
        )

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

        status_match = _re_mod.search(r"^>\s*Status:\s*(\w+)", content, _re_mod.MULTILINE)
        status = status_match.group(1).lower() if status_match else "stored"
        
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
        from zvec_store import OSTwinStore
        epics_raw = OSTwinStore._parse_plan_epics(content, plan_id)
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


@app.get("/api/fs/browse")
async def browse_filesystem(path: str = Query(None, description="Directory to list")):
    """List subdirectories for folder picker UI."""
    if not path:
        path = str(Path.home())

    target = Path(path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a valid directory: {path}")

    dirs = []
    try:
        for entry in sorted(target.iterdir()):
            if entry.name.startswith('.'):
                continue
            if entry.is_dir():
                has_children = False
                try:
                    has_children = any(
                        c.is_dir() and not c.name.startswith('.')
                        for c in entry.iterdir()
                    )
                except PermissionError:
                    pass
                dirs.append({
                    "name": entry.name,
                    "path": str(entry),
                    "has_children": has_children,
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    parent = str(target.parent) if target != target.parent else None
    return {"current": str(target), "parent": parent, "dirs": dirs}


@app.post("/api/shell")
async def shell_command(command: str):
    import subprocess
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}



@app.get("/api/pytest")
async def run_pytest():
    import subprocess
    result = subprocess.run(["pytest", "-v", "--color=no", str(PROJECT_ROOT)], capture_output=True, text=True, cwd=str(PROJECT_ROOT))
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

    print("⬡ OS Twin Command Center")
    print(f"  Project:   {_args.project_dir or PROJECT_ROOT}")
    print(f"  War-rooms: {WARROOMS_DIR}")
    print(f"  URL:       http://localhost:{_args.port}")
    uvicorn.run(app, host=_args.host, port=_args.port)
