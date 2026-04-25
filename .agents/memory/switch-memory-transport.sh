#!/bin/bash
# Switch memory MCP transport between http, stdio, and sse for a project.
#
# Usage:
#   switch-memory-transport.sh http [project-dir]     # switch to HTTP via dashboard (default)
#   switch-memory-transport.sh stdio [project-dir]    # switch to stdio (per-process)
#   switch-memory-transport.sh sse [project-dir]      # switch to sse (persistent daemon)
#   switch-memory-transport.sh status [project-dir]   # show current transport

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${OSTWIN_PYTHON:-${HOME}/.ostwin/.venv/bin/python}"
TRANSPORT="${1:-status}"
shift 2>/dev/null || true
PROJECT_DIR="${1:-$(pwd)}"
PROJECT_DIR="$(cd "$PROJECT_DIR" 2>/dev/null && pwd || echo "$PROJECT_DIR")"

MCP_CONFIG="$PROJECT_DIR/.agents/mcp/config.json"

if [[ ! -f "$MCP_CONFIG" ]]; then
  echo "No MCP config at $MCP_CONFIG"
  echo "Run 'ostwin init' first."
  exit 1
fi

case "$TRANSPORT" in
  status)
    "$PYTHON" - "$MCP_CONFIG" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    c = json.load(f)
# Support both OpenCode format ("mcp") and legacy format ("mcpServers")
servers = c.get("mcp", c.get("mcpServers", {}))
mem = servers.get("memory", {})
mtype = mem.get("type", "")
url = mem.get("url", "")
if mtype == "remote" and "/api/knowledge/" in url:
    print(f"Transport: http (via dashboard)")
    print(f"URL:       {url}")
    import subprocess
    # Extract port from URL
    try:
        port = url.split("://")[1].split(":")[1].split("/")[0]
        r = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True)
        if f":{port} " in r.stdout:
            print(f"Dashboard: running (port {port})")
        else:
            print(f"Dashboard: NOT running (port {port})")
    except (IndexError, Exception):
        print(f"Dashboard: unknown")
elif mtype == "sse":
    print(f"Transport: sse")
    print(f"URL:       {url}")
    import subprocess
    port = url.split(":")[-1].split("/")[0]
    if port:
        r = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True)
        if f":{port} " in r.stdout:
            print(f"Daemon:    running (port {port})")
        else:
            print(f"Daemon:    NOT running (port {port})")
elif "command" in mem:
    print(f"Transport: stdio")
    cmd = mem.get("command", "N/A")
    if isinstance(cmd, list):
        print(f"Command:   {' '.join(cmd)}")
    else:
        print(f"Command:   {cmd}")
        print(f"Args:      {mem.get('args', [])}")
else:
    print("Transport: unknown")
    print(json.dumps(mem, indent=2))
PYEOF
    ;;

  http)
    DASHBOARD_PORT="${DASHBOARD_PORT:-3366}"
    "$PYTHON" - "$MCP_CONFIG" "$PROJECT_DIR" "$DASHBOARD_PORT" <<'PYEOF'
import json, sys, os
config_path, project_dir, port = sys.argv[1], sys.argv[2], sys.argv[3]
with open(config_path) as f:
    config = json.load(f)
# Support both OpenCode format ("mcp") and legacy format ("mcpServers")
key = "mcp" if "mcp" in config else "mcpServers"
if key not in config:
    config[key] = {}
persist_dir = os.path.join(project_dir, ".memory")
config[key]["memory"] = {
    "type": "remote",
    "url": f"http://localhost:{port}/api/knowledge/mcp?persist_dir={persist_dir}"
}
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)
    f.write("\n")
print(f"Switched to http (dashboard port {port})")
print(f"  Config:      {config_path}")
print(f"  persist_dir: {persist_dir}")
print(f"  Note: requires dashboard running on port {port}")
PYEOF
    ;;

  stdio)
    "$PYTHON" - "$MCP_CONFIG" "$PROJECT_DIR" <<'PYEOF'
import json, sys, os
config_path, project_dir = sys.argv[1], sys.argv[2]
with open(config_path) as f:
    config = json.load(f)

key = "mcp" if "mcp" in config else "mcpServers"
if key not in config:
    config[key] = {}

home = os.path.expanduser("~")
# OpenCode format: command is an array
config[key]["memory"] = {
    "type": "local",
    "command": [
        os.path.join(home, ".ostwin", ".venv", "bin", "python"),
        os.path.join(home, ".ostwin", ".agents", "memory", "mcp_server.py"),
    ],
    "timeout": 120000,
    "environment": {
        "AGENT_OS_ROOT": project_dir,
        "MEMORY_PERSIST_DIR": os.path.join(project_dir, ".memory"),
        "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
    }
}

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)
    f.write("\n")
print(f"Switched to stdio")
print(f"  Config: {config_path}")
print(f"  Note: each agent spawns its own server process")
PYEOF
    ;;

  sse)
    # Check if daemon is running, start if not
    PORT_FILE="$PROJECT_DIR/.memory/.daemon.port"
    if [[ ! -f "$PORT_FILE" ]]; then
      echo "No SSE daemon running for $PROJECT_DIR"
      echo "Start one with: $SCRIPT_DIR/start-memory-daemon.sh $PROJECT_DIR"
      exit 1
    fi
    PORT=$(cat "$PORT_FILE")

    # Verify daemon is actually running
    PID_FILE="$PROJECT_DIR/.memory/.daemon.pid"
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
      "$PYTHON" - "$MCP_CONFIG" "$PORT" <<'PYEOF'
import json, sys
config_path, port = sys.argv[1], sys.argv[2]
with open(config_path) as f:
    config = json.load(f)
key = "mcp" if "mcp" in config else "mcpServers"
if key not in config:
    config[key] = {}
config[key]["memory"] = {
    "type": "sse",
    "url": f"http://127.0.0.1:{port}/sse"
}
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)
    f.write("\n")
print(f"Switched to sse (port {port})")
print(f"  Config: {config_path}")
print(f"  Note: persistent daemon, 60s auto-sync")
PYEOF
    else
      echo "SSE daemon not running for $PROJECT_DIR"
      echo "Start one with: $SCRIPT_DIR/start-memory-daemon.sh $PROJECT_DIR"
      exit 1
    fi
    ;;

  *)
    echo "Usage: $0 {http|stdio|sse|status} [project-dir]"
    exit 1
    ;;
esac
