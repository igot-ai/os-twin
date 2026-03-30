import httpx
import logging
from typing import Any, Dict, Optional
from .base import BaseChatAdapter

logger = logging.getLogger(__name__)

class DiscordAdapter(BaseChatAdapter):
    """Adapter for sending/receiving messages via Discord."""

    async def send_message(self, text: str, room_id: Optional[str] = None) -> bool:
        webhook_url = self.config.get("webhook_url")
        if not webhook_url:
            logger.warning("Discord webhook URL is not configured.")
            return False
            
        # Add ?wait=true to get the message response
        url = webhook_url
        if "?" in url:
            url += "&wait=true"
        else:
            url += "?wait=true"
            
        payload = {"content": text}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                if room_id:
                    result = response.json()
                    msg_id = result.get("id")
                    channel_id = result.get("channel_id")
                    if msg_id:
                        from dashboard.api_utils import save_thread_mapping, save_last_active_room
                        save_thread_mapping("discord", msg_id, room_id)
                        if channel_id:
                            save_last_active_room(f"discord:{channel_id}", room_id)
                
                logger.info("Discord message sent successfully.")
                return True
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            return False

    async def handle_webhook(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None, raw_body: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
        """Process inbound Discord interaction (slash commands)."""
        # Signature verification
        public_key_hex = self.config.get("public_key")
        if public_key_hex and headers and raw_body:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from cryptography.exceptions import InvalidSignature
            signature = headers.get("x-signature-ed25519")
            timestamp = headers.get("x-signature-timestamp")
            if signature and timestamp:
                try:
                    public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
                    message = timestamp.encode() + raw_body
                    public_key.verify(bytes.fromhex(signature), message)
                except (InvalidSignature, Exception) as e:
                    logger.warning(f"Discord signature verification failed: {e}")
                    return None
            else:
                logger.warning("Discord signature or timestamp header missing.")
                return None
        elif public_key_hex:
            logger.warning("Discord public key configured but headers or body missing.")
            return None

        # Interaction type 1 = Ping
        if payload.get("type") == 1:
            return {"type": 1}
            
        # Interaction type 2 = Application Command
        if payload.get("type") == 2:
            data = payload.get("data", {})
            if data.get("name") == "ostwin":
                options_list = data.get("options", [])
                options = {opt["name"]: opt["value"] for opt in options_list}
                
                command = options.get("command") or data.get("options", [{}])[0].get("name")
                
                if command == "ask":
                    question = options.get("question") or options.get("message")
                    if question:
                        from dashboard.agent_bridge import ask_agent
                        async def respond():
                            answer = await ask_agent(question, platform="discord")
                            await self.send_message(answer)
                        import asyncio
                        asyncio.create_task(respond())
                        return {
                            "type": 4, # CHANNEL_MESSAGE_WITH_SOURCE
                            "data": {
                                "content": "Thinking..."
                            }
                        }

                room_id = options.get("room")
                body = options.get("message")
                from_user = payload.get("member", {}).get("user", {}).get("username") or "discord_user"
                channel_id = payload.get("channel_id")
                
                if room_id and body:
                    # Save last active room for this channel
                    if channel_id:
                        from dashboard.api_utils import save_last_active_room
                        save_last_active_room(f"discord:{channel_id}", room_id)
                    return {
                        "room_id": room_id,
                        "message": {
                            "body": body,
                            "from": f"discord:{from_user}",
                            "to": "manager",
                            "type": "human-directive"
                        }
                    }
        
        # 3. Handle message events (if delivered to this webhook)
        # This covers thread replies to bot notifications
        message_id = payload.get("id")
        content = payload.get("content")
        author = payload.get("author", {})
        
        if content and author and not author.get("bot"):
            room_id = None
            # Resolve from message reference (reply)
            message_reference = payload.get("message_reference", {})
            referenced_msg_id = message_reference.get("message_id")
            if referenced_msg_id:
                from dashboard.api_utils import get_room_id_from_thread
                room_id = get_room_id_from_thread("discord", str(referenced_msg_id))
            
            # Fallback to last active room for this channel
            channel_id = payload.get("channel_id")
            if not room_id and channel_id:
                from dashboard.api_utils import get_last_active_room
                room_id = get_last_active_room(f"discord:{channel_id}")
            
            if room_id:
                # Save last active
                if channel_id:
                    from dashboard.api_utils import save_last_active_room
                    save_last_active_room(f"discord:{channel_id}", room_id)
                    
                return {
                    "room_id": room_id,
                    "message": {
                        "body": content,
                        "from": f"discord:{author.get('username', 'unknown')}",
                        "to": "manager",
                        "type": "human-directive"
                    }
                }
        
        return None

    def validate_config(self) -> bool:
        return bool(self.config.get("webhook_url"))
