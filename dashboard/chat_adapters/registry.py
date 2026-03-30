import json
import logging
from pathlib import Path
from typing import Dict, Type, Optional, Any, List
from .base import BaseChatAdapter
from .telegram import TelegramAdapter
from .discord import DiscordAdapter
from .slack import SlackAdapter

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".ostwin" / "chat_adapters.json"

class AdapterRegistry:
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self._adapters: Dict[str, Type[BaseChatAdapter]] = {
            "telegram": TelegramAdapter,
            "discord": DiscordAdapter,
            "slack": SlackAdapter
        }
        self.configs: Dict[str, Dict[str, Any]] = self._load_configs()

    def _load_configs(self) -> Dict[str, Dict[str, Any]]:
        if not self.config_path.exists():
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            return {}
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load adapter configs: {e}")
            return {}

    def save_configs(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self.configs, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save adapter configs: {e}")

    def get_registered_platforms(self) -> List[str]:
        return list(self._adapters.keys())

    def get_adapter(self, platform: str) -> Optional[BaseChatAdapter]:
        if platform not in self._adapters:
            return None
        config = self.configs.get(platform, {})
        return self._adapters[platform](config)

    def get_settings(self) -> Dict[str, Any]:
        """Get global notification settings."""
        return self.configs.get("_settings", {
            "important_events": ["room_status_change", "error", "escalation", "alert", "done"],
            "enabled_platforms": ["telegram", "discord", "slack"]
        })

    def update_settings(self, settings: Dict[str, Any]):
        """Update global notification settings."""
        self.configs["_settings"] = settings
        self.save_configs()

    def update_config(self, platform: str, config: Dict[str, Any]):
        self.configs[platform] = config
        self.save_configs()

# Singleton instance
registry = AdapterRegistry()
