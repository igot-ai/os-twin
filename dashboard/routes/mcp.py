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
from typing import Optional

from dashboard.api_utils import AGENTS_DIR
from dashboard.auth import get_current_user

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

MCP_DIR = AGENTS_DIR / "mcp"
EXTENSIONS_FILE = MCP_DIR / "extensions.json"
CATALOG_FILE = MCP_DIR / "mcp-catalog.json"
CONFIG_FILE = MCP_DIR / "mcp-config.json"
SCRIPT = MCP_DIR / "mcp-extension.sh"


class InstallRequest(BaseModel):
    """Request body for installing an MCP extension."""
    repo: Optional[str] = None   # Git URL (alternative to name)
    name: Optional[str] = None   # Package name from catalog, or override name for git URL
    branch: Optional[str] = None # Git branch


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

    config = _read_json(CONFIG_FILE)
    return {
        "status": "synced",
        "output": result["stdout"],
        "config": config,
    }


@router.get("/config")
async def get_mcp_config(user: dict = Depends(get_current_user)):
    """Get the current merged mcp-config.json."""
    config = _read_json(CONFIG_FILE)
    return config
