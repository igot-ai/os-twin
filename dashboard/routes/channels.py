import json
import logging
import secrets
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends
from dashboard.auth import get_current_user
import dashboard.global_state as global_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/channels", tags=["channels"])

CHANNELS_CONFIG_PATH = Path.home() / ".ostwin" / "channels.json"


def _notify_bot_restart() -> None:
    """Schedule a debounced bot restart after channel config changes."""
    if global_state.bot_manager is not None:
        logger.info("[CHANNELS] Config changed — scheduling bot restart")
        global_state.bot_manager.schedule_restart()
    else:
        logger.debug("[CHANNELS] No bot_manager — skipping restart signal")

class NotificationPreferences(BaseModel):
    events: List[str] = Field(default_factory=list)
    enabled: bool = True

class ConnectorConfig(BaseModel):
    platform: str
    enabled: bool = False
    credentials: Dict[str, str] = Field(default_factory=dict)
    settings: Dict[str, Any] = Field(default_factory=dict)
    authorized_users: List[str] = Field(default_factory=list)
    pairing_code: str = ""
    notification_preferences: NotificationPreferences = Field(default_factory=NotificationPreferences)

class ChannelStatus(BaseModel):
    platform: str
    status: str # 'connected' | 'disconnected' | 'connecting' | 'error' | 'needs_setup' | 'not_configured'
    config: Optional[ConnectorConfig] = None
    health: Optional[Dict[str, Any]] = None

class SetupStep(BaseModel):
    title: str
    description: str
    instructions: str

# Helper to read config
def read_channels_config() -> List[ConnectorConfig]:
    if not CHANNELS_CONFIG_PATH.exists():
        return []
    try:
        with open(CHANNELS_CONFIG_PATH, "r") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            return [ConnectorConfig(**item) for item in data]
    except Exception as e:
        print(f"Error reading channels config: {e}")
        return []

# Helper to save config
def save_channels_config(configs: List[ConnectorConfig]):
    CHANNELS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHANNELS_CONFIG_PATH, "w") as f:
        json.dump([c.model_dump() for c in configs], f, indent=2)

def _mask_credentials(config: Optional[ConnectorConfig]) -> Optional[ConnectorConfig]:
    """Mask credential values in config to prevent secret exposure."""
    if config is None:
        return None
    
    masked_creds = {}
    for key, value in config.credentials.items():
        if value:
            masked_creds[key] = "***"
        else:
            masked_creds[key] = ""
    
    masked_config = ConnectorConfig(
        platform=config.platform,
        enabled=config.enabled,
        credentials=masked_creds,
        settings=config.settings,
        authorized_users=config.authorized_users,
        pairing_code=config.pairing_code,
        notification_preferences=config.notification_preferences,
    )
    return masked_config


@router.get("", response_model=List[ChannelStatus])
async def list_channels(user: dict = Depends(get_current_user)):
    configs = read_channels_config()
    platforms = ["telegram", "discord", "slack"]
    result = []
    config_map = {c.platform: c for c in configs}
    
    for p in platforms:
        config = config_map.get(p)
        status = "not_configured"
        
        if config:
            if config.enabled:
                status = "connected"
            elif not config.credentials:
                status = "needs_setup"
            else:
                status = "disconnected"
            
        result.append(ChannelStatus(
            platform=p,
            status=status,
            config=_mask_credentials(config)
        ))
    return result

@router.get("/{platform}", response_model=ChannelStatus)
async def get_channel(platform: str, user: dict = Depends(get_current_user)):
    configs = read_channels_config()
    config = next((c for c in configs if c.platform == platform), None)
    
    status = "not_configured"
    if config:
        if config.enabled:
            status = "connected"
        elif not config.credentials:
            status = "needs_setup"
        else:
            status = "disconnected"
            
    return ChannelStatus(
        platform=platform,
        status=status,
        config=_mask_credentials(config)
    )

