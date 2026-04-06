import os
import json
import uuid
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from dashboard.api_utils import PROJECT_ROOT

# Add connectors package to sys.path
CONNECTORS_PATH = str(PROJECT_ROOT / "connectors" / "python" / "src")
if CONNECTORS_PATH not in sys.path:
    sys.path.append(CONNECTORS_PATH)

try:
    from connectors.registry import registry
    from connectors.models import ConnectorConfig
    from vault import get_vault
    from config_resolver import ConfigResolver
    
    # Dynamically import all connectors to register them
    import pkgutil
    import connectors
    def load_connectors():
        package_path = os.path.dirname(connectors.__file__)
        for _, name, is_pkg in pkgutil.iter_modules([package_path]):
            if not is_pkg and name not in ("base", "models", "registry", "utils", "client"):
                try:
                    __import__(f"connectors.{name}")
                except Exception as e:
                    print(f"Error loading connector {name}: {e}")
    
    load_connectors()
except ImportError:
    registry = None
    get_vault = None
    ConfigResolver = None

def get_connector_config_path() -> Path:
    override = os.environ.get("OSTWIN_CONNECTORS_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".ostwin" / "connectors.json"

def read_connector_configs() -> List[Dict[str, Any]]:
    path = get_connector_config_path()
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_connector_configs(configs: List[Dict[str, Any]]):
    path = get_connector_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(configs, f, indent=2)

def get_connector_instance(instance_id: str) -> Optional[Dict[str, Any]]:
    configs = read_connector_configs()
    return next((c for c in configs if c["id"] == instance_id), None)

async def resolve_connector_config(config: Dict[str, Any]) -> Dict[str, Any]:
    if not ConfigResolver or not get_vault:
        return config
    
    resolver = ConfigResolver()
    vault = get_vault()
    return await resolver.resolve(config, vault)
