import os
import json
import signal
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends
try:
    import notify
except ImportError:
    notify = None

from dashboard.models import TelegramConfigRequest
from dashboard.api_utils import (
    AGENTS_DIR, PROJECT_ROOT, 
    resolve_plan_warrooms_dir, read_channel
)
from dashboard.auth import get_current_user

# Resolve Python: ~/.ostwin/.venv → system fallback
_VENV_PYTHON = Path.home() / ".ostwin" / ".venv" / "bin" / "python"
PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.is_file() else "python3"

router = APIRouter(prefix="/api", tags=["system"])

# ── .env settings ─────────────────────────────────────────────────────

_OSTWIN_DIR = Path.home() / ".ostwin"
_ENV_FILE = _OSTWIN_DIR / ".env"

def _parse_env(text: str) -> list[dict]:
    """Parse .env file into structured entries.
    Each entry is {type, key, value, enabled, comment} or {type, text}.
    """
    entries = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            entries.append({"type": "blank"})
        elif stripped.startswith("#") and "=" in stripped:
            # Commented-out variable: # KEY=value
            rest = stripped.lstrip("# ").strip()
            key, _, value = rest.partition("=")
            entries.append({"type": "var", "key": key.strip(), "value": value.strip(), "enabled": False, "comment": ""})
        elif stripped.startswith("#"):
            # Pure comment line
            entries.append({"type": "comment", "text": stripped})
        elif "=" in stripped:
            key, _, value = stripped.partition("=")
            entries.append({"type": "var", "key": key.strip(), "value": value.strip(), "enabled": True, "comment": ""})
        else:
            entries.append({"type": "comment", "text": stripped})
    return entries

def _serialize_env(entries: list[dict]) -> str:
    """Serialize structured entries back to .env format."""
    lines = []
    for e in entries:
        t = e.get("type", "comment")
        if t == "blank":
            lines.append("")
        elif t == "comment":
            lines.append(e.get("text", ""))
        elif t == "var":
            key = e.get("key", "")
            value = e.get("value", "")
            if e.get("enabled", True):
                lines.append(f"{key}={value}")
            else:
                lines.append(f"# {key}={value}")
    return "\n".join(lines) + "\n"

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

@router.get("/providers/api-keys")
async def check_api_keys(user: dict = Depends(get_current_user)):
    """Check which AI providers have API keys configured in the .env file."""
    keys_found = {
        "Claude": False,
        "GPT": False,
        "Gemini": False
    }
    
    if _ENV_FILE.exists():
        text = _ENV_FILE.read_text()
        entries = _parse_env(text)
        for e in entries:
            if e.get("type") == "var" and e.get("enabled", False):
                key = e.get("key", "")
                if key == "ANTHROPIC_API_KEY" and e.get("value"):
                    keys_found["Claude"] = True
                elif key == "OPENAI_API_KEY" and e.get("value"):
                    keys_found["GPT"] = True
                elif key == "GOOGLE_API_KEY" and e.get("value"):
                    keys_found["Gemini"] = True
                    
    return keys_found

@router.get("/run_tests_direct")
async def run_tests_direct(user: dict = Depends(get_current_user)):
    import subprocess
    test_file = Path(__file__).parent.parent / "tests" / "test_room_state_backend.py"
    result = subprocess.run([PYTHON, str(test_file)], capture_output=True, text=True)
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
    return notify.get_config()

@router.post("/telegram/config")
async def save_telegram_config(config: TelegramConfigRequest):
    success = notify.save_config(config.bot_token, config.chat_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save telegram config")
    return {"status": "success"}

@router.post("/telegram/test")
async def test_telegram_connection():
    success = await notify.send_message("Test message from OS Twin!")
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send test message")
    return {"status": "success"}

@router.post("/shell")
async def shell_command(command: str):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

@router.get("/run_pytest_auth")
async def run_pytest_auth():
    import asyncio
    cmd = [PYTHON, "-m", "pytest", str(PROJECT_ROOT / "test_auth.py"), "-v"]
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
    cmd = [PYTHON, str(PROJECT_ROOT / "test_ws.py")]
    process = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "stdout": process.stdout,
        "stderr": process.stderr,
        "returncode": process.returncode
    }