@router.post("/{platform}/connect")
async def connect_channel(platform: str, config_update: Optional[Dict[str, Any]] = None, user: dict = Depends(get_current_user)):
    configs = read_channels_config()
    config = next((c for c in configs if c.platform == platform), None)
    
    if not config:
        config = ConnectorConfig(platform=platform)
        configs.append(config)
    
    if config_update:
        if "credentials" in config_update:
            config.credentials.update(config_update["credentials"])
        if "settings" in config_update:
            config.settings.update(config_update["settings"])
            
    config.enabled = True
    if not config.pairing_code:
        config.pairing_code = secrets.token_hex(4)
        
    # ── Discord: extract webhook_url from credentials into settings ──
    # The frontend SetupWizard sends credentials.token as the bot token
    # and credentials.webhook_url as the Discord webhook URL.
    if platform == "discord":
        wh = config.credentials.pop("webhook_url", None)
        if wh:
            config.settings["webhook_url"] = wh
        # Also accept webhook_url directly in settings update
        if config_update and "settings" in config_update:
            settings_wh = config_update["settings"].get("webhook_url")
            if settings_wh:
                config.settings["webhook_url"] = settings_wh

    # ── Slack: extract webhook_url from credentials into settings ──
    if platform == "slack":
        wh = config.credentials.pop("webhook_url", None)
        if wh:
            config.settings["webhook_url"] = wh
        if config_update and "settings" in config_update:
            settings_wh = config_update["settings"].get("webhook_url")
            if settings_wh:
                config.settings["webhook_url"] = settings_wh

    save_channels_config(configs)
    _notify_bot_restart()
    return {"status": "ok", "message": f"{platform} connector enabled"}

@router.post("/{platform}/disconnect")
async def disconnect_channel(platform: str, user: dict = Depends(get_current_user)):
    configs = read_channels_config()
    config = next((c for c in configs if c.platform == platform), None)
    
    if config:
        config.enabled = False
        save_channels_config(configs)
        _notify_bot_restart()
        return {"status": "ok", "message": f"{platform} connector disabled"}
    
    raise HTTPException(status_code=404, detail="Channel not found")

class ChannelSanityResult(BaseModel):
    platform: str
    enabled: bool
    has_credentials: bool
    notification_enabled: bool
    bot_available: bool
    bot_running: bool
    status: str
    issues: List[str] = Field(default_factory=list)


def _check_channel_credentials(platform: str, config: Optional[ConnectorConfig]) -> bool:
    """Check if required credentials are present for a platform.
    
    For Discord and Slack, a webhook URL in settings is also sufficient
    for outbound notifications (even without full bot credentials).
    """
    if not config:
        return False
    
    # Check settings-based webhook config (sufficient for outbound notifications)
    if platform in ("discord", "slack"):
        settings = config.settings or {}
        credentials = config.credentials or {}
        has_webhook = bool(settings.get("webhook_url") or credentials.get("webhook_url"))
        if has_webhook:
            return True
    
    if not config.credentials:
        return False
    
    required_keys = {
        "telegram": ["token"],
        "discord": ["token"],
        "slack": ["app_token", "bot_token"],
    }
    
    if platform not in required_keys:
        logger.warning(f"Unknown platform '{platform}' - cannot verify credentials")
        return False
    
    platform_keys = required_keys[platform]
    return all(config.credentials.get(k) for k in platform_keys)


@router.post("/{platform}/test", response_model=ChannelSanityResult)
async def test_channel(platform: str, user: dict = Depends(get_current_user)):
    """Perform real sanity checks for a notification channel connector.
    
    Checks:
    - Channel enabled in config
    - Required credentials present (never exposed)
    - notification_preferences.enabled
    - Bot manager available/running (for platforms needing bot process)
    - For Discord/Slack: actually sends a test message via webhook
    
    Returns structured sanity result without exposing secret values.
    """
    issues: List[str] = []
    
    configs = read_channels_config()
    config = next((c for c in configs if c.platform == platform), None)
    
    enabled = config.enabled if config else False
    has_credentials = _check_channel_credentials(platform, config)
    notification_enabled = config.notification_preferences.enabled if config else False
    
    bot_available = global_state.bot_manager is not None
    bot_running = global_state.bot_manager.is_running if bot_available else False
    
    if not config:
        status = "not_configured"
        issues.append("Channel not configured")
    elif not enabled:
        status = "disabled"
        issues.append("Channel is disabled")
    elif not has_credentials:
        status = "missing_credentials"
        issues.append("Required credentials not configured")
    elif not notification_enabled:
        status = "notifications_disabled"
        issues.append("Notification preferences are disabled")
    elif not bot_available:
        status = "bot_unavailable"
        issues.append("Bot manager not initialized")
    elif not bot_running:
        status = "bot_not_running"
        issues.append("Bot process not running")
    else:
        status = "healthy"
    
    # ── Live webhook test for Discord/Slack ──
    # These platforms can send a test message via webhook even without
    # the bot process running, so check independently.
    if platform in ("discord", "slack") and config and enabled:
        settings = config.settings or {}
        credentials = config.credentials or {}
        webhook_url = settings.get("webhook_url") or credentials.get("webhook_url")
        if not webhook_url:
            if status == "healthy":
                status = "missing_webhook"
            issues.append("Webhook URL not configured — notifications will not be delivered")
        else:
            # Actually send a test notification
            test_msg = "✅ OS-Twin test notification — channel is working!"
            try:
                if platform == "discord":
                    from dashboard.notify import send_discord_notification
                    ok = await send_discord_notification(test_msg, webhook_url)
                else:
                    from dashboard.notify import send_slack_notification
                    ok = await send_slack_notification(test_msg, webhook_url)
                if not ok and status == "healthy":
                    status = "webhook_failed"
                    issues.append("Webhook test message failed to deliver")
            except Exception as exc:
                if status == "healthy":
                    status = "webhook_error"
                issues.append(f"Webhook test error: {exc}")
    
    return ChannelSanityResult(
        platform=platform,
        enabled=enabled,
        has_credentials=has_credentials,
        notification_enabled=notification_enabled,
        bot_available=bot_available,
        bot_running=bot_running,
        status=status,
        issues=issues,
    )

