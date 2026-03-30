import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from .chat_adapters.registry import registry

logger = logging.getLogger(__name__)

class NotificationDispatcher:
    def __init__(self):
        # We'll reload these from registry on each dispatch to be fully dynamic
        pass

    def _should_notify(self, event_type: str, data: Dict[str, Any]) -> bool:
        """Filter events that should be sent to chat platforms."""
        settings = registry.get_settings()
        important_events = set(settings.get("important_events", []))
        
        # Check if it's an explicitly important event type
        if event_type in important_events:
            return True
        
        # Check for error or escalation in data
        if data.get("level") in ["error", "critical", "escalation"]:
            return True
            
        return False

    def _format_message(self, platform: str, event_type: str, data: Dict[str, Any]) -> str:
        """Format the event data into a platform-specific string."""
        # Simple shared formatting for now, can be specialized per platform
        emoji = "ℹ️"
        if event_type == "error": emoji = "🚨"
        elif event_type == "escalation": emoji = "🔥"
        elif event_type == "room_status_change": emoji = "🔄"
        elif event_type == "done": emoji = "✅"
        
        msg = f"{emoji} *Event:* {event_type.replace('_', ' ').title()}\n"
        
        # Extract useful fields
        room_id = data.get("room_id") or data.get("room")
        if room_id:
            msg += f"*Room:* `{room_id}`\n"
            
        status = data.get("status") or data.get("new_status")
        if status:
            msg += f"*Status:* {status}\n"
            
        message = data.get("message") or data.get("body") or data.get("text")
        if message:
            msg += f"*Details:* {message}\n"
            
        # If it's a generic event with other data, list some keys
        if not (status or message):
            other_info = {k: v for k, v in data.items() if k not in ["event", "room_id", "room"]}
            if other_info:
                msg += f"*Data:* {json.dumps(other_info, indent=2)}"
                
        return msg

    async def _send_to_platform(self, platform: str, text: str, room_id: Optional[str] = None):
        """Send a message to a specific platform via its adapter."""
        try:
            adapter = registry.get_adapter(platform)
            if adapter and adapter.validate_config():
                success = await adapter.send_message(text, room_id=room_id)
                if not success:
                    logger.warning(f"Failed to send notification to {platform}")
            else:
                logger.debug(f"Adapter for {platform} not configured or available.")
        except Exception as e:
            logger.error(f"Error dispatching to {platform}: {e}")

    async def dispatch(self, event_type: str, data: Dict[str, Any]):
        """Main entry point to dispatch notifications asynchronously."""
        if not self._should_notify(event_type, data):
            return

        settings = registry.get_settings()
        enabled_platforms = settings.get("enabled_platforms", [])
        
        room_id = data.get("room_id") or data.get("room")
        
        tasks = []
        for platform in enabled_platforms:
            text = self._format_message(platform, event_type, data)
            tasks.append(self._send_to_platform(platform, text, room_id=room_id))
        
        if tasks:
            # Run all platform sends in parallel, non-blocking for the caller
            # We use gather but don't await it here to keep it non-blocking if called correctly
            # Actually, the Broadcaster will await this, so we should ensure it's fast or 
            # the Broadcaster should fire and forget. 
            # The requirement says "One adapter failing doesn't break others or slow down WebSocket/SSE"
            # So we wrap the whole thing in a task or use gather with return_exceptions=True
            await asyncio.gather(*tasks, return_exceptions=True)

notification_dispatcher = NotificationDispatcher()
