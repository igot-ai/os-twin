import asyncio
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from dashboard.api_utils import (
    WARROOMS_DIR, AGENTS_DIR, PROJECT_ROOT, 
    read_room, read_channel, process_notification
)
import dashboard.global_state as global_state
from dashboard.zvec_store import OSTwinStore

logger = logging.getLogger(__name__)

async def poll_war_rooms():
    """Background task to poll war-room state and broadcast changes."""
    last_snapshot: dict[str, dict] = {}
    
    # Initialize snapshot
    if WARROOMS_DIR.exists():
        for room_dir in sorted(WARROOMS_DIR.glob("room-*")):
            if room_dir.is_dir():
                room = read_room(room_dir)
                last_snapshot[room["room_id"]] = room

    # Release file
    release_file = AGENTS_DIR / "RELEASE.md"
    if release_file.exists():
        last_snapshot["__release__"] = {"mtime": release_file.stat().st_mtime}

    # Plans
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
                    await global_state.broadcaster.broadcast("room_created", {"room": room})
                    await process_notification("room_created", {"room": room})
                    if global_state.store:
                        global_state.store.upsert_room_metadata(room_id, room)
                    
                    # Ensure initial messages are broadcast
                    if room["message_count"] > 0:
                        messages = read_channel(WARROOMS_DIR / room_id)
                        event_data = {"room": room, "new_messages": messages}
                        await global_state.broadcaster.broadcast("room_updated", event_data)
                        await process_notification("room_updated", event_data)
                        if global_state.store:
                            global_state.store.index_messages_batch(room_id, messages)
                elif (
                    prev["status"] != room["status"]
                    or prev["message_count"] != room["message_count"]
                ):
                    # Changed room — include latest channel messages
                    messages = read_channel(WARROOMS_DIR / room_id)
                    new_messages = messages[prev["message_count"]:]
                    event_data = {"room": room, "new_messages": new_messages}
                    await global_state.broadcaster.broadcast("room_updated", event_data)
                    await process_notification("room_updated", event_data)
                    
                    # Index new messages and update metadata in zvec
                    if global_state.store:
                        global_state.store.index_messages_batch(room_id, new_messages)
                        global_state.store.upsert_room_metadata(room_id, room)
                        # Sync epic status if room status changed
                        if prev["status"] != room["status"]:
                            epic_ref = room.get("task_ref", "")
                            if epic_ref:
                                # Find plan_id from plans dir (latest launched)
                                try:
                                    p_dir = AGENTS_DIR / "plans"
                                    if p_dir.exists():
                                        latest = max(
                                            p_dir.glob("agent-os-plan-*.md"),
                                            key=lambda p: p.stat().st_mtime,
                                            default=None,
                                        )
                                        if latest:
                                            global_state.store.update_epic_status(
                                                latest.stem, epic_ref, room["status"]
                                            )
                                except Exception: pass

            # Detect removed rooms
            for room_id in last_snapshot:
                if room_id != "__release__" and not room_id.startswith("__plan_") and room_id not in current:
                    await global_state.broadcaster.broadcast("room_removed", {"room_id": room_id})

            # Check release
            if release_file.exists():
                curr_mtime = release_file.stat().st_mtime
                if curr_mtime != last_snapshot.get("__release__", {}).get("mtime", 0):
                    await global_state.broadcaster.broadcast("release", {"content": release_file.read_text()})
                    current["__release__"] = {"mtime": curr_mtime}

            # Check plans
            plans_changed = False
            if plans_dir.exists():
                for plan_file in plans_dir.glob("*.md"):
                    if plan_file.stem == "PLAN.template": continue
                    plan_key = f"__plan_{plan_file.name}__"
                    curr_mtime = plan_file.stat().st_mtime
                    if curr_mtime != last_snapshot.get(plan_key, {}).get("mtime", 0):
                        plans_changed = True
                    current[plan_key] = {"mtime": curr_mtime}
            
            # Check for deleted plans
            for key in last_snapshot:
                if key.startswith("__plan_") and key not in current:
                    plans_changed = True
            
            if plans_changed:
                await global_state.broadcaster.broadcast("plans_updated", {})

            last_snapshot = current
            await asyncio.sleep(1)
        except asyncio.CancelledError: break
        except Exception as e:
            logger.error(f"poll_war_rooms error: {e}")
            await asyncio.sleep(2)

async def startup_all():
    """Initialize state."""
    asyncio.create_task(poll_war_rooms())
    try:
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        # Initialize store in global state
        global_state.store = OSTwinStore(WARROOMS_DIR, agents_dir=AGENTS_DIR)
        global_state.store.ensure_collections()
        global_state.store.sync_from_disk()
    except Exception as e:
        logger.error(f"zvec init failed: {e}")
        global_state.store = None
