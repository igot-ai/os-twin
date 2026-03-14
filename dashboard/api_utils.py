import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import List, AsyncIterator, Optional, Any

# === Paths ===
# Resolved relative to this file
_dashboard_parent = Path(__file__).parent.parent
if _dashboard_parent.name == ".agents":
    # Installed via ostwin init: .agents/dashboard/api_utils.py
    AGENTS_DIR = _dashboard_parent
    PROJECT_ROOT = AGENTS_DIR.parent
elif (_dashboard_parent / ".agents").exists():
    # Source repo layout: dashboard/api_utils.py alongside .agents/
    PROJECT_ROOT = _dashboard_parent
    AGENTS_DIR = PROJECT_ROOT / ".agents"
else:
    # Global installation: ~/.ostwin/dashboard/api_utils.py
    PROJECT_ROOT = _dashboard_parent
    AGENTS_DIR = _dashboard_parent

# Default war-rooms location
WARROOMS_DIR = PROJECT_ROOT / ".war-rooms"
DEMO_DIR = Path(__file__).parent

# Next.js export detection
NEXTJS_OUT_DIR = DEMO_DIR / "nextjs" / "out"
USE_NEXTJS = NEXTJS_OUT_DIR.exists() and (NEXTJS_OUT_DIR / "index.html").exists()

# === Helper Functions ===

def read_room(room_dir: Path) -> dict:
    """Read war-room state from disk."""
    import re as _re
    # Run pytest if requested (legacy hook)
    if (room_dir / "run_pytest_now").exists():
        import subprocess
        try:
            command = ["pwsh", "-File", str(AGENTS_DIR / "debug_test.ps1")]
            result = subprocess.run(command, capture_output=True, text=True)
            (room_dir / "pytest_results.txt").write_text(f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nCODE: {result.returncode}")
        except Exception as e:
            (room_dir / "pytest_results.txt").write_text(f"ERROR running command: {e}")
        (room_dir / "run_pytest_now").unlink()

    room_id = room_dir.name
    status = (room_dir / "status").read_text().strip() if (room_dir / "status").exists() else "unknown"
    task_ref = (room_dir / "task-ref").read_text().strip() if (room_dir / "task-ref").exists() else None
    retries_str = (room_dir / "retries").read_text().strip() if (room_dir / "retries").exists() else "0"
    retries = int(retries_str) if retries_str.isdigit() else 0
    task_md = (room_dir / "brief.md").read_text() if (room_dir / "brief.md").exists() else None

    # Fallback: extract ref from TASKS.md header
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

    # Fallback: use TASKS.md as description
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

async def process_notification(event_type: str, data: dict):
    """Asynchronously process notifications."""
    await asyncio.sleep(0.1)
    notifications_file = PROJECT_ROOT / ".data" / "notifications.log"
    notifications_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = json.dumps({"ts": timestamp, "event": event_type, "data": data})
    with open(notifications_file, "a") as f:
        f.write(log_entry + "\n")

# Router helpers
def resolve_plan_warrooms_dir(plan_id: str) -> Path:
    """Resolve the war-rooms directory for a plan."""
    import re
    plan_meta_file = AGENTS_DIR / "plans" / f"{plan_id}.meta.json"
    if plan_meta_file.exists():
        try:
            meta = json.loads(plan_meta_file.read_text())
            working_dir = meta.get("working_dir")
            if working_dir:
                return Path(working_dir) / ".war-rooms"
        except (json.JSONDecodeError, KeyError):
            pass

    plan_file = AGENTS_DIR / "plans" / f"{plan_id}.md"
    if plan_file.exists():
        content = plan_file.read_text()
        m = re.search(r"working_dir:\s*(.+)", content)
        if m:
            working_dir = m.group(1).strip()
            if working_dir and Path(working_dir).is_absolute():
                return Path(working_dir) / ".war-rooms"

def get_plan_roles_config(plan_id: str) -> dict:
    """Load the per-plan role config file, or fall back to global config."""
    plan_roles_file = AGENTS_DIR / "plans" / f"{plan_id}.roles.json"
    if plan_roles_file.exists():
        try:
            return json.loads(plan_roles_file.read_text())
        except json.JSONDecodeError:
            pass
    config_file = AGENTS_DIR / "config.json"
    if config_file.exists():
        return json.loads(config_file.read_text())
    return {}

def build_roles_list(config: dict) -> list:
    """Build roles list from registry + config."""
    from dashboard.constants import ROLE_DEFAULTS
    registry_file = AGENTS_DIR / "roles" / "registry.json"
    registry_roles = []
    if registry_file.exists():
        registry = json.loads(registry_file.read_text())
        registry_roles = registry.get("roles", [])

    roles = []
    for role in registry_roles:
        name = role["name"]
        role_config = config.get(name, {})
        defaults = ROLE_DEFAULTS.get(name, {})
        roles.append({
            "name": name,
            "description": role.get("description", ""),
            "default_model": role_config.get("default_model", role.get("default_model", defaults.get("default_model", "gemini-3-flash-preview"))),
            "timeout_seconds": role_config.get("timeout_seconds", defaults.get("timeout_seconds", 600)),
            "runner": role.get("runner"),
            "capabilities": role.get("capabilities", []),
            "supported_task_types": role.get("supported_task_types", []),
            "default_assignment": role.get("default_assignment", False),
            "instance_support": role.get("instance_support", False),
        })
    return roles

# Engagement Stubs (to be moved to dedicated store later)
def load_engagement(entity_id: str) -> dict:
    """Stub: Load reactions and comments for an entity."""
    return {"entity_id": entity_id, "reactions": {}, "comments": [], "stats": {"reactions": 0, "comments": 0}}

def toggle_reaction(entity_id: str, user_id: str, reaction_type: str) -> dict:
    """Stub: Toggle a reaction."""
    return {"status": "ok", "reactions": {reaction_type: [user_id]}}

def add_comment(entity_id: str, user_id: str, body: str, parent_id: Optional[str] = None):
    """Stub: Add a comment."""
    from dashboard.models import CommentRequest # Avoid circular
    comment = {"id": "stub-1", "user_id": user_id, "body": body, "ts": datetime.now(timezone.utc).isoformat()}
    return {"entity_id": entity_id, "stats": {"comments": 1}}, type('obj', (object,), {"model_dump": lambda: comment})()
