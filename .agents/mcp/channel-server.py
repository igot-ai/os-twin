#!/usr/bin/env python3
"""
Agent OS — MCP Channel Server

Exposes war-room channel operations as MCP tools.
Engineers and QA agents call these tools to post messages
and read the JSONL channel without shelling out to bash.

Usage (via mcp-config.json):
    python3 .agents/mcp/channel-server.py

Environment:
    AGENT_OS_ROOT  Root of the agent-os repo (default: ".")
"""

import fcntl
import json
import os
import time
import pathlib
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

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

# ── Validation constants ─────────────────────────────────────────────────────

VALID_ROLES = {
    "manager",
    "engineer",
    "qa",
    "architect",
    "devops",
    "tech-writer",
    "security",
    "product-owner",
}

MAX_BODY_BYTES = 65536

# ── Module-level state ────────────────────────────────────────────────────────


def _find_project_root() -> str:
    """Find project root from env vars, falling back to CWD."""
    for var in ("AGENT_OS_ROOT", "AGENT_OS_PROJECT_DIR"):
        val = os.environ.get(var, "")
        if val and os.path.isabs(val) and os.path.isdir(val):
            return val
    return os.getcwd()


AGENT_OS_ROOT: str = _find_project_root()


def _resolve_room_dir(room_dir: str) -> str:
    """Resolve room_dir relative to AGENT_OS_ROOT if not absolute."""
    if os.path.isabs(room_dir):
        return room_dir
    return os.path.join(AGENT_OS_ROOT, room_dir)


mcp = FastMCP("ostwin-channel", log_level="CRITICAL")

# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool()
def post_message(
    room_dir: Annotated[
        str,
        Field(
            description="Absolute or relative path to the war-room directory (e.g. .agents/war-rooms/room-001)"
        ),
    ],
    from_role: Annotated[
        str, Field(description="Sender role: manager | engineer | qa | architect")
    ],
    to_role: Annotated[
        str, Field(description="Recipient role: manager | engineer | qa | architect")
    ],
    msg_type: Annotated[
        str,
        Field(
            description="Message type: task | done | review | pass | fail | fix | error | signoff"
        ),
    ],
    ref: Annotated[str, Field(description="Task reference, e.g. TASK-001")],
    body: Annotated[str, Field(description="Message body text")],
) -> str:
    """Post a message to the war-room channel.

    Appends a JSON message to {room_dir}/channel.jsonl using an exclusive
    file lock (fcntl.LOCK_EX) so concurrent writers cannot corrupt the log.
    Returns a confirmation string with the generated message ID.
    """
    # Enforce body size limit
    if len(body) > MAX_BODY_BYTES:
        body = (
            body[:MAX_BODY_BYTES]
            + f"\n[TRUNCATED: original {len(body)} bytes, max {MAX_BODY_BYTES}]"
        )

    room_dir = _resolve_room_dir(room_dir)
    os.makedirs(room_dir, exist_ok=True)
    channel_file = os.path.join(room_dir, "channel.jsonl")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Nanosecond precision — matches .agents/channel/post.sh which uses date +%s%N
    msg_id = f"{from_role}-{msg_type}-{time.time_ns()}-{os.getpid()}"

    msg = {
        "v": 1,
        "id": msg_id,
        "ts": ts,
        "from": from_role,
        "to": to_role,
        "type": msg_type,
        "ref": ref,
        "body": body,
    }

    with open(channel_file, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(msg) + "\n")
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return f"posted:{msg_id}"


@mcp.tool()
def read_messages(
    room_dir: Annotated[
        str, Field(description="Absolute or relative path to the war-room directory")
    ],
    msg_type: Annotated[
        Optional[str],
        Field(
            description="Filter by message type (task/done/review/pass/fail/fix/error/signoff). Omit for all types."
        ),
    ] = None,
    from_role: Annotated[
        Optional[str],
        Field(description="Filter by sender role. Omit for all senders."),
    ] = None,
    to_role: Annotated[
        Optional[str],
        Field(description="Filter by recipient role. Omit for all recipients."),
    ] = None,
    ref: Annotated[
        Optional[str],
        Field(
            description="Filter by task reference (e.g. TASK-001). Omit for all refs."
        ),
    ] = None,
    last_n: Annotated[
        Optional[int],
        Field(
            description="Return only the last N messages. Omit for all messages.", ge=1
        ),
    ] = None,
) -> str:
    """Read messages from the war-room channel with optional filters.

    Reads {room_dir}/channel.jsonl and returns a JSON array string of
    matching messages. All filter parameters are optional and combinable.
    Returns an empty JSON array ("[]") if the channel file does not exist.
    """
    room_dir = _resolve_room_dir(room_dir)
    channel_file = os.path.join(room_dir, "channel.jsonl")

    if not os.path.exists(channel_file):
        return "[]"

    messages = []
    with open(channel_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # skip corrupted lines gracefully
            if msg_type is not None and msg.get("type") != msg_type:
                continue
            if from_role is not None and msg.get("from") != from_role:
                continue
            if to_role is not None and msg.get("to") != to_role:
                continue
            if ref is not None and msg.get("ref") != ref:
                continue
            messages.append(msg)

    # Use `is not None` — not `if last_n:` — so last_n=1 is handled correctly
    if last_n is not None:
        messages = messages[-last_n:]

    return json.dumps(messages)


@mcp.tool()
def get_latest(
    room_dir: Annotated[
        str, Field(description="Absolute or relative path to the war-room directory")
    ],
    msg_type: Annotated[
        str,
        Field(
            description="Message type to search for (task/done/review/pass/fail/fix/error/signoff)"
        ),
    ],
) -> str:
    """Get the most recent message of a given type from the war-room channel.

    Reads {room_dir}/channel.jsonl linearly, keeping the last match.
    Returns the message as a JSON string, or the string "null" if no
    message of that type exists or the file does not exist.
    """
    room_dir = _resolve_room_dir(room_dir)
    channel_file = os.path.join(room_dir, "channel.jsonl")

    if not os.path.exists(channel_file):
        return "null"

    latest = None
    with open(channel_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == msg_type:
                latest = msg

    return json.dumps(latest)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
