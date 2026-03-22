import os
import json
import asyncio
import re
import yaml
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, AsyncIterator, Optional, Any, Dict

from dashboard.models import Skill

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
# Preference: where the rooms actually are
if (DEMO_DIR / ".war-rooms").exists():
    # If DEMO_DIR has room-* subdirs, prefer it
    if any((DEMO_DIR / ".war-rooms").glob("room-*")):
        WARROOMS_DIR = DEMO_DIR / ".war-rooms"
SKILLS_DIRS = [
    AGENTS_DIR / "skills",
    PROJECT_ROOT / ".agents" / "skills",
    PROJECT_ROOT / ".deepagents" / "skills",
    Path("~/.deepagents/agent/skills").expanduser(),
]
if os.environ.get("OSTWIN_PROJECT_DIR"):
    PROJECT_ROOT = Path(os.environ.get("OSTWIN_PROJECT_DIR"))
    AGENTS_DIR = PROJECT_ROOT / ".agents"
    WARROOMS_DIR = PROJECT_ROOT / ".war-rooms"

# Next.js export detection
NEXTJS_OUT_DIR = DEMO_DIR / "nextjs" / "out"
USE_NEXTJS = NEXTJS_OUT_DIR.exists() and (NEXTJS_OUT_DIR / "index.html").exists()

# === Helper Functions ===

def read_room(room_dir: Path, include_metadata: bool = False) -> dict:
    """Read war-room state from disk.

    Args:
        room_dir: Path to the room directory.
        include_metadata: When True, also reads config.json, role instance
            files, state_changed_at, and artifact directory listing.
    """
    # Run pytest if requested (legacy hook)
    if (room_dir / "run_pytest_now").exists():
        try:
            command = ["pwsh", "-File", str(AGENTS_DIR / "debug_test.ps1")]
            result = subprocess.run(command, capture_output=True, text=True)
            log_msg = (
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}\n"
                f"CODE: {result.returncode}"
            )
            (room_dir / "pytest_results.txt").write_text(log_msg)
        except Exception as e:
            (room_dir / "pytest_results.txt").write_text(f"ERROR running command: {e}")
        (room_dir / "run_pytest_now").unlink()

    room_id = room_dir.name
    status_file = room_dir / "status"
    status = status_file.read_text().strip() if status_file.exists() else "unknown"
    
    tr_file = room_dir / "task-ref"
    task_ref = tr_file.read_text().strip() if tr_file.exists() else None
    
    retries_file = room_dir / "retries"
    retries_str = retries_file.read_text().strip() if retries_file.exists() else "0"
    retries = int(retries_str) if retries_str.isdigit() else 0
    
    brief_file = room_dir / "brief.md"
    task_md = brief_file.read_text() if brief_file.exists() else None

    # Fallback: extract ref from TASKS.md header
    if not task_ref:
        tasks_file = room_dir / "TASKS.md"
        if tasks_file.exists():
            header = tasks_file.read_text().split("\n", 1)[0]
            m = re.search(r"(EPIC-\d+|TASK-\d+)", header)
            if m:
                task_ref = m.group(1)
    # Fallback: derive from room-id
    if not task_ref:
        m = re.match(r"room-(\d+)", room_id)
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
        goal_total = len(re.findall(r"- \[[ xX]\]", tasks_content))
        goal_done = len(re.findall(r"- \[[xX]\]", tasks_content))

    channel_file = room_dir / "channel.jsonl"
    message_count = 0
    last_activity = None

    if channel_file.exists():
        raw_content = channel_file.read_text()
        lines = [l.strip() for l in raw_content.splitlines() if l.strip()]
        message_count = len(lines)
        if lines:
            try:
                last_msg = json.loads(lines[-1])
                last_activity = last_msg.get("ts")
            except json.JSONDecodeError:
                pass

    result = {
        "room_id": room_id,
        "task_ref": task_ref,
        "status": status,
        "retries": retries,
        "message_count": message_count,
        "last_activity": last_activity,
        "task_description": task_md or "",
        "goal_total": goal_total,
        "goal_done": goal_done,
    }

    # --- Extended metadata (opt-in to keep backward compatibility) ---
    if include_metadata:
        # lifecycle.json — state machine
        lifecycle_file = room_dir / "lifecycle.json"
        if lifecycle_file.exists():
            try:
                result["lifecycle"] = json.loads(lifecycle_file.read_text())
            except (json.JSONDecodeError, OSError):
                result["lifecycle"] = {}
        else:
            result["lifecycle"] = {}

        # config.json — room-level configuration
        config_file = room_dir / "config.json"
        if config_file.exists():
            try:
                result["config"] = json.loads(config_file.read_text())
            except (json.JSONDecodeError, OSError):
                result["config"] = {}
        else:
            result["config"] = {}

        # state_changed_at — last state transition timestamp
        sca_file = room_dir / "state_changed_at"
        result["state_changed_at"] = (
            sca_file.read_text().strip() if sca_file.exists() else None
        )

        # Role instance files (*_*.json except config.json)
        roles = []
        for f in sorted(room_dir.glob("*_*.json")):
            if f.name == "config.json":
                continue
            try:
                data = json.loads(f.read_text())
                if "role" in data and "instance_id" in data:
                    data["filename"] = f.name
                    roles.append(data)
            except (json.JSONDecodeError, KeyError, OSError):
                continue
        result["roles"] = roles

        # artifacts/ directory listing
        artifacts_dir = room_dir / "artifacts"
        if artifacts_dir.exists() and artifacts_dir.is_dir():
            result["artifact_files"] = sorted(
                e.name for e in artifacts_dir.iterdir() if e.is_file()
            )
        else:
            result["artifact_files"] = []

        # audit.log — last 20 lines
        audit_file = room_dir / "audit.log"
        if audit_file.exists():
            try:
                lines = audit_file.read_text().splitlines()
                if len(lines) > 20:
                    result["audit_tail"] = lines[-20:]
                else:
                    result["audit_tail"] = lines
            except OSError:
                result["audit_tail"] = []
        else:
            result["audit_tail"] = []

    return result

