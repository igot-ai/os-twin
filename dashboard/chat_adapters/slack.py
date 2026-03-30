import httpx
import logging
import re
from typing import Any, Dict, Optional
from .base import BaseChatAdapter

logger = logging.getLogger(__name__)

class SlackAdapter(BaseChatAdapter):
    """Adapter for sending/receiving messages via Slack."""

    async def send_message(self, text: str, room_id: Optional[str] = None) -> bool:
        webhook_url = self.config.get("webhook_url")
        # Check if we have a proper Slack token for chat.postMessage
        bot_token = self.config.get("bot_token")
        channel_id = self.config.get("channel_id")
        
        if bot_token and channel_id:
            url = "https://slack.com/api/chat.postMessage"
            headers = {"Authorization": f"Bearer {bot_token}"}
            payload = {"channel": channel_id, "text": text}
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    if result.get("ok"):
                        if room_id:
                            ts = result.get("ts")
                            if ts:
                                from dashboard.api_utils import save_thread_mapping, save_last_active_room
                                save_thread_mapping("slack", ts, room_id)
                                save_last_active_room(f"slack:{channel_id}", room_id)
                        logger.info("Slack message sent successfully via API.")
                        return True
                    else:
                        logger.error(f"Slack API error: {result.get('error')}")
                        # Fallback to webhook if configured
            except Exception as e:
                logger.error(f"Failed to send Slack message via API: {e}")

        if not webhook_url:
            logger.warning("Slack webhook URL is not configured.")
            return False
            
        payload = {"text": text}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
                logger.info("Slack message sent successfully via Webhook.")
                return True
        except Exception as e:
            logger.error(f"Failed to send Slack message via Webhook: {e}")
            return False

    async def handle_webhook(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None, raw_body: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
        """Process inbound Slack events (mentions, thread replies)."""
        # Signature verification
        signing_secret = self.config.get("signing_secret")
        if signing_secret and headers and raw_body:
            import hmac
            import hashlib
            timestamp = headers.get("x-slack-request-timestamp")
            signature = headers.get("x-slack-signature")
            if timestamp and signature:
                sig_basestring = f"v0:{timestamp}:{raw_body.decode('utf-8')}"
                my_signature = "v0=" + hmac.new(
                    signing_secret.encode("utf-8"),
                    sig_basestring.encode("utf-8"),
                    hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(my_signature, signature):
                    logger.warning("Slack signature verification failed.")
                    return None
            else:
                logger.warning("Slack signature or timestamp header missing.")
                return None
        elif signing_secret:
            logger.warning("Slack signing secret configured but headers or body missing.")
            return None

        # URL verification for Slack Events API
        if payload.get("type") == "url_verification":
            return {"challenge": payload.get("challenge")}
            
        event = payload.get("event", {})
        if not event:
            return None
            
        # Ignore bot messages to avoid loops
        if event.get("bot_id"):
            return None
            
        # 0. Check for @mention or AI ask
        if event.get("type") == "app_mention":
            from dashboard.agent_bridge import ask_agent
            text = event.get("text", "")
            # Remove @bot_id from text
            clean_text = re.sub(r"<@U[A-Z0-9]+>", "", text).strip()
            
            async def respond():
                answer = await ask_agent(clean_text, platform="slack")
                await self.send_message(answer)
            import asyncio
            asyncio.create_task(respond())
            return {"status": "ai_ask_triggered"}

        text = event.get("text", "")
        thread_ts = event.get("thread_ts")
        room_id = None
        
        # 1. Resolve room from thread if possible
        if thread_ts:
            from dashboard.api_utils import get_room_id_from_thread
            room_id = get_room_id_from_thread("slack", thread_ts)
            
        # 2. Resolve room from message text (explicit targeting)
        if not room_id:
            m = re.search(r"(room-\d+)", text)
            if m:
                room_id = m.group(1)
                
        # 3. Fallback to last active room for this channel
        if not room_id:
            channel_id = event.get("channel")
            if channel_id:
                from dashboard.api_utils import get_last_active_room
                room_id = get_last_active_room(f"slack:{channel_id}")
                
        if room_id:
            # Save this as last active for the channel
            channel_id = event.get("channel")
            if channel_id:
                from dashboard.api_utils import save_last_active_room
                save_last_active_room(f"slack:{channel_id}", room_id)
                
            # Clean up text (remove mention and room ID)
            body = re.sub(r"<@.*?>", "", text).strip()
            body = body.replace(room_id, "").strip()
            # If body is empty but it was a mention, maybe the user just pinged it
            if not body:
                return None
                
            from_user = event.get("user") or "slack_user"
            return {
                "room_id": room_id,
                "message": {
                    "body": body,
                    "from": f"slack:{from_user}",
                    "to": "manager",
                    "type": "human-directive"
                }
            }
        return None

    def validate_config(self) -> bool:
        has_webhook = bool(self.config.get("webhook_url"))
        has_bot = bool(self.config.get("bot_token") and self.config.get("channel_id"))
        return has_webhook or has_bot
