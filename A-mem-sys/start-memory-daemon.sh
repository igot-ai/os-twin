#!/bin/bash
# Start the memory MCP server as a persistent background daemon (SSE transport).
# Usage: start-memory-daemon.sh [project-dir] [--port PORT]
#
# The daemon persists memories to <project-dir>/.memory/ and serves
# MCP tools via SSE on http://127.0.0.1:PORT/sse (default port: 6463).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${OSTWIN_PYTHON:-${HOME}/.ostwin/.venv/bin/python}"
PORT="${MEMORY_PORT:-6463}"
PROJECT_DIR=""

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --stop)
      PID_FILE="${HOME}/.ostwin/memory-daemon.pid"
      if [[ -f "$PID_FILE" ]]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null && echo "Stopped memory daemon" || echo "Daemon not running"
        rm -f "$PID_FILE"
      else
        echo "No PID file found"
      fi
      exit 0
      ;;
    *) PROJECT_DIR="$1"; shift ;;
  esac
done

if [[ -z "$PROJECT_DIR" ]]; then
  PROJECT_DIR="$(pwd)"
fi
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

PERSIST_DIR="$PROJECT_DIR/.memory"
PID_FILE="${HOME}/.ostwin/memory-daemon.pid"

# Kill existing daemon if running
if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE")"
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Stopping existing memory daemon (PID $OLD_PID)..."
    kill "$OLD_PID" 2>/dev/null
    sleep 1
  fi
fi

# Check if port is already in use
if command -v ss &>/dev/null; then
  if ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
    echo "Port $PORT already in use. Memory daemon may already be running."
    echo "Use: $0 --stop  to stop it first."
    exit 1
  fi
fi

mkdir -p "$PERSIST_DIR"

echo "Starting memory daemon..."
echo "  Project: $PROJECT_DIR"
echo "  Persist: $PERSIST_DIR"
echo "  URL:     http://127.0.0.1:$PORT/sse"

export MEMORY_PERSIST_DIR="$PERSIST_DIR"
export GOOGLE_API_KEY="${GOOGLE_API_KEY}"

nohup "$PYTHON" "$SCRIPT_DIR/mcp_server.py" --transport sse --port "$PORT" \
  > "$PERSIST_DIR/daemon.log" 2>&1 &

DAEMON_PID=$!
echo "$DAEMON_PID" > "$PID_FILE"

# Wait a moment and check it started
sleep 1
if kill -0 "$DAEMON_PID" 2>/dev/null; then
  echo "  PID:     $DAEMON_PID"
  echo "  Log:     $PERSIST_DIR/daemon.log"
  echo ""
  echo "Memory daemon started. It will persist data to $PERSIST_DIR/."
  echo "Stop with: $0 --stop"
else
  echo "ERROR: Daemon failed to start. Check $PERSIST_DIR/daemon.log"
  cat "$PERSIST_DIR/daemon.log" 2>/dev/null | tail -10
  exit 1
fi
