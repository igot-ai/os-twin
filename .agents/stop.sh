#!/usr/bin/env bash
# Agent OS — Graceful Shutdown
#
# Stops the running manager loop and all child agent processes.
#
# Usage: stop.sh [--force]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR"
MANAGER_PID_FILE="$AGENTS_DIR/manager.pid"
WARROOMS="${WARROOMS_DIR:-$AGENTS_DIR/war-rooms}"
FORCE=false
DASHBOARD_PID_FILE="$AGENTS_DIR/dashboard.pid"

# ── Always stop the dashboard on exit (even if no manager is running) ──
stop_dashboard() {
  if [[ -f "$DASHBOARD_PID_FILE" ]]; then
    DASH_PID=$(cat "$DASHBOARD_PID_FILE")
    if kill -0 "$DASH_PID" 2>/dev/null; then
      echo "[STOP] Stopping dashboard (PID $DASH_PID)..."
      kill "$DASH_PID" 2>/dev/null || true
      # Wait up to 5s for graceful shutdown (tunnel cleanup needs time)
      for _i in $(seq 1 5); do
        if ! kill -0 "$DASH_PID" 2>/dev/null; then
          break
        fi
        sleep 1
      done
      if kill -0 "$DASH_PID" 2>/dev/null; then
        echo "[STOP] Dashboard still alive, force-killing..."
        kill -9 "$DASH_PID" 2>/dev/null || true
      fi
      echo "[STOP] Dashboard stopped."
    fi
    rm -f "$DASHBOARD_PID_FILE"
  fi
}
trap stop_dashboard EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=true; shift ;;
    *)       shift ;;
  esac
done

if [[ ! -f "$MANAGER_PID_FILE" ]]; then
  echo "[STOP] No manager running (no PID file)."
  exit 0
fi

PID=$(cat "$MANAGER_PID_FILE")

if ! kill -0 "$PID" 2>/dev/null; then
  echo "[STOP] Manager PID $PID not running. Cleaning up PID file."
  rm -f "$MANAGER_PID_FILE"
  exit 0
fi

echo "[STOP] Sending SIGTERM to manager (PID $PID)..."
kill "$PID" 2>/dev/null || true

# Wait for graceful shutdown (up to 10 seconds)
for i in $(seq 1 10); do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "[STOP] Manager stopped gracefully."
    rm -f "$MANAGER_PID_FILE"
    exit 0
  fi
  sleep 1
done

# Force kill if still alive
if kill -0 "$PID" 2>/dev/null; then
  if $FORCE; then
    echo "[STOP] Force-killing manager (PID $PID)..."
    kill -9 "$PID" 2>/dev/null || true
    # Kill any remaining agent processes
    for pid_file in "$WARROOMS"/room-*/pids/*.pid; do
      [ -f "$pid_file" ] || continue
      agent_pid=$(cat "$pid_file")
      kill -9 "$agent_pid" 2>/dev/null || true
      rm -f "$pid_file"
    done
    rm -f "$MANAGER_PID_FILE"
    echo "[STOP] Force shutdown complete."
  else
    echo "[STOP] Manager still running after 10s. Use --force to kill." >&2
    exit 1
  fi
fi

# Dashboard is stopped via the EXIT trap registered at the top of this script.
