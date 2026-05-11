"""
notify.py — Outbound notification config & messaging for Ostwin Dashboard.

Manages Telegram bot configuration (token, authorized chats, pairing),
Discord webhook, Slack webhook, and Lark webhook notifications.
Provides send_message() and notify_all_channels() for pushing
notifications to every configured connector.
"""

import json
import logging
import os
import secrets
from pathlib import Path
from typing import Any, Dict

import httpx
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = Path(__file__).parent / "notify_config.json"
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Channels config path (shared with the TS bot and channels route)
CHANNELS_CONFIG_PATH = Path.home() / ".ostwin" / "channels.json"

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
        with open(CONFIG_FILE) as f:
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
        legacy_chat = config.get("chat_id")
        if (
            legacy_chat
            and legacy_chat != "test_chat"
            and str(legacy_chat) not in config["authorized_chats"]
        ):
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

async def send_lark_message(message: str, title: str = "🚀 OS-Twin Notification") -> bool:
    """Send a rich-text message to the configured Lark (Feishu) webhook using Post format."""
    webhook_url = os.environ.get("LARK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("LARK_WEBHOOK_URL is not configured (os.environ). Skipping message.")
        return False

    # Process multi-line message into Lark Post segments
    lines = message.split("\n")
    content_segments = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Convert simple markdown **bold** to something cleaner for Lark text
        clean_line = stripped.replace("**", "").replace("`", "")
        content_segments.append([{"tag": "text", "text": clean_line}])

    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "en_us": {
                    "title": title,
                    "content": content_segments
                }
            }
        }
    }

    logger.info(f"Attempting to send Lark notification to {webhook_url[:30]}...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=15.0)
            if response.status_code != 200:
                logger.error(f"Lark API returned error {response.status_code}: {response.text}")
                return False
            logger.info("Successfully sent rich-text message to Lark")
            return True
    except httpx.ConnectError:
        logger.error("Failed to connect to Lark (DNS or Network issue)")
        return False
    except Exception as e:
        logger.error(f"Failed to send Lark message due to unexpected error: {e}")
        return False


# ── Discord Webhook ──────────────────────────────────────────────────────────

async def send_discord_notification(message: str, webhook_url: str) -> bool:
    """Send a plain-text message to a Discord channel via webhook URL.

    Discord webhook format: POST https://discord.com/api/webhooks/{id}/{token}
    Body: {"content": "<message>"}
    """
    if not webhook_url or not webhook_url.startswith("https://discord.com/api/webhooks/"):
        logger.warning("Discord webhook URL is missing or invalid. Skipping message.")
        return False

    # Strip markdown bold/codes that Discord doesn't render in plain webhook content
    clean_message = message.replace("**", "").replace("`", "")

    payload = {"content": clean_message}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=15.0)
            if response.status_code not in (200, 204):
                logger.error(f"Discord webhook returned error {response.status_code}: {response.text}")
                return False
            logger.info("Successfully sent message to Discord via webhook")
            return True
    except httpx.ConnectError:
        logger.error("Failed to connect to Discord (DNS or Network issue)")
        return False
    except Exception as e:
        logger.error(f"Failed to send Discord message: {e}")
        return False


# ── Slack Webhook ────────────────────────────────────────────────────────────

async def send_slack_notification(message: str, webhook_url: str) -> bool:
    """Send a plain-text message to a Slack channel via incoming webhook URL.

    Slack webhook format: POST https://hooks.slack.com/services/...
    Body: {"text": "<message>"}
    """
    if not webhook_url or not webhook_url.startswith("https://hooks.slack.com/"):
        logger.warning("Slack webhook URL is missing or invalid. Skipping message.")
        return False

    # Convert simple markdown **bold** -> *bold* for Slack mrkdwn, strip backticks
    clean_message = message.replace("**", "*").replace("`", "")

    payload = {"text": clean_message}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=15.0)
            if response.status_code not in (200, 204):
                logger.error(f"Slack webhook returned error {response.status_code}: {response.text}")
                return False
            logger.info("Successfully sent message to Slack via webhook")
            return True
    except httpx.ConnectError:
        logger.error("Failed to connect to Slack (DNS or Network issue)")
        return False
    except Exception as e:
        logger.error(f"Failed to send Slack message: {e}")
        return False


# ── Multi-channel dispatcher ─────────────────────────────────────────────────

def _read_channels_config() -> list[dict[str, Any]]:
    """Read channel connector configs from ~/.ostwin/channels.json."""
    if not CHANNELS_CONFIG_PATH.exists():
        return []
    try:
        with open(CHANNELS_CONFIG_PATH) as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            return data
    except Exception as e:
        logger.error(f"Failed to read channels config: {e}")
        return []


