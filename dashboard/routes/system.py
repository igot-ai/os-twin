import os
import json
import signal
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
try:
    import telegram_bot
except ImportError:
    telegram_bot = None

from dashboard.models import TelegramConfigRequest, UpdatePlanRoleConfigRequest
from dashboard.api_utils import (
    AGENTS_DIR, PROJECT_ROOT, 
    build_roles_list, get_plan_roles_config,
    resolve_plan_warrooms_dir, read_channel
)
from dashboard.constants import ROLE_DEFAULTS
from dashboard.auth import get_current_user

router = APIRouter(prefix="/api", tags=["system"])

@router.get("/status")
async def get_status(user: dict = Depends(get_current_user)):
    """Get current manager run status."""
    pid_file = AGENTS_DIR / "manager.pid"
    running = False
    pid = None
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            running = True
        except (ValueError, ProcessLookupError, PermissionError):
            pid_file.unlink(missing_ok=True)
            pid = None
    return {"running": running, "pid": pid}

@router.get("/run_tests_direct")
async def run_tests_direct(user: dict = Depends(get_current_user)):
    import subprocess
    # Note: Using absolute path as in original code
    result = subprocess.run(["python3", "/Users/paulaan/PycharmProjects/agent-os/manual_test.py"], capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}

@router.post("/stop")
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

@router.get("/release")
async def get_release(user: dict = Depends(get_current_user)):
    """Get the release notes."""
    release_file = AGENTS_DIR / "RELEASE.md"
    if not release_file.exists():
        return {"available": False, "content": None}
    return {"available": True, "content": release_file.read_text()}

@router.get("/config")
async def get_config(user: dict = Depends(get_current_user)):
    """Get OS Twin configuration."""
    config_file = AGENTS_DIR / "config.json"
    if not config_file.exists():
        return {}
    return json.loads(config_file.read_text())

@router.get("/telegram/config")
async def get_telegram_config():
    return telegram_bot.get_config()

@router.post("/telegram/config")
async def save_telegram_config(config: TelegramConfigRequest):
    success = telegram_bot.save_config(config.bot_token, config.chat_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save telegram config")
    return {"status": "success"}

@router.post("/telegram/test")
async def test_telegram_connection():
    success = await telegram_bot.send_message("Test message from OS Twin!")
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send test message")
    return {"status": "success"}

@router.get("/roles")
async def list_roles(user: dict = Depends(get_current_user)):
    config_file = AGENTS_DIR / "config.json"
    config = json.loads(config_file.read_text()) if config_file.exists() else {}
    roles = build_roles_list(config)
    return {"roles": roles, "count": len(roles)}

@router.get("/roles/{role_name}/config")
async def get_role_config(role_name: str, user: dict = Depends(get_current_user)):
    config_file = AGENTS_DIR / "config.json"
    config = json.loads(config_file.read_text()) if config_file.exists() else {}
    role_config = config.get(role_name, {})
    role_json_file = AGENTS_DIR / "roles" / role_name / "role.json"
    role_json = json.loads(role_json_file.read_text()) if role_json_file.exists() else {}
    registry_file = AGENTS_DIR / "roles" / "registry.json"
    registry_entry = {}
    if registry_file.exists():
        registry = json.loads(registry_file.read_text())
        for r in registry.get("roles", []):
            if r["name"] == role_name:
                registry_entry = r
                break
    defaults = ROLE_DEFAULTS.get(role_name, {})
    return {
        "name": role_name,
        "default_model": role_config.get("default_model", role_json.get("model", defaults.get("default_model", "gemini-3-flash-preview"))),
        "timeout_seconds": role_config.get("timeout_seconds", defaults.get("timeout_seconds", 600)),
        "cli": role_config.get("cli", role_json.get("cli", "deepagents")),
        "capabilities": registry_entry.get("capabilities", role_json.get("capabilities", [])),
        "quality_gates": registry_entry.get("quality_gates", role_json.get("quality_gates", [])),
        "instances": role_config.get("instances", {}),
        "role_json": role_json,
        "config_overrides": role_config,
    }

@router.get("/fs/browse")
async def browse_filesystem(path: str = Query(None)):
    if not path:
        path = str(Path.home())
    target = Path(path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=400, detail="Not a valid directory")
    dirs = []
    try:
        for entry in sorted(target.iterdir()):
            if entry.name.startswith('.'): continue
            if entry.is_dir():
                has_children = False
                try: has_children = any(c.is_dir() and not c.name.startswith('.') for c in entry.iterdir())
                except PermissionError: pass
                dirs.append({"name": entry.name, "path": str(entry), "has_children": has_children})
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    parent = str(target.parent) if target != target.parent else None
    return {"current": str(target), "parent": parent, "dirs": dirs}

@router.post("/shell")
async def shell_command(command: str):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

@router.get("/run_pytest_auth")
async def run_pytest_auth():
    import asyncio
    cmd = ["python3", "-m", "pytest", str(PROJECT_ROOT / "test_auth.py"), "-v"]
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

@router.get("/test_ws")
async def run_ws_test():
    import subprocess
    cmd = ["python3", str(PROJECT_ROOT / "test_ws.py")]
    process = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "stdout": process.stdout,
        "stderr": process.stderr,
        "returncode": process.returncode
    }

@router.get("/notifications")
async def get_notifications(
    plan_id: str = Query(..., description="Plan ID to scope notifications to"),
    room_id: str | None = None,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    """Retrieve notifications scoped to a plan's war-rooms directory.

    When *room_id* is supplied the endpoint returns entries from that room's
    ``channel.jsonl``.  Otherwise it aggregates across every room under the
    plan's resolved war-rooms directory.
    """
    warrooms_dir = resolve_plan_warrooms_dir(plan_id)

    if room_id:
        # ── Single room ─────────────────────────────────────────────
        room_dir = warrooms_dir / room_id
        if not room_dir.exists():
            return {"notifications": [], "plan_id": plan_id, "room_id": room_id}
        results = read_channel(room_dir)
        return {"notifications": results[-limit:], "plan_id": plan_id, "room_id": room_id}

    # ── All rooms in the plan ───────────────────────────────────────
    if not warrooms_dir.exists():
        return {"notifications": [], "plan_id": plan_id}

    results = []
    for room_dir in sorted(warrooms_dir.glob("room-*")):
        if room_dir.is_dir():
            for msg in read_channel(room_dir):
                # Tag each entry with its source room_id for the frontend
                msg.setdefault("room_id", room_dir.name)
                results.append(msg)

    # Sort by timestamp so the combined feed is chronological
    results.sort(key=lambda m: m.get("ts", ""))

    return {"notifications": results[-limit:], "plan_id": plan_id}
