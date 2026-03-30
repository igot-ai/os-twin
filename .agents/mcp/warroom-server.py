#!/usr/bin/env python3
"""
warroom-server.py — MCP server for OS Twin war-room operations.

Provides tools for agents to:
  - Update war-room status
  - List artifacts
  - Report progress

Transport: stdio (invoked via deepagents --mcp-config)
"""

import json
import os
import pathlib
from datetime import datetime, timezone
from typing import Annotated, get_args, Literal

# Monkey patch pathlib to bypass macOS SIP PermissionError on .env files
original_is_file = pathlib.Path.is_file
def safe_is_file(self):
    try:
        return original_is_file(self)
    except PermissionError:
        return False
pathlib.Path.is_file = safe_is_file

from pydantic import Field
from mcp.server.fastmcp import FastMCP

StatusType = Literal[
    "pending",
    "engineering",
    "qa-review",
    "fixing",
]

mcp = FastMCP("agent-os-warroom", log_level="CRITICAL")


@mcp.tool()
def update_status(
    room_dir: Annotated[str, Field(description="Absolute or relative path to the war-room directory")],
    status: Annotated[StatusType, Field(description="New status: pending | engineering | qa-review | fixing (terminal states like passed/failed-final are manager-only)")],
) -> str:
    """Update the war-room status file.

    Writes {status} to {room_dir}/status.
    Terminal states (passed, failed-final) are reserved for the manager —
    agents must NOT set them directly.
    Raises ValueError for an unrecognised or forbidden status string.
    Returns a confirmation string "status:{status}".
    """
    valid = get_args(StatusType)
    if status not in valid:
        raise ValueError(
            f"Invalid status {status!r}. Must be one of: {list(valid)}. "
            f"Terminal states (passed, failed-final) are manager-only."
        )

    os.makedirs(room_dir, exist_ok=True)
    status_file = os.path.join(room_dir, "status")

    # Read old status for audit
    old_status = "unknown"
    if os.path.exists(status_file):
        with open(status_file) as f:
            old_status = f.read().strip()

    # Write new status
    with open(status_file, "w") as f:
        f.write(status)

    # Write state_changed_at (epoch seconds)
    epoch = int(datetime.now(timezone.utc).timestamp())
    with open(os.path.join(room_dir, "state_changed_at"), "w") as f:
        f.write(str(epoch))

    # Append audit log
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(room_dir, "audit.log"), "a") as f:
        f.write(f"{ts} STATUS {old_status} -> {status}\n")

    return f"status:{status}"


@mcp.tool()
def list_artifacts(
    room_dir: Annotated[str, Field(description="Absolute or relative path to the war-room directory")],
) -> str:
    """List all artifacts produced in this war-room.

    Walks {room_dir}/artifacts/ and returns a JSON array of
    {path, size_bytes, modified} objects sorted by path.
    Returns an empty JSON array ("[]") if the artifacts directory
    does not exist.
    """
    artifacts_dir = os.path.join(room_dir, "artifacts")
    if not os.path.exists(artifacts_dir):
        return "[]"

    files = []
    for root, _dirs, fnames in os.walk(artifacts_dir):
        for fname in fnames:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, artifacts_dir)
            stat = os.stat(full_path)
            files.append({
                "path": rel_path,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })

    return json.dumps(sorted(files, key=lambda x: x["path"]))


@mcp.tool()
def report_progress(
    room_dir: Annotated[str, Field(description="Absolute or relative path to the war-room directory")],
    percent: Annotated[int, Field(description="Completion percentage (0–100)", ge=0, le=100)],
    message: Annotated[str, Field(description="Human-readable progress message")],
) -> str:
    """Write a progress snapshot to {room_dir}/progress.json.

    Clamps percent to [0, 100] even if the schema constraint is bypassed.
    Returns the written progress object as a JSON string.
    """
    os.makedirs(room_dir, exist_ok=True)
    progress_file = os.path.join(room_dir, "progress.json")

    progress = {
        "percent": max(0, min(100, percent)),
        "message": message,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    with open(progress_file, "w") as f:
        json.dump(progress, f, indent=2)

    return json.dumps(progress)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