@router.get("/notifications")
async def get_notifications(
    plan_id: str | None = Query(None, description="Plan ID to scope notifications to"),
    room_id: str | None = None,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    """Retrieve notifications scoped to a plan's war-rooms directory.

    When *room_id* is supplied the endpoint returns entries from that room's
    ``channel.jsonl``.  Otherwise it aggregates across every room under the
    plan's resolved war-rooms directory.
    """
    if not plan_id:
        return {"notifications": [], "plan_id": None}

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


# ── ENV Settings (read/write ~/.ostwin/.env) ───────────────────────────

@router.get("/env")
async def get_env(user: dict = Depends(get_current_user)):
    """Read and parse ~/.ostwin/.env into structured entries."""
    if not _ENV_FILE.exists():
        return {"path": str(_ENV_FILE), "entries": [], "raw": ""}
    raw = _ENV_FILE.read_text()
    entries = _parse_env(raw)
    return {"path": str(_ENV_FILE), "entries": entries, "raw": raw}


_VAULT_MANAGED_KEYS = {
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
    "TELEGRAM_BOT_TOKEN", "DISCORD_TOKEN", "NGROK_AUTHTOKEN", "OSTWIN_API_KEY",
}


@router.post("/env")
async def save_env(request: dict, user: dict = Depends(get_current_user)):
    """Write structured entries back to ~/.ostwin/.env.

    Body: { "entries": [...] }
    Each entry: { type: "var"|"comment"|"blank", key?, value?, enabled?, text? }

    Known secret keys (API keys, bot tokens) are blocked from being
    written as plaintext.  Use the /api/settings/vault endpoint instead.
    """
    entries = request.get("entries", [])
    if not entries:
        raise HTTPException(status_code=400, detail="entries is required")

    for entry in entries:
        key = entry.get("key", "")
        value = entry.get("value", "")
        if key in _VAULT_MANAGED_KEYS and value and not value.startswith("${vault:"):
            raise HTTPException(
                status_code=400,
                detail=f"'{key}' is vault-managed. Use POST /api/settings/vault/... to set its value.",
            )

    # Ensure ~/.ostwin directory exists
    _OSTWIN_DIR.mkdir(parents=True, exist_ok=True)

    content = _serialize_env(entries)
    _ENV_FILE.write_text(content)
    return {"status": "saved", "path": str(_ENV_FILE)}


@router.post("/env/reload")
async def reload_env(user: dict = Depends(get_current_user)):
    """Trigger an immediate reload of ~/.ostwin/.env into os.environ.

    Useful after saving changes via POST /api/env — hot-reloads keys
    without waiting for the background poller (3 s cycle).
    """
    from dashboard.env_watcher import reload_env_file
    import dashboard.global_state as gs

    result = reload_env_file()
    all_changes = result["added"] + result["changed"] + result["removed"]
    if all_changes:
        await gs.broadcaster.broadcast(
            "env_reloaded",
            {
                "added": result["added"],
                "changed": result["changed"],
                "removed": result["removed"],
            },
        )
    return {"status": "reloaded", **result}

# ── Bot Process Management ────────────────────────────────────────────

@router.get("/bot/status")
async def bot_status(user: dict = Depends(get_current_user)):
    """Get the bot process status."""
    import dashboard.global_state as gs
    if gs.bot_manager is None:
        return {"running": False, "pid": None, "started_at": None, "available": False}
    status = gs.bot_manager.status()
    status["available"] = True
    return status


@router.post("/bot/start")
async def bot_start(user: dict = Depends(get_current_user)):
    """Start the bot process."""
    import dashboard.global_state as gs
    if gs.bot_manager is None:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")
    started = await gs.bot_manager.start()
    return {"started": started, **gs.bot_manager.status()}


@router.post("/bot/stop")
async def bot_stop(user: dict = Depends(get_current_user)):
    """Stop the bot process."""
    import dashboard.global_state as gs
    if gs.bot_manager is None:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")
    stopped = await gs.bot_manager.stop()
    return {"stopped": stopped}


@router.post("/bot/restart")
async def bot_restart(user: dict = Depends(get_current_user)):
    """Restart the bot process (stop + start)."""
    import dashboard.global_state as gs
    if gs.bot_manager is None:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")
    restarted = await gs.bot_manager.restart()
    return {"restarted": restarted, **gs.bot_manager.status()}


@router.get("/bot/logs")
async def bot_logs(limit: int = 100, user: dict = Depends(get_current_user)):
    """Get recent bot process logs."""
    import dashboard.global_state as gs
    if gs.bot_manager is None:
        return {"logs": [], "count": 0}
    logs = gs.bot_manager.get_logs(limit)
    return {"logs": logs, "count": len(logs)}


@router.get("/fs/browse")
async def browse_filesystem(path: str = Query(None), user: dict = Depends(get_current_user)):
    if not path:
        path = str(Path.home())
    target = Path(path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=400, detail="Not a valid directory")
    dirs = []
    try:
        for entry in sorted(target.iterdir()):
            if entry.name.startswith('.'):
                continue
            if entry.is_dir():
                has_children = False
                try:
                    has_children = any(c.is_dir() and not c.name.startswith('.') for c in entry.iterdir())
                except PermissionError:
                    pass
                dirs.append({"name": entry.name, "path": str(entry), "has_children": has_children})
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    parent = str(target.parent) if target != target.parent else None
    return {"current": str(target), "parent": parent, "dirs": dirs}
