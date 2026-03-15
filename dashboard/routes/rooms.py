from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import AsyncIterator
import asyncio
from pathlib import Path

from dashboard.api_utils import (
    WARROOMS_DIR, PROJECT_ROOT, AGENTS_DIR,
    read_room, read_channel, process_notification
)
import dashboard.global_state as global_state
from dashboard.auth import get_current_user

router = APIRouter(tags=["rooms"])

@router.get("/api/rooms")
async def list_rooms(user: dict = Depends(get_current_user)):
    """List all war-rooms with current status."""
    rooms = []
    if not WARROOMS_DIR.exists():
        return {"rooms": [], "summary": {}}

    for room_dir in sorted(WARROOMS_DIR.glob("room-*")):
        if room_dir.is_dir():
            rooms.append(read_room(room_dir))

    # Summary counts
    summary = {"total": len(rooms)}
    for status in ("pending", "engineering", "qa-review", "fixing", "passed", "failed-final"):
        summary[status.replace("-", "_")] = sum(1 for r in rooms if r["status"] == status)

    return {"rooms": rooms, "summary": summary, "debug": {"project_root": str(PROJECT_ROOT), "agents_dir": str(AGENTS_DIR)}}

@router.get("/api/rooms/{room_id}/channel")
async def get_channel(room_id: str, user: dict = Depends(get_current_user)):
    """Get messages for a specific war-room (searches global + plan-specific dirs)."""
    import json as _json
    room_dir = WARROOMS_DIR / room_id
    if not room_dir.exists():
        # Search plan-specific war-room directories
        plans_dir = AGENTS_DIR / "plans"
        if plans_dir.exists():
            for meta_file in plans_dir.glob("*.meta.json"):
                try:
                    meta = _json.loads(meta_file.read_text())
                    wd = meta.get("working_dir")
                    if wd:
                        candidate = Path(wd) / ".war-rooms" / room_id
                        if candidate.exists():
                            room_dir = candidate
                            break
                except (ValueError, KeyError):
                    pass
    if not room_dir.exists():
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    return {"messages": read_channel(room_dir)}

@router.get("/api/events")
async def sse_events():
    """Server-Sent Events stream."""
    async def event_generator() -> AsyncIterator[str]:
        queue = await global_state.broadcaster.subscribe_sse()
        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            global_state.broadcaster.unsubscribe_sse(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

@router.get("/api/search")
async def search_messages(
    q: str = Query(..., min_length=1),
    room_id: str | None = Query(None),
    type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Semantic vector search across all indexed messages."""
    store = global_state.store
    if not store:
        raise HTTPException(status_code=503, detail="Vector search not available")
    results = store.search(q, room_id=room_id, msg_type=type, limit=limit)
    return {"results": results, "count": len(results)}

@router.get("/api/rooms/{room_id}/context")
async def search_room_context(
    room_id: str,
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
):
    """Semantic search scoped to a single room."""
    store = global_state.store
    if not store:
        raise HTTPException(status_code=503, detail="Vector search not available")
    results = store.search(q, room_id=room_id, limit=limit)
    return {"results": results, "count": len(results)}

@router.get("/api/rooms/{room_id}/state")
async def get_room_state(room_id: str):
    """Get room metadata."""
    store = global_state.store
    if store:
        meta = store.get_room_metadata(room_id)
        if meta:
            return meta
    # Fallback to file-based read
    room_dir = WARROOMS_DIR / room_id
    if not room_dir.exists():
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    return read_room(room_dir)

@router.post("/api/rooms/{room_id}/action")
async def room_action(room_id: str, background_tasks: BackgroundTasks, action: str = Query(...)):
    """Perform an action on a room (stop, pause, resume)."""
    room_dir = WARROOMS_DIR / room_id
    if not room_dir.exists():
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")

    status_file = room_dir / "status"
    if action == "stop":
        status_file.write_text("failed-final")
    elif action == "pause":
        status_file.write_text("paused")
    elif action == "resume" or action == "start":
        status_file.write_text("pending")
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    background_tasks.add_task(process_notification, "room_action", {"room_id": room_id, "action": action})
    return {"status": "ok", "action": action, "room_id": room_id}
