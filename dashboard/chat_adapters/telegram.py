import httpx
import logging
import re
import asyncio
from typing import Any, Dict, Optional
from .base import BaseChatAdapter

logger = logging.getLogger(__name__)

class TelegramAdapter(BaseChatAdapter):
    """Adapter for sending/receiving messages to/from a Telegram chat."""

    async def send_message(self, text: str, room_id: Optional[str] = None) -> bool:
        bot_token = self.config.get("bot_token")
        chat_id = self.config.get("chat_id")
        
        if not bot_token or not chat_id:
            logger.warning("Telegram adapter not fully configured.")
            return False
            
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                # If we have a room_id and message response, we can map the thread/chat
                if room_id:
                    result = response.json().get("result", {})
                    # For Telegram, the message_id can be the thread indicator
                    msg_id = result.get("message_id")
                    if msg_id:
                        from dashboard.api_utils import save_thread_mapping, save_last_active_room
                        save_thread_mapping("telegram", str(msg_id), room_id)
                        save_last_active_room(f"telegram:{chat_id}", room_id)
                
                logger.info("Telegram message sent successfully.")
                return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def handle_webhook(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None, raw_body: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
        """Process inbound Telegram message."""
        # Verification using secret token if configured
        secret_token = self.config.get("secret_token")
        if secret_token and headers:
            if headers.get("x-telegram-bot-api-secret-token") != secret_token:
                logger.warning("Telegram secret token verification failed.")
                return None
        elif secret_token:
            logger.warning("Telegram secret token configured but headers missing.")
            return None

        message = payload.get("message")
        if not message or "text" not in message:
            return None
            
        text = message["text"]
        from_user = message.get("from", {}).get("username") or message.get("from", {}).get("first_name", "unknown")
        chat_id = message.get("chat", {}).get("id")
        room_id = None
        
        # 0. Check for @mention or AI ask
        bot_username = self.config.get("bot_username")
        is_private = message.get("chat", {}).get("type") == "private"
        is_mention = bot_username and f"@{bot_username}" in text
        
        if (is_mention or is_private) and not text.startswith("/room"):
            # AI Ask flow
            from dashboard.agent_bridge import ask_agent
            clean_text = text.replace(f"@{bot_username}", "").strip() if bot_username else text.strip()
            
            # Run AI synthesis in background to avoid webhook timeout if possible, 
            # but Telegram expects a 200 OK quickly.
            # For simplicity now, we'll do it inline but we should consider backgrounding.
            async def respond():
                answer = await ask_agent(clean_text, platform="telegram")
                await self.send_message(answer)
            
            asyncio.create_task(respond())
            return {"status": "ai_ask_triggered"}

        # 1. Resolve room from /room command: /room room-001 message content
        m = re.match(r"/room\s+(room-\d+)(?:\s+(.*))?", text, re.DOTALL)
        if m:
            room_id = m.group(1)
            body = m.group(2) or "Checking in"
        else:
            # 2. Resolve room from thread/reply
            reply_to_message = message.get("reply_to_message")
            if reply_to_message:
                thread_id = str(reply_to_message.get("message_id"))
                from dashboard.api_utils import get_room_id_from_thread
                room_id = get_room_id_from_thread("telegram", thread_id)
            
            # 3. Fallback to last active room for this chat
            if not room_id and chat_id:
                from dashboard.api_utils import get_last_active_room
                room_id = get_last_active_room(f"telegram:{chat_id}")
            
            body = text

        if room_id:
            # Save this as last active for the chat
            if chat_id:
                from dashboard.api_utils import save_last_active_room
                save_last_active_room(f"telegram:{chat_id}", room_id)

            return {
                "room_id": room_id,
                "message": {
                    "body": body,
                    "from": f"telegram:{from_user}",
                    "to": "manager",
                    "type": "human-directive"
                }
            }
        
        return None

    def validate_config(self) -> bool:
        return bool(self.config.get("bot_token") and self.config.get("chat_id"))
