#!/usr/bin/env bash
# Agent OS — Graceful Shutdown
#
# Stops the running manager loop and all child agent processes.
# Uses three strategies in order:
#   1. SIGTERM the manager (graceful — it cleans up its own children)
#   2. Process-tree kill via pgrep -P (catches orphaned grandchildren)
#   3. PGID group kill (catches anything that inherited the process group)
#
# Usage: stop.sh [--force]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR"
MANAGER_PID_FILE="$AGENTS_DIR/manager.pid"
MANAGER_PGID_FILE="$AGENTS_DIR/manager.pgid"
WARROOMS="${WARROOMS_DIR:-$AGENTS_DIR/war-rooms}"
FORCE=false
DASHBOARD_PID_FILE="$AGENTS_DIR/dashboard.pid"

stop_dashboard() {
  if [[ -f "$DASHBOARD_PID_FILE" ]]; then
    DASH_PID=$(cat "$DASHBOARD_PID_FILE")
    if kill -0 "$DASH_PID" 2>/dev/null; then
      echo "[STOP] Stopping dashboard (PID $DASH_PID)..."
      kill "$DASH_PID" 2>/dev/null || true
      for _i in $(seq 1 5); do
        kill -0 "$DASH_PID" 2>/dev/null || break
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

kill_descendants() { # Recursively kill all descendants of a PID
  local parent="$1" sig="${2:-TERM}"
  local children
  children=$(pgrep -P "$parent" 2>/dev/null) || true
  for child in $children; do
    kill_descendants "$child" "$sig"
  done
  kill "-$sig" "$parent" 2>/dev/null || true
}

kill_room_pids() { # Kill every PID recorded in war-room pid files + their trees
  local sig="${1:-TERM}"
  for pid_file in "$WARROOMS"/room-*/pids/*.pid; do
    [ -f "$pid_file" ] || continue
    local agent_pid
    agent_pid=$(cat "$pid_file" 2>/dev/null) || continue
    [[ "$agent_pid" =~ ^[0-9]+$ ]] || continue
    if kill -0 "$agent_pid" 2>/dev/null; then
      kill_descendants "$agent_pid" "$sig"
    fi
    rm -f "$pid_file"
  done
  for spawned in "$WARROOMS"/room-*/pids/*.spawned_at; do # clean spawn locks
    [ -f "$spawned" ] && rm -f "$spawned"
  done
}

cleanup_pid_files() {
  rm -f "$MANAGER_PID_FILE" "$MANAGER_PGID_FILE"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=true; shift ;;
    *)       shift ;;
  esac
done

if [[ ! -f "$MANAGER_PID_FILE" ]]; then
  echo "[STOP] No manager PID file. Sweeping for orphaned room processes..."
  kill_room_pids TERM
  cleanup_pid_files
  echo "[STOP] Sweep complete."
  exit 0
fi

PID=$(cat "$MANAGER_PID_FILE")
PGID=""
[[ -f "$MANAGER_PGID_FILE" ]] && PGID=$(cat "$MANAGER_PGID_FILE" 2>/dev/null | tr -d '[:space:]')

if ! kill -0 "$PID" 2>/dev/null; then
  echo "[STOP] Manager PID $PID not running. Sweeping orphaned processes..."
  kill_room_pids TERM
  cleanup_pid_files
  echo "[STOP] Sweep complete."
  exit 0
fi

# --- Strategy 1: graceful SIGTERM to manager (it stops its own children) ---
echo "[STOP] Sending SIGTERM to manager (PID $PID)..."
kill "$PID" 2>/dev/null || true

for _i in $(seq 1 10); do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "[STOP] Manager stopped gracefully."
    kill_room_pids TERM # sweep any stragglers the manager missed
    cleanup_pid_files
    exit 0
  fi
  sleep 1
done

# --- Strategy 2: process-tree kill (catches orphaned grandchildren) ---
echo "[STOP] Manager still alive after 10s. Killing process tree..."
kill_descendants "$PID" TERM
kill_room_pids TERM
sleep 2

if ! kill -0 "$PID" 2>/dev/null; then
  echo "[STOP] Process tree killed."
  cleanup_pid_files
  exit 0
fi

# --- Strategy 3: PGID group kill + SIGKILL (nuclear option, requires --force) ---
if $FORCE; then
  echo "[STOP] Force-killing..."
  if [[ -n "$PGID" && "$PGID" =~ ^[0-9]+$ ]]; then
    if kill -0 -- "-$PGID" 2>/dev/null; then # verify PGID still has live processes
      echo "[STOP]   Killing process group $PGID..."
      kill -9 -- "-$PGID" 2>/dev/null || true
    else
      echo "[STOP]   Process group $PGID already dead, skipping."
    fi
  fi
  kill_descendants "$PID" KILL
  kill_room_pids KILL
  kill -9 "$PID" 2>/dev/null || true
  cleanup_pid_files
  echo "[STOP] Force shutdown complete."
else
  echo "[STOP] Still alive. Use --force to SIGKILL the entire tree." >&2
  exit 1
fi
