#!/usr/bin/env python3
"""
Agent OS — MCP War-Room Server

Exposes war-room state management as MCP tools.
Agents call these tools to read their task, update status,
list artifacts, and report progress without shelling out to bash.

Usage (via mcp-config.json):
    python3 .agents/mcp/warroom-server.py

Environment:
    AGENT_OS_ROOT  Root of the agent-os repo (default: ".")
"""

import json
import os
from datetime import datetime, timezone
from typing import Annotated, Literal, get_args

from pydantic import Field
from mcp.server.fastmcp import FastMCP

# ── Status type ───────────────────────────────────────────────────────────────
# Defined as a Literal so the SDK auto-generates an enum-constrained JSON
# Schema for calling agents, and get_args() drives runtime validation without
# duplicating the list.

StatusType = Literal[
    "pending",
    "engineering",
    "qa-review",
    "fixing",
    "passed",
    "failed-final",
]

# ── Module-level state ────────────────────────────────────────────────────────

AGENT_OS_ROOT: str = os.environ.get("AGENT_OS_ROOT", ".")

mcp = FastMCP("agent-os-warroom")

# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_task(
    room_dir: Annotated[str, Field(description="Absolute or relative path to the war-room directory (e.g. .agents/war-rooms/room-001)")],
) -> str:
    """Read the current task assignment for this war-room.

    Reads task.md and the latest task/fix message from channel.jsonl.
    Returns a JSON string with {task_description, latest_instruction, room_dir}.
    Raises RuntimeError if task.md does not exist.
    """
    task_file = os.path.join(room_dir, "task.md")
    if not os.path.exists(task_file):
        raise RuntimeError(f"No task file found in {room_dir!r}")

    with open(task_file, "r") as f:
        content = f.read()

    # Also read the latest task/fix message from channel
    channel_file = os.path.join(room_dir, "channel.jsonl")
    latest_instruction = None
    if os.path.exists(channel_file):
        with open(channel_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") in ("task", "fix"):
                    latest_instruction = msg

    result = {
        "task_description": content,
        "latest_instruction": latest_instruction,
        "room_dir": room_dir,
    }
    return json.dumps(result)


@mcp.tool()
def update_status(
    room_dir: Annotated[str, Field(description="Absolute or relative path to the war-room directory")],
    status: Annotated[StatusType, Field(description="New status: pending | engineering | qa-review | fixing | passed | failed-final")],
) -> str:
    """Update the war-room status file.

    Writes {status} to {room_dir}/status.
    Raises ValueError for an unrecognised status string.
    Returns a confirmation string "status:{status}".
    """
    valid = get_args(StatusType)
    if status not in valid:
        raise ValueError(f"Invalid status {status!r}. Must be one of: {list(valid)}")

    os.makedirs(room_dir, exist_ok=True)
    status_file = os.path.join(room_dir, "status")
    with open(status_file, "w") as f:
        f.write(status)

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
