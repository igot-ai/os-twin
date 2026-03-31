import json
import os
import secrets
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends
from dashboard.auth import get_current_user

router = APIRouter(prefix="/api/channels", tags=["channels"])

CHANNELS_CONFIG_PATH = Path.home() / ".ostwin" / "channels.json"

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
                # In a real app, we would check the bot's health or status
                status = "connected"
            elif not config.credentials:
                status = "needs_setup"
            else:
                status = "disconnected"
            
        result.append(ChannelStatus(
            platform=p,
            status=status,
            config=config
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
        config=config
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
        
    save_channels_config(configs)
    return {"status": "ok", "message": f"{platform} connector enabled"}

@router.post("/{platform}/disconnect")
async def disconnect_channel(platform: str, user: dict = Depends(get_current_user)):
    configs = read_channels_config()
    config = next((c for c in configs if c.platform == platform), None)
    
    if config:
        config.enabled = False
        save_channels_config(configs)
        return {"status": "ok", "message": f"{platform} connector disabled"}
    
    raise HTTPException(status_code=404, detail="Channel not found")

@router.post("/{platform}/test")
async def test_channel(platform: str, user: dict = Depends(get_current_user)):
    # In a real app, this would perform a real health check
    return {"status": "healthy", "message": f"Connection to {platform} is working (mocked)"}

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
                instructions="1. Send /newbot to [@BotFather](https://t.me/BotFather)\n2. Follow the prompts to name your bot\n3. Copy the API Token provided."
            ),
            SetupStep(
                title="Configure Token",
                description="Add your bot token to the configuration.",
                instructions="Paste the token into the 'token' field in credentials."
            )
        ],
        "discord": [
            SetupStep(
                title="Create Application",
                description="Go to [Discord Developer Portal](https://discord.com/developers/applications).",
                instructions="1. Create a New Application.\n2. Go to Bot section and reset/copy Token.\n3. Enable Message Content Intent."
            ),
            SetupStep(
                title="Add to Server",
                description="Generate invite link.",
                instructions="1. Go to OAuth2 -> URL Generator.\n2. Select 'bot' and 'Administrator' (or specific perms).\n3. Use the link to add bot to your server."
            )
        ],
        "slack": [
            SetupStep(
                title="Create App",
                description="Go to [api.slack.com](https://api.slack.com/apps).",
                instructions="1. Create New App -> From Scratch.\n2. Go to Socket Mode and Enable it.\n3. Generate an App-Level Token (xapp-...) with connections:write."
            ),
            SetupStep(
                title="Configure Bot Token",
                description="Get Bot User OAuth Token.",
                instructions="1. Go to OAuth & Permissions.\n2. Add scopes (chat:write, etc.).\n3. Install to Workspace and copy xoxb- token."
            )
        ]
    }
    
    return setup_data.get(platform, [])