def _build_plan_message(event_type: str, data: dict) -> str:
    """Build a human-readable notification message from an event payload."""
    if event_type == "plan_completed":
        plan = data.get("plan", data)
        plan_id = plan.get("plan_id", "unknown")
        title = plan.get("title", plan_id)
        progress = data.get("progress", {})
        parts = [f"🏁 Plan Completed: {title}"]
        parts.append(f"Plan ID: {plan_id}")
        if progress:
            total = progress.get("total", 0)
            passed = progress.get("passed", 0)
            if total:
                parts.append(f"Progress: {passed}/{total} epics passed")
        return "\n".join(parts)

    # Generic fallback
    return json.dumps(data, default=str)[:1000]


async def notify_all_channels(event_type: str, data: dict) -> dict[str, bool]:
    """Send a notification to every configured connector (Telegram, Discord, Slack, Lark).

    Returns a dict mapping platform name -> success bool.
    Errors in one connector do NOT block others.
    """
    message = _build_plan_message(event_type, data)
    results: dict[str, bool] = {}
    configs = _read_channels_config()
    config_map = {c.get("platform"): c for c in configs if isinstance(c, dict)}

    # ── Telegram (Bot API) ────────────────────────────────────
    telegram_config = config_map.get("telegram")
    telegram_enabled = telegram_config and telegram_config.get("enabled", False)
    if telegram_enabled:
        try:
            ok = await send_message(message)
            results["telegram"] = ok
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
            results["telegram"] = False
    else:
        # Try legacy notify_config.json path
        notify_config = get_config()
        if notify_config.get("bot_token") and notify_config.get("authorized_chats"):
            try:
                ok = await send_message(message)
                results["telegram"] = ok
            except Exception as e:
                logger.error(f"Telegram notification (legacy) failed: {e}")
                results["telegram"] = False

    # ── Discord (webhook) ─────────────────────────────────────
    discord_config = config_map.get("discord")
    discord_enabled = discord_config and discord_config.get("enabled", False)
    if discord_enabled:
        # Look for webhook URL in settings, then credentials, then env
        settings = discord_config.get("settings", {})
        credentials = discord_config.get("credentials", {})
        webhook_url = (
            settings.get("webhook_url")
            or credentials.get("webhook_url")
            or os.environ.get("DISCORD_WEBHOOK_URL", "")
        )
        if webhook_url:
            try:
                ok = await send_discord_notification(message, webhook_url)
                results["discord"] = ok
            except Exception as e:
                logger.error(f"Discord notification failed: {e}")
                results["discord"] = False
        else:
            logger.info("Discord connector enabled but no webhook_url configured — skipping")
    else:
        # Fallback: check env var directly
        env_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
        if env_webhook:
            try:
                ok = await send_discord_notification(message, env_webhook)
                results["discord"] = ok
            except Exception as e:
                logger.error(f"Discord notification (env fallback) failed: {e}")
                results["discord"] = False

    # ── Slack (webhook) ───────────────────────────────────────
    slack_config = config_map.get("slack")
    slack_enabled = slack_config and slack_config.get("enabled", False)
    if slack_enabled:
        settings = slack_config.get("settings", {})
        credentials = slack_config.get("credentials", {})
        webhook_url = (
            settings.get("webhook_url")
            or credentials.get("webhook_url")
            or os.environ.get("SLACK_WEBHOOK_URL", "")
        )
        if webhook_url:
            try:
                ok = await send_slack_notification(message, webhook_url)
                results["slack"] = ok
            except Exception as e:
                logger.error(f"Slack notification failed: {e}")
                results["slack"] = False
        else:
            logger.info("Slack connector enabled but no webhook_url configured — skipping")
    else:
        env_webhook = os.environ.get("SLACK_WEBHOOK_URL")
        if env_webhook:
            try:
                ok = await send_slack_notification(message, env_webhook)
                results["slack"] = ok
            except Exception as e:
                logger.error(f"Slack notification (env fallback) failed: {e}")
                results["slack"] = False

    # ── Lark / Feishu (webhook) ───────────────────────────────
    lark_webhook = os.environ.get("LARK_WEBHOOK_URL")
    if lark_webhook:
        try:
            ok = await send_lark_message(message)
            results["lark"] = ok
        except Exception as e:
            logger.error(f"Lark notification failed: {e}")
            results["lark"] = False

    if results:
        logger.info("notify_all_channels results: %s", results)
    else:
        logger.info("No notification channels configured — nothing sent")

    return results