@router.put("/{platform}/settings")
async def update_settings(platform: str, settings: Dict[str, Any], user: dict = Depends(get_current_user)):
    configs = read_channels_config()
    config = next((c for c in configs if c.platform == platform), None)
    
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    if "notification_preferences" in settings:
        prefs = settings["notification_preferences"]
        config.notification_preferences.events = prefs.get("events", config.notification_preferences.events)
        config.notification_preferences.enabled = prefs.get("enabled", config.notification_preferences.enabled)
        
    if "authorized_users" in settings:
        config.authorized_users = settings["authorized_users"]
        
    if "settings" in settings:
        config.settings.update(settings["settings"])
        
    save_channels_config(configs)
    _notify_bot_restart()
    return {"status": "ok", "config": config}

@router.get("/{platform}/pairing")
async def get_pairing(platform: str, user: dict = Depends(get_current_user)):
    configs = read_channels_config()
    config = next((c for c in configs if c.platform == platform), None)
    
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    return {"pairing_code": config.pairing_code}

@router.post("/{platform}/pairing/regenerate")
async def regenerate_pairing(platform: str, user: dict = Depends(get_current_user)):
    configs = read_channels_config()
    config = next((c for c in configs if c.platform == platform), None)
    
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    config.pairing_code = secrets.token_hex(4)
    save_channels_config(configs)
    return {"pairing_code": config.pairing_code}

@router.get("/{platform}/setup", response_model=List[SetupStep])
async def get_setup(platform: str, user: dict = Depends(get_current_user)):
    setup_data = {
        "telegram": [
            SetupStep(
                title="Create a Bot",
                description="Talk to [@BotFather](https://t.me/BotFather) on Telegram to create a new bot.",
                instructions="1. Send /newbot to [@BotFather](https://t.me/BotFather)\n2. Follow the prompts to name your bot\n3. Copy the Bot Token provided."
            ),
            SetupStep(
                title="Configure Token",
                description="Paste the bot token into the field below.",
                instructions="The token looks like: 123456:ABC-DEF1234ghIkl-zyx57W2v..."
            )
        ],
        "discord": [
            SetupStep(
                title="Create Application",
                description="Go to [Discord Developer Portal](https://discord.com/developers/applications).",
                instructions="1. Create a New Application.\n2. Go to Bot section and reset/copy the Bot Token.\n3. Copy the Client ID from General Information.\n4. Enable Message Content Intent under Bot settings."
            ),
            SetupStep(
                title="Add to Server",
                description="Generate an invite link and get your Server ID.",
                instructions="1. Go to OAuth2 → URL Generator.\n2. Select 'bot' and 'Administrator' (or specific perms).\n3. Use the link to add bot to your server.\n4. Right-click your server name → Copy Server ID."
            )
        ],
        "slack": [
            SetupStep(
                title="Create App & Enable Socket Mode",
                description="Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app.",
                instructions="1. Create New App → From Scratch.\n2. Go to Socket Mode and Enable it.\n3. Generate an App-Level Token (xapp-...) with connections:write scope.\n4. Copy the App-Level Token for the field below."
            ),
            SetupStep(
                title="Get Bot Token & Install",
                description="Configure bot permissions and install to your workspace.",
                instructions="1. Go to OAuth & Permissions.\n2. Add Bot Token Scopes: chat:write, commands, im:history.\n3. Install App to Workspace.\n4. Copy the Bot User OAuth Token (xoxb-...) for the field below."
            )
        ]
    }
    
    return setup_data.get(platform, [])
