"""
MCP Tool Call Logger — shared logging for all OS Twin MCP servers.

Intercepts every tool call and appends a JSONL record to
{room_dir}/mcp-tools.jsonl inside the war-room that the tool operates on.

Usage (call BEFORE defining tools):

    from mcp_log import install_tool_logging
    mcp = FastMCP("my-server", log_level="CRITICAL")
    install_tool_logging(mcp, "my-server")

    @mcp.tool()          # ← now automatically logged
    def my_tool(room_dir, ...):
        ...
"""

import fcntl
import functools
import inspect
import json
import os
import time
from datetime import datetime, timezone

# ── Configuration ────────────────────────────────────────────────────────────

_LOG_FILENAME = "mcp-tools.jsonl"
_MAX_RESULT_LEN = 4096  # truncate logged results to keep the file manageable


# ── Room directory resolution ────────────────────────────────────────────────

def _resolve_room_dir(kwargs: dict) -> str | None:
    """Extract the war-room directory from tool arguments.

    Checks for `room_dir` (warroom/channel tools) first, then resolves
    `room_id` (memory tools) via AGENT_OS_ROOT environment variable.
    Returns None if no room can be determined.
    """
    # warroom & channel tools pass room_dir directly
    room_dir = kwargs.get("room_dir")
    if room_dir:
        return room_dir

    # memory tools pass room_id (e.g. "room-001")
    room_id = kwargs.get("room_id")
    if room_id:
        root = os.environ.get("AGENT_OS_ROOT", ".")
        candidate = os.path.join(root, ".war-rooms", room_id)
        if os.path.isdir(candidate):
            return candidate

    return None


# ── Writer ───────────────────────────────────────────────────────────────────

def _write_log(room_dir: str, entry: dict) -> None:
    """Append a JSON line to {room_dir}/mcp-tools.jsonl (file-lock safe)."""
    os.makedirs(room_dir, exist_ok=True)
    log_path = os.path.join(room_dir, _LOG_FILENAME)
    line = json.dumps(entry, default=str) + "\n"
    try:
        with open(log_path, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass  # never crash the MCP server because of logging


# ── Decorator factory ────────────────────────────────────────────────────────

def _make_logging_wrapper(server_name: str, func):
    """Wrap a tool function to log calls and results."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tool_name = func.__name__
        resolved_kwargs = kwargs or _positional_to_dict(func, args)
        room_dir = _resolve_room_dir(resolved_kwargs)

        # No room context → skip logging (don't block the tool)
        if not room_dir:
            return func(*args, **kwargs)

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        t0 = time.monotonic()

        entry = {
            "ts": ts,
            "server": server_name,
            "tool": tool_name,
            "args": _safe_args(resolved_kwargs),
        }

        try:
            result = func(*args, **kwargs)
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            result_str = str(result)
            entry["result"] = (
                result_str[:_MAX_RESULT_LEN] + "…"
                if len(result_str) > _MAX_RESULT_LEN
                else result_str
            )
            entry["ok"] = True
            entry["elapsed_ms"] = elapsed_ms
            _write_log(room_dir, entry)
            return result
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["elapsed_ms"] = elapsed_ms
            _write_log(room_dir, entry)
            raise

    return wrapper


def _safe_args(d: dict) -> dict:
    """Sanitise argument dict for JSON serialisation."""
    out = {}
    for k, v in d.items():
        try:
            json.dumps(v)
            out[k] = v
        except (TypeError, ValueError):
            out[k] = repr(v)
    return out


def _positional_to_dict(func, args) -> dict:
    """Best-effort mapping of positional args to parameter names."""
    params = list(inspect.signature(func).parameters.keys())
    return {params[i]: a for i, a in enumerate(args) if i < len(params)}


# ── Public API ───────────────────────────────────────────────────────────────

def install_tool_logging(mcp_instance, server_name: str) -> None:
    """Monkey-patch *mcp_instance.tool* so every future @mcp.tool()
    automatically logs calls to {room_dir}/mcp-tools.jsonl.

    Must be called BEFORE the @mcp.tool() decorators are evaluated.
    """
    original_tool = mcp_instance.tool

    @functools.wraps(original_tool)
    def patched_tool(*dec_args, **dec_kwargs):
        decorator = original_tool(*dec_args, **dec_kwargs)

        @functools.wraps(decorator)
        def logging_decorator(func):
            wrapped = _make_logging_wrapper(server_name, func)
            return decorator(wrapped)

        return logging_decorator

    mcp_instance.tool = patched_tool
