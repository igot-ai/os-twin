"""Plan lifecycle tracking.

A plan's lifecycle state is derived from three on-disk signals — never guessed:

  1. ``meta.json.runner_pid`` and ``meta.json.launched_at`` — set when
     ``/api/run`` spawns the ostwin runner subprocess.
  2. Whether that PID is still alive on this host.
  3. ``progress.json`` mtime under the plan's war-rooms dir — the manager loop
     refreshes it every ~10s, so it doubles as a heartbeat.

The derived state is one of:

  * ``draft``      — plan exists but has never been launched.
  * ``running``    — runner PID is alive *and* heartbeat is fresh.
  * ``stopped``    — runner PID is gone, no epics passed, work incomplete.
  * ``completed``  — all rooms reached ``passed`` (whether or not the PID lives).
  * ``failed``     — runner PID is gone and at least one room is ``failed-final``.

Callers that need a fresh read just call :func:`derive_lifecycle`. There is no
background daemon — derivation is cheap and runs on each request.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dashboard.api_utils import (
    PLANS_DIR,
    resolve_runtime_plan_warrooms_dir,
)

logger = logging.getLogger(__name__)

# Heartbeat is considered stale after this many seconds. The manager loop
# refreshes progress.json every ~10s, so 60s gives a generous 6× margin
# before we declare a plan stopped.
HEARTBEAT_TIMEOUT_S = 60


def _pid_alive(pid: Optional[int]) -> bool:
    """Return True if ``pid`` is a running process on this host.

    Uses ``os.kill(pid, 0)`` (POSIX) — sends signal 0 which performs the
    permission/existence check without actually delivering a signal.
    A ``PermissionError`` means the process exists but we lack signal
    rights, which still counts as alive.
    """
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _read_meta(plan_id: str) -> Dict[str, Any]:
    meta_file = PLANS_DIR / f"{plan_id}.meta.json"
    if not meta_file.exists():
        return {}
    try:
        return json.loads(meta_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_meta(plan_id: str, meta: Dict[str, Any]) -> None:
    meta_file = PLANS_DIR / f"{plan_id}.meta.json"
    meta_file.write_text(json.dumps(meta, indent=2) + "\n")


def record_launch(plan_id: str, runner_pid: int) -> None:
    """Persist the runner PID so future requests can check liveness.

    Called by ``/api/run`` right after the ostwin subprocess starts.
    Overwrites any prior runner_pid (a relaunch supersedes an old runner).
    """
    meta = _read_meta(plan_id)
    if not meta:
        logger.warning("record_launch: no meta.json for %s; skipping", plan_id)
        return
    meta["runner_pid"] = int(runner_pid)
    meta["launched_at"] = datetime.now(timezone.utc).isoformat()
    # status is the user-facing label; lifecycle is the derived truth.
    meta["status"] = "running"
    _write_meta(plan_id, meta)


def _read_progress(plan_id: str, meta: Dict[str, Any]) -> tuple[Optional[Dict[str, Any]], Optional[float]]:
    """Return ``(progress_dict, mtime_epoch)`` for the plan's progress.json, or (None, None)."""
    warrooms_dir = meta.get("warrooms_dir")
    if not warrooms_dir:
        runtime = resolve_runtime_plan_warrooms_dir(plan_id)
        warrooms_dir = str(runtime) if runtime else None
    if not warrooms_dir:
        return None, None
    prog_file = Path(warrooms_dir) / "progress.json"
    if not prog_file.exists():
        return None, None
    try:
        return json.loads(prog_file.read_text()), prog_file.stat().st_mtime
    except (json.JSONDecodeError, OSError):
        return None, prog_file.stat().st_mtime if prog_file.exists() else None


def derive_lifecycle(plan_id: str) -> Dict[str, Any]:
    """Compute the current lifecycle state for a plan from on-disk signals.

    Never invents numbers — if a signal is missing, the returned dict omits
    it (or sets it to ``None``) and the state defaults to ``draft``.
    """
    meta = _read_meta(plan_id)
    runner_pid: Optional[int] = meta.get("runner_pid") if isinstance(meta.get("runner_pid"), int) else None
    launched_at: Optional[str] = meta.get("launched_at")

    progress, mtime = _read_progress(plan_id, meta)

    now = datetime.now(timezone.utc).timestamp()
    heartbeat_age: Optional[float] = (now - mtime) if mtime else None
    heartbeat_fresh = heartbeat_age is not None and heartbeat_age <= HEARTBEAT_TIMEOUT_S
    alive = _pid_alive(runner_pid)

    # Room-level outcome flags from progress.json (truthful — written by the
    # manager loop). If progress.json is absent we can't claim completion or
    # failure, only draft/running/stopped.
    rooms = (progress or {}).get("rooms", []) or []
    total_rooms = len(rooms)
    passed_rooms = sum(1 for r in rooms if r.get("status") == "passed")
    failed_rooms = sum(1 for r in rooms if r.get("status") == "failed-final")
    all_passed = total_rooms > 0 and passed_rooms == total_rooms

    if not launched_at and not runner_pid:
        state, reason = "draft", "never launched"
    elif all_passed:
        state, reason = "completed", f"all {total_rooms} room(s) passed"
    elif alive and heartbeat_fresh:
        state, reason = "running", f"pid {runner_pid} alive, heartbeat {int(heartbeat_age or 0)}s old"
    elif alive and not heartbeat_fresh:
        # Process is up but the manager loop isn't ticking — treat as running
        # so we don't flap, but surface the stale heartbeat in the reason.
        state, reason = "running", f"pid {runner_pid} alive, heartbeat stale ({int(heartbeat_age or 0)}s)"
    elif failed_rooms > 0:
        state, reason = "failed", f"pid {runner_pid or '?'} gone, {failed_rooms} room(s) failed-final"
    else:
        state, reason = "stopped", f"pid {runner_pid or '?'} gone, {passed_rooms}/{total_rooms} room(s) passed"

    return {
        "state": state,
        "reason": reason,
        "runner_pid": runner_pid,
        "alive": alive,
        "launched_at": launched_at,
        "last_heartbeat_at": (
            datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat() if mtime else None
        ),
        "heartbeat_age_s": round(heartbeat_age, 1) if heartbeat_age is not None else None,
    }
