#!/bin/bash
# `.agents/roles/manager/loop.sh`
# Bash wrapper for manager loop that reads configuration from config.json
# This is a bash alternative to Start-ManagerLoop.ps1

set -euo pipefail

# Find the agents directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source the config reading library
source "$AGENTS_DIR/lib/read-config.sh"

# --- Read configuration values with defaults ---
# Canonical manager settings live under .manager.*, with .runtime.* used only
# as a secondary source for the same canonical key names.
_poll_manager=$(read_config '.manager.poll_interval_seconds' '')
_poll_runtime_canonical=$(read_config '.runtime.poll_interval_seconds' '')
POLL_INTERVAL="${_poll_manager:-${_poll_runtime_canonical:-5}}"
_max_manager=$(read_config '.manager.max_concurrent_rooms' '')
_max_runtime=$(read_config '.runtime.max_concurrent_rooms' '')
MAX_CONCURRENT_ROOMS="${_max_manager:-${_max_runtime:-50}}"
IDLE_EXPLORE_ENABLED=$(read_config '.autonomy.idle_explore_enabled' false)

# Export configuration for sub-processes
export MANAGER_POLL_INTERVAL="$POLL_INTERVAL"
export MANAGER_MAX_CONCURRENT="$MAX_CONCURRENT_ROOMS"
export MANAGER_IDLE_EXPLORE="$IDLE_EXPLORE_ENABLED"

# Log configuration
echo "[loop.sh] Configuration loaded:"
echo "  poll_interval_seconds: $POLL_INTERVAL"
echo "  max_concurrent_rooms: $MAX_CONCURRENT_ROOMS"
echo "  idle_explore_enabled: $IDLE_EXPLORE_ENABLED"

# --- Main loop implementation ---
# For now, this is a placeholder that demonstrates config reading
# The full implementation would delegate to the PowerShell manager loop
# or implement the loop logic in bash

WARROOMS_DIR="${WARROOMS_DIR:-$AGENTS_DIR/war-rooms}"
MANAGER_PID_FILE="$AGENTS_DIR/manager.pid"

# Write PID
echo $$ > "$MANAGER_PID_FILE"

# Cleanup on exit
cleanup() {
    rm -f "$MANAGER_PID_FILE"
    exit 0
}
trap cleanup EXIT INT TERM

# Main loop
echo "[loop.sh] Starting manager loop with polling interval ${POLL_INTERVAL}s"
echo "[loop.sh] War-rooms directory: $WARROOMS_DIR"
echo "[loop.sh] Max concurrent rooms: $MAX_CONCURRENT_ROOMS"

# Check if PowerShell manager loop exists and delegate to it
MANAGER_PS1="$SCRIPT_DIR/Start-ManagerLoop.ps1"
if [[ -f "$MANAGER_PS1" ]]; then
    echo "[loop.sh] Delegating to PowerShell manager loop..."
    # Remove PID file before exec — exec replaces this shell so the EXIT
    # trap will never fire. Let the PowerShell process manage its own PID.
    rm -f "$MANAGER_PID_FILE"
    exec pwsh -NoProfile -File "$MANAGER_PS1" "$@"
else
    echo "[loop.sh] WARNING: PowerShell manager loop not found"
    echo "[loop.sh] Running basic bash implementation..."
    
    # Basic loop implementation
    while true; do
        # Check for war-rooms that need processing
        if [[ -d "$WARROOMS_DIR" ]]; then
            room_count=$(find "$WARROOMS_DIR" -maxdepth 1 -type d -name "room-*" | wc -l | tr -d ' ')
            echo "[loop.sh] Active war-rooms: $room_count / $MAX_CONCURRENT_ROOMS"
        fi
        
        # Idle exploration (if enabled)
        if [[ "$IDLE_EXPLORE_ENABLED" == "true" ]]; then
            echo "[loop.sh] Idle exploration enabled - would run idle tasks here"
        fi
        
        sleep "$POLL_INTERVAL"
    done
fi
