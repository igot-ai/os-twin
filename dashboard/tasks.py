import asyncio
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from dashboard.api_utils import (
    WARROOMS_DIR,
    AGENTS_DIR,
    PLANS_DIR,
    PROJECT_ROOT,
    read_room,
    read_channel,
    process_notification,
)
import dashboard.global_state as global_state
from dashboard.epic_manager import EpicSkillsManager
from dashboard.zvec_store import OSTwinStore
# Telegram command handling is now in the Node.js bot (bot/src/telegram.ts).
# Outbound notifications use notify.py (formerly telegram_bot.py).

logger = logging.getLogger(__name__)


async def poll_war_rooms():
    """Background task to poll war-room state and broadcast changes."""
    last_snapshot: dict[str, dict] = {}

    def _discover_warroom_dirs() -> list[Path]:
        """Discover all war-room directories: global + plan-specific."""
        dirs = set()
        if WARROOMS_DIR.exists():
            dirs.add(WARROOMS_DIR)
        # Scan plans meta for plan-specific war-room dirs
        plans_dir = PLANS_DIR
        if plans_dir.exists():
            for meta_file in plans_dir.glob("*.meta.json"):
                try:
                    meta = json.loads(meta_file.read_text())
                    wd = meta.get("working_dir") or meta.get("warrooms_dir")
                    if wd:
                        warrooms_path = Path(wd)
                        if warrooms_path.name != ".war-rooms":
                            warrooms_path = warrooms_path / ".war-rooms"
                        if warrooms_path.exists():
                            dirs.add(warrooms_path)
                except (json.JSONDecodeError, KeyError):
                    pass
        return list(dirs)

    def _find_plan_id_for_warroom_dir(warroom_dir: Path) -> str | None:
        """Find the plan_id whose warrooms_dir matches."""
        if not PLANS_DIR.exists():
            return None
        resolved = warroom_dir.resolve()
        for meta_file in PLANS_DIR.glob("*.meta.json"):
            try:
                meta = json.loads(meta_file.read_text())
                wd = meta.get("warrooms_dir") or meta.get("working_dir")
                if wd:
                    wd_path = Path(wd)
                    if wd_path.name != ".war-rooms":
                        wd_path = wd_path / ".war-rooms"
                    if wd_path.resolve() == resolved:
                        return meta.get("plan_id", meta_file.stem.replace(".meta", ""))
            except (json.JSONDecodeError, KeyError):
                continue
        return None

    # Initialize snapshot
    for warroom_dir in _discover_warroom_dirs():
        for room_dir in sorted(warroom_dir.glob("room-*")):
            if room_dir.is_dir():
                room = read_room(room_dir)
                last_snapshot[room["room_id"]] = room

    # Release file
    release_file = AGENTS_DIR / "RELEASE.md"
    if release_file.exists():
        last_snapshot["__release__"] = {"mtime": release_file.stat().st_mtime}

    # Plans
    plans_dir = PLANS_DIR
    if plans_dir.exists():
        for plan_file in plans_dir.glob("*.md"):
            last_snapshot[f"__plan_{plan_file.name}__"] = {
                "mtime": plan_file.stat().st_mtime
            }

    while True:
        try:
            current: dict[str, dict] = {}
            for warroom_dir in _discover_warroom_dirs():
                for room_dir in sorted(warroom_dir.glob("room-*")):
                    if room_dir.is_dir():
                        room = read_room(room_dir)
                        current[room["room_id"]] = room

            # Detect changes: new rooms, status changes, new messages
            for room_id, room in current.items():
                prev = last_snapshot.get(room_id)
                if prev is None:
                    # New room
                    await global_state.broadcaster.broadcast(
                        "room_created", {"room": room}
                    )
                    await process_notification("room_created", {"room": room})
                    if global_state.store:
                        global_state.store.upsert_room_metadata(room_id, room)

                    room_parent = None
                    for wd in _discover_warroom_dirs():
                        if (wd / room_id).is_dir():
                            room_parent = wd
                            break

                    if room_parent:
                        plan_id = _find_plan_id_for_warroom_dir(room_parent)
                        if plan_id:
                            try:
                                EpicSkillsManager.sync_room_skills(
                                    room_parent / room_id, plan_id
                                )
                            except Exception as e:
                                logger.warning(
                                    "Failed to sync skills for room %s: %s", room_id, e
                                )

                    if room_parent and room["message_count"] > 0:
                        messages = read_channel(room_parent / room_id)
                        event_data = {"room": room, "new_messages": messages}
                        await global_state.broadcaster.broadcast(
                            "room_updated", event_data
                        )
                        await process_notification("room_updated", event_data)
                        if global_state.store:
                            global_state.store.index_messages_batch(room_id, messages)
                elif (
                    prev["status"] != room["status"]
                    or prev["message_count"] != room["message_count"]
                ):
                    # Changed room — find correct dir and include latest channel messages
                    room_parent = None
                    for wd in _discover_warroom_dirs():
                        if (wd / room_id).is_dir():
                            room_parent = wd
                            break
                    if room_parent:
                        messages = read_channel(room_parent / room_id)
                    else:
                        messages = read_channel(WARROOMS_DIR / room_id)
                    new_messages = messages[prev["message_count"] :]
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
                                    p_dir = PLANS_DIR
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
                                except Exception:
                                    pass

            # Detect removed rooms
            for room_id in last_snapshot:
                if (
                    room_id != "__release__"
                    and not room_id.startswith("__plan_")
                    and room_id not in current
                ):
                    await global_state.broadcaster.broadcast(
                        "room_removed", {"room_id": room_id}
                    )

            # Check release
            if release_file.exists():
                curr_mtime = release_file.stat().st_mtime
                if curr_mtime != last_snapshot.get("__release__", {}).get("mtime", 0):
                    await global_state.broadcaster.broadcast(
                        "release", {"content": release_file.read_text()}
                    )
                    current["__release__"] = {"mtime": curr_mtime}

            # Check plans
            plans_changed = False
            if plans_dir.exists():
                for plan_file in plans_dir.glob("*.md"):
                    if plan_file.stem == "PLAN.template":
                        continue
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
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"poll_war_rooms error: {e}")
            await asyncio.sleep(2)


