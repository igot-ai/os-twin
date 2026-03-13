#!/usr/bin/env python3
"""
Ostwin Dashboard — WebSocket-enabled API

FastAPI backend with:
- REST endpoints for war-room status, channel messages, goals
- WebSocket endpoint for real-time state change push
- File-system watcher that broadcasts updates

Epic 6 — Dashboard WebSocket Updates
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
    from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn
    import telegram_bot
except ImportError:
    print("[ERROR] Missing dependencies: pip install fastapi uvicorn websockets", file=sys.stderr)
    sys.exit(1)

# --- Config ---
SCRIPT_DIR = Path(__file__).parent
DEFAULT_PORT = 9000

app = FastAPI(title="Ostwin Dashboard", version="0.2.0")

# --- Global state ---
PROJECT_DIR = Path.cwd()
WARROOMS_DIR = PROJECT_DIR / ".war-rooms"

from ws import manager, create_ws_router

def get_warrooms_dir():
    return WARROOMS_DIR


# --- File system watcher ---
async def watch_warrooms():
    """Polls war-room status files and broadcasts changes."""
    while True:
        try:
            if WARROOMS_DIR.exists():
                # Check plan queue / progress.json
                progress_file = WARROOMS_DIR / "progress.json"
                if progress_file.exists():
                    try:
                        progress_mtime = progress_file.stat().st_mtime
                        prev_progress = manager._last_states.get("progress_mtime")
                        if prev_progress != progress_mtime:
                            manager._last_states["progress_mtime"] = progress_mtime
                            if prev_progress is not None:
                                progress_data = json.loads(progress_file.read_text())
                                await manager.broadcast({
                                    "event": "plan_update",
                                    "progress": progress_data,
                                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                                })
                    except Exception:
                        pass

                for room_dir in sorted(WARROOMS_DIR.iterdir()):
                    if not room_dir.is_dir() or not room_dir.name.startswith("room-"):
                        continue

                    room_id = room_dir.name
                    status_file = room_dir / "status"
                    status = status_file.read_text().strip() if status_file.exists() else "unknown"

                    prev = manager._last_states.get(room_id)
                    if prev != status:
                        manager._last_states[room_id] = status
                        if prev is not None:  # Skip initial load
                            await manager.broadcast({
                                "event": "status_change",
                                "room_id": room_id,
                                "old_status": prev,
                                "new_status": status,
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                            })
                            asyncio.create_task(telegram_bot.send_message(f"🔄 **War Room Update**: {room_id}\nStatus changed from `{prev}` to `{status}`"))

                    # Check for new messages
                    channel_file = room_dir / "channel.jsonl"
                    if channel_file.exists():
                        lines = [line for line in open(channel_file) if line.strip()]
                        line_count = len(lines)
                        count_key = f"{room_id}_msgs"
                        prev_count = manager._last_states.get(count_key, 0)
                        if line_count > prev_count:
                            manager._last_states[count_key] = line_count
                            if prev_count > 0:
                                await manager.broadcast({
                                    "event": "new_message",
                                    "room_id": room_id,
                                    "message_count": line_count,
                                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                                })
                                # Parse new messages and send to telegram if plan/task
                                for i in range(prev_count, line_count):
                                    try:
                                        msg = json.loads(lines[i].strip())
                                        if msg.get("type") in ["task", "plan"]:
                                            msg_type = msg.get("type", "").capitalize()
                                            body = msg.get("body", "")
                                            ref = msg.get("ref", "")
                                            title = f"📝 **New {msg_type}** in {room_id}"
                                            if ref:
                                                title += f" ({ref})"
                                            asyncio.create_task(telegram_bot.send_message(f"{title}\n\n`{body}`"))
                                    except Exception:
                                        pass

                    # Check goals
                    goal_file = room_dir / "goal-verification.json"
                    config_file = room_dir / "config.json"
                    
                    goal_mtime = goal_file.stat().st_mtime if goal_file.exists() else 0
                    config_mtime = config_file.stat().st_mtime if config_file.exists() else 0
                    
                    goal_key = f"{room_id}_goals"
                    prev_goal_mtime = manager._last_states.get(goal_key, (0, 0))
                    
                    if prev_goal_mtime != (goal_mtime, config_mtime):
                        manager._last_states[goal_key] = (goal_mtime, config_mtime)
                        if prev_goal_mtime != (0, 0):  # Skip initial
                            await manager.broadcast({
                                "event": "goal_update",
                                "room_id": room_id,
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                            })
                            asyncio.create_task(telegram_bot.send_message(f"🎯 **Goal Update**: {room_id}\nGoals have been updated."))

        except Exception as e:
            pass  # Don't crash watcher on transient errors

        await asyncio.sleep(2)


@app.on_event("startup")
async def startup():
    asyncio.create_task(watch_warrooms())


# --- REST Endpoints ---

@app.get("/api/status")
async def get_status():
    """Get status of all war-rooms."""
    rooms = []
    summary = {"total": 0, "pending": 0, "engineering": 0, "qa_review": 0,
               "fixing": 0, "passed": 0, "failed": 0}

    if WARROOMS_DIR.exists():
        for room_dir in sorted(WARROOMS_DIR.iterdir()):
            if not room_dir.is_dir() or not room_dir.name.startswith("room-"):
                continue

            summary["total"] += 1
            room_data = _read_room(room_dir)
            rooms.append(room_data)

            status_key = room_data["status"].replace("-", "_")
            if status_key == "failed_final":
                status_key = "failed"
            if status_key in summary:
                summary[status_key] += 1

    return {"rooms": rooms, "summary": summary, "ws_clients": manager.client_count}


@app.get("/api/rooms/{room_id}")
async def get_room(room_id: str):
    """Get detailed info for a single room."""
    room_dir = WARROOMS_DIR / room_id
    if not room_dir.exists():
        return JSONResponse({"error": f"Room {room_id} not found"}, status_code=404)

    data = _read_room(room_dir, include_config=True, include_goals=True)
    return data


@app.get("/api/rooms/{room_id}/messages")
async def get_messages(room_id: str, type: Optional[str] = None, last: int = 0):
    """Get channel messages for a room."""
    channel_file = WARROOMS_DIR / room_id / "channel.jsonl"
    if not channel_file.exists():
        return {"messages": []}

    messages = []
    for line in open(channel_file):
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            if type and msg.get("type") != type:
                continue
            messages.append(msg)
        except json.JSONDecodeError:
            pass

    if last > 0:
        messages = messages[-last:]

    return {"messages": messages, "total": len(messages)}


@app.get("/api/rooms/{room_id}/goals")
async def get_goals(room_id: str):
    """Get goal verification status for a room."""
    room_dir = WARROOMS_DIR / room_id

    # Config goals
    config_file = room_dir / "config.json"
    config_goals = {}
    if config_file.exists():
        try:
            cfg = json.loads(config_file.read_text())
            config_goals = cfg.get("goals", {})
        except Exception:
            pass

    # Verification report
    verification = {}
    goal_file = room_dir / "goal-verification.json"
    if goal_file.exists():
        try:
            verification = json.loads(goal_file.read_text())
        except Exception:
            pass

    return {"config_goals": config_goals, "verification": verification}


@app.get("/api/run")
async def run_cmd(cmd: str):
    import subprocess
    try:
        result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=10)
        return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "0.2.0",
        "ws_clients": manager.client_count,
        "warrooms_dir": str(WARROOMS_DIR),
        "project_dir": str(PROJECT_DIR)
    }


class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str

@app.get("/api/telegram/config")
async def get_telegram_config():
    return telegram_bot.get_config()

@app.post("/api/telegram/config")
async def update_telegram_config(config: TelegramConfig):
    success = telegram_bot.save_config(config.bot_token, config.chat_id)
    if success:
        return {"status": "success"}
    return JSONResponse({"error": "Failed to save config"}, status_code=500)

@app.post("/api/telegram/test")
async def test_telegram_connection():
    success = await telegram_bot.send_message("Hello from Ostwin Dashboard! Connection successful \u2705")
    if success:
        return {"status": "success"}
    return JSONResponse({"error": "Failed to send test message. Check token and chat ID."}, status_code=500)


import re
from fastapi import Request

@app.get("/api/plans")
async def get_plans():
    plans = []
    for plan_file in PROJECT_DIR.glob("plan-*.md"):
        content = plan_file.read_text()
        status_match = re.search(r"> Status:\s*(.*)", content)
        created_match = re.search(r"> Created:\s*(.*)", content)
        
        status = status_match.group(1).strip() if status_match else "unknown"
        created = created_match.group(1).strip() if created_match else ""
        
        plans.append({
            "id": plan_file.stem,
            "status": status,
            "created": created
        })
    return {"plans": plans}

@app.post("/api/plans/{plan_id}/status")
async def update_plan_status(plan_id: str, req: Request):
    payload = await req.json()
    new_status = payload.get("status")
    if not new_status:
        return JSONResponse({"error": "status is required"}, status_code=400)
        
    plan_file = PROJECT_DIR / f"{plan_id}.md"
    if not plan_file.exists():
        return JSONResponse({"error": "Plan not found"}, status_code=404)
        
    content = plan_file.read_text()
    if re.search(r"> Status:\s*(.*)", content):
        content = re.sub(r"(> Status:\s*).*", f"\\g<1>{new_status}", content)
    else:
        content = f"> Status: {new_status}\n" + content
        
    plan_file.write_text(content)
    return {"status": "success", "new_status": new_status}

@app.post("/api/rooms/{room_id}/action")
async def room_action(room_id: str, req: Request):
    payload = await req.json()
    action = payload.get("action")
    if not action:
        return JSONResponse({"error": "action is required"}, status_code=400)
        
    room_dir = WARROOMS_DIR / room_id
    if not room_dir.exists():
        return JSONResponse({"error": "Room not found"}, status_code=404)
    
    control_file = room_dir / "control"
    control_file.write_text(action)
    return {"status": "success", "action": action}

@app.get("/api/goals")
async def get_all_goals():
    matrix = []
    if WARROOMS_DIR.exists():
        for room_dir in sorted(WARROOMS_DIR.iterdir()):
            if not room_dir.is_dir() or not room_dir.name.startswith("room-"):
                continue
            room_data = _read_room(room_dir, include_config=True, include_goals=True)
            matrix.append({
                "room_id": room_dir.name,
                "task_ref": room_data.get("task_ref", ""),
                "goals": room_data.get("goal_verification", {}).get("goals", []),
                "config_goals": room_data.get("config", {}).get("goals", {})
            })
    return {"matrix": matrix}


# --- WebSocket Endpoint ---

ws_router = create_ws_router(get_warrooms_dir, lambda d: _read_room(d))
app.include_router(ws_router)


# --- Frontend ---

@app.get("/")
async def root():
    frontend_path = SCRIPT_DIR / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return HTMLResponse("<h1>Ostwin Dashboard</h1><p>Frontend not found.</p>")


# Mount static files
frontend_dir = SCRIPT_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


# --- Helpers ---

def _read_room(room_dir: Path, include_config=False, include_goals=False) -> dict:
    """Read room data from filesystem."""
    status = "unknown"
    status_file = room_dir / "status"
    if status_file.exists():
        status = status_file.read_text().strip()

    task_ref = ""
    ref_file = room_dir / "task-ref"
    if ref_file.exists():
        task_ref = ref_file.read_text().strip()

    retries = 0
    retries_file = room_dir / "retries"
    if retries_file.exists():
        try:
            retries = int(retries_file.read_text().strip())
        except ValueError:
            pass

    # Message count
    msg_count = 0
    last_activity = None
    channel_file = room_dir / "channel.jsonl"
    if channel_file.exists():
        lines = [l for l in open(channel_file) if l.strip()]
        msg_count = len(lines)
        if lines:
            try:
                last_msg = json.loads(lines[-1])
                last_activity = last_msg.get("ts")
            except Exception:
                pass

    # Goals
    goals_met = 0
    goals_total = 0
    config_file = room_dir / "config.json"
    if config_file.exists():
        try:
            cfg = json.loads(config_file.read_text())
            goals_total = len(cfg.get("goals", {}).get("definition_of_done", []))
        except Exception:
            pass

    goal_file = room_dir / "goal-verification.json"
    if goal_file.exists():
        try:
            gv = json.loads(goal_file.read_text())
            goals_met = gv.get("summary", {}).get("goals_met", 0)
        except Exception:
            pass

    # Active PIDs
    active_pids = []
    pids_dir = room_dir / "pids"
    if pids_dir.exists():
        for pid_file in pids_dir.glob("*.pid"):
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)  # Check if alive
                active_pids.append(pid)
            except (ValueError, OSError):
                pass

    data = {
        "room_id": room_dir.name,
        "task_ref": task_ref,
        "status": status,
        "retries": retries,
        "messages": msg_count,
        "goals": f"{goals_met}/{goals_total}",
        "goals_met": goals_met,
        "goals_total": goals_total,
        "active_pids": active_pids,
        "last_activity": last_activity
    }

    if include_config and config_file.exists():
        try:
            data["config"] = json.loads(config_file.read_text())
        except Exception:
            pass

    if include_goals and goal_file.exists():
        try:
            data["goal_verification"] = json.loads(goal_file.read_text())
        except Exception:
            pass

    return data


# --- CLI ---
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ostwin Dashboard")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--project-dir", type=str, default=str(Path.cwd()))
    args = parser.parse_args()

    PROJECT_DIR = Path(args.project_dir).resolve()
    WARROOMS_DIR = PROJECT_DIR / ".war-rooms"

    print(f"[DASHBOARD] Starting on http://localhost:{args.port}")
    print(f"  Project: {PROJECT_DIR}")
    print(f"  War-rooms: {WARROOMS_DIR}")
    print(f"  WebSocket: ws://localhost:{args.port}/ws")
    print()

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
