#!/usr/bin/env python3
"""
MCP Server: War-Room Channel Tools

Exposes channel read/write operations as MCP tools so that
Engineer and QA agents can post messages and read the channel
directly without shelling out to bash scripts.

Protocol: JSON-RPC 2.0 over stdio (MCP standard)
"""

import json
import sys
import os
from datetime import datetime, timezone

AGENT_OS_ROOT = os.environ.get("AGENT_OS_ROOT", ".")


def post_message(room_dir: str, from_role: str, to_role: str,
                 msg_type: str, ref: str, body: str) -> dict:
    """Post a message to a war-room channel."""
    channel_file = os.path.join(room_dir, "channel.jsonl")
    os.makedirs(room_dir, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    msg_id = f"{from_role}-{msg_type}-{int(datetime.now().timestamp())}-{os.getpid()}"

    msg = {
        "id": msg_id,
        "ts": ts,
        "from": from_role,
        "to": to_role,
        "type": msg_type,
        "ref": ref,
        "body": body,
    }

    # Use file locking for concurrent safety
    import fcntl
    with open(channel_file, "a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.write(json.dumps(msg) + "\n")
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return {"message_id": msg_id, "status": "posted"}


def read_messages(room_dir: str, msg_type: str = None,
                  from_role: str = None, to_role: str = None,
                  ref: str = None, last_n: int = None) -> list:
    """Read messages from a war-room channel with optional filters."""
    channel_file = os.path.join(room_dir, "channel.jsonl")

    if not os.path.exists(channel_file):
        return []

    messages = []
    with open(channel_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            if msg_type and msg.get("type") != msg_type:
                continue
            if from_role and msg.get("from") != from_role:
                continue
            if to_role and msg.get("to") != to_role:
                continue
            if ref and msg.get("ref") != ref:
                continue
            messages.append(msg)

    if last_n:
        messages = messages[-last_n:]

    return messages


def get_latest(room_dir: str, msg_type: str) -> dict:
    """Get the most recent message of a given type."""
    messages = read_messages(room_dir, msg_type=msg_type, last_n=1)
    return messages[0] if messages else None


# === MCP Server Protocol ===

TOOLS = [
    {
        "name": "post_message",
        "description": "Post a message to the war-room channel",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_dir": {"type": "string", "description": "Path to the war-room directory"},
                "from_role": {"type": "string", "description": "Sender role (manager/engineer/qa)"},
                "to_role": {"type": "string", "description": "Recipient role"},
                "msg_type": {"type": "string", "description": "Message type (task/done/review/pass/fail/fix/signoff)"},
                "ref": {"type": "string", "description": "Task reference (e.g., TASK-001)"},
                "body": {"type": "string", "description": "Message body"},
            },
            "required": ["room_dir", "from_role", "to_role", "msg_type", "ref", "body"],
        },
    },
    {
        "name": "read_messages",
        "description": "Read messages from the war-room channel with optional filters",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_dir": {"type": "string", "description": "Path to the war-room directory"},
                "msg_type": {"type": "string", "description": "Filter by message type"},
                "from_role": {"type": "string", "description": "Filter by sender"},
                "to_role": {"type": "string", "description": "Filter by recipient"},
                "ref": {"type": "string", "description": "Filter by task reference"},
                "last_n": {"type": "integer", "description": "Return only the last N messages"},
            },
            "required": ["room_dir"],
        },
    },
    {
        "name": "get_latest",
        "description": "Get the most recent message of a given type from the channel",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_dir": {"type": "string", "description": "Path to the war-room directory"},
                "msg_type": {"type": "string", "description": "Message type to find"},
            },
            "required": ["room_dir", "msg_type"],
        },
    },
]


def handle_request(request: dict) -> dict:
    """Handle a JSON-RPC 2.0 request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "agent-os-channel",
                    "version": "0.1.0",
                },
            },
        }

    if method == "notifications/initialized":
        return None  # No response for notifications

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        try:
            if tool_name == "post_message":
                result = post_message(**args)
            elif tool_name == "read_messages":
                result = read_messages(**args)
            elif tool_name == "get_latest":
                result = get_latest(**args)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def main():
    """Main loop: read JSON-RPC requests from stdin, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
