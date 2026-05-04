#!/usr/bin/env python3
"""
MCP Stdio Proxy — intercepts tools/call JSON-RPC and logs to mcp-tools.jsonl.

Sits between the MCP client (deepagents) and the real MCP server, forwarding
all stdio traffic transparently while logging tool call requests and responses.

Usage:
    python mcp-proxy.py [--server-name NAME] -- <command> [args...]

Environment:
    AGENT_OS_ROOM_DIR   War-room directory for log output (optional; no logging if unset)
"""

import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

# ── Configuration ────────────────────────────────────────────────────────────

_LOG_FILENAME = "mcp-tools.jsonl"
_MAX_RESULT_LEN = 4096


# ── Argument parsing ────────────────────────────────────────────────────────

def parse_args(argv=None):
    """Parse CLI arguments: [--server-name NAME] -- command [args...]

    Returns (server_name, child_cmd_list).
    Raises SystemExit if '--' separator is missing.
    """
    if argv is None:
        argv = sys.argv[1:]

    server_name = None
    i = 0
    while i < len(argv):
        if argv[i] == "--":
            child_cmd = argv[i + 1:]
            if not child_cmd:
                print("mcp-proxy: no command after '--'", file=sys.stderr)
                sys.exit(1)
            if server_name is None:
                server_name = os.path.basename(child_cmd[0])
            return server_name, child_cmd
        elif argv[i] == "--server-name" and i + 1 < len(argv):
            server_name = argv[i + 1]
            i += 2
        else:
            i += 1

    print("mcp-proxy: missing '--' separator. "
          "Usage: mcp-proxy.py [--server-name NAME] -- command [args...]",
          file=sys.stderr)
    sys.exit(1)


# ── Log writer ──────────────────────────────────────────────────────────────

def write_log(room_dir, entry):
    """Append a JSON line to {room_dir}/mcp-tools.jsonl (file-lock safe)."""
    if not room_dir:
        return
    try:
        os.makedirs(room_dir, exist_ok=True)
        log_path = os.path.join(room_dir, _LOG_FILENAME)
        line = json.dumps(entry, default=str) + "\n"
        with open(log_path, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass  # never crash the proxy because of logging


# ── JSON-RPC helpers ────────────────────────────────────────────────────────

def _try_parse_json(line_bytes):
    """Try to parse a bytes line as JSON. Returns (dict, True) or (None, False)."""
    try:
        return json.loads(line_bytes), True
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, False


def _truncate(s, max_len=_MAX_RESULT_LEN):
    if len(s) > max_len:
        return s[:max_len] + "…"
    return s


# ── Forwarding threads ─────────────────────────────────────────────────────

def forward_client_to_server(client_stdin, server_stdin, pending, lock):
    """Read lines from client (deepagents), intercept tools/call, forward to server."""
    try:
        for line in client_stdin:
            if not line.strip():
                server_stdin.write(line)
                server_stdin.flush()
                continue

            msg, ok = _try_parse_json(line)
            if ok and msg.get("method") == "tools/call" and "id" in msg:
                params = msg.get("params", {})
                call_id = msg["id"]
                with lock:
                    pending[call_id] = {
                        "tool": params.get("name", "unknown"),
                        "args": params.get("arguments", {}),
                        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "t0": time.monotonic(),
                    }

            server_stdin.write(line)
            server_stdin.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            server_stdin.close()
        except OSError:
            pass


def forward_server_to_client(server_stdout, client_stdout, pending, lock,
                             room_dir, server_name):
    """Read lines from server, match responses to pending calls, log, forward to client."""
    try:
        for line in server_stdout:
            if not line.strip():
                client_stdout.write(line)
                client_stdout.flush()
                continue

            msg, ok = _try_parse_json(line)
            if ok and "id" in msg:
                call_id = msg["id"]
                with lock:
                    call_info = pending.pop(call_id, None)

                if call_info and room_dir:
                    elapsed_ms = round((time.monotonic() - call_info["t0"]) * 1000, 1)
                    entry = {
                        "ts": call_info["ts"],
                        "server": server_name,
                        "tool": call_info["tool"],
                        "args": call_info["args"],
                        "elapsed_ms": elapsed_ms,
                    }
                    if "error" in msg:
                        entry["ok"] = False
                        entry["error"] = _truncate(
                            msg["error"].get("message", str(msg["error"]))
                        )
                    else:
                        entry["ok"] = True
                        entry["result"] = _truncate(
                            json.dumps(msg.get("result"), default=str)
                        )
                    write_log(room_dir, entry)

            client_stdout.write(line)
            client_stdout.flush()
    except (BrokenPipeError, OSError):
        pass


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    server_name, child_cmd = parse_args()
    room_dir = os.environ.get("AGENT_OS_ROOM_DIR", "")

    # Spawn the real MCP server
    proc = subprocess.Popen(
        child_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,  # pass through stderr directly
    )

    # Forward SIGTERM/SIGINT to child
    def _signal_handler(signum, _frame):
        try:
            proc.send_signal(signum)
        except OSError:
            pass

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    pending = {}
    lock = threading.Lock()

    t_in = threading.Thread(
        target=forward_client_to_server,
        args=(sys.stdin.buffer, proc.stdin, pending, lock),
        daemon=True,
    )
    t_out = threading.Thread(
        target=forward_server_to_client,
        args=(proc.stdout, sys.stdout.buffer, pending, lock, room_dir, server_name),
        daemon=True,
    )

    t_in.start()
    t_out.start()

    # Wait for child to exit
    exit_code = proc.wait()

    # Give the output thread a moment to drain remaining lines
    t_out.join(timeout=2)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
