#!/usr/bin/env python3
"""
Agent OS — MCP Connector Server

Exposes OS Twin connector operations as MCP tools.
Agents call these tools to browse, configure, and fetch data
from Telegram, Discord, and Slack connectors.

Usage (via mcp-config.json):
    python3 .agents/mcp/connector-server.py

Environment:
    AGENT_OS_ROOT  Root of the agent-os repo (default: ".")
"""

import json
import os
import sys
import pathlib
import asyncio
from pathlib import Path
from typing import Annotated, Dict, Any, List, Optional
from pydantic import Field
from mcp.server.fastmcp import FastMCP

# ── Configuration ────────────────────────────────────────────────────────────

AGENT_OS_ROOT: str = os.environ.get("AGENT_OS_ROOT", ".")
PROJECT_ROOT = Path(AGENT_OS_ROOT).resolve()
CHANNELS_CONFIG_PATH = Path.home() / ".ostwin" / "channels.json"
CONNECTORS_CONFIG_PATH = Path.home() / ".ostwin" / "connectors.json"

# Add project root to sys.path for dashboard imports
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    from dashboard.connectors.registry import registry
    import dashboard.connectors  # auto-registers all connectors via __init__.py
    from dashboard.policies import PolicyEngine
    from vault import get_vault
    from config_resolver import ConfigResolver
    policy_engine = PolicyEngine()
    config_resolver = ConfigResolver()
except ImportError:
    registry = None
    policy_engine = None
    config_resolver = None

mcp = FastMCP("ostwin-connector", log_level="CRITICAL")

# ── Models ───────────────────────────────────────────────────────────────────

PLATFORMS = ["telegram", "discord", "slack"]

# ── Helpers ──────────────────────────────────────────────────────────────────

def read_channels_config() -> List[Dict[str, Any]]:
    """Read the channels config from ~/.ostwin/channels.json."""
    if not CHANNELS_CONFIG_PATH.exists():
        return []
    try:
        with open(CHANNELS_CONFIG_PATH, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_channels_config(configs: List[Dict[str, Any]]):
    """Save the channels config to ~/.ostwin/channels.json."""
    CHANNELS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHANNELS_CONFIG_PATH, "w") as f:
        json.dump(configs, f, indent=2)

def read_connectors_config() -> List[Dict[str, Any]]:
    """Read the connectors config from ~/.ostwin/connectors.json."""
    if not CONNECTORS_CONFIG_PATH.exists():
        return []
    try:
        with open(CONNECTORS_CONFIG_PATH, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_connectors_config(configs: List[Dict[str, Any]]):
    """Save the connectors config to ~/.ostwin/connectors.json."""
    CONNECTORS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONNECTORS_CONFIG_PATH, "w") as f:
        json.dump(configs, f, indent=2)

# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_connector_types() -> str:
    """List all available connector types and their metadata.
    
    Returns a JSON string containing the registry of available connectors.
    """
    if not registry:
        return json.dumps({"error": "Connector registry not available"}, indent=2)
    
    connectors_list = []
    for cid, ccls in registry.list_connectors().items():
        try:
            inst = ccls()
            conf = inst.config
            connectors_list.append({
                "id": conf.id,
                "name": conf.name,
                "description": conf.description,
                "version": conf.version,
                "icon": conf.icon
            })
        except Exception as e:
            connectors_list.append({"id": cid, "error": str(e)})
            
    return json.dumps(connectors_list, indent=2)

@mcp.tool()
def list_connector_instances() -> str:
    """List all configured connector instances.
    
    Includes both legacy messaging channels and registry-based connectors.
    """
    channels = read_channels_config()
    instances = read_connectors_config()
    
    # Label channels as 'messaging' and instances as 'data' or similar
    all_instances = []
    for c in channels:
        all_instances.append({
            "id": c.get("platform"),
            "type": "messaging",
            "name": c.get("platform").capitalize(),
            "enabled": c.get("enabled", False),
            "status": get_connector_status_raw(c.get("platform"), c)
        })
        
    for inst in instances:
        all_instances.append({
            "id": inst.get("id"),
            "connector_id": inst.get("connector_id"),
            "type": "registry",
            "name": inst.get("name"),
            "enabled": inst.get("enabled", True),
            "status": "configured" # Simplified for registry connectors
        })
        
    return json.dumps(all_instances, indent=2)

