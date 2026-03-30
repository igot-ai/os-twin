"""
MCP Extension Management API Routes.

Provides endpoints to install, list, remove, and sync MCP server extensions.
Delegates to mcp-extension.sh for actual operations.
"""

import json
import subprocess
import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

from dashboard.api_utils import AGENTS_DIR, PROJECT_ROOT
from dashboard.auth import get_current_user

# Try to import vault and config_resolver from .agents/mcp
import sys
import os
MCP_MODULE_PATH = str(AGENTS_DIR / "mcp")
if MCP_MODULE_PATH not in sys.path:
    sys.path.append(MCP_MODULE_PATH)

try:
    from vault import get_vault
    from config_resolver import ConfigResolver
except ImportError:
    # Fallback if not in the right environment
    get_vault = None
    ConfigResolver = None

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

MCP_DIR = AGENTS_DIR / "mcp"
EXTENSIONS_FILE = MCP_DIR / "extensions.json"
CATALOG_FILE = MCP_DIR / "mcp-catalog.json"
BUILTIN_CONFIG_FILE = MCP_DIR / "mcp-builtin.json"
HOME_CONFIG_FILE = Path.home() / ".ostwin" / "mcp" / "mcp-config.json"
SCRIPT = MCP_DIR / "mcp-extension.sh"


class InstallRequest(BaseModel):
    """Request body for installing an MCP extension."""
    repo: Optional[str] = None   # Git URL (alternative to name)
    name: Optional[str] = None   # Package name from catalog, or override name for git URL
    branch: Optional[str] = None # Git branch


class McpServerConfig(BaseModel):
    name: str
    type: str # 'stdio' or 'http'
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    httpUrl: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    store_in_vault: bool = False


class CredentialUpdate(BaseModel):
    value: str


def _read_json(path: Path) -> dict:
    """Read a JSON file, return empty dict if missing."""
    if not path.exists():
        return {}
    return json.loads(path.read_text())


async def _run_script(args: list[str], timeout: int = 120) -> dict:
    """Run mcp-extension.sh with given args and return stdout/stderr/code."""
    cmd = ["bash", str(SCRIPT)] + args
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
        return {
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "returncode": process.returncode,
        }
    except asyncio.TimeoutError:
        process.kill()
        return {
            "stdout": "",
            "stderr": "Command timed out",
            "returncode": -1,
        }


@router.get("/extensions")
async def list_extensions(user: dict = Depends(get_current_user)):
    """List all installed MCP extensions."""
    data = _read_json(EXTENSIONS_FILE)
    return {
        "extensions": data.get("extensions", []),
        "count": len(data.get("extensions", [])),
    }


def _mask_sensitive_config(config: dict) -> dict:
    """Return a copy of the MCP server config with env/header values masked."""
    import copy
    safe = copy.deepcopy(config)
    for section in ("env", "headers"):
        if section in safe and isinstance(safe[section], dict):
            for k, v in safe[section].items():
                if isinstance(v, str) and not v.startswith("${"):
                    # Plaintext value — mask it
                    safe[section][k] = v[:4] + "****" if len(v) > 4 else "****"
    return safe


@router.get("/servers")
async def list_mcp_servers(user: dict = Depends(get_current_user)):
    """List all MCP servers from builtin and home config with credential status."""
    builtin = _read_json(BUILTIN_CONFIG_FILE).get("mcpServers", {})
    home = _read_json(HOME_CONFIG_FILE).get("mcpServers", {})

    merged = {}
    merged.update(builtin)
    merged.update(home)

    resolver = ConfigResolver() if ConfigResolver else None
    vault = get_vault() if get_vault else None

    servers = []
    for name, config in merged.items():
        is_builtin = name in builtin
        server_type = "http" if "httpUrl" in config else "stdio"
        
        # Check credential status
        credential_status = "ok" # Default if no vault refs
        missing_keys = []
        if resolver:
            refs = resolver.extract_vault_refs(config)
            for s, k in refs:
                if vault and vault.get(s, k) is None:
                    missing_keys.append(f"{s}/{k}")
            
            if missing_keys:
                credential_status = "missing"

        servers.append({
            "name": name,
            "type": server_type,
            "status": "active", # Placeholder status
            "credential_status": credential_status,
            "missing_keys": missing_keys,
            "builtin": is_builtin,
            "config": _mask_sensitive_config(config)
        })

    return {"servers": servers}


