import asyncio
import logging
from typing import Dict, Any, Optional
from .chat_adapters.registry import registry

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    NOTIFY_EVENTS = {
        "room_message",
        "room_created",
        "room_updated",
        "room_removed",
        "plans_updated",
        "reaction_toggled",
        "comment_published",
    }

    def _should_notify(self, event_type: str, data: Dict[str, Any]) -> bool:
        if event_type in self.NOTIFY_EVENTS:
            return True
        if data.get("level") in ["error", "critical", "escalation"]:
            return True
        return False

    async def _send_to_platform(self, platform: str, event_type: str, data: Dict[str, Any], room_id: Optional[str] = None):
        try:
            adapter = registry.get_adapter(platform)
            if adapter and adapter.validate_config():
                text = adapter.format_notification(event_type, data)
                success = await adapter.send_message(text, room_id=room_id)
                if not success:
                    logger.warning(f"Failed to send notification to {platform}")
            else:
                logger.debug(f"Adapter for {platform} not configured or available.")
        except Exception as e:
            logger.error(f"Error dispatching to {platform}: {e}")

    async def dispatch(self, event_type: str, data: Dict[str, Any]):
        if not self._should_notify(event_type, data):
            return

        settings = registry.get_settings()
        enabled_platforms = settings.get("enabled_platforms", [])

        room = data.get("room")
        room_id = data.get("room_id") or (room.get("room_id") if isinstance(room, dict) else None)

        tasks = []
        for platform in enabled_platforms:
            tasks.append(self._send_to_platform(platform, event_type, data, room_id=room_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


notification_dispatcher = NotificationDispatcher()