@mcp.tool()
async def configure_connector(
    platform: Annotated[str, Field(description="Platform or instance ID to configure: telegram | discord | slack | <instance-id>")],
    enabled: Annotated[Optional[bool], Field(description="Whether the connector is enabled")] = None,
    credentials: Annotated[Optional[Dict[str, str]], Field(description="Key-value pairs for credentials (e.g. token, api_key)")] = None,
    settings: Annotated[Optional[Dict[str, Any]], Field(description="Additional settings for the connector")] = None,
    name: Annotated[Optional[str], Field(description="Human-readable name for this instance (only for registry-based)")] = None,
    connector_id: Annotated[Optional[str], Field(description="The connector type ID (only when creating a new instance)")] = None,
) -> str:
    """Update or create a connector configuration.

    Supports both legacy messaging platforms (telegram, discord, slack) and 
    new registry-based connectors.
    
    If platform is one of the legacy platforms, it updates the global config for that platform.
    If platform is an existing instance ID, it updates that instance.
    If connector_id is provided, it creates a new instance.
    """
    # Legacy handling
    if platform in PLATFORMS:
        configs = read_channels_config()
        config_map = {c.get("platform"): c for c in configs}
        
        config = config_map.get(platform)
        if not config:
            config = {
                "platform": platform,
                "enabled": False,
                "credentials": {},
                "settings": {},
                "authorized_users": [],
                "pairing_code": "",
                "notification_preferences": {"events": [], "enabled": True}
            }
            configs.append(config)
        
        if enabled is not None:
            config["enabled"] = enabled
        if credentials is not None:
            config["credentials"].update(credentials)
        if settings is not None:
            config["settings"].update(settings)
        
        save_channels_config(configs)
        return f"updated:{platform}"

    # Registry-based handling
    instances = read_connectors_config()
    instance = next((inst for inst in instances if inst.get("id") == platform), None)
    
    if not instance and connector_id:
        # Create new instance
        if not registry or connector_id not in registry.list_connectors():
            return f"error: Connector type '{connector_id}' not found in registry"
            
        instance = {
            "id": platform if platform not in PLATFORMS else str(pathlib.Path("/dev/urandom").read_bytes(8).hex()),
            "connector_id": connector_id,
            "name": name or connector_id.capitalize(),
            "enabled": True,
            "config": {}
        }
        instances.append(instance)
    
    if not instance:
        return f"error: Instance '{platform}' not found and no connector_id provided to create it"
        
    if enabled is not None:
        instance["enabled"] = enabled
    if name is not None:
        instance["name"] = name
    if credentials:
        instance["config"].update(credentials)
    if settings:
        instance["config"].update(settings)
        
    # Optional: validate config if registry is available
    if registry and instance["connector_id"] in registry.list_connectors():
        try:
            ccls = registry.get_class(instance["connector_id"])
            inst = ccls()
            # Resolve config with vault references for validation
            resolved_config = config_resolver.resolve_config(instance["config"])
            await inst.validate_config(resolved_config)
        except Exception as e:
            return f"error: Failed to validate connector: {str(e)}"

    save_connectors_config(instances)
    return f"updated:{instance['id']}"

@mcp.tool()
def delete_connector_instance(
    instance_id: Annotated[str, Field(description="The ID of the instance to delete")]
) -> str:
    """Delete a connector instance configuration."""
    instances = read_connectors_config()
    new_instances = [inst for inst in instances if inst.get("id") != instance_id]
    
    if len(new_instances) == len(instances):
        return f"error: Instance '{instance_id}' not found"
        
    save_connectors_config(new_instances)
    return f"deleted:{instance_id}"

