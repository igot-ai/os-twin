from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseChatAdapter(ABC):
    """Base class for all chat platform adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def send_message(self, text: str, room_id: Optional[str] = None) -> bool:
        """Send a message to the chat platform."""
        pass

    @abstractmethod
    async def handle_webhook(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None, raw_body: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
        """Process an inbound webhook payload.
        
        Returns a dictionary with room_id and message to be posted, or None if ignored.
        Expected return format: {"room_id": "room-001", "message": {"body": "...", "from": "...", ...}}
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Check if the current configuration is valid and complete."""
        pass