@router.post("/servers")
async def add_mcp_server(server: McpServerConfig, user: dict = Depends(get_current_user)):
    """Add a new MCP server to home config."""
    data = _read_json(HOME_CONFIG_FILE)
    if "mcpServers" not in data:
        data["mcpServers"] = {}

    config = {}
    vault = get_vault() if get_vault else None

    def process_dict(d: Dict[str, str], prefix: str):
        processed = {}
        for k, v in d.items():
            if server.store_in_vault and vault:
                # Store in vault as {server_name}/{prefix}_{k}
                vault_key = f"{prefix}_{k}" if prefix else k
                vault.set(server.name, vault_key, v)
                processed[k] = f"${{vault:{server.name}/{vault_key}}}"
            else:
                processed[k] = v
        return processed

    if server.type == "http":
        config["httpUrl"] = server.httpUrl
        if server.headers:
            config["headers"] = process_dict(server.headers, "HEADER")
    else:
        config["command"] = server.command
        if server.args:
            config["args"] = server.args
        if server.env:
            config["env"] = process_dict(server.env, "")

    data["mcpServers"][server.name] = config
    
    # Ensure directory exists
    HOME_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    HOME_CONFIG_FILE.write_text(json.dumps(data, indent=2))

    return {"status": "success", "name": server.name}


@router.delete("/servers/{name}")
async def remove_mcp_server(name: str, user: dict = Depends(get_current_user)):
    """Remove an MCP server from home config."""
    data = _read_json(HOME_CONFIG_FILE)
    if "mcpServers" in data and name in data["mcpServers"]:
        del data["mcpServers"][name]
        HOME_CONFIG_FILE.write_text(json.dumps(data, indent=2))
        return {"status": "success"}
    
    raise HTTPException(status_code=404, detail=f"Server {name} not found in home config")


@router.post("/servers/{name}/test")
async def test_mcp_server(name: str, user: dict = Depends(get_current_user)):
    """Test connectivity to an MCP server by performing protocol handshake."""
    builtin = _read_json(BUILTIN_CONFIG_FILE).get("mcpServers", {})
    home = _read_json(HOME_CONFIG_FILE).get("mcpServers", {})
    config = home.get(name) or builtin.get(name)

    if not config:
        raise HTTPException(status_code=404, detail=f"Server {name} not found")

    resolver = ConfigResolver() if ConfigResolver else None
    if resolver:
        try:
            config = resolver.resolve_config(config)
        except Exception as e:
            return {"status": "error", "message": f"Config resolution failed: {e}"}

    async def _test_session(session: ClientSession) -> dict:
        """Initialize session, list tools, and return structured result."""
        init_result = await asyncio.wait_for(session.initialize(), timeout=10)
        server_info = getattr(init_result, "serverInfo", None) or {}
        server_name = getattr(server_info, "name", "unknown") if server_info else "unknown"
        server_version = getattr(server_info, "version", "unknown") if server_info else "unknown"

        # Fetch available tools
        tools_result = await asyncio.wait_for(session.list_tools(), timeout=10)
        tools_list = getattr(tools_result, "tools", []) if tools_result else []
        tool_summaries = [
            {"name": getattr(t, "name", str(t)), "description": getattr(t, "description", "")}
            for t in tools_list
        ]

        return {
            "status": "success",
            "message": f"Connected — {len(tool_summaries)} tools available",
            "server_name": server_name,
            "server_version": server_version,
            "tools_count": len(tool_summaries),
            "tools": tool_summaries,
        }

    try:
        if "httpUrl" in config:
            url = config["httpUrl"]
            headers = config.get("headers", {})
            async with sse_client(url, headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    return await _test_session(session)
        else:
            command = config.get("command", "")
            if command.startswith("${AGENT_DIR}"):
                command = command.replace("${AGENT_DIR}", str(AGENTS_DIR))
            
            # Split multi-word command strings (e.g. "npx -y @modelcontextprotocol/server-github")
            # into executable + extra args, then prepend extra args to config args.
            import shlex
            import shutil
            parts = shlex.split(command)
            executable = parts[0] if parts else command
            extra_args = parts[1:] if len(parts) > 1 else []
            
            # Resolve executable via PATH
            full_command = shutil.which(executable) or executable
            
            server_params = StdioServerParameters(
                command=full_command,
                args=extra_args + config.get("args", []),
                env={**os.environ, **config.get("env", {})}
            )
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    return await _test_session(session)
                    
    except asyncio.TimeoutError:
        return {"status": "error", "message": "Connection timed out after 10 seconds"}
    except Exception as e:
        return {"status": "error", "message": f"Connection failed: {str(e)}"}


@router.get("/servers/{name}/credentials")
async def list_server_credentials(name: str, user: dict = Depends(get_current_user)):
    """List credential key names for a server."""
    builtin = _read_json(BUILTIN_CONFIG_FILE).get("mcpServers", {})
    home = _read_json(HOME_CONFIG_FILE).get("mcpServers", {})
    config = home.get(name) or builtin.get(name)

    if not config:
        raise HTTPException(status_code=404, detail=f"Server {name} not found")

    resolver = ConfigResolver() if ConfigResolver else None
    if not resolver:
        return {"keys": []}

    refs = resolver.extract_vault_refs(config)
    # Filter refs that belong to this server (in vault terms)
    # The vault ref format is ${vault:vault_server_name/key}
    # Often vault_server_name matches name, but not always.
    
    keys = []
    for s, k in refs:
        keys.append({"vault_server": s, "key": k})

    return {"credentials": keys}


@router.put("/servers/{name}/credentials/{key:path}")
async def set_server_credential(
    name: str, 
    key: str, 
    update: CredentialUpdate, 
    user: dict = Depends(get_current_user)
):
    """Set a credential value in the vault."""
    vault = get_vault() if get_vault else None
    if not vault:
        raise HTTPException(status_code=500, detail="Vault not available")

    # If key contains /, split it into vault_server and actual key
    if "/" in key:
        vault_server, vault_key = key.split("/", 1)
    else:
        vault_server = name
        vault_key = key

    vault.set(vault_server, vault_key, update.value)
    return {"status": "success"}


@router.delete("/servers/{name}/credentials/{key:path}")
async def delete_server_credential(
    name: str, 
    key: str, 
    user: dict = Depends(get_current_user)
):
    """Delete a credential from the vault."""
    vault = get_vault() if get_vault else None
    if not vault:
        raise HTTPException(status_code=500, detail="Vault not available")

    # If key contains /, split it into vault_server and actual key
    if "/" in key:
        vault_server, vault_key = key.split("/", 1)
    else:
        vault_server = name
        vault_key = key

    vault.delete(vault_server, vault_key)
    return {"status": "success"}


@router.get("/catalog")
async def get_catalog(user: dict = Depends(get_current_user)):
    """Get the predefined MCP extension catalog."""
    data = _read_json(CATALOG_FILE)
    installed = _read_json(EXTENSIONS_FILE)
    installed_names = {e["name"] for e in installed.get("extensions", [])}

    packages = []
    for name, spec in data.get("packages", {}).items():
        packages.append({
            "name": name,
            "description": spec.get("description", ""),
            "repo": spec.get("repo", ""),
            "build_type": spec.get("build_type", ""),
            "branch": spec.get("branch", "main"),
            "installed": name in installed_names,
        })

    return {
        "catalog_version": data.get("catalog_version", ""),
        "packages": packages,
        "count": len(packages),
    }


@router.post("/extensions/install")
async def install_extension(req: InstallRequest, user: dict = Depends(get_current_user)):
    """Install an MCP extension by name (from catalog) or git URL."""
    if not SCRIPT.exists():
        raise HTTPException(status_code=500, detail="mcp-extension.sh not found")

    args = ["install"]

    if req.repo:
        # Git URL mode
        args.append(req.repo)
        if req.name:
            args.extend(["--name", req.name])
    elif req.name:
        # Catalog name mode
        args.append(req.name)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'name' (catalog) or 'repo' (git URL)",
        )

    if req.branch:
        args.extend(["--branch", req.branch])

    result = await _run_script(args, timeout=300)

    if result["returncode"] != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Installation failed",
                "stdout": result["stdout"],
                "stderr": result["stderr"],
            },
        )

    # Return updated extensions list
    data = _read_json(EXTENSIONS_FILE)
    return {
        "status": "installed",
        "output": result["stdout"],
        "extensions": data.get("extensions", []),
    }


