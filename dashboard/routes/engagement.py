from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import AsyncIterator
import asyncio

from dashboard.models import ReactionRequest, CommentRequest
from dashboard.api_utils import (
    load_engagement, 
    toggle_reaction, 
    add_comment, 
    process_notification
)
from dashboard.global_state import broadcaster
from dashboard.auth import get_current_user

router = APIRouter(prefix="/api/engagement", tags=["engagement"])

@router.get("/{entity_id}")
async def get_engagement(entity_id: str, user: dict = Depends(get_current_user)):
    """Retrieve all reactions and comments for an entity."""
    return load_engagement(entity_id)

@router.post("/reactions")
async def post_reaction(req: ReactionRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Toggle a reaction on an entity."""
    state = toggle_reaction(req.entity_id, req.user_id, req.reaction_type)
    event_data = {
        "entity_id": req.entity_id,
        "user_id": req.user_id,
        "reaction_type": req.reaction_type,
        "state": state
    }
    await broadcaster.broadcast("reaction_toggled", event_data)
    background_tasks.add_task(process_notification, "reaction_toggled", event_data)
    return state

@router.post("/comments")
async def post_comment(req: CommentRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Post a hierarchical comment."""
    state, new_comment = add_comment(req.entity_id, req.user_id, req.body, req.parent_id)
    event_data = {
        "entity_id": req.entity_id,
        "comment": new_comment.model_dump() if hasattr(new_comment, "model_dump") else new_comment,
        "state": state.model_dump() if hasattr(state, "model_dump") else state
    }
    await broadcaster.broadcast("comment_published", event_data)
    background_tasks.add_task(process_notification, "comment_published", event_data)
    return {"state": state, "new_comment": new_comment}

@router.get("/events")
async def engagement_events():
    """Real-time event gateway for engagement."""
    async def event_generator() -> AsyncIterator[str]:
        queue = await broadcaster.subscribe_sse()
        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe_sse(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
