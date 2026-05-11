import asyncio
import os
import json
import logging
from pathlib import Path
from typing import Dict, Set

from dashboard.api_utils import (
    WARROOMS_DIR,
    AGENTS_DIR,
    PLANS_DIR,
    GLOBAL_PLANS_DIR,
    read_room,
    read_channel,
    process_notification,
    resolve_runtime_plan_warrooms_dir,
)
import dashboard.global_state as global_state
from dashboard.plan_completion import mark_plan_completed, progress_is_completed
from dashboard.epic_manager import EpicSkillsManager
# Heavy imports moved to background thread to prevent startup blocking

# Telegram command handling is now in the Node.js bot (bot/src/telegram.ts).
# Outbound notifications use notify.py (formerly telegram_bot.py).

logger = logging.getLogger(__name__)


async def _check_plan_completions(completed_plans: Set[str], max_size: int = 1000) -> None:
    """Check for newly completed plans and trigger deploy preview.
    
    A plan is considered completed when:
    - All rooms have status "passed"
    - Deploy has not already been triggered for this completion
    
    Args:
        completed_plans: Set of plan_ids that have already been processed
        max_size: Maximum size of completed_plans set to prevent unbounded growth
    """
    from dashboard.deploy_completion import (
        read_progress_json,
        is_plan_completed,
        handle_plan_completion,
    )
    
    plans_dir = PLANS_DIR
    if not plans_dir.exists():
        return
    
    for meta_file in plans_dir.glob("*.meta.json"):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            plan_id = meta.get("plan_id", meta_file.stem.replace(".meta", ""))
            
            if plan_id in completed_plans:
                continue
            
            warrooms_dir = resolve_runtime_plan_warrooms_dir(plan_id)
            if not warrooms_dir or not warrooms_dir.exists():
                continue
            
            progress = read_progress_json(warrooms_dir)
            if not progress:
                continue
            
            if is_plan_completed(progress):
                completed_plans.add(plan_id)
                
                # Trim arbitrary entries if set exceeds max size (sets don't maintain order)
                if len(completed_plans) > max_size:
                    excess = len(completed_plans) - max_size
                    for _ in range(excess):
                        completed_plans.pop()
                
                working_dir = meta.get("working_dir")
                if not working_dir:
                    continue
                
                working_path = Path(working_dir)
                if not working_path.is_absolute():
                    from dashboard.api_utils import PROJECT_ROOT
                    working_path = PROJECT_ROOT / working_path
                
                plan_title = meta.get("title", plan_id)
                
                dashboard_url = None
                if global_state.tunnel_url:
                    dashboard_url = global_state.tunnel_url
                else:
                    port = os.environ.get("DASHBOARD_PORT", "3366")
                    dashboard_url = f"http://localhost:{port}"
                
                logger.info(f"Plan {plan_id} completed, triggering deploy preview")
                
                try:
                    await handle_plan_completion(
                        plan_id=plan_id,
                        working_dir=working_path,
                        plan_title=plan_title,
                        broadcaster=global_state.broadcaster,
                        dashboard_base_url=dashboard_url,
                    )
                except Exception as e:
                    logger.error(f"Failed to handle completion for plan {plan_id}: {e}")
                    
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning(f"Error checking plan completion for {meta_file}: {e}")
            continue