async def startup_all():
    """Initialize state."""
    asyncio.create_task(poll_war_rooms())

    # ── Load model catalog from models.dev ────────────────────────────
    try:
        from dashboard.lib.settings.models_dev_loader import load_models_on_startup

        load_models_on_startup()
    except Exception as e:
        logger.error("Models catalog load failed: %s", e)

    # Telegram polling removed — handled by the Node.js bot (bot/src/telegram.ts)
    # Planning thread store (independent of zvec)
    try:
        from dashboard.planning_thread_store import PlanningThreadStore

        global_state.planning_store = PlanningThreadStore()
        logger.info("Planning thread store initialized")
    except Exception as e:
        logger.error(f"Planning store init failed: {e}")

    try:
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        # Initialize store in global state
        global_state.store = OSTwinStore(WARROOMS_DIR, agents_dir=AGENTS_DIR)

        # Force re-index if requested via CLI flag
        if os.environ.get("OSTWIN_REINDEX") == "true":
            logger.info("Forcing full re-index as requested")
            import shutil

            if global_state.store.zvec_dir.exists():
                shutil.rmtree(global_state.store.zvec_dir)
                global_state.store.zvec_dir.mkdir(parents=True, exist_ok=True)

        global_state.store.ensure_collections()

        # Run the heavy embedding sync in a background thread so uvicorn
        # can start accepting connections immediately.  The sync generates
        # embeddings for every skill/role/message which takes ~5 min on
        # first run (57 skills * ~5s each).  Blocking the event loop here
        # causes the install-script health-check to time out.
        def _background_sync():
            try:
                global_state.store.sync_from_disk()
                from dashboard.api_utils import SKILLS_DIRS

                global_state.store.sync_skills(SKILLS_DIRS)
                logger.info("Skills synced from disk")
                global_state.store.sync_roles(AGENTS_DIR / "roles")
                logger.info("Roles synced from disk")
                from dashboard.routes.roles import sync_roles_from_disk

                result = sync_roles_from_disk()
                if result["synced"]:
                    logger.info(
                        "Roles bridged from disk role.json: %s", result["synced"]
                    )
                logger.info("Background zvec sync complete")
            except Exception as e:
                logger.error("Background zvec sync failed: %s", e)

        import threading

        sync_thread = threading.Thread(
            target=_background_sync, daemon=True, name="zvec-sync"
        )
        sync_thread.start()
        logger.info("zvec sync started in background thread")
    except Exception as e:
        logger.error(f"zvec init failed: {e}")
        global_state.store = None

    # Auto-start ngrok tunnel if NGROK_AUTHTOKEN is set
    auth_token = os.environ.get("NGROK_AUTHTOKEN")
    if auth_token:
        try:
            from dashboard.tunnel import start_tunnel

            port = int(os.environ.get("DASHBOARD_PORT", "9000"))
            domain = os.environ.get("NGROK_DOMAIN")
            url = await start_tunnel(port, auth_token, domain)
            global_state.tunnel_url = url
            logger.info("ngrok tunnel active: %s", url)
            # Notify Telegram chats
            try:
                from dashboard.notify import send_message

                await send_message(f"📡 Dashboard is live at: {url}")
            except Exception:
                pass
        except Exception as e:
            logger.error("ngrok tunnel failed: %s", e)
