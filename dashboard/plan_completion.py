import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dashboard.api_utils import GLOBAL_PLANS_DIR, PLANS_DIR, process_notification
import dashboard.global_state as global_state

logger = logging.getLogger(__name__)

COMPLETED_STATUS = "completed"


def is_completed_status(status: Any) -> bool:
    return str(status or "").strip().lower() == COMPLETED_STATUS


def find_plan_meta_path(plan_id: str) -> Path:
    local = PLANS_DIR / f"{plan_id}.meta.json"
    if local.exists():
        return local

    if GLOBAL_PLANS_DIR != PLANS_DIR:
        global_path = GLOBAL_PLANS_DIR / f"{plan_id}.meta.json"
        if global_path.exists():
            return global_path

    return GLOBAL_PLANS_DIR / f"{plan_id}.meta.json"


def read_plan_meta(plan_id: str, meta_path: Optional[Path] = None) -> Dict[str, Any]:
    path = meta_path or find_plan_meta_path(plan_id)
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read plan meta for completion broadcast: %s", path)
        return {}


def write_plan_meta(
    plan_id: str,
    meta: Dict[str, Any],
    meta_path: Optional[Path] = None,
) -> None:
    path = meta_path or find_plan_meta_path(plan_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2) + "\n")


def build_plan_completed_payload(
    plan_id: str,
    meta: Dict[str, Any],
    progress: Optional[Dict[str, Any]] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    plan: Dict[str, Any] = {
        "plan_id": plan_id,
        "title": meta.get("title") or plan_id,
        "status": COMPLETED_STATUS,
        "completed_at": meta.get("completed_at"),
    }

    for key in ("working_dir", "warrooms_dir"):
        if meta.get(key):
            plan[key] = meta[key]

    payload: Dict[str, Any] = {"plan": plan}
    if progress is not None:
        payload["progress"] = progress
    if source:
        payload["source"] = source
    return payload


def progress_is_completed(progress: Dict[str, Any]) -> bool:
    try:
        total = int(progress.get("total") or 0)
        passed = int(progress.get("passed") or 0)
    except (TypeError, ValueError):
        return False

    return total > 0 and passed >= total


async def mark_plan_completed(
    plan_id: str,
    *,
    meta: Optional[Dict[str, Any]] = None,
    meta_path: Optional[Path] = None,
    progress: Optional[Dict[str, Any]] = None,
    source: Optional[str] = None,
) -> bool:
    """Persist completed status and broadcast a plan_completed event once."""
    plan_meta = dict(meta if meta is not None else read_plan_meta(plan_id, meta_path))
    plan_meta.setdefault("plan_id", plan_id)
    plan_meta["status"] = COMPLETED_STATUS

    now = datetime.now(timezone.utc).isoformat()
    plan_meta.setdefault("completed_at", now)

    should_broadcast = not plan_meta.get("completion_broadcast_at")
    if should_broadcast:
        plan_meta["completion_broadcast_at"] = now

    write_plan_meta(plan_id, plan_meta, meta_path)

    if not should_broadcast:
        return False

    payload = build_plan_completed_payload(plan_id, plan_meta, progress, source)
    await global_state.broadcaster.broadcast("plan_completed", payload)
    await process_notification("plan_completed", payload)
    logger.info("Broadcasted plan completion for %s", plan_id)
    return True


def reset_plan_completion_broadcast(
    plan_id: str,
    meta: Dict[str, Any],
    meta_path: Optional[Path] = None,
) -> None:
    meta.pop("completion_broadcast_at", None)
    write_plan_meta(plan_id, meta, meta_path)