@mcp.tool()
def get_connector_status(
    platform: Annotated[str, Field(description="Platform or instance ID to check: telegram | discord | slack | <instance-id>")]
) -> str:
    """Check the real-time status of a connector.

    Returns a JSON string with the current status (connected, disconnected, error, etc.).
    """
    # Legacy check
    if platform in PLATFORMS:
        configs = read_channels_config()
        config = next((c for c in configs if c.get("platform") == platform), None)
        status = get_connector_status_raw(platform, config)
        return json.dumps({"platform": platform, "status": status}, indent=2)
        
    # Registry instance check
    instances = read_connectors_config()
    instance = next((inst for inst in instances if inst.get("id") == platform), None)
    if instance:
        return json.dumps({
            "id": instance["id"],
            "connector_id": instance["connector_id"],
            "name": instance["name"],
            "enabled": instance["enabled"],
            "status": "configured" # Basic status
        }, indent=2)
        
    return json.dumps({"error": f"Platform or instance '{platform}' not found"}, indent=2)

@mcp.tool()
def get_setup_instructions(
    platform: Annotated[str, Field(description="Platform or Connector ID: telegram | discord | slack | <connector-id>")]
) -> str:
    """Get step-by-step setup instructions for a connector.

    Returns a JSON string with setup steps or the connector configuration schema.
    """
    # Legacy instructions
    legacy_instructions = {
        "telegram": [
            {
                "title": "Create a Bot",
                "description": "Talk to @BotFather on Telegram to create a new bot.",
                "instructions": "1. Send /newbot to @BotFather\n2. Follow the prompts to name your bot\n3. Copy the API Token provided."
            },
            {
                "title": "Configure Token",
                "description": "Add your bot token to the configuration.",
                "instructions": "Use configure_connector with credentials={'token': 'YOUR_TOKEN'}."
            }
        ],
        "discord": [
            {
                "title": "Create Discord App",
                "description": "Create an application on Discord Developer Portal.",
                "instructions": "1. Go to https://discord.com/developers/applications\n2. Click 'New Application'\n3. Go to 'Bot' section and copy the Token.\n4. Go to 'General Information' and copy the Client ID."
            },
            {
                "title": "Configure Credentials",
                "description": "Add your token and client_id to the configuration.",
                "instructions": "Use configure_connector with credentials={'token': '...', 'client_id': '...'}"
            }
        ],
        "slack": [
            {
                "title": "Create Slack App",
                "description": "Create an app at api.slack.com/apps",
                "instructions": "1. Enable Socket Mode\n2. Add Slash Commands (/ostwin, /draft, etc.)\n3. Add Bot Token Scopes (chat:write, commands, im:history)\n4. Generate an App-Level Token with connections:write scope"
            },
            {
                "title": "Configure Tokens",
                "description": "Add your Bot Token and App-Level Token to the configuration.",
                "instructions": "Use configure_connector with credentials={'token': 'xoxb-...', 'appToken': 'xapp-...'}"
            }
        ]
    }
    
    if platform in legacy_instructions:
        return json.dumps(legacy_instructions[platform], indent=2)
        
    # Registry instructions (schema)
    if registry and platform in registry.list_connectors():
        try:
            ccls = registry.get_class(platform)
            inst = ccls()
            conf = inst.config
            
            steps = []
            if conf.auth_config.mode == "apiKey":
                steps.append({
                    "title": f"Get {conf.name} API Key",
                    "description": f"You need an API key from {conf.name} to connect.",
                    "instructions": conf.auth_config.placeholder or "Check documentation for how to get an API key."
                })
            
            for field in conf.config_fields:
                steps.append({
                    "title": field.title,
                    "description": field.description or f"Enter value for {field.id}",
                    "instructions": field.placeholder or ""
                })
                
            return json.dumps(steps, indent=2)
        except Exception as e:
            return f"error: {str(e)}"
            
    return "[]"

