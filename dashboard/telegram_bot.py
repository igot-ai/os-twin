import httpx
import json
import logging
from pathlib import Path
from typing import Any, Dict
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config file in local dashboard directory (original behavior)
CONFIG_FILE = Path(__file__).parent / "telegram_config.json"

# Fallback to absolute paths if module context is tricky
try:
    from .chat_adapters.telegram import TelegramAdapter
except (ImportError, ValueError):
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from chat_adapters.telegram import TelegramAdapter

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
    """Send a text message using the TelegramAdapter for consistency."""
    config = get_config()
    adapter = TelegramAdapter(config)
    return await adapter.send_message(text)

