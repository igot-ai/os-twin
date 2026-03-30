import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from dashboard.chat_adapters.registry import registry
from dashboard.models import ChatAdapterConfigRequest, ChatNotificationSettings
from dashboard.auth import get_current_user

from dashboard.api_utils import find_room_dir, post_message_to_room

router = APIRouter(prefix="/api/chat-adapters", tags=["chat-adapters"])
logger = logging.getLogger(__name__)

@router.post("/{platform}/webhook")
async def chat_platform_webhook(platform: str, request: Request):
    """Unified webhook receiver for all chat platforms."""
    payload = await request.json()
    headers = dict(request.headers)
    raw_body = await request.body()
    
    adapter = registry.get_adapter(platform)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Platform {platform} not found")
        
    result = await adapter.handle_webhook(payload, headers=headers, raw_body=raw_body)
    if not result:
        return {"status": "ignored"}
        
    # Handle Slack-style URL verification or Discord Ping
    if "challenge" in result or "type" in result:
        return result
        
    room_id = result.get("room_id")
    message = result.get("message")
    
    if room_id and message:
        room_dir = find_room_dir(room_id)
        if not room_dir:
            logger.error(f"Received message for unknown room: {room_id}")
            raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
        
        await post_message_to_room(room_dir, message)
        return {"status": "success", "room_id": room_id}
        
    return {"status": "processed"}

@router.get("/config")
async def get_all_configs(user: dict = Depends(get_current_user)):
    """Get all configured chat adapter settings and global dispatcher settings."""
    adapters_config = {k: v for k, v in registry.configs.items() if not k.startswith("_")}
    return {
        "adapters": adapters_config,
        "registered_platforms": registry.get_registered_platforms(),
        "settings": registry.get_settings()
    }

@router.post("/settings")
async def update_settings(settings: ChatNotificationSettings, user: dict = Depends(get_current_user)):
    """Update global notification settings (important_events, enabled_platforms)."""
    registry.update_settings(settings.model_dump())
    return {"status": "success", "settings": settings}

@router.post("/config")
async def update_adapter_config(request: ChatAdapterConfigRequest, user: dict = Depends(get_current_user)):
    """Update configuration for a specific platform."""
    if request.platform not in registry.get_registered_platforms():
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {request.platform}")
    
    registry.update_config(request.platform, request.config)
    return {"status": "success", "platform": request.platform}

@router.post("/{platform}/test")
async def test_adapter(platform: str, user: dict = Depends(get_current_user)):
    """Send a test message through the specified platform adapter."""
    adapter = registry.get_adapter(platform)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Platform {platform} not found or not supported")
    
    if not adapter.validate_config():
        raise HTTPException(status_code=400, detail=f"Configuration for {platform} is incomplete")
        
    success = await adapter.send_message(f"Test message from OS Twin ({platform} adapter)!")
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to send test message via {platform}")
        
    return {"status": "success", "platform": platform}
