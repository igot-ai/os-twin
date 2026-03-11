#!/usr/bin/env python3
"""
MCP Server: War-Room State Tools

Exposes war-room state management as MCP tools so that
agents can read their task, update status, and report progress.

Protocol: JSON-RPC 2.0 over stdio (MCP standard)
"""

import json
import sys
import os
from datetime import datetime, timezone

AGENT_OS_ROOT = os.environ.get("AGENT_OS_ROOT", ".")


def get_task(room_dir: str) -> dict:
    """Read the current task assignment for this war-room."""
    task_file = os.path.join(room_dir, "task.md")
    if not os.path.exists(task_file):
        return {"error": "No task file found"}

    with open(task_file, "r") as f:
        content = f.read()

    # Also read latest task/fix message from channel
    channel_file = os.path.join(room_dir, "channel.jsonl")
    latest_instruction = None
    if os.path.exists(channel_file):
        with open(channel_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                msg = json.loads(line)
                if msg.get("type") in ("task", "fix"):
                    latest_instruction = msg

    return {
        "task_description": content,
        "latest_instruction": latest_instruction,
        "room_dir": room_dir,
    }


def update_status(room_dir: str, status: str) -> dict:
    """Update the war-room status."""
    valid_statuses = [
        "pending", "engineering", "qa-review",
        "fixing", "passed", "failed-final",
    ]
    if status not in valid_statuses:
        return {"error": f"Invalid status: {status}. Must be one of: {valid_statuses}"}

    status_file = os.path.join(room_dir, "status")
    with open(status_file, "w") as f:
        f.write(status)

    return {"status": status, "updated": True}


def list_artifacts(room_dir: str) -> dict:
    """List all artifacts in the war-room."""
    artifacts_dir = os.path.join(room_dir, "artifacts")
    if not os.path.exists(artifacts_dir):
        return {"artifacts": []}

    artifacts = []
    for root, _dirs, files in os.walk(artifacts_dir):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, artifacts_dir)
            stat = os.stat(full_path)
            artifacts.append({
                "path": rel_path,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })

    return {"artifacts": artifacts, "count": len(artifacts)}


def report_progress(room_dir: str, percent: int, message: str) -> dict:
    """Report progress for the current task."""
    progress_file = os.path.join(room_dir, "progress.json")

    progress = {
        "percent": max(0, min(100, percent)),
        "message": message,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    with open(progress_file, "w") as f:
        json.dump(progress, f, indent=2)

    return progress


# === MCP Server Protocol ===

TOOLS = [
    {
        "name": "get_task",
        "description": "Read the current task assignment for this war-room",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_dir": {"type": "string", "description": "Path to the war-room directory"},
            },
            "required": ["room_dir"],
        },
    },
    {
        "name": "update_status",
        "description": "Update the war-room status",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_dir": {"type": "string", "description": "Path to the war-room directory"},
                "status": {"type": "string", "description": "New status (pending/engineering/qa-review/fixing/passed/failed-final)"},
            },
            "required": ["room_dir", "status"],
        },
    },
    {
        "name": "list_artifacts",
        "description": "List all artifacts in the war-room",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_dir": {"type": "string", "description": "Path to the war-room directory"},
            },
            "required": ["room_dir"],
        },
    },
    {
        "name": "report_progress",
        "description": "Report progress for the current task",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_dir": {"type": "string", "description": "Path to the war-room directory"},
                "percent": {"type": "integer", "description": "Progress percentage (0-100)"},
                "message": {"type": "string", "description": "Progress message"},
            },
            "required": ["room_dir", "percent", "message"],
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
                    "name": "agent-os-warroom",
                    "version": "0.1.0",
                },
            },
        }

    if method == "notifications/initialized":
        return None

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
            if tool_name == "get_task":
                result = get_task(**args)
            elif tool_name == "update_status":
                result = update_status(**args)
            elif tool_name == "list_artifacts":
                result = list_artifacts(**args)
            elif tool_name == "report_progress":
                result = report_progress(**args)
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
