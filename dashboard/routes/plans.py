import os
import json
import hashlib
import asyncio
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
_re_mod = re
from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse

from dashboard.models import CreatePlanRequest, SavePlanRequest, RefineRequest, UpdatePlanRoleConfigRequest, RunRequest
from dashboard.api_utils import (
    AGENTS_DIR, PROJECT_ROOT, WARROOMS_DIR, PLANS_DIR,
    get_plan_roles_config, build_roles_list, resolve_plan_warrooms_dir,
    resolve_runtime_plan_warrooms_dir,
    process_notification
)
import dashboard.global_state as global_state
from dashboard.auth import get_current_user

router = APIRouter(tags=["plans"])
logger = logging.getLogger(__name__)

def _merge_plan_meta(plan: dict, plans_dir: Path) -> None:
    """Merge {plan_id}.meta.json fields into a plan dict (in-place).
    
    Adds working_dir, warrooms_dir, launched_at, and a nested 'meta' object
    so the frontend has the full project context from plan creation.
    """
    meta_file = plans_dir / f"{plan['plan_id']}.meta.json"
    if not meta_file.exists():
        return
    try:
        meta = json.loads(meta_file.read_text())
        for key in ("working_dir", "warrooms_dir", "launched_at", "status"):
            if key in meta and meta[key]:
                plan[key] = meta[key]
        plan["meta"] = meta
    except (json.JSONDecodeError, OSError):
        pass

