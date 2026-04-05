import os
import json
import hashlib
import asyncio
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dashboard.auth import get_current_user
import dashboard.global_state as global_state
from dashboard.plan_agent import brainstorm_stream, refine_plan, _resolve_model
from dashboard.api_utils import PLANS_DIR, PROJECT_ROOT, AGENTS_DIR

router = APIRouter(tags=["threads"])
logger = logging.getLogger(__name__)

class ImageData(BaseModel):
    url: str
    name: str = ""
    type: str = "image/jpeg"

class ThreadMessageRequest(BaseModel):
    message: str
    images: Optional[List[ImageData]] = None

class PromoteRequest(BaseModel):
    title: Optional[str] = None
    working_dir: Optional[str] = None

@router.post("/api/plans/threads", status_code=201)
async def create_thread(request: ThreadMessageRequest, user: dict = Depends(get_current_user)):
    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    
    store = global_state.planning_store
    if not store:
        raise HTTPException(status_code=500, detail="Planning store not initialized")
        
    thread = store.create(title="New Idea")
    images_data = [img.model_dump() for img in request.images] if request.images else None
    await store.append_message(thread.id, "user", request.message, images=images_data)

    return {"thread_id": thread.id, "title": thread.title}

@router.get("/api/plans/threads")
async def list_threads(limit: int = Query(20), offset: int = Query(0), user: dict = Depends(get_current_user)):
    store = global_state.planning_store
    if not store:
        raise HTTPException(status_code=500, detail="Planning store not initialized")
        
    threads = store.list_threads(limit=limit, offset=offset)
    total = len(store._read_index())
    return {"threads": threads, "total": total}

@router.get("/api/plans/threads/{thread_id}")
async def get_thread(thread_id: str, user: dict = Depends(get_current_user)):
    store = global_state.planning_store
    if not store:
        raise HTTPException(status_code=500, detail="Planning store not initialized")
        
    thread = store.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    messages = store.get_messages(thread_id)
    return {"thread": thread, "messages": messages}

async def auto_generate_title(thread_id: str, first_message: str):
    try:
        chat_model = _resolve_model()
        from langchain_core.messages import HumanMessage
        prompt = f"Generate a 4-8 word title for this conversation: {first_message}"
        result = await chat_model.ainvoke([HumanMessage(content=prompt)])
        
        title = result.content
        if isinstance(title, list):
            title = "".join([b["text"] if isinstance(b, dict) and "text" in b else str(b) for b in title])
        
        title = title.strip().strip('"').strip("'")
        store = global_state.planning_store
        if store:
            store.update_title(thread_id, title)
    except Exception as e:
        logger.error("Auto-title generation failed: %s", e)

@router.post("/api/plans/threads/{thread_id}/messages/stream")
async def stream_thread_message(thread_id: str, request: ThreadMessageRequest, user: dict = Depends(get_current_user)):
    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    # Validate images
    images_data = None
    if request.images:
        if len(request.images) > 10:
            raise HTTPException(status_code=422, detail="Maximum 10 images allowed")
        for img in request.images:
            if not img.url.startswith("data:image/"):
                raise HTTPException(status_code=422, detail="Images must be data URIs (data:image/...)")
            if len(img.url) > 2 * 1024 * 1024:
                raise HTTPException(status_code=422, detail=f"Image '{img.name}' exceeds 2MB limit")
        images_data = [img.model_dump() for img in request.images]

    store = global_state.planning_store
    if not store:
        raise HTTPException(status_code=500, detail="Planning store not initialized")

    thread = store.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Only append user message if the last stored message isn't already this exact text
    # (avoids duplicates when auto-triggering reply for the initial message)
    existing = store.get_messages(thread_id)
    last_msg = existing[-1] if existing else None
    if not (last_msg and last_msg.role == "user" and last_msg.content == request.message):
        await store.append_message(thread_id, "user", request.message, images=images_data)
    elif last_msg and not images_data and last_msg.images:
        # Dedup case: message already stored (e.g. auto-trigger) — use stored images
        images_data = last_msg.images

    # Load history (include images for multimodal replay)
    db_messages = store.get_messages(thread_id)
    chat_history = [{"role": m.role, "content": m.content, "images": m.images} for m in db_messages[:-1]]

    async def event_generator():
        full_response = ""
        try:
            async for token in brainstorm_stream(user_message=request.message, chat_history=chat_history, images=images_data):
                if "[Error:" in token:
                    yield f'data: {{"error": {json.dumps(token)}}}\n\n'
                else:
                    full_response += token
                    yield f'data: {{"token": {json.dumps(token)}}}\n\n'
            
            # Save assistant response
            if full_response:
                await store.append_message(thread_id, "assistant", full_response)
                
            yield 'data: {"done": true}\n\n'
            
            # Trigger auto-title if needed
            if thread.title == "New Idea" and thread.message_count <= 2:
                first_msg = next((m.content for m in db_messages if m.role == "user"), request.message)
                asyncio.create_task(auto_generate_title(thread_id, first_msg))
                
        except Exception as e:
            logger.error("Streaming error: %s", e)
            yield f'data: {{"error": {json.dumps(str(e))}}}\n\n'
            yield 'data: {"done": true}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/api/plans/threads/{thread_id}/promote")