async def poll_war_rooms():
    """Background task to poll war-room state and broadcast changes."""
    last_snapshot: dict[str, dict] = {}
    
    _completed_plans: Set[str] = set()
    _MAX_COMPLETED_PLANS = 1000  # Prevent unbounded growth

    _cached_warroom_dirs: list[Path] = []
    _cached_warroom_dirs_time: float = 0
    _WARROOM_CACHE_TTL = 10  # seconds

    def _iter_plan_meta_files() -> list[Path]:
        meta_files: list[Path] = []
        seen: set[Path] = set()
        for plans_dir in (PLANS_DIR, GLOBAL_PLANS_DIR):
            if not plans_dir.exists():
                continue
            for meta_file in plans_dir.glob("*.meta.json"):
                resolved = meta_file.resolve()
                if resolved not in seen:
                    meta_files.append(meta_file)
                    seen.add(resolved)
        return meta_files

    def _discover_warroom_dirs() -> list[Path]:
        """Discover all war-room directories: global + plan-specific.

        Results are cached for 10 seconds to avoid re-globbing and re-reading
        .meta.json files on every 1-second poll cycle, which can exhaust the
        OS file-descriptor limit (macOS default is often only 256).
        """
        nonlocal _cached_warroom_dirs, _cached_warroom_dirs_time
        import time

        now = time.monotonic()
        if (
            _cached_warroom_dirs
            and (now - _cached_warroom_dirs_time) < _WARROOM_CACHE_TTL
        ):
            return _cached_warroom_dirs

        dirs = set()
        if WARROOMS_DIR.exists():
            dirs.add(WARROOMS_DIR)
        # Scan plans meta for plan-specific war-room dirs
        for meta_file in _iter_plan_meta_files():
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

        _cached_warroom_dirs = list(dirs)
        _cached_warroom_dirs_time = now
        return _cached_warroom_dirs

    def _find_plan_meta_for_warroom_dir(warroom_dir: Path) -> tuple[str, Path, dict] | None:
        """Find the plan metadata whose warrooms_dir matches."""
        resolved = warroom_dir.resolve()
        for meta_file in _iter_plan_meta_files():
            try:
                meta = json.loads(meta_file.read_text())
                wd = meta.get("warrooms_dir") or meta.get("working_dir")
                if wd:
                    wd_path = Path(wd)
                    if wd_path.name != ".war-rooms":
                        wd_path = wd_path / ".war-rooms"
                    if wd_path.resolve() == resolved:
                        return (
                            meta.get("plan_id", meta_file.stem.replace(".meta", "")),
                            meta_file,
                            meta,
                        )
            except (json.JSONDecodeError, KeyError):
                continue
        return None

    def _find_plan_id_for_warroom_dir(warroom_dir: Path) -> str | None:
        """Find the plan_id whose warrooms_dir matches."""
        found = _find_plan_meta_for_warroom_dir(warroom_dir)
        return found[0] if found else None

    def _build_progress_from_warroom_dir(warroom_dir: Path) -> dict:
        total = passed = failed = blocked = active = pending = 0
        rooms = []

        for room_dir in sorted(warroom_dir.glob("room-*")):
            if not room_dir.is_dir():
                continue

            total += 1
            status_file = room_dir / "status"
            status = status_file.read_text().strip() if status_file.exists() else "pending"
            task_ref_file = room_dir / "task-ref"
            task_ref = task_ref_file.read_text().strip() if task_ref_file.exists() else "?"

            if status == "passed":
                passed += 1
            elif status == "failed-final":
                failed += 1
            elif status == "blocked":
                blocked += 1
            elif status == "pending":
                pending += 1
            else:
                active += 1

            rooms.append({"room_id": room_dir.name, "task_ref": task_ref, "status": status})

        pct_complete = round((passed / total) * 100, 1) if total > 0 else 0
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "active": active,
            "pending": pending,
            "pct_complete": pct_complete,
            "rooms": rooms,
        }

    async def _maybe_mark_plan_completed_from_warrooms(warroom_dir: Path) -> None:
        found = _find_plan_meta_for_warroom_dir(warroom_dir)
        if not found:
            return
        plan_id, meta_path, meta = found

        progress = _build_progress_from_warroom_dir(warroom_dir)
        if not progress_is_completed(progress):
            return

        try:
            await mark_plan_completed(
                plan_id,
                meta=meta,
                meta_path=meta_path,
                progress=progress,
                source="warroom_poll",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to broadcast completion for plan %s: %s", plan_id, exc)

    def _read_plan_title(plan_id: str | None) -> str | None:
        if not plan_id or not PLANS_DIR.exists():
            return None
        plan_file = PLANS_DIR / f"{plan_id}.md"
        if not plan_file.exists():
            matches = list(PLANS_DIR.glob(f"{plan_id}*.md"))
            plan_file = matches[0] if matches else plan_file
        if not plan_file.exists():
            return None
        try:
            first_line = plan_file.read_text().splitlines()[0].strip()
        except (OSError, IndexError):
            return None
        for prefix in ("# Plan:", "# PLAN:", "# "):
            if first_line.startswith(prefix):
                return first_line[len(prefix):].strip()
        return first_line.lstrip("#").strip() or None

    async def _broadcast_completed_plans() -> None:
        for warroom_dir in _discover_warroom_dirs():
            progress = _build_progress_from_warroom_dir(warroom_dir)
            if not progress.get("total"):
                continue

            found = _find_plan_meta_for_warroom_dir(warroom_dir)
            if not found:
                continue
            plan_id, meta_path, meta = found

            is_complete = progress_is_completed(progress)
            if is_complete and plan_id not in completed_plan_ids:
                completed_plan_ids.add(plan_id)
                await mark_plan_completed(
                    plan_id,
                    meta=meta,
                    meta_path=meta_path,
                    progress=progress,
                    source="warroom_poll",
                )
            elif not is_complete:
                completed_plan_ids.discard(plan_id)

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

    for warroom_dir in _discover_warroom_dirs():
        rooms = [p for p in sorted(warroom_dir.glob("room-*")) if p.is_dir()]
        if not rooms:
            continue
        statuses = [
            (room_dir / "status").read_text().strip()
            if (room_dir / "status").exists()
            else "pending"
            for room_dir in rooms
        ]
        if statuses and all(status == "passed" for status in statuses):
            completed_plan_ids.add(_find_plan_id_for_warroom_dir(warroom_dir) or warroom_dir.name)

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
                            # EPIC-004: Inject assets into war room
                            epic_ref = room.get("task_ref", "")
                            if epic_ref:
                                try:
                                    EpicSkillsManager.inject_room_assets(
                                        room_parent / room_id, plan_id, epic_ref
                                    )
                                except Exception as e:
                                    logger.warning(
                                        "Failed to inject assets for room %s: %s",
                                        room_id,
                                        e,
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
                    if room_parent and prev["status"] != room["status"]:
                        await _maybe_mark_plan_completed_from_warrooms(room_parent)

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

            await _check_plan_completions(_completed_plans, _MAX_COMPLETED_PLANS)

            last_snapshot = current
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - intentional catch-all for polling resilience
            logger.error("poll_war_rooms error: %s", e, exc_info=True)
            await asyncio.sleep(2)


async def startup_all():
    """Initialize state."""
    asyncio.create_task(poll_war_rooms())

    # ── Push Deployment Notification to Lark ──────────────────────────
    # Only trigger at runtime on Cloud Run (excludes Docker build phase)
    if os.environ.get("K_SERVICE"):
        async def _notify_lark_delayed():
            try:
                # Small delay to ensure networking is fully up and stable
                await asyncio.sleep(5)
                
                from dashboard.notify import send_lark_message
                env_path = Path.home() / ".ostwin" / ".env"
                if env_path.exists():
                    from dotenv import load_dotenv
                    load_dotenv(env_path)

                api_key = os.environ.get("OSTWIN_API_KEY")
                if api_key:
                    app_url = os.environ.get("BASE_URL")
                    msg_lines = [
                        f"🔑 **OSTWIN_API_KEY**: {api_key}",
                        f"📦 **Revision**: {os.environ.get('K_REVISION', 'unknown')}",
                    ]
                    if app_url:
                        msg_lines.append(f"🌐 **Dashboard**: {app_url}")
                    else:
                        msg_lines.append("🌐 **Service**: Cloud Run (URL not set)")

                    msg = "\n".join(msg_lines)
                    await send_lark_message(msg, title="🚀 OS-Twin Deployed Successfully")
            except Exception as e:
                logger.error(f"Lark notification background task failed: {e}")

        asyncio.create_task(_notify_lark_delayed())



    # ── Hot-reload ~/.ostwin/.env on file changes ─────────────────────

    try:
        from dashboard.env_watcher import watch_env_file

        asyncio.create_task(watch_env_file())
    except Exception as e:
        logger.error("env_watcher failed to start: %s", e)

    # Models catalog and heavy syncs move to the background thread

    # Telegram polling removed — handled by the Node.js bot (bot/src/telegram.ts)
    # Planning thread store (initialized early/sync to avoid race conditions with first requests)
    try:
        from dashboard.planning_thread_store import PlanningThreadStore

        global_state.planning_store = PlanningThreadStore()
        logger.info("Planning thread store initialized (Sync)")
    except Exception as e:
        logger.error(f"Planning store init failed: {e}")

    try:
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        # Initialize store in the background thread to prevent slow imports
        # (torch, sentence_transformers) from blocking the main loop.

        # Force re-index if requested via CLI flag
        if os.environ.get("OSTWIN_REINDEX") == "true":
            logger.info("Forcing full re-index as requested")
            import shutil

            if global_state.store.zvec_dir.exists():
                shutil.rmtree(global_state.store.zvec_dir)
                global_state.store.zvec_dir.mkdir(parents=True, exist_ok=True)

        global_state.store.ensure_collections()

        def _background_sync():
            from dashboard.routes import skills as skills_routes

            skills_routes._sync_in_progress = True
            try:
                # ── Grace Period ──
                # Give the browser 5 seconds to load HTML/JS/CSS before we
                # start hogging the CPU with Torch and YAML parsing.
                import time

                time.sleep(5)

                # Lazy import of heavy vector store
                from dashboard.zvec_store import OSTwinStore

                global_state.store = OSTwinStore(WARROOMS_DIR, agents_dir=AGENTS_DIR)

                # ── Load model catalog from models.dev ────────────────────────────
                try:
                    from dashboard.lib.settings.models_dev_loader import (
                        load_models_on_startup,
                    )

                    load_models_on_startup()
                except Exception as e:
                    logger.error("Models catalog load failed: %s", e)

                # ── Initialize master agent client ────────────────────────────
                try:
                    from dashboard.master_agent import get_master_client
                    client = get_master_client()
                    logger.info("Master agent client initialized")
                except Exception as e:
                    logger.warning("Master agent init failed (will retry on first use): %s", e)
                
                # Initialization (slow — loads 600MB model)
                global_state.store.ensure_collections()

                # Syncing
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
            finally:
                skills_routes._sync_in_progress = False

        import threading

        sync_thread = threading.Thread(
            target=_background_sync, daemon=True, name="zvec-sync"
        )
        sync_thread.start()
        logger.info("zvec sync started in background thread")
    except Exception as e:
        logger.error(f"zvec init failed: {e}")
        global_state.store = None

    # Initialize bot manager but don't auto-start — use POST /api/bot/start instead
    try:
        from dashboard.bot_manager import BotProcessManager, BOT_DIR

        if BOT_DIR.exists():
            global_state.bot_manager = BotProcessManager()
            logger.info("Bot manager initialized — start via POST /api/bot/start")
        else:
            logger.info("Bot directory not found — bot manager disabled")
    except Exception as e:
        logger.error("Bot manager init failed: %s", e)

    # Auto-start ngrok tunnel if NGROK_AUTHTOKEN is set
    auth_token = os.environ.get("NGROK_AUTHTOKEN")
    if auth_token:
        try:
            from dashboard.tunnel import start_tunnel

            port = int(os.environ.get("DASHBOARD_PORT", "3366"))
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