def read_channel(
    room_dir: Path,
    from_role: Optional[str] = None,
    to_role: Optional[str] = None,
    msg_type: Optional[str] = None,
    ref: Optional[str] = None,
    query: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """Read and filter messages from a channel file."""
    channel_file = room_dir / "channel.jsonl"
    if not channel_file.exists():
        return []
    messages = []

    # Pre-compile regex for query if provided
    q_re = re.compile(re.escape(query), re.IGNORECASE) if query else None

    for line in channel_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)

            # Apply filters
            if from_role and msg.get("from") != from_role:
                continue
            if to_role and msg.get("to") != to_role:
                continue
            if msg_type and msg.get("type") != msg_type:
                continue
            if ref and msg.get("ref") != ref:
                continue
            if q_re and not q_re.search(msg.get("body", "")):
                continue

            messages.append(msg)
        except json.JSONDecodeError:
            pass

    if limit is not None and limit > 0:
        messages = messages[-limit:]

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

def parse_skill_md(path: Path) -> Optional[Dict[str, Any]]:
    """Parse SKILL.md for metadata and content using YAML frontmatter."""
    skill_file = path / "SKILL.md"
    if not skill_file.exists():
        return None
    
    content = skill_file.read_text(encoding="utf-8")
    name = path.name
    description = ""
    tags = []
    body = content
    trust_level = "experimental"  # Model default fallback
    
    # Check for YAML frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1])
                if isinstance(meta, dict):
                    name = meta.get("name", name)
                    description = meta.get("description", description)
                    tags = meta.get("tags", tags)
                    if isinstance(tags, str):
                        tags = [t.strip() for t in tags.split(",")]
                    elif not isinstance(tags, list):
                        tags = []
                    trust_level = meta.get("trust_level", trust_level)
                    body = parts[2].strip()
            except Exception as e:
                logger = logging.getLogger("api_utils")
                logger.warning(f"Failed to parse YAML frontmatter in {skill_file}: {e}")

    # Determine source based on path
    source = "project"
    in_agents = str(PROJECT_ROOT / ".agents") in str(path)
    in_deepagents = str(PROJECT_ROOT / ".deepagents") in str(path)
    if in_agents or in_deepagents:
        source = "project"
    elif str(Path("~").expanduser()) in str(path):
        source = "user"
    else:
        source = "local"

    # Compute relative_path: path relative to the closest SKILLS_DIRS parent
    # e.g. "skills/roles/engineer/write-tests" for searchability
    relative_path = None
    resolved_path = path.resolve()
    for sdir in SKILLS_DIRS:
        try:
            resolved_sdir = sdir.resolve()
            if resolved_path.is_relative_to(resolved_sdir):
                # Get the path below the skills dir (e.g. "roles/engineer/write-tests")
                sub_path = resolved_path.relative_to(resolved_sdir)
                # Prefix with "skills/" so manager can search by this path
                relative_path = f"skills/{sub_path}"
                break
        except (ValueError, OSError):
            continue
    # Fallback: use the directory name as relative_path
    if not relative_path:
        relative_path = f"skills/{path.name}"

    return {
        "name": name,
        "description": description,
        "tags": tags,
        "path": str(path),
        "relative_path": relative_path,
        "content": body,
        "trust_level": trust_level,
        "source": source
    }