@router.delete("/extensions/{name}")
async def remove_extension(name: str, user: dict = Depends(get_current_user)):
    """Remove an installed MCP extension."""
    if not SCRIPT.exists():
        raise HTTPException(status_code=500, detail="mcp-extension.sh not found")

    result = await _run_script(["remove", name])

    if result["returncode"] != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Failed to remove '{name}'",
                "stdout": result["stdout"],
                "stderr": result["stderr"],
            },
        )

    return {"status": "removed", "name": name, "output": result["stdout"]}


@router.post("/extensions/sync")
async def sync_config(user: dict = Depends(get_current_user)):
    """Force rebuild mcp-config.json from builtin + installed extensions."""
    if not SCRIPT.exists():
        raise HTTPException(status_code=500, detail="mcp-extension.sh not found")

    result = await _run_script(["sync"])

    # Merge builtin + home config to return the current state
    builtin = _read_json(BUILTIN_CONFIG_FILE).get("mcpServers", {})
    home = _read_json(HOME_CONFIG_FILE).get("mcpServers", {})
    merged = {"mcpServers": {**builtin, **home}}
    return {
        "status": "synced",
        "output": result["stdout"],
        "config": merged,
    }


@router.get("/config")
async def get_mcp_config(user: dict = Depends(get_current_user)):
    """Get the current merged mcp-config.json (builtin + home)."""
    builtin = _read_json(BUILTIN_CONFIG_FILE).get("mcpServers", {})
    home = _read_json(HOME_CONFIG_FILE).get("mcpServers", {})
    return {"mcpServers": {**builtin, **home}}