@router.get("/api/plans")
async def list_plans(user: dict = Depends(get_current_user)):
    """List all stored plans (disk is source of truth, zvec enriches)."""
    store = global_state.store
    plans_dir = PLANS_DIR

    if not plans_dir.exists():
        return {"plans": [], "count": 0}

    # Build a lookup of zvec-indexed plans for enrichment
    zvec_plans: Dict[str, dict] = {}
    if store:
        try:
            for p in store.get_all_plans():
                zvec_plans[p["plan_id"]] = p
        except Exception as e:
            logger.warning("Failed to load plans from zvec: %s", e)

    plans = []
    for f in sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        # Skip template and .refined.md variants
        if f.stem == "PLAN.template":
            continue
        if f.name.endswith(".refined.md"):
            continue
        content = f.read_text()
        if not content.strip():
            continue

        plan_id = f.stem

        # Start from zvec data if available, otherwise parse from disk
        if plan_id in zvec_plans:
            p = zvec_plans[plan_id].copy()
            # Ensure disk-derived fields are present
            if "filename" not in p or not p["filename"]:
                p["filename"] = f.name
            if "content" not in p or not p["content"]:
                p["content"] = content
        else:
            title_match = re.search(r"^# (?:Plan|PLAN):\s*(.+)", content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else plan_id

            epics_found = re.findall(r"^#{2,3} (?:(?:Epic|Task):\s*\S+|EPIC-\d+|TASK-\d+)", content, re.MULTILINE)
            epic_count = len(epics_found)

            status_match = re.search(r"^>\s*Status:\s*(\w+)", content, re.MULTILINE)
            status = status_match.group(1).lower() if status_match else "stored"

            p = {
                "plan_id": plan_id,
                "title": title,
                "content": content,
                "status": status,
                "epic_count": epic_count,
                "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
                "filename": f.name,
            }

            # Best-effort: backfill zvec index for this missing plan
            if store:
                try:
                    store.index_plan(
                        plan_id=plan_id, title=p["title"], content=content,
                        epic_count=p.get("epic_count", 0), filename=f.name,
                        status=p["status"], created_at=p["created_at"],
                        file_mtime=f.stat().st_mtime,
                    )
                    logger.info("Backfilled zvec index for plan %s", plan_id)
                except Exception as e:
                    logger.warning("Failed to backfill plan %s into zvec: %s", plan_id, e)

        # Enrich status from zvec epics
        if store:
            try:
                epics = store.get_epics_for_plan(plan_id)
                if epics and all(e.get("status") == "passed" for e in epics):
                    p["status"] = "completed"
            except Exception:
                pass

        # Merge meta.json for working_dir etc.
        _merge_plan_meta(p, plans_dir)

        # Enrich from progress.json if available
        warrooms_dir = p.get("warrooms_dir")
        if not warrooms_dir:
            runtime_warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
            if runtime_warrooms_dir:
                warrooms_dir = str(runtime_warrooms_dir)
                p["warrooms_dir"] = warrooms_dir

        if warrooms_dir:
            # Role distribution from DAG.json
            dag_file = Path(warrooms_dir) / "DAG.json"
            role_dist = {}
            if dag_file.exists():
                try:
                    dag_data = json.loads(dag_file.read_text())
                    for node_data in dag_data.get("nodes", {}).values():
                        role = node_data.get("role")
                        if role:
                            role_dist[role] = role_dist.get(role, 0) + 1
                except (json.JSONDecodeError, OSError):
                    pass
            p["role_distribution"] = role_dist

            prog_file = Path(warrooms_dir) / "progress.json"
            if prog_file.exists():
                try:
                    prog = json.loads(prog_file.read_text())
                    p["epic_count"] = prog.get("total", p.get("epic_count", 0))
                    p["completed_epics"] = prog.get("passed", 0)
                    p["active_epics"] = prog.get("active", 0)
                    p["pct_complete"] = prog.get("pct_complete", 0)
                    p["escalations"] = sum(
                        1 for r in prog.get("rooms", [])
                        if r.get("status") == "manager-triage"
                    )
                    cp_str = prog.get("critical_path", "")
                    if "/" in str(cp_str):
                        parts = str(cp_str).split("/")
                        p["critical_path"] = {"completed": int(parts[0]), "total": int(parts[1])}
                except (json.JSONDecodeError, OSError, ValueError):
                    pass

        # Add mock jitter if enabled
        if os.environ.get("NEXT_PUBLIC_ENABLE_MOCK_REALTIME") == "true":
            import random
            p["pct_complete"] = min(100, max(0, random.randint(30, 95)))
            p["active_epics"] = random.randint(1, max(1, p.get("epic_count", 5)))
            p["completed_epics"] = random.randint(0, max(0, p.get("epic_count", 5) - p["active_epics"]))

        plans.append(p)

    return {"plans": plans, "count": len(plans)}

def _get_stats_history() -> List[Dict]:
    history_file = AGENTS_DIR / "stats_history.json"
    if history_file.exists():
        try:
            return json.loads(history_file.read_text())
        except:
            return []
    return []

def _save_stats_snapshot(current_stats: Dict):
    history = _get_stats_history()
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    
    # One snapshot per day is enough for the trends/sparkline requested
    today_str = now_str[:10]
    if history and history[-1]["timestamp"][:10] == today_str:
        history[-1].update(current_stats)
        history[-1]["timestamp"] = now_str
    else:
        history.append({"timestamp": now_str, **current_stats})
    
    # Keep last 14 days
    if len(history) > 14:
        history = history[-14:]
    
    (AGENTS_DIR / "stats_history.json").write_text(json.dumps(history, indent=2) + "\n")

@router.get("/api/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    """Aggregate stats across all plans from progress.json files."""
    from datetime import timedelta
    plans_dir = PLANS_DIR
    total_plans = 0
    plan_status_counts = {"active": 0, "completed": 0, "draft": 0}
    active_epics = 0
    total_epics = 0
    passed_epics = 0
    escalations = 0

    seen_progress_files = set()
    
    if plans_dir.exists():
        for f in sorted(plans_dir.glob("*.md")):
            if f.stem == "PLAN.template" or f.name.endswith(".refined.md"):
                continue
            total_plans += 1
            
            plan_id = f.stem
            meta_file = plans_dir / f"{plan_id}.meta.json"
            plan_status = "draft"
            
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                    warrooms_dir = meta.get("warrooms_dir")
                    if warrooms_dir:
                        prog_file = Path(warrooms_dir) / "progress.json"
                        if prog_file.exists():
                            seen_progress_files.add(str(prog_file))
                            prog = json.loads(prog_file.read_text())
                            pct = prog.get("pct_complete", 0)
                            active = prog.get("active", 0)
                            passed = prog.get("passed", 0)
                            
                            if pct >= 100:
                                plan_status = "completed"
                            elif active > 0 or passed > 0:
                                plan_status = "active"
                            else:
                                plan_status = "draft"
                except (json.JSONDecodeError, OSError):
                    pass
            
            plan_status_counts[plan_status] += 1

    # Aggregate from unique progress files to avoid double-counting
    for pf_path in seen_progress_files:
        try:
            prog = json.loads(Path(pf_path).read_text())
            active_epics += prog.get("active", 0)
            total_epics += prog.get("total", 0)
            passed_epics += prog.get("passed", 0)
            for room in prog.get("rooms", []):
                if room.get("status") == "manager-triage":
                    escalations += 1
        except (json.JSONDecodeError, OSError):
            pass

    # Weighted average completion rate
    completion_rate = (passed_epics / total_epics * 100) if total_epics > 0 else 0
    
    current_stats = {
        "total_plans": total_plans,
        "active_epics": active_epics,
        "completion_rate": round(completion_rate, 1),
        "escalations_pending": escalations,
        "plan_status_counts": plan_status_counts
    }
    
    # Load history
    history = _get_stats_history()
    
    # Calculate trends
    def get_trend(key, days_ago):
        target_date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()[:10]
        # Find the value closest to target_date
        past_val = current_stats[key]
        if history:
            for h in reversed(history):
                if h["timestamp"][:10] <= target_date:
                    past_val = h[key]
                    break
        
        delta = current_stats[key] - past_val
        direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
        return {"direction": direction, "delta": abs(round(delta, 1))}

    # Active Epics Sparkline (7 points from last 14 days)
    sparkline_points = []
    # history currently has 14 mock points + 1 current snapshot
    full_history = history + [{"timestamp": datetime.now(timezone.utc).isoformat(), **current_stats}]
    
    # Take up to 7 samples from history
    if len(full_history) >= 7:
        # Sample evenly across history
        step = len(full_history) / 7
        for i in range(7):
            idx = int(i * step)
            sparkline_points.append(full_history[idx]["active_epics"])
    else:
        # Pad with current value if not enough history
        for h in full_history:
            sparkline_points.append(h["active_epics"])
        while len(sparkline_points) < 7:
            sparkline_points.insert(0, sparkline_points[0] if sparkline_points else 0)

    # If no history, we need to save one now so it starts accumulating
    if not history:
        _save_stats_snapshot(current_stats)

    # Add mock jitter if enabled
    is_mock = os.environ.get("NEXT_PUBLIC_ENABLE_MOCK_REALTIME") == "true"
    if is_mock:
        import random
        active_epics += random.randint(-1, 1)
        completion_rate = min(100, max(0, completion_rate + random.uniform(-0.5, 0.5)))
        if random.random() > 0.8:
            escalations += random.randint(0, 1)

    return {
        "total_plans": {
            "value": total_plans,
            "trend": get_trend("total_plans", 7),
            "distribution": {
                "active": plan_status_counts["active"],
                "completed": plan_status_counts["completed"],
                "draft": plan_status_counts["draft"]
            }
        },
        "active_epics": {
            "value": active_epics,
            "trend": get_trend("active_epics", 1),
            "sparkline": sparkline_points
        },
        "completion_rate": {
            "value": round(completion_rate, 1),
            "trend": get_trend("completion_rate", 7)
        },
        "escalations_pending": {
            "value": escalations,
            "trend": get_trend("escalations_pending", 1)
        }
    }

@router.post("/api/plans/{plan_id}/reload")
async def reload_plan_from_disk(plan_id: str, user: dict = Depends(get_current_user)):
    """Re-read .md file from disk and update zvec index."""
    plans_dir = PLANS_DIR
    plan_file = plans_dir / f"{plan_id}.md"
    if not plan_file.exists():
        raise HTTPException(status_code=404, detail="Plan file not found")
    
    content = plan_file.read_text()
    mtime = plan_file.stat().st_mtime
    
    # Re-parse metadata
    title_match = re.search(r"^# (?:Plan|PLAN):\s*(.+)", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else plan_id
    epics_found = re.findall(r"^#{2,3} (?:(?:Epic|Task):\s*\S+|EPIC-\d+|TASK-\d+)", content, re.MULTILINE)
    epic_count = len(epics_found)
    
    # Get created_at from meta.json if available
    meta_file = plans_dir / f"{plan_id}.meta.json"
    created_at = ""
    status = "stored"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text())
            created_at = meta.get("created_at", "")
            status = meta.get("status", "stored")
        except Exception: pass

    store = global_state.store
    if store:
        try:
            store.index_plan(
                plan_id=plan_id,
                title=title,
                content=content,
                epic_count=epic_count,
                filename=f"{plan_id}.md",
                status=status,
                created_at=created_at,
                file_mtime=mtime
            )
        except Exception as e:
            logger.error(f"Failed to update zvec in reload_plan: {e}")
            raise HTTPException(status_code=500, detail=str(e))
            
    return {"status": "reloaded", "plan_id": plan_id}

@router.get("/api/plans/{plan_id}/sync-status")
async def get_plan_sync_status(plan_id: str, user: dict = Depends(get_current_user)):
    """Check if the physical .md file is in sync with zvec index."""
    plans_dir = PLANS_DIR
    plan_file = plans_dir / f"{plan_id}.md"
    if not plan_file.exists():
        raise HTTPException(status_code=404, detail="Plan file not found")
    
    disk_mtime = plan_file.stat().st_mtime
    
    store = global_state.store
    zvec_mtime = 0.0
    if store:
        p = store.get_plan(plan_id)
        if p:
            zvec_mtime = p.get("file_mtime", 0.0)
    
    # Simple float comparison for mtime
    in_sync = abs(disk_mtime - zvec_mtime) < 0.001
    
    return {
        "in_sync": in_sync,
        "disk_mtime": disk_mtime,
        "zvec_mtime": zvec_mtime
    }

@router.get("/api/plans/{plan_id}")
async def get_plan(plan_id: str, user: dict = Depends(get_current_user)):
    """Get a specific plan with its epics and meta.json details."""
    store = global_state.store
    plan = None
    epics = []

    if store:
        plan = store.get_plan(plan_id)
        epics = store.get_epics_for_plan(plan_id)

    if not plan:
        plans_dir = PLANS_DIR
        plan_file = plans_dir / f"{plan_id}.md"
        if not plan_file.exists():
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
        content = plan_file.read_text()
        title_match = re.search(r"^# (?:Plan|PLAN):\s*(.+)", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else plan_id
        epic_count = len(re.findall(r"^#{2,3} (?:(?:Epic|Task):\s*\S+|EPIC-\d+|TASK-\d+)", content, re.MULTILINE))
        plan = {
            "plan_id": plan_id, "title": title, "content": content, "status": "stored",
            "epic_count": epic_count,
            "created_at": datetime.fromtimestamp(plan_file.stat().st_mtime, tz=timezone.utc).isoformat(),
            "filename": plan_file.name,
        }

    # --- Merge meta.json for full project context ---
    _merge_plan_meta(plan, PLANS_DIR)

    return {"plan": plan, "epics": epics}

@router.post("/api/plans/create")
async def create_plan(request: CreatePlanRequest):
    """Create a new plan."""
    raw = f"{request.path}:{datetime.now(timezone.utc).isoformat()}"
    plan_id = hashlib.sha256(raw.encode()).hexdigest()[:12]
    plans_dir = PLANS_DIR
    plans_dir.mkdir(exist_ok=True)
    plan_file = plans_dir / f"{plan_id}.md"
    working_dir = request.working_dir or request.path or ''

    # Auto-create project subfolder under PROJECT_ROOT/projects/ if no dir specified
    if not working_dir or working_dir == '.':
        slug = _re_mod.sub(r'[^a-zA-Z0-9]+', '-', request.title.lower()).strip('-')[:40]
        if not slug:
            slug = plan_id
        project_dir = PROJECT_ROOT / "projects" / slug
        project_dir.mkdir(parents=True, exist_ok=True)
        working_dir = str(project_dir)

    if request.content:
        plan_file.write_text(request.content)
    else:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan_file.write_text(f"# Plan: {request.title}\n\n> Created: {now}\n> Status: draft\n> Project: {request.path}\n\n## Config\n\nworking_dir: {working_dir}\n\n---\n\n## Goal\n\n{request.title}\n\n## Epics\n\n### EPIC-001 — {request.title}\n\n#### Definition of Done\n- [ ] Core functionality implemented\n\n#### Tasks\n- [ ] TASK-001 — Design and plan implementation\n\ndepends_on: []\n")

    meta_file = plans_dir / f"{plan_id}.meta.json"
    meta = {"plan_id": plan_id, "title": request.title, "working_dir": working_dir, "warrooms_dir": str(Path(working_dir) / ".war-rooms"), "created_at": datetime.now(timezone.utc).isoformat(), "status": "draft"}
    meta_file.write_text(json.dumps(meta, indent=2) + "\n")

    plan_roles_file = plans_dir / f"{plan_id}.roles.json"
    if not plan_roles_file.exists():
        global_config_file = AGENTS_DIR / "config.json"
        seed_config = json.loads(global_config_file.read_text()) if global_config_file.exists() else {}
        from dashboard.routes.roles import load_roles
        for role in load_roles():
            if role.name not in seed_config:
                seed_config[role.name] = {}
            rc = seed_config[role.name]
            rc.setdefault("default_model", role.version)
            rc.setdefault("timeout_seconds", role.timeout_seconds)
            if role.skill_refs:
                rc.setdefault("skill_refs", role.skill_refs)
        plan_roles_file.write_text(json.dumps(seed_config, indent=2) + "\n")

    store = global_state.store
    if store:
        try:
            store.index_plan(plan_id=plan_id, title=request.title, content=plan_file.read_text(), epic_count=1, filename=f"{plan_id}.md", status="draft", created_at=meta["created_at"], file_mtime=plan_file.stat().st_mtime)
        except Exception as e:
            logger.warning("Failed to index new plan %s in zvec: %s", plan_id, e)
    return {"plan_id": plan_id, "url": f"/plans/{plan_id}", "title": request.title, "path": request.path, "working_dir": working_dir, "filename": f"{plan_id}.md"}

@router.post("/api/plans/{plan_id}/save")
async def save_plan(plan_id: str, request: SavePlanRequest, user: dict = Depends(get_current_user)):
    plans_dir = PLANS_DIR
    plan_file = plans_dir / f"{plan_id}.md"
    if not plan_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    
    store = global_state.store
    old_content = plan_file.read_text()
    if old_content.strip() and old_content.strip() != request.content.strip():
        if store:
            try:
                old_title_match = re.search(r"^# (?:Plan|PLAN):\s*(.+)", old_content, re.MULTILINE)
                old_title = old_title_match.group(1).strip() if old_title_match else plan_id
                old_epics = len(re.findall(r"^#{2,3} (?:(?:Epic|Task):\s*\S+|EPIC-\d+|TASK-\d+)", old_content, re.MULTILINE))
                store.save_plan_version(
                    plan_id=plan_id, content=old_content, title=old_title,
                    epic_count=old_epics, change_source=request.change_source,
                )
            except Exception as e:
                logger.warning("Failed to snapshot plan version for %s: %s", plan_id, e)

    plan_file.write_text(request.content)
    new_mtime = plan_file.stat().st_mtime
    
    # Update meta if title changed (best effort)
    title_match = re.search(r"^# (?:Plan|PLAN):\s*(.+)", request.content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else plan_id
    
    meta = {"plan_id": plan_id, "title": title, "status": "draft", "created_at": datetime.now(timezone.utc).isoformat()}
    meta_file = plans_dir / f"{plan_id}.meta.json"
    if meta_file.exists():
        try:
            stored_meta = json.loads(meta_file.read_text())
            meta.update(stored_meta) # keep existing fields
            meta["title"] = title    # update title from content
            meta_file.write_text(json.dumps(meta, indent=2) + "\n")
        except Exception: pass

    # Update zvec if available
    if store:
        try:
            # Re-parse epic count
            epics_found = re.findall(r"^#{2,3} (?:(?:Epic|Task):\s*\S+|EPIC-\d+|TASK-\d+)", request.content, re.MULTILINE)
            epic_count = len(epics_found)
            
            store.index_plan(
                plan_id=plan_id, 
                title=title,
                content=request.content,
                epic_count=epic_count,
                filename=f"{plan_id}.md",
                status=meta.get("status", "draft"),
                created_at=meta.get("created_at", datetime.now(timezone.utc).isoformat()),
                file_mtime=new_mtime
            )
        except Exception as e:
            logger.error(f"Failed to update zvec in save_plan: {e}")

    return {"status": "saved", "plan_id": plan_id}

@router.get("/api/plans/{plan_id}/roles")
async def get_plan_roles(plan_id: str, user: dict = Depends(get_current_user)):
    """Get the roles assigned to a plan, combining registry defaults with per-plan config."""
    config = get_plan_roles_config(plan_id)
    roles = build_roles_list(config, include_skills=False)
    if not roles:
        from dashboard.routes.roles import load_roles
        roles = [
            {"name": r.name, "description": r.description, "default_model": r.version,
             "timeout_seconds": r.timeout_seconds, "skill_refs": r.skill_refs}
            for r in load_roles()
        ]
    return {"role_defaults": roles}

@router.get("/api/plans/{plan_id}/config")
async def get_plan_config(plan_id: str, user: dict = Depends(get_current_user)):
    """Get the role configuration for a plan."""
    return get_plan_roles_config(plan_id)

@router.post("/api/plans/{plan_id}/config")
async def update_plan_config(plan_id: str, config: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Update the role configuration for a plan."""
    plans_dir = PLANS_DIR
    config_file = plans_dir / f"{plan_id}.roles.json"
    config_file.write_text(json.dumps(config, indent=2) + "\n")
    return {"status": "updated", "plan_id": plan_id}

@router.post("/api/plans/{plan_id}/skills")
async def attach_skill(plan_id: str, skill: Dict[str, str], user: dict = Depends(get_current_user)):
    """Attach a skill to a plan."""
    config = get_plan_roles_config(plan_id)
    if "attached_skills" not in config:
        config["attached_skills"] = []
    
    skill_name = skill.get("name")
    if not skill_name:
        raise HTTPException(status_code=400, detail="Skill name is required")
         
    if skill_name not in config["attached_skills"]:
        config["attached_skills"].append(skill_name)
    
    plans_dir = PLANS_DIR
    config_file = plans_dir / f"{plan_id}.roles.json"
    config_file.write_text(json.dumps(config, indent=2) + "\n")
    return {"status": "attached", "plan_id": plan_id, "skill": skill_name}

@router.delete("/api/plans/{plan_id}/skills/{skill_name}")
async def detach_skill(plan_id: str, skill_name: str, user: dict = Depends(get_current_user)):
    """Detach a skill from a plan."""
    config = get_plan_roles_config(plan_id)
    if "attached_skills" in config and skill_name in config["attached_skills"]:
        config["attached_skills"].remove(skill_name)
    
    plans_dir = PLANS_DIR
    config_file = plans_dir / f"{plan_id}.roles.json"
    config_file.write_text(json.dumps(config, indent=2) + "\n")
    return {"status": "detached", "plan_id": plan_id, "skill": skill_name}

@router.post("/api/run")
async def run_plan(request: RunRequest, user: dict = Depends(get_current_user)):
    """Launch OS Twin with the provided plan content.

    plan_id is required. The endpoint is idempotent:
    - .md file is only written when the content actually changed.
    - .meta.json is upserted (preserves created_at and custom fields).
    - .roles.json is only seeded from global config when it does not exist yet,
      so user customisations are never overwritten.
    """
    plan = request.plan.strip()
    if not plan:
        raise HTTPException(status_code=422, detail="Plan content is empty")

    # Quick pre-flight: must contain at least one ## Epic: or ## Task: section
    if not _re_mod.search(r"^#{2,3} (?:EPIC-|Task:|Epic:)", plan, _re_mod.MULTILINE):
        raise HTTPException(status_code=400, detail="Plan contains no epics or tasks. Add at least one '## EPIC-XXX - Title' section.")

    run_sh = AGENTS_DIR / "run.sh"
    if not run_sh.exists():
        raise HTTPException(status_code=500, detail="OS Twin run.sh not found")

    plans_dir = PLANS_DIR
    plans_dir.mkdir(exist_ok=True)

    plan_id = request.plan_id
    plan_path = plans_dir / f"{plan_id}.md"
    plan_filename = plan_path.name

    # --- .md: only write when content actually changed ---
    existing_content = plan_path.read_text() if plan_path.exists() else None
    store = global_state.store
    if existing_content != plan:
        # Snapshot old content before overwriting
        if existing_content and existing_content.strip() and store:
            try:
                old_title_match = _re_mod.search(r"^# (?:Plan|PLAN):\s*(.+)", existing_content, _re_mod.MULTILINE)
                old_title = old_title_match.group(1).strip() if old_title_match else plan_id
                old_epics = len(_re_mod.findall(r"^#{2,3} (?:(?:Epic|Task):\s*\S+|EPIC-\d+|TASK-\d+)", existing_content, _re_mod.MULTILINE))
                store.save_plan_version(
                    plan_id=plan_id, content=existing_content, title=old_title,
                    epic_count=old_epics, change_source="expansion",
                )
            except Exception as e:
                logger.warning("Failed to snapshot plan version before launch %s: %s", plan_id, e)
        plan_path.write_text(plan)
        logger.info(f"run_plan: wrote updated plan content for {plan_id}")
    else:
        logger.debug(f"run_plan: plan content unchanged for {plan_id}, skipping write")

    # Extract title
    title_match = _re_mod.search(r"^# (?:Plan|PLAN):\s*(.+)", plan, _re_mod.MULTILINE)
    title = title_match.group(1).strip() if title_match else plan_id

    # Extract working_dir from plan content (## Config section)
    working_dir = None
    wd_match = _re_mod.search(r"working_dir:\s*(.+)", plan)
    if wd_match:
        working_dir = wd_match.group(1).strip()
    if not working_dir or working_dir == '.':
        working_dir = str(PROJECT_ROOT)

    # If working_dir is relative, resolve under PROJECT_ROOT/projects/
    wd_path = Path(working_dir)
    if not wd_path.is_absolute():
        wd_path = PROJECT_ROOT / "projects" / working_dir
    # Create the directory if it doesn't exist
    wd_path.mkdir(parents=True, exist_ok=True)
    working_dir = str(wd_path)

    # --- .meta.json: upsert — merge into existing, preserve created_at ---
    meta_path = plans_dir / f"{plan_id}.meta.json"
    existing_meta = {}
    if meta_path.exists():
        try:
            existing_meta = json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    meta = {
        **existing_meta,                           # keep previous fields
        "plan_id": plan_id,
        "title": title,
        "working_dir": working_dir,
        "warrooms_dir": str(Path(working_dir) / ".war-rooms") if Path(working_dir).is_absolute() else str(PROJECT_ROOT / working_dir / ".war-rooms"),
        "status": "launched",
    }
    # Preserve original created_at; only set if missing
    if "created_at" not in meta:
        meta["created_at"] = datetime.now(timezone.utc).isoformat()
    meta["launched_at"] = datetime.now(timezone.utc).isoformat()

    meta_path.write_text(json.dumps(meta, indent=2))

    # --- .roles.json: seed from engine config + dashboard roles when file does NOT exist ---
    role_config_path = plans_dir / f"{plan_id}.roles.json"
    if not role_config_path.exists():
        global_config_file = AGENTS_DIR / "config.json"
        seed_config = {}
        if global_config_file.exists():
            try:
                seed_config = json.loads(global_config_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        # Merge dashboard roles (which have skill_refs) into the plan config
        from dashboard.routes.roles import load_roles
        for role in load_roles():
            if role.name not in seed_config:
                seed_config[role.name] = {}
            rc = seed_config[role.name]
            rc.setdefault("default_model", role.version)
            rc.setdefault("timeout_seconds", role.timeout_seconds)
            if role.skill_refs:
                rc.setdefault("skill_refs", role.skill_refs)
        role_config_path.write_text(json.dumps(seed_config, indent=2))
        logger.info(f"run_plan: seeded roles.json for {plan_id} from engine config + dashboard roles")
    else:
        logger.debug(f"run_plan: roles.json already exists for {plan_id}, preserving user customisations")

    # Sync with zvec store if available
    store = global_state.store
    if store:
        try:
            from dashboard.zvec_store import OSTwinStore
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
            logger.error(f"zvec: plan indexing failed ({e})")

    # Ensure target project is initialized with ostwin
    wd_path = Path(working_dir) if Path(working_dir).is_absolute() else PROJECT_ROOT / working_dir
    if not (wd_path / ".agents").exists():
        logger.info(f"run_plan: target dir {wd_path} not initialized, running ostwin init...")
        ostwin_bin = AGENTS_DIR / "bin" / "ostwin"
        if ostwin_bin.exists():
            init_result = subprocess.run(
                [str(ostwin_bin), "init"],
                cwd=str(wd_path),
                capture_output=True, text=True, timeout=120,
            )
            if init_result.returncode != 0:
                logger.error(f"ostwin init failed in {wd_path}: {init_result.stderr}")
                raise HTTPException(status_code=500, detail=f"ostwin init failed in {wd_path}: {init_result.stderr[:200]}")
            logger.info(f"run_plan: ostwin init completed in {wd_path}")
        else:
            logger.warning(f"ostwin binary not found at {ostwin_bin}, skipping init")

    # Spawn OS Twin in background
    subprocess.Popen(
        [str(run_sh), plan_path],
        cwd=str(wd_path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return {"status": "launched", "plan_file": plan_filename, "plan_id": plan_id}

@router.post("/api/plans/{plan_id}/status")
async def update_plan_status(plan_id: str, request: dict):
    plans_dir = PLANS_DIR
    meta_file = plans_dir / f"{plan_id}.meta.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    meta = json.loads(meta_file.read_text())
    meta["status"] = request.get("status", meta["status"])
    meta_file.write_text(json.dumps(meta, indent=2) + "\n")
    
    # Update zvec if available
    store = global_state.store
    if store:
        try:
            store.index_plan(
                plan_id=plan_id, title=meta.get("title", ""),
                content="", # placeholder
                status=meta["status"],
                filename=f"{plan_id}.md",
                created_at=meta.get("created_at", "")
            )
        except Exception: pass
    return {"status": "updated", "plan_id": plan_id, "new_status": meta["status"]}

# --- Plan Versioning ---

@router.get("/api/plans/{plan_id}/versions")
async def list_plan_versions(plan_id: str, user: dict = Depends(get_current_user)):
    """List all versions for a plan (content excluded for performance)."""
    store = global_state.store
    if not store or not hasattr(store, 'get_plan_versions'):
        return {"plan_id": plan_id, "versions": [], "count": 0}
    try:
        versions = store.get_plan_versions(plan_id)
    except Exception:
        return {"plan_id": plan_id, "versions": [], "count": 0}
    return {"plan_id": plan_id, "versions": versions, "count": len(versions)}

@router.get("/api/plans/{plan_id}/versions/{version}")
async def get_plan_version(plan_id: str, version: int, user: dict = Depends(get_current_user)):
    """Fetch a specific plan version with full content."""
    store = global_state.store
    if not store or not hasattr(store, 'get_plan_version'):
        raise HTTPException(status_code=503, detail="Version store not available")
    try:
        v = store.get_plan_version(plan_id, version)
    except Exception:
        raise HTTPException(status_code=503, detail="Version store error")
    if not v:
        raise HTTPException(status_code=404, detail=f"Version {version} not found for plan {plan_id}")
    return {"plan_id": plan_id, "version": v}

@router.post("/api/plans/{plan_id}/versions/{version}/restore")
async def restore_plan_version(plan_id: str, version: int, user: dict = Depends(get_current_user)):
    """Restore a previous version as the current plan content."""
    store = global_state.store
    if not store:
        raise HTTPException(status_code=503, detail="Version store not available")

    # Fetch the version to restore
    v = store.get_plan_version(plan_id, version)
    if not v:
        raise HTTPException(status_code=404, detail=f"Version {version} not found for plan {plan_id}")

    plans_dir = PLANS_DIR
    plan_file = plans_dir / f"{plan_id}.md"
    if not plan_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    # Snapshot current content before restoring
    current_content = plan_file.read_text()
    if current_content.strip():
        try:
            cur_title_match = re.search(r"^# (?:Plan|PLAN):\s*(.+)", current_content, re.MULTILINE)
            cur_title = cur_title_match.group(1).strip() if cur_title_match else plan_id
            cur_epics = len(re.findall(r"^#{2,3} (?:(?:Epic|Task):\s*\S+|EPIC-\d+|TASK-\d+)", current_content, re.MULTILINE))
            store.save_plan_version(
                plan_id=plan_id, content=current_content, title=cur_title,
                epic_count=cur_epics, change_source="before_restore",
            )
        except Exception as e:
            logger.warning("Failed to snapshot before restore %s: %s", plan_id, e)

    # Restore
    restored_content = v["content"]
    plan_file.write_text(restored_content)

    # Update zvec plan index
    try:
        title_match = re.search(r"^# (?:Plan|PLAN):\s*(.+)", restored_content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else plan_id
        epics_found = re.findall(r"^#{2,3} (?:(?:Epic|Task):\s*\S+|EPIC-\d+|TASK-\d+)", restored_content, re.MULTILINE)
        store.index_plan(
            plan_id=plan_id, title=title, content=restored_content,
            epic_count=len(epics_found), filename=f"{plan_id}.md",
        )
    except Exception as e:
        logger.warning("Failed to update zvec after restore %s: %s", plan_id, e)

    return {"status": "restored", "plan_id": plan_id, "restored_version": version}

@router.get("/api/plans/{plan_id}/changes")
async def list_plan_changes(plan_id: str, user: dict = Depends(get_current_user)):
    """Unified timeline of plan versions and git-based asset changes."""
    store = global_state.store
    plans_dir = PLANS_DIR
    plan_file = plans_dir / f"{plan_id}.md"
    
    if not plan_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    # 1. Get working_dir from plan meta
    working_dir = None
    meta_file = plans_dir / f"{plan_id}.meta.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text())
            working_dir = meta.get("working_dir")
        except Exception:
            pass
    
    if not working_dir:
        # Try resolving via api_utils
        from dashboard.api_utils import resolve_plan_warrooms_dir
        warrooms_dir = resolve_plan_warrooms_dir(plan_id)
        if warrooms_dir:
            working_dir = str(warrooms_dir.parent)

    changes = []
    
    # 2. Get git log and status if available
    if working_dir and Path(working_dir).exists():
        try:
            # Check if we are in a git repo
            proc_check = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--is-inside-work-tree",
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc_check.communicate()
            
            if proc_check.returncode == 0:
                # 2.1. Get uncommitted changes (git status)
                proc_status = await asyncio.create_subprocess_exec(
                    "git", "status", "--porcelain",
                    cwd=working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout_status, _ = await proc_status.communicate()
                if stdout_status:
                    status_lines = stdout_status.decode().splitlines()
                    uncommitted_files = []
                    for line in status_lines:
                        if len(line) > 3:
                            uncommitted_files.append(line[3:].strip())
                    
                    if uncommitted_files:
                        changes.append({
                            "id": "uncommitted",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "author": "Current Session",
                            "message": "Uncommitted local changes",
                            "files": uncommitted_files,
                            "type": "asset_change",
                            "source": "git",
                            "is_uncommitted": True
                        })

                # 2.2. Get last 50 commits with file changes
                cmd = ["git", "log", "-n", "50", "--pretty=format:%H|%cI|%an|%s", "--name-only"]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0:
                    lines = stdout.decode().splitlines()
                    current_commit = None
                    for line in lines:
                        if "|" in line:
                            parts = line.split("|", 3)
                            if len(parts) == 4:
                                current_commit = {
                                    "id": parts[0],
                                    "timestamp": parts[1],
                                    "author": parts[2],
                                    "message": parts[3],
                                    "files": [],
                                    "type": "asset_change",
                                    "source": "git"
                                }
                                changes.append(current_commit)
                        elif line.strip() and current_commit:
                            current_commit["files"].append(line.strip())
        except Exception as e:
            logger.warning(f"Failed to read git log for {plan_id}: {e}")

    # 3. Add plan versions from zvec if available
    if store:
        if hasattr(store, 'get_plan_versions'):
            try:
                versions = store.get_plan_versions(plan_id)
                for v in versions:
                    changes.append({
                        "id": v["id"],
                        "version": v["version"],
                        "timestamp": v["created_at"],
                        "title": v["title"],
                        "change_source": v["change_source"],
                        "type": "plan_version",
                        "source": "zvec"
                    })
            except Exception: pass

        if hasattr(store, 'get_changes_for_plan'):
            try:
                asset_changes = store.get_changes_for_plan(plan_id)
                for ac in asset_changes:
                    changes.append({
                        "id": ac["id"],
                        "timestamp": ac["timestamp"],
                        "change_type": ac["change_type"],
                        "file_path": ac["file_path"],
                        "diff_summary": ac["diff_summary"],
                        "source": ac["source"],
                        "type": "asset_change"
                    })
            except Exception: pass

    # 4. Sort all changes by timestamp desc
    changes.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {"plan_id": plan_id, "changes": changes, "count": len(changes)}

@router.get("/api/plans/{plan_id}/changes/{change_id}/diff")
async def get_change_diff(plan_id: str, change_id: str, file_path: str = Query(None), user: dict = Depends(get_current_user)):
    """Fetch the diff for a specific change entry."""
    store = global_state.store
    plans_dir = PLANS_DIR

    # Case 1: Plan version (zvec)
    if change_id.startswith(f"{plan_id}-v"):
        if not store or not hasattr(store, 'get_plan_version'):
            raise HTTPException(status_code=503, detail="Version store not available")
        
        try:
            # We want to compare v with v-1
            m = re.match(rf"{plan_id}-v(\d+)", change_id)
            if not m:
                raise HTTPException(status_code=400, detail="Invalid change ID")
            v_num = int(m.group(1))
            
            v_curr = store.get_plan_version(plan_id, v_num)
            if not v_curr:
                raise HTTPException(status_code=404, detail="Version not found")
            
            # Get previous content
            v_prev_content = ""
            if v_num > 1:
                v_prev = store.get_plan_version(plan_id, v_num - 1)
                if v_prev:
                    v_prev_content = v_prev["content"]
            else:
                # v1 should be compared with nothing or the very first state if known
                pass

            import difflib
            diff = difflib.unified_diff(
                v_prev_content.splitlines(keepends=True),
                v_curr["content"].splitlines(keepends=True),
                fromfile=f"v{v_num-1}", tofile=f"v{v_num}"
            )
            return {"diff": "".join(diff), "type": "plan_version", "id": change_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Case 1.5: Asset change from zvec
    if store and hasattr(store, 'get_change_event'):
        ce = store.get_change_event(change_id)
        if ce:
            return {
                "diff": ce.get("diff_summary", "No diff available."),
                "type": "asset_change",
                "id": change_id,
                "source": ce.get("source"),
                "file_path": ce.get("file_path")
            }

    # Case 2: Git commit (asset change)
    # 2.1. Find working_dir
    working_dir = None
    meta_file = plans_dir / f"{plan_id}.meta.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text())
            working_dir = meta.get("working_dir")
        except Exception:
            pass
    if not working_dir:
        from dashboard.api_utils import resolve_plan_warrooms_dir
        warrooms_dir = resolve_plan_warrooms_dir(plan_id)
        if warrooms_dir:
            working_dir = str(warrooms_dir.parent)

    if working_dir and Path(working_dir).exists():
        try:
            if change_id == "uncommitted":
                # git diff for unstaged and staged changes
                cmd = ["git", "diff", "HEAD", "--no-color"]
                if file_path:
                    cmd = ["git", "diff", "HEAD", "--no-color", "--", file_path]
            else:
                # git show change_id
                cmd = ["git", "show", change_id, "--no-color"]
                if file_path:
                    cmd = ["git", "show", change_id, "--no-color", "--", file_path]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                diff_out = stdout.decode()
                if not diff_out and change_id == "uncommitted":
                    diff_out = "No diff available for uncommitted changes (might be untracked files)."
                return {"diff": diff_out, "type": "asset_change", "id": change_id}
            else:
                raise HTTPException(status_code=500, detail=stderr.decode())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=404, detail="Change entry not found")

@router.get("/api/goals")
async def get_all_goals():
    """Aggregate goals from all plans."""
    plans_dir = PLANS_DIR
    if not plans_dir.exists():
        return {"goals": []}
    
    all_goals = []
    for f in plans_dir.glob("*.md"):
        if f.stem == "PLAN.template":
            continue
        content = f.read_text()
        # Simple heuristic for goals
        goal_section = re.search(r"## Goal\n\n(.*?)\n\n##", content, re.DOTALL)
        if goal_section:
            all_goals.append({
                "plan_id": f.stem,
                "goal": goal_section.group(1).strip()
            })
    return {"goals": all_goals}
@router.post("/api/plans/refine")
async def refine_plan_endpoint(request: RefineRequest):
    try:
        from plan_agent import refine_plan
        plans_dir = PLANS_DIR
        plan_content = request.plan_content
        if request.plan_id and not plan_content:
            p_file = plans_dir / f"{request.plan_id}.md"
            if p_file.exists():
                plan_content = p_file.read_text()
        result = await refine_plan(user_message=request.message, plan_content=plan_content, chat_history=request.chat_history, model=request.model, plans_dir=plans_dir if plans_dir.exists() else None, working_dir=request.working_dir or None)
        if isinstance(result, dict):
            # Backward compatible: refined_plan is a string. Rich info is also available.
            return {
                "refined_plan": result.get("full_response", ""),
                "explanation": result.get("explanation", ""),
                "actions": result.get("actions", []),
                "plan": result.get("plan", ""),
                "raw_result": result # For debugging/future-proofing
            }
        return {"refined_plan": result}
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"deepagents not available: {e}. Install with: pip install deepagents")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plan refinement failed: {str(e)}")

@router.post("/api/plans/refine/stream")
async def refine_plan_stream_endpoint(request: RefineRequest):
    try:
        from plan_agent import refine_plan_stream
        plans_dir = PLANS_DIR
        plan_content = request.plan_content
        if request.plan_id and not plan_content:
            p_file = plans_dir / f"{request.plan_id}.md"
            if p_file.exists():
                plan_content = p_file.read_text()
        async def event_generator():
            try:
                from plan_agent import parse_structured_response
                full_response = ""
                async for chunk in refine_plan_stream(user_message=request.message, plan_content=plan_content, chat_history=request.chat_history, model=request.model, plans_dir=plans_dir if plans_dir.exists() else None, working_dir=request.working_dir or None):
                    if isinstance(chunk, dict):
                        # If a dictionary is yielded, treat it as a rich event and accumulate if it has a 'token'
                        token = chunk.get("token", "")
                        full_response += token
                        yield f"data: {json.dumps(chunk)}\n\n"
                    else:
                        full_response += chunk
                        yield f"data: {json.dumps({'token': chunk})}\n\n"
                
                # After streaming is complete, parse the full response and emit as a structured result event
                result = parse_structured_response(full_response)
                yield f"data: {json.dumps({'result': result})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"deepagents not available: {e}")

@router.get("/api/plans/{plan_id}/epics")
async def get_plan_epics(plan_id: str):
    store = global_state.store
    if store:
        epics = store.get_epics_for_plan(plan_id)
        if epics: return {"epics": epics, "count": len(epics)}
    plans_dir = PLANS_DIR
    plan_file = plans_dir / f"{plan_id}.md"
    if not plan_file.exists():
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    content = plan_file.read_text()
    if store:
        from dashboard.zvec_store import OSTwinStore
        epics_raw = OSTwinStore._parse_plan_epics(content, plan_id)
    else: epics_raw = []
    return {"epics": epics_raw, "count": len(epics_raw)}

@router.get("/api/search/plans")
async def search_plans(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=50)):
    store = global_state.store
    if not store: raise HTTPException(status_code=503, detail="Vector search not available")
    results = store.search_plans(q, limit=limit)
    return {"results": results, "count": len(results)}

@router.get("/api/search/epics")
async def search_epics(q: str = Query(..., min_length=1), plan_id: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=100)):
    store = global_state.store
    if not store: raise HTTPException(status_code=503, detail="Vector search not available")
    results = store.search_epics(q, plan_id=plan_id, limit=limit)
    return {"results": results, "count": len(results)}

# --- Plan-scoped roles & rooms ---

@router.get("/api/plans/{plan_id}/roles/assignments")
async def get_plan_role_assignments(plan_id: str, user: dict = Depends(get_current_user)):
    config = get_plan_roles_config(plan_id)
    roles = build_roles_list(config, include_skills=True)
    warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
    rooms_with_roles = []
    role_summary: Dict[str, int] = {}
    if warrooms_dir and warrooms_dir.exists():
        for room_dir in sorted(warrooms_dir.glob("room-*")):
            if not room_dir.is_dir(): continue
            room_config_file = room_dir / "config.json"
            room_config = {}
            if room_config_file.exists():
                try:
                    room_config = json.loads(room_config_file.read_text())
                    if room_config.get("plan_id") and room_config["plan_id"] != plan_id: continue
                except json.JSONDecodeError: continue
            role_instances = []
            for f in sorted(room_dir.glob("*_*.json")):
                if f.name == "config.json": continue
                try:
                    data = json.loads(f.read_text())
                    if "role" in data and "instance_id" in data:
                        data["filename"] = f.name
                        role_instances.append(data)
                        rn = data["role"]
                        role_summary[rn] = role_summary.get(rn, 0) + 1
                except (json.JSONDecodeError, KeyError): continue
            if role_instances:
                rooms_with_roles.append({"room_id": room_dir.name, "task_ref": room_config.get("task_ref", "UNKNOWN"), "roles": role_instances})
    return {
        "plan_id": plan_id, 
        "warrooms_dir": str(warrooms_dir) if warrooms_dir else None, 
        "role_defaults": roles, 
        "rooms": rooms_with_roles, 
        "summary": role_summary, 
        "total_assignments": sum(role_summary.values()),
        "attached_skills": config.get("attached_skills", [])
    }

@router.put("/api/plans/{plan_id}/roles/{role_name}/config")
async def update_plan_role_config(plan_id: str, role_name: str, request: UpdatePlanRoleConfigRequest, user: dict = Depends(get_current_user)):
    plans_dir = PLANS_DIR
    plan_roles_file = plans_dir / f"{plan_id}.roles.json"
    if plan_roles_file.exists(): config = json.loads(plan_roles_file.read_text())
    else:
        config_file = AGENTS_DIR / "config.json"
        config = json.loads(config_file.read_text()) if config_file.exists() else {}
    if role_name not in config: config[role_name] = {}
    if request.default_model is not None: config[role_name]["default_model"] = request.default_model
    if request.temperature is not None: config[role_name]["temperature"] = request.temperature
    if request.timeout_seconds is not None: config[role_name]["timeout_seconds"] = request.timeout_seconds
    if request.cli is not None: config[role_name]["cli"] = request.cli
    if request.skill_refs is not None: config[role_name]["skill_refs"] = request.skill_refs
    if request.disabled_skills is not None: config[role_name]["disabled_skills"] = request.disabled_skills
    plan_roles_file.write_text(json.dumps(config, indent=2) + "\n")
    return {"status": "updated", "plan_id": plan_id, "role": role_name, "config": config[role_name]}

@router.get("/api/plans/{plan_id}/rooms")
async def get_plan_rooms(plan_id: str, user: dict = Depends(get_current_user)):
    """Get war-rooms for a specific plan, using the plan's working_dir."""
    from dashboard.api_utils import read_room
    warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
    if not warrooms_dir or not warrooms_dir.exists():
        return {"plan_id": plan_id, "warrooms_dir": str(warrooms_dir) if warrooms_dir else None, "rooms": [], "count": 0}
    rooms = []
    for room_dir in sorted(warrooms_dir.glob("room-*")):
        if not room_dir.is_dir(): continue
        room_config_file = room_dir / "config.json"
        if room_config_file.exists():
            try:
                rc = json.loads(room_config_file.read_text())
                room_plan_id = rc.get("plan_id", "")
                # Only include shared-dir rooms that either explicitly match
                # the plan or are legacy unstamped rooms inside a plan-scoped dir.
                if room_plan_id and room_plan_id != plan_id:
                    continue
            except json.JSONDecodeError: continue
        # Use enhanced read_room with metadata for rich data
        room_data = read_room(room_dir, include_metadata=True)
        rooms.append(room_data)
    return {"plan_id": plan_id, "warrooms_dir": str(warrooms_dir), "rooms": rooms, "count": len(rooms)}


@router.get("/api/plans/{plan_id}/progress")
async def get_plan_progress(plan_id: str, user: dict = Depends(get_current_user)):
    """Get the progress.json content for a specific plan."""
    warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
    if not warrooms_dir:
        return {
            "total": 0, "passed": 0, "failed": 0, "blocked": 0, "active": 0, "pending": 0,
            "pct_complete": 0, "rooms": []
        }
    prog_file = warrooms_dir / "progress.json"
    if not prog_file.exists():
        return {
            "total": 0, "passed": 0, "failed": 0, "blocked": 0, "active": 0, "pending": 0,
            "pct_complete": 0, "rooms": []
        }
    try:
        data = json.loads(prog_file.read_text())
        cp_str = data.get("critical_path", "")
        if isinstance(cp_str, str) and "/" in cp_str:
            parts = cp_str.split("/")
            data["critical_path"] = {"completed": int(parts[0]), "total": int(parts[1])}
        return data
    except (json.JSONDecodeError, OSError):
        raise HTTPException(status_code=500, detail="Failed to read progress.json")

@router.get("/api/plans/{plan_id}/dag")
async def get_plan_dag(plan_id: str, user: dict = Depends(get_current_user)):
    """Return the DAG.json for a plan, read from its warrooms_dir.

    The DAG.json is produced by the OS-Twin planner and contains the full
    directed-acyclic-graph of war-room / EPIC dependencies including nodes,
    critical_path, waves, topological_order, and metadata like max_depth.
    """
    warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
    if not warrooms_dir:
        return {
            "nodes": [],
            "edges": [],
            "critical_path": [],
            "waves": {},
            "topological_order": [],
            "max_depth": 0,
            "error": "DAG.json not found"
        }
    dag_file = warrooms_dir / "DAG.json"
    if not dag_file.exists():
        # Avoid 404 for missing resource (prevents it being confused with missing endpoint)
        return {
            "nodes": [],
            "edges": [],
            "critical_path": [],
            "waves": {},
            "topological_order": [],
            "max_depth": 0,
            "error": "DAG.json not found"
        }
    try:
        dag = json.loads(dag_file.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read DAG.json: {exc}")
    return dag


@router.get("/api/plans/{plan_id}/epics/{task_ref}")
async def get_plan_epic(
    plan_id: str,
    task_ref: str,
    include_metadata: bool = Query(False),
    include_messages: bool = Query(False),
    user: dict = Depends(get_current_user)
):
    """Get full details for a specific EPIC within a plan."""
    from dashboard.api_utils import read_room
    warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
    if not warrooms_dir or not warrooms_dir.exists():
        raise HTTPException(status_code=404, detail=f"No war-rooms for plan {plan_id}")

    for room_dir in warrooms_dir.glob("room-*"):
        if not room_dir.is_dir():
            continue
        tr_file = room_dir / "task-ref"
        current_ref = tr_file.read_text().strip() if tr_file.exists() else None

        # Fallback to config.json if task-ref file missing
        if not current_ref:
            room_config_file = room_dir / "config.json"
            if room_config_file.exists():
                try:
                    rc = json.loads(room_config_file.read_text())
                    current_ref = rc.get("task_ref")
                except json.JSONDecodeError:
                    pass

        if current_ref == task_ref:
            room_data = read_room(room_dir, include_metadata=include_metadata, include_messages=include_messages)
            
            # Enrich with plan title
            plan_file = PLANS_DIR / f"{plan_id}.md"
            if plan_file.exists():
                content = plan_file.read_text()
                title_match = re.search(r"^# (?:Plan|PLAN):\s*(.+)", content, re.MULTILINE)
                if title_match:
                    room_data["plan_title"] = title_match.group(1).strip()
            
            # Enrich with DAG info (dependents)
            dag_file = warrooms_dir / "DAG.json"
            if dag_file.exists():
                try:
                    dag = json.loads(dag_file.read_text())
                    node_info = dag.get("nodes", {}).get(task_ref, {})
                    if "dependents" in node_info:
                        # Add to config so frontend can find it easily
                        if "config" not in room_data:
                            room_data["config"] = {}
                        room_data["config"]["dependents"] = node_info["dependents"]
                        # Also add to top level
                        room_data["dependents"] = node_info["dependents"]
                except (json.JSONDecodeError, OSError):
                    pass
            
            return room_data

    raise HTTPException(status_code=404, detail=f"EPIC {task_ref} not found in plan {plan_id}")

@router.get("/api/plans/{plan_id}/rooms/{room_id}/roles")
async def get_plan_room_roles(plan_id: str, room_id: str, user: dict = Depends(get_current_user)):
    warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
    if not warrooms_dir:
        raise HTTPException(status_code=404, detail="Room not found")
    room_dir = warrooms_dir / room_id
    if not room_dir.exists(): raise HTTPException(status_code=404, detail="Room not found")
    role_instances = []
    for f in sorted(room_dir.glob("*_*.json")):
        if f.name == "config.json": continue
        try:
            data = json.loads(f.read_text())
            if "role" in data and "instance_id" in data:
                data["filename"] = f.name
                role_instances.append(data)
        except (json.JSONDecodeError, KeyError): continue
    return {"plan_id": plan_id, "room_id": room_id, "roles": role_instances, "count": len(role_instances)}

@router.get("/api/plans/{plan_id}/rooms/{room_id}/channel")
async def get_plan_room_channel(plan_id: str, room_id: str, user: dict = Depends(get_current_user)):
    """Get channel messages for a plan-scoped war-room."""
    from dashboard.api_utils import read_channel
    warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
    if not warrooms_dir:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found in plan {plan_id}")
    room_dir = warrooms_dir / room_id
    if not room_dir.exists():
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found in plan {plan_id}")
    return {"messages": read_channel(room_dir), "plan_id": plan_id, "room_id": room_id}

@router.get("/api/plans/{plan_id}/rooms/{room_id}/state")
async def get_plan_room_state(plan_id: str, room_id: str, user: dict = Depends(get_current_user)):
    """Get full room state with metadata for a plan-scoped war-room."""
    from dashboard.api_utils import read_room
    warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
    if not warrooms_dir:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found in plan {plan_id}")
    room_dir = warrooms_dir / room_id
    if not room_dir.exists():
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found in plan {plan_id}")
    room_data = read_room(room_dir, include_metadata=True)
    return {"plan_id": plan_id, **room_data}

@router.post("/api/plans/{plan_id}/rooms/{room_id}/action")
async def plan_room_action(
    plan_id: str,
    room_id: str,
    background_tasks: BackgroundTasks,
    action: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """Perform an action on a plan-scoped war-room (stop, pause, resume, start)."""
    warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
    if not warrooms_dir:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found in plan {plan_id}")
    room_dir = warrooms_dir / room_id
    if not room_dir.exists():
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found in plan {plan_id}")

    status_file = room_dir / "status"
    if action == "stop":
        status_file.write_text("failed-final")
    elif action == "pause":
        status_file.write_text("paused")
    elif action in ("resume", "start"):
        status_file.write_text("pending")
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    background_tasks.add_task(
        process_notification, "room_action",
        {"room_id": room_id, "action": action, "plan_id": plan_id},
    )
    return {"status": "ok", "action": action, "room_id": room_id, "plan_id": plan_id}


def _resolve_room_dir(plan_id: str, task_ref: str) -> Optional[Path]:
    """Internal helper to find the room directory for a given task/epic reference."""
    warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
    if not warrooms_dir or not warrooms_dir.exists():
        return None

    for room_dir in warrooms_dir.glob("room-*"):
        if not room_dir.is_dir():
            continue
        # 1. task-ref file
        tr_file = room_dir / "task-ref"
        if tr_file.exists():
            if tr_file.read_text().strip() == task_ref:
                return room_dir
        # 2. config.json
        cfg_file = room_dir / "config.json"
        if cfg_file.exists():
            try:
                if json.loads(cfg_file.read_text()).get("task_ref") == task_ref:
                    return room_dir
            except (json.JSONDecodeError, OSError): pass
    return None

@router.get("/api/plans/{plan_id}/epics/{task_ref}/tasks")
async def get_epic_tasks(plan_id: str, task_ref: str, user: dict = Depends(get_current_user)):
    """Parse TASKS.md from the war-room and return structured task list."""
    room_dir = _resolve_room_dir(plan_id, task_ref)
    if not room_dir:
        return {"tasks": [], "raw": ""}
    tasks_file = room_dir / "TASKS.md"
    if not tasks_file.exists():
        return {"tasks": [], "raw": ""}
    raw = tasks_file.read_text()
    tasks = []
    current_task = None
    for line in raw.splitlines():
        line_stripped = line.strip()
        # Match: - [x] TASK-001 — Description  or  - [ ] TASK-002 — Description
        if line_stripped.startswith("- ["):
            completed = line_stripped.startswith("- [x]") or line_stripped.startswith("- [X]")
            rest = line_stripped[6:].strip()  # after "- [x] " or "- [ ] "
            parts = rest.split(" — ", 1) if " — " in rest else rest.split(" - ", 1)
            task_id = parts[0].strip() if len(parts) > 1 else rest
            description = parts[1].strip() if len(parts) > 1 else ""
            current_task = {"task_id": task_id, "description": description, "completed": completed, "acceptance_criteria": []}
            tasks.append(current_task)
        elif line_stripped.startswith("- AC:") and current_task:
            current_task["acceptance_criteria"].append(line_stripped[5:].strip())
    return {"tasks": tasks, "count": len(tasks), "raw": raw}

@router.get("/api/plans/{plan_id}/epics/{task_ref}/lifecycle")
async def get_epic_lifecycle(plan_id: str, task_ref: str, user: dict = Depends(get_current_user)):
    room_dir = _resolve_room_dir(plan_id, task_ref)
    if not room_dir: return {"states": {}, "transitions": [], "error": "Room not found"}
    lc_file = room_dir / "lifecycle.json"
    if not lc_file.exists(): return {"states": {}, "transitions": [], "error": "lifecycle.json not found"}
    try: return json.loads(lc_file.read_text())
    except (json.JSONDecodeError, OSError): return {"states": {}, "transitions": [], "error": "JSON error"}

@router.get("/api/plans/{plan_id}/epics/{task_ref}/audit")
async def get_epic_audit(plan_id: str, task_ref: str, user: dict = Depends(get_current_user)):
    room_dir = _resolve_room_dir(plan_id, task_ref)
    if not room_dir: return []
    audit_file = room_dir / "audit.log"
    if not audit_file.exists(): return []
    try:
        lines = audit_file.read_text().splitlines()
        # Parse lines like: [2026-03-24T03:46:16Z] Transitioning: state1 -> state2
        results = []
        for line in lines:
            if "Transitioning:" in line:
                m = re.search(r"\[(.*?)\] Transitioning: (.*?) -> (.*)", line)
                if m:
                    results.append({"timestamp": m.group(1), "from_state": m.group(2), "to_state": m.group(3)})
        return results
    except OSError: return []

@router.get("/api/plans/{plan_id}/epics/{task_ref}/brief")
async def get_epic_brief(plan_id: str, task_ref: str, user: dict = Depends(get_current_user)):
    room_dir = _resolve_room_dir(plan_id, task_ref)
    if not room_dir: return {"content": "", "working_dir": "", "created_at": None}
    brief_file = room_dir / "brief.md"
    config_file = room_dir / "config.json"
    content = brief_file.read_text() if brief_file.exists() else "# No brief provided"
    working_dir = "."
    if config_file.exists():
        try:
            cfg = json.loads(config_file.read_text())
            working_dir = cfg.get("working_dir", ".")
        except: pass
    return {"content": content, "working_dir": working_dir, "created_at": None}

@router.get("/api/plans/{plan_id}/epics/{task_ref}/artifacts")
async def get_epic_artifacts(plan_id: str, task_ref: str, user: dict = Depends(get_current_user)):
    room_dir = _resolve_room_dir(plan_id, task_ref)
    if not room_dir: return []
    art_dir = room_dir / "artifacts"
    if not art_dir.exists(): return []
    files = []
    for f in art_dir.iterdir():
        if f.is_file():
            files.append({"name": f.name, "size": f.stat().st_size, "type": f.suffix.lstrip(".")})
    return sorted(files, key=lambda x: x["name"])

@router.get("/api/plans/{plan_id}/epics/{task_ref}/agents")
async def get_epic_agents(plan_id: str, task_ref: str, user: dict = Depends(get_current_user)):
    room_dir = _resolve_room_dir(plan_id, task_ref)
    if not room_dir: return []
    agents = []
    # Any role-named file like architect_001.json
    for f in room_dir.glob("*_*.json"):
        if f.name == "config.json": continue
        try:
            data = json.loads(f.read_text())
            if "role" in data: agents.append(data)
        except: pass
    return agents

@router.get("/api/plans/{plan_id}/epics/{task_ref}/config")
async def get_epic_config(plan_id: str, task_ref: str, user: dict = Depends(get_current_user)):
    room_dir = _resolve_room_dir(plan_id, task_ref)
    if not room_dir: return {"error": "Room not found"}
    cfg_file = room_dir / "config.json"
    if not cfg_file.exists(): return {"error": "config.json missing"}
    try: return json.loads(cfg_file.read_text())
    except: return {"error": "JSON parse error"}

@router.get("/api/plans/{plan_id}/epics/{task_ref}/roles")
async def get_epic_roles(plan_id: str, task_ref: str, user: dict = Depends(get_current_user)):
    """Get roles list for a specific Epic, including overrides from war-room config."""
    room_dir = _resolve_room_dir(plan_id, task_ref)
    if not room_dir: raise HTTPException(status_code=404, detail="Epic room not found")
    
    plan_config = get_plan_roles_config(plan_id)
    room_config_file = room_dir / "config.json"
    room_overrides = {}
    candidate_roles = []
    if room_config_file.exists():
        try:
            rc = json.loads(room_config_file.read_text())
            room_overrides = rc.get("roles", {})
            candidate_roles = rc.get("assignment", {}).get("candidate_roles", [])
        except json.JSONDecodeError: pass
        
    merged_config = plan_config.copy()
    for role_name, role_overrides in room_overrides.items():
        if role_name not in merged_config:
             merged_config[role_name] = {}
        # Deep update if we have nested dicts? Currently roles are flat configs.
        merged_config[role_name].update(role_overrides)
        
    roles = build_roles_list(merged_config, include_skills=True)
    return {
        "roles": roles,
        "plan_config": plan_config,
        "room_overrides": room_overrides,
        "candidate_roles": candidate_roles
    }

from pydantic import BaseModel
class UpdateEpicAssignmentRequest(BaseModel):
    candidate_roles: List[str]

@router.put("/api/plans/{plan_id}/epics/{task_ref}/roles/assignment")
async def update_epic_role_assignment(
    plan_id: str, 
    task_ref: str, 
    request: UpdateEpicAssignmentRequest, 
    user: dict = Depends(get_current_user)
):
    """Update role assignment (candidate_roles) for a specific Epic."""
    room_dir = _resolve_room_dir(plan_id, task_ref)
    if not room_dir: raise HTTPException(status_code=404, detail="Epic room not found")
    
    room_config_file = room_dir / "config.json"
    if not room_config_file.exists():
         raise HTTPException(status_code=404, detail="config.json missing")
         
    try:
        rc = json.loads(room_config_file.read_text())
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid config.json")
        
    if "assignment" not in rc: rc["assignment"] = {}
    rc["assignment"]["candidate_roles"] = request.candidate_roles

    room_config_file.write_text(json.dumps(rc, indent=2) + "\n")
    return {"status": "updated", "task_ref": task_ref, "candidate_roles": rc["assignment"]["candidate_roles"]}

@router.put("/api/plans/{plan_id}/epics/{task_ref}/roles/{role_name}/config")
async def update_epic_role_config(
    plan_id: str, 
    task_ref: str, 
    role_name: str, 
    request: UpdatePlanRoleConfigRequest, 
    user: dict = Depends(get_current_user)
):
    """Update role configuration for a specific Epic (saved in war-room config.json)."""
    room_dir = _resolve_room_dir(plan_id, task_ref)
    if not room_dir: raise HTTPException(status_code=404, detail="Epic room not found")
    
    room_config_file = room_dir / "config.json"
    if not room_config_file.exists():
         raise HTTPException(status_code=404, detail="config.json missing")
         
    try:
        rc = json.loads(room_config_file.read_text())
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid config.json")
        
    if "roles" not in rc: rc["roles"] = {}
    if role_name not in rc["roles"]: rc["roles"][role_name] = {}
    
    if request.default_model is not None: rc["roles"][role_name]["default_model"] = request.default_model
    if request.temperature is not None: rc["roles"][role_name]["temperature"] = request.temperature
    if request.timeout_seconds is not None: rc["roles"][role_name]["timeout_seconds"] = request.timeout_seconds
    if request.cli is not None: rc["roles"][role_name]["cli"] = request.cli
    if request.skill_refs is not None: rc["roles"][role_name]["skill_refs"] = request.skill_refs
    if request.disabled_skills is not None: rc["roles"][role_name]["disabled_skills"] = request.disabled_skills

    room_config_file.write_text(json.dumps(rc, indent=2) + "\n")
    return {"status": "updated", "task_ref": task_ref, "role": role_name, "config": rc["roles"][role_name]}

@router.get("/api/plans/{plan_id}/epics/{task_ref}/roles/{role_name}/preview")
async def preview_epic_role_prompt(
    plan_id: str, 
    task_ref: str, 
    role_name: str, 
    user: dict = Depends(get_current_user)
):
    """Generate and return the final system prompt preview for a role in an Epic."""
    from dashboard.epic_manager import EpicSkillsManager
    try:
        prompt = EpicSkillsManager.generate_system_prompt(plan_id, task_ref, role_name)
        return {"role": role_name, "prompt": prompt}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate prompt: {e}")