def sync_skills_from_disk(store: Any, skills_dirs: List[Path]) -> Dict[str, Any]:
    """Synchronize vector store with SKILL.md files on disk, handling additions, updates, and removals."""
    added = []
    updated = []
    removed = []
    synced_count = 0

    # 1. Collect current skills from disk (recursive glob)
    disk_skills = {}
    for sdir in skills_dirs:
        if not sdir.exists():
            continue
        for skill_md in sdir.rglob("SKILL.md"):
            skill_dir = skill_md.parent
            skill_data = parse_skill_md(skill_dir)
            if skill_data:
                disk_skills[skill_data["name"]] = skill_data

    # 2. Fetch all indexed skill names from the zvec store
    try:
        indexed_skills = store.get_all_skills(limit=1000)
        indexed_names = {s["name"] for s in indexed_skills}
    except Exception as e:
        logger = logging.getLogger("api_utils")
        logger.warning(f"Failed to fetch indexed skills during sync: {e}")
        indexed_names = set()

    # 3. Handle Additions and Updates
    for name, data in disk_skills.items():
        existing = store.get_skill(name)
        # Compare sanitized content to avoid unnecessary re-indexing
        # index_skill sanitizes on write
        content_bytes = data["content"].encode("ascii", errors="replace")
        content_ascii = content_bytes.decode("ascii")
        if existing and existing["content"] == content_ascii:
            continue
        
        if store.index_skill(
            name=data["name"],
            description=data["description"],
            tags=data.get("tags", []),
            path=data["path"],
            relative_path=data.get("relative_path", ""),
            trust_level=data.get("trust_level", "experimental"),
            source=data["source"],
            content=data["content"]
        ):
            synced_count += 1
            if not existing:
                added.append(name)
            else:
                updated.append(name)

    # 4. Handle Removals
    disk_names = set(disk_skills.keys())
    for name in indexed_names:
        if name not in disk_names:
            if store.delete_skill(name):
                removed.append(name)

    return {
        "synced_count": synced_count,
        "added": added,
        "updated": updated,
        "removed": removed
    }