@mcp.tool()
async def list_documents(
    instance_id: Annotated[str, Field(description="The ID of the connector instance")],
    cursor: Annotated[Optional[str], Field(description="Pagination cursor")] = None
) -> str:
    """List documents from a configured connector instance.
    
    Returns a JSON string containing the documents and a next_cursor if available.
    """
    if not registry:
        return json.dumps({"error": "Registry not available"}, indent=2)
        
    instances = read_connectors_config()
    instance = next((inst for inst in instances if inst.get("id") == instance_id), None)
    if not instance:
        return json.dumps({"error": f"Instance '{instance_id}' not found"}, indent=2)
        
    try:
        ccls = registry.get_class(instance["connector_id"])
        inst = ccls()
        
        # Resolve config with vault references
        resolved_config = config_resolver.resolve_config(instance["config"])
        
        result = await inst.list_documents(resolved_config, cursor=cursor)
        return result.model_dump_json(by_alias=True, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)

@mcp.tool()
async def get_document(
    instance_id: Annotated[str, Field(description="The ID of the connector instance")],
    external_id: Annotated[str, Field(description="The external ID of the document to fetch")]
) -> str:
    """Fetch the full content of a specific document from a connector instance.
    
    Returns a JSON string containing the ExternalDocument.
    """
    if not registry:
        return json.dumps({"error": "Registry not available"}, indent=2)
        
    instances = read_connectors_config()
    instance = next((inst for inst in instances if inst.get("id") == instance_id), None)
    if not instance:
        return json.dumps({"error": f"Instance '{instance_id}' not found"}, indent=2)
        
    try:
        ccls = registry.get_class(instance["connector_id"])
        inst = ccls()
        
        # Resolve config with vault references
        resolved_config = config_resolver.resolve_config(instance["config"])
        
        result = await inst.get_document(external_id, resolved_config)
        return result.model_dump_json(by_alias=True, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)

@mcp.tool()
def list_policies() -> str:
    """List all registered policy components (fetchers, processors, reactors)."""
    if not policy_engine:
        return json.dumps({"error": "Policy engine not available"}, indent=2)
        
    return json.dumps({
        "fetchers": list(policy_engine.registered_fetchers.keys()),
        "processors": list(policy_engine.registered_processors.keys()),
        "reactors": list(policy_engine.registered_reactors.keys())
    }, indent=2)

@mcp.tool()
async def trigger_policy(
    workflow_name: Annotated[str, Field(description="Name of the workflow/policy to trigger")],
    params: Annotated[Dict[str, Any], Field(description="Parameters for the workflow (fetcher, processor, reactor and their params)")]
) -> str:
    """Trigger a policy workflow.
    
    Executes a workflow: Fetch -> Process -> React.
    """
    if not policy_engine:
        return "error: Policy engine not available"
        
    try:
        await policy_engine.execute_workflow(workflow_name, params)
        return f"triggered:{workflow_name}"
    except Exception as e:
        return f"error: {str(e)}"

# ── Helper implementations ───────────────────────────────────────────────────

def get_connector_status_raw(platform: str, config: Optional[Dict[str, Any]]) -> str:
    """Helper to determine connector status."""
    if not config:
        return "not_configured"
    
    # Check if bot process is running (simple check for server.pid)
    bot_running = False
    pid_file = Path(AGENT_OS_ROOT) / "server.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            # Check if PID exists on macOS/Linux
            os.kill(pid, 0)
            bot_running = True
        except (ValueError, ProcessLookupError, PermissionError):
            pass

    if config.get("enabled"):
        return "connected" if bot_running else "disconnected"
    elif not config.get("credentials"):
        return "needs_setup"
    else:
        return "disconnected"

if __name__ == "__main__":
    mcp.run()
