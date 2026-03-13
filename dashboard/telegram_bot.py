"""
Telegram Integration Module for Ostwin Dashboard
"""

import httpx
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = Path(__file__).parent / "telegram_config.json"

def get_config():
    if not CONFIG_FILE.exists():
        return {"bot_token": "", "chat_id": ""}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read config: {e}")
        return {"bot_token": "", "chat_id": ""}

def save_config(bot_token: str, chat_id: str):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"bot_token": bot_token, "chat_id": chat_id}, f)
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False

async def send_message(text: str) -> bool:
    """Send a text message to the configured Telegram chat."""
    config = get_config()
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    
    if not bot_token or not chat_id:
        logger.warning("Telegram is not configured. Skipping message.")
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
            logger.info("Successfully sent message to Telegram")
            return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False