def build_skills_list(
    query: Optional[str] = None, 
    role: Optional[str] = None, 
    tags: List[str] = []
) -> List[Skill]:
    """Helper to build and filter skills list from zvec and disk."""
    from dashboard import global_state
    store = getattr(global_state, "store", None)
    skills = []

    # 1. Semantic search or fetch all from zvec
    if store:
        try:
            if query:
                results = store.search_skills(query, limit=50)
                skills = [Skill(**res) for res in results]
            else:
                results = store.get_all_skills(limit=100)
                skills = [Skill(**res) for res in results]
        except Exception as e:
            logging.getLogger("api_utils").error("Skill store fetch failed: %s", e)

    # 2. Fallback/Enrich from disk if zvec is empty or unavailable
    # Also useful to catch newly added skills before sync
    skills_map = {s.name: s for s in skills}
    for sdir in SKILLS_DIRS:
        if not sdir.exists():
            continue
        try:
            for skill_md in sdir.rglob("SKILL.md"):
                path = skill_md.parent
                skill_data = parse_skill_md(path)
                if skill_data and skill_data["name"] not in skills_map:
                    skills_map[skill_data["name"]] = Skill(**skill_data)
        except Exception:
            pass
    skills = list(skills_map.values())

    # 3. Apply post-filters
    filtered = []
    for s in skills:
        # Role match
        if role:
            role_l = role.lower()
            # Try exact tag match, word-boundary match in description or content
            in_tags = any(role_l == t.lower() for t in s.tags)
            
            p_desc = rf"\b{re.escape(role_l)}\b"
            in_desc = bool(re.search(p_desc, s.description.lower()))
            
            p_cont = rf"\b{re.escape(role_l)}\b"
            has_cont = s.content and bool(re.search(p_cont, s.content.lower()))
            
            if not (in_tags or in_desc or has_cont):
                continue
            
        if tags and not any(t.lower() in [st.lower() for st in s.tags] for t in tags):
            continue
            
        filtered.append(s)
    
    # Sort results if not already ranked by search
    if not query:
        filtered.sort(key=lambda x: x.name)
    
    return filtered

# Router helpers
def resolve_plan_warrooms_dir(plan_id: str) -> Path:
    """Resolve the war-rooms directory for a plan.

    Resolution order:
    1. meta.json  → working_dir field
    2. plan .md   → working_dir: line (absolute or relative to PROJECT_ROOT)
    3. Fallback   → global WARROOMS_DIR
    """
    plan_meta_file = AGENTS_DIR / "plans" / f"{plan_id}.meta.json"
    if plan_meta_file.exists():
        try:
            meta = json.loads(plan_meta_file.read_text())
            working_dir = meta.get("working_dir")
            if working_dir:
                wd = Path(working_dir)
                if not wd.is_absolute():
                    wd = PROJECT_ROOT / wd
                return wd / ".war-rooms"
        except (json.JSONDecodeError, KeyError):
            pass

    plan_file = AGENTS_DIR / "plans" / f"{plan_id}.md"
    if plan_file.exists():
        content = plan_file.read_text()
        m = re.search(r"working_dir:\s*(.+)", content)
        if m:
            working_dir = m.group(1).strip()
            if working_dir:
                wd = Path(working_dir)
                if not wd.is_absolute():
                    wd = PROJECT_ROOT / wd
                return wd / ".war-rooms"

    # Fallback: global war-rooms directory
    return WARROOMS_DIR

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

def build_roles_list(config: dict, include_skills: bool = False) -> list:
    """Build roles list from registry + config.
    Optionally includes resolved skills for each role.
    """
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
        
        dm_def = defaults.get("default_model", "gemini-3-flash-preview")
        dm = role_config.get("default_model", role.get("default_model", dm_def))
        
        ts_def = defaults.get("timeout_seconds", 600)
        ts = role_config.get("timeout_seconds", ts_def)

        role_data = {
            "name": name,
            "description": role.get("description", ""),
            "default_model": dm,
            "timeout_seconds": ts,
            "runner": role.get("runner"),
            "capabilities": role.get("capabilities", []),
            "supported_task_types": role.get("supported_task_types", []),
            "default_assignment": role.get("default_assignment", False),
            "instance_support": role.get("instance_support", False),
        }
        
        if include_skills:
            # Simple resolution: skills matching the role name as a tag or in desc/content
            role_data["resolved_skills"] = build_skills_list(role=name)
            
        roles.append(role_data)
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
    from dashboard.models import CommentRequest  # Avoid circular
    ts = datetime.now(timezone.utc).isoformat()
    comment = {"id": "stub-1", "user_id": user_id, "body": body, "ts": ts}
    
    res = {"entity_id": entity_id, "stats": {"comments": 1}}
    return res, type('obj', (object,), {"model_dump": lambda: comment})()
