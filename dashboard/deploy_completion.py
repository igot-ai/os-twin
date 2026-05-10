"""
deploy_completion.py — Auto-start deploy preview on plan completion.

Handles:
- Detecting plan completion (all rooms passed)
- Starting deploy preview once per completion
- Broadcasting deploy events
- Sending notifications to configured channels
- Idempotent completion tracking
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


DEPLOY_ATTEMPTED_KEY = "deploy_attempted_for_completion"
DEPLOY_ATTEMPTED_AT_KEY = "deploy_attempted_at"


def read_progress_json(warrooms_dir: Path) -> Optional[Dict[str, Any]]:
    """Read progress.json from warrooms directory."""
    prog_file = warrooms_dir / "progress.json"
    if not prog_file.exists():
        return None
    try:
        return json.loads(prog_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read progress.json: {e}")
        return None


def is_plan_completed(progress: Dict[str, Any]) -> bool:
    """Check if all rooms in progress have passed."""
    total = progress.get("total", 0)
    passed = progress.get("passed", 0)
    failed = progress.get("failed", 0)
    blocked = progress.get("blocked", 0)
    
    if total == 0:
        return False
    
    return total == passed and failed == 0 and blocked == 0


def get_deploy_completion_state(working_dir: Path) -> Dict[str, Any]:
    """Get deploy state including completion tracking."""
    from dashboard.deploy_preview import read_preview_state
    
    state = read_preview_state(working_dir)
    if not state:
        return {
            DEPLOY_ATTEMPTED_KEY: False,
            DEPLOY_ATTEMPTED_AT_KEY: None,
        }
    
    return {
        DEPLOY_ATTEMPTED_KEY: state.get(DEPLOY_ATTEMPTED_KEY, False),
        DEPLOY_ATTEMPTED_AT_KEY: state.get(DEPLOY_ATTEMPTED_AT_KEY),
    }


def mark_deploy_attempted(working_dir: Path) -> None:
    """Mark that deploy was attempted for this completion."""
    from dashboard.deploy_preview import read_preview_state, write_preview_state
    
    state = read_preview_state(working_dir) or {}
    state[DEPLOY_ATTEMPTED_KEY] = True
    state[DEPLOY_ATTEMPTED_AT_KEY] = datetime.now(timezone.utc).isoformat()
    write_preview_state(working_dir, state)


async def auto_start_deploy_preview(
    plan_id: str,
    working_dir: Path,
    broadcaster: Any = None,
) -> Dict[str, Any]:
    """Auto-start deploy preview after plan completion.
    
    Idempotent: only starts once per completion.
    
    Args:
        plan_id: The plan ID
        working_dir: Working directory for the plan
        broadcaster: Optional broadcaster for websocket/SSE events
    
    Returns:
        Dict with status, deploy_status, and any error
    """
    from dashboard.deploy_preview import (
        start_preview,
        get_preview_status,
        read_preview_state,
        write_preview_state,
        PathCheckError,
        PreviewConfigError,
    )
    
    result = {
        "plan_id": plan_id,
        "deploy_started": False,
        "deploy_status": None,
        "error": None,
        "already_attempted": False,
    }
    
    state = read_preview_state(working_dir) or {}
    
    if state.get(DEPLOY_ATTEMPTED_KEY, False):
        result["already_attempted"] = True
        result["deploy_status"] = get_preview_status(working_dir)
        logger.info(f"Deploy already attempted for plan {plan_id}, skipping")
        return result
    
    try:
        deploy_status = start_preview(working_dir)
        deploy_status[DEPLOY_ATTEMPTED_KEY] = True
        deploy_status[DEPLOY_ATTEMPTED_AT_KEY] = datetime.now(timezone.utc).isoformat()
        write_preview_state(working_dir, deploy_status)
        
        result["deploy_started"] = True
        result["deploy_status"] = deploy_status
        
        logger.info(f"Auto-started deploy preview for plan {plan_id}")
        
    except PathCheckError as e:
        error_msg = f"Path check failed: {e}"
        result["error"] = error_msg
        result["deploy_status"] = {
            "status": "error",
            "error": error_msg,
            DEPLOY_ATTEMPTED_KEY: True,
            DEPLOY_ATTEMPTED_AT_KEY: datetime.now(timezone.utc).isoformat(),
        }
        write_preview_state(working_dir, result["deploy_status"])
        logger.warning(f"Deploy preview path check failed for plan {plan_id}: {e}")
        
    except PreviewConfigError as e:
        error_msg = str(e)
        result["error"] = error_msg
        result["deploy_status"] = {
            "status": "not_configured",
            "error": error_msg,
            DEPLOY_ATTEMPTED_KEY: True,
            DEPLOY_ATTEMPTED_AT_KEY: datetime.now(timezone.utc).isoformat(),
        }
        write_preview_state(working_dir, result["deploy_status"])
        logger.info(f"Deploy preview not configured for plan {plan_id}: {e}")
        
    except OSError as e:
        error_msg = f"No free port available: {e}"
        result["error"] = error_msg
        result["deploy_status"] = {
            "status": "error",
            "error": error_msg,
            DEPLOY_ATTEMPTED_KEY: True,
            DEPLOY_ATTEMPTED_AT_KEY: datetime.now(timezone.utc).isoformat(),
        }
        write_preview_state(working_dir, result["deploy_status"])
        logger.warning(f"Deploy preview failed to find port for plan {plan_id}: {e}")
    
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        result["error"] = error_msg
        result["deploy_status"] = {
            "status": "error",
            "error": error_msg,
            DEPLOY_ATTEMPTED_KEY: True,
            DEPLOY_ATTEMPTED_AT_KEY: datetime.now(timezone.utc).isoformat(),
        }
        write_preview_state(working_dir, result["deploy_status"])
        logger.error(f"Deploy preview failed unexpectedly for plan {plan_id}: {e}")
    
    return result


async def broadcast_deploy_event(
    broadcaster: Any,
    plan_id: str,
    deploy_status: Dict[str, Any],
    event_type: str = "deploy_updated",
) -> None:
    """Broadcast deploy status update via websocket/SSE."""
    if broadcaster is None:
        return
    
    event_data = {
        "plan_id": plan_id,
        "deploy_status": deploy_status.get("status"),
        "local_url": deploy_status.get("local_url"),
        "public_url": deploy_status.get("public_url"),
        "port": deploy_status.get("port"),
        "pid": deploy_status.get("pid"),
        "error": deploy_status.get("error"),
    }
    
    await broadcaster.broadcast(event_type, event_data)
    logger.info(f"Broadcast {event_type} for plan {plan_id}")


async def send_deploy_notification(
    plan_id: str,
    plan_title: str,
    deploy_status: Dict[str, Any],
    dashboard_base_url: Optional[str] = None,
) -> bool:
    """Send notification about deploy preview to configured channels.
    
    Args:
        plan_id: The plan ID
        plan_title: The plan title
        deploy_status: Deploy status dict
        dashboard_base_url: Optional base URL for dashboard links
    
    Returns:
        True if notification was sent successfully
    """
    from dashboard.notify import send_message
    
    status = deploy_status.get("status", "unknown")
    local_url = deploy_status.get("local_url")
    public_url = deploy_status.get("public_url")
    error = deploy_status.get("error")
    
    if status == "not_configured":
        message_lines = [
            f"⚠️ **Plan Completed: {plan_title}**",
            f"",
            f"Preview deployment is not configured.",
            f"Add a `package.json` with `dev`/`preview` script or `index.html`.",
        ]
    elif status == "error":
        message_lines = [
            f"⚠️ **Plan Completed: {plan_title}**",
            f"",
            f"Preview deployment failed: {error}",
        ]
    elif status == "running":
        message_lines = [
            f"✅ **Plan Completed: {plan_title}**",
            f"",
            f"🎉 Preview is running!",
        ]
        
        if local_url:
            message_lines.append(f"📍 **Local:** {local_url}")
        
        if public_url:
            message_lines.append(f"🌐 **Public:** {public_url}")
        
        if dashboard_base_url:
            plan_url = f"{dashboard_base_url}/plans/{plan_id}"
            message_lines.append(f"📋 **Dashboard:** {plan_url}")
    else:
        message_lines = [
            f"✅ **Plan Completed: {plan_title}**",
            f"",
            f"Preview status: {status}",
        ]
    
    message = "\n".join(message_lines)
    
    try:
        return await send_message(message)
    except Exception as e:
        logger.warning(f"Failed to send deploy notification: {e}")
        return False


async def handle_plan_completion(
    plan_id: str,
    working_dir: Path,
    plan_title: str = "",
    broadcaster: Any = None,
    dashboard_base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Handle plan completion: start deploy, broadcast, notify.
    
    This is the main entry point for auto-deploy on completion.
    
    Args:
        plan_id: The plan ID
        working_dir: Working directory for the plan
        plan_title: The plan title (for notifications)
        broadcaster: Optional broadcaster for events
        dashboard_base_url: Optional base URL for dashboard links
    
    Returns:
        Dict with completion handling results
    """
    result = {
        "plan_id": plan_id,
        "deploy_result": None,
        "notification_sent": False,
    }
    
    deploy_result = await auto_start_deploy_preview(plan_id, working_dir, broadcaster)
    result["deploy_result"] = deploy_result
    
    if broadcaster and deploy_result.get("deploy_status"):
        await broadcast_deploy_event(
            broadcaster,
            plan_id,
            deploy_result["deploy_status"],
        )
    
    if deploy_result.get("deploy_status"):
        notification_sent = await send_deploy_notification(
            plan_id,
            plan_title or plan_id,
            deploy_result["deploy_status"],
            dashboard_base_url,
        )
        result["notification_sent"] = notification_sent
    
    return result
