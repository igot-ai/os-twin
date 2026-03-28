"""
Telegram Integration Module for Ostwin Dashboard
"""

import httpx
import json
import logging
import secrets
import os
from pathlib import Path
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = Path(__file__).parent / "telegram_config.json"
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

def get_config():
    # Load .env file first
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
        
    default_config = {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""), # Legacy support
        "authorized_chats": [],
        "pairing_code": secrets.token_hex(4)
    }
    
    # If we got chat_id from env, add it to authorized chats
    if default_config["chat_id"]:
        default_config["authorized_chats"].append(str(default_config["chat_id"]))
    
    if not CONFIG_FILE.exists():
        save_raw_config(default_config)
        return default_config
        
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            
        # Priority 1: Environment variables override file config for tokens/ids
        env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        env_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        needs_save = False
        
        # Override bot token if present in env
        if env_token and config.get("bot_token") != env_token:
            config["bot_token"] = env_token
            needs_save = True
            
        # Migration from old format & handle env chat_id
        if "authorized_chats" not in config:
            config["authorized_chats"] = []
            needs_save = True
            
        # Add legacy chat_id to authorized list if missing
        if config.get("chat_id") and config.get("chat_id") != "test_chat" and str(config["chat_id"]) not in config["authorized_chats"]:
            config["authorized_chats"].append(str(config["chat_id"]))
            needs_save = True
            
        # Add env chat_id to authorized list if missing
        if env_chat_id and str(env_chat_id) not in config["authorized_chats"]:
            config["authorized_chats"].append(str(env_chat_id))
            # Also update the base chat_id to match env
            config["chat_id"] = env_chat_id
            needs_save = True
            
        if "pairing_code" not in config:
            config["pairing_code"] = secrets.token_hex(4)
            needs_save = True
            
        if needs_save:
            save_raw_config(config)
            
        return config
    except Exception as e:
        logger.error(f"Failed to read config: {e}")
        return default_config

def save_raw_config(config: dict):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Failed to save raw config: {e}")
        return False

def save_config(bot_token: str, chat_id: str):
    config = get_config()
    config["bot_token"] = bot_token
    config["chat_id"] = chat_id
    if chat_id and chat_id != "test_chat" and str(chat_id) not in config["authorized_chats"]:
        config["authorized_chats"].append(str(chat_id))
    return save_raw_config(config)

def authorize_chat(chat_id: str) -> bool:
    config = get_config()
    chat_id_str = str(chat_id)
    if chat_id_str not in config["authorized_chats"]:
        config["authorized_chats"].append(chat_id_str)
        return save_raw_config(config)
    return True

async def send_message(text: str, specific_chat_id: str = None) -> bool:
    """Send a text message to the configured Telegram chat."""
    config = get_config()
    bot_token = config.get("bot_token")
    
    # Send to specific chat or the first authorized chat (or legacy chat_id)
    chat_id = specific_chat_id
    if not chat_id:
        if config.get("authorized_chats"):
            chat_id = config["authorized_chats"][0]
        else:
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