async def promote_thread(thread_id: str, request: PromoteRequest, user: dict = Depends(get_current_user)):
    store = global_state.planning_store
    if not store:
        raise HTTPException(status_code=500, detail="Planning store not initialized")
        
    thread = store.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    if thread.status == "promoted":
        raise HTTPException(status_code=400, detail="Thread is already promoted")
        
    db_messages = store.get_messages(thread_id)
    chat_history = [{"role": m.role, "content": m.content} for m in db_messages]
    
    try:
        user_msg = "Based on this brainstorming conversation, create a structured plan"
        result = await refine_plan(
            user_message=user_msg, 
            plan_content="", 
            chat_history=chat_history,
            plans_dir=PLANS_DIR
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
            
        plan_content = result.get("plan")
        if not plan_content:
            plan_content = result.get("full_response", "Failed to generate plan content.")
            
        title = request.title or thread.title
        raw = f"{title}:{datetime.now(timezone.utc).isoformat()}"
        plan_id = hashlib.sha256(raw.encode()).hexdigest()[:12]
        
        plans_dir = PLANS_DIR
        plans_dir.mkdir(exist_ok=True)
        plan_file = plans_dir / f"{plan_id}.md"
        
        working_dir = request.working_dir or ''
        if not working_dir or working_dir == '.':
            slug = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-')[:40]
            if not slug:
                slug = plan_id
            project_dir = PROJECT_ROOT / "projects" / slug
            project_dir.mkdir(parents=True, exist_ok=True)
            working_dir = str(project_dir)
            
        plan_file.write_text(plan_content)
        
        meta_file = plans_dir / f"{plan_id}.meta.json"
        meta = {
            "plan_id": plan_id,
            "title": title,
            "thread_id": thread_id,
            "working_dir": working_dir,
            "warrooms_dir": str(Path(working_dir) / ".war-rooms"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "draft"
        }
        meta_file.write_text(json.dumps(meta, indent=2) + "\n")
        
        plan_roles_file = plans_dir / f"{plan_id}.roles.json"
        if not plan_roles_file.exists():
            global_config_file = AGENTS_DIR / "config.json"
            seed_config = json.loads(global_config_file.read_text()) if global_config_file.exists() else {}
            try:
                from dashboard.routes.roles import load_roles
                for role in load_roles():
                    if role.name not in seed_config:
                        seed_config[role.name] = {}
                    rc = seed_config[role.name]
                    rc.setdefault("default_model", role.version)
                    rc.setdefault("timeout_seconds", role.timeout_seconds)
                    if role.skill_refs:
                        rc.setdefault("skill_refs", role.skill_refs)
            except Exception:
                pass
            plan_roles_file.write_text(json.dumps(seed_config, indent=2) + "\n")
            
        store.set_promoted(thread_id, plan_id)
        
        zstore = global_state.store
        if zstore:
            try:
                zstore.index_plan(
                    plan_id=plan_id, title=title, content=plan_content, 
                    epic_count=1, filename=f"{plan_id}.md", 
                    status="draft", created_at=meta["created_at"], 
                    file_mtime=plan_file.stat().st_mtime
                )
            except Exception as e:
                logger.warning("Failed to index promoted plan %s in zvec: %s", plan_id, e)
                
        return {"plan_id": plan_id, "url": f"/plans/{plan_id}"}
        
    except Exception as e:
        logger.error("Promote failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
