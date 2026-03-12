#!/usr/bin/env bash
# Agent OS — Shared Utilities
#
# Source this from any Agent OS script:
#   source "$AGENTS_DIR/lib/utils.sh"

# --- Portable timeout ---
# macOS does not include `timeout` by default.
# Try: timeout → gtimeout → perl fallback
PYTHON="${AGENTS_DIR:-}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"

if ! command -v timeout &>/dev/null; then
  if command -v gtimeout &>/dev/null; then
    timeout() { gtimeout "$@"; }
  else
    timeout() {
      local duration=$1; shift
      perl -e "alarm $duration; exec @ARGV" -- "$@"
    }
  fi
fi

# --- Config reader ---
# Reads a value from config JSON. Uses AGENT_OS_CONFIG env var if set.
# Usage: read_config "manager.poll_interval_seconds"
read_config() {
  local key_path="$1"
  local config="${AGENT_OS_CONFIG:-${AGENTS_DIR}/config.json}"
  "$PYTHON" -c "
import json, sys, functools
config = json.load(open('$config'))
keys = '${key_path}'.split('.')
val = functools.reduce(lambda d, k: d[k], keys, config)
print(val if not isinstance(val, bool) else str(val).lower())
" 2>/dev/null
}

# --- Atomic status write with audit ---
# Usage: set_status <room_dir> <new_status>
set_status() {
  local room_dir="$1"
  local new_status="$2"
  local old_status
  old_status=$(cat "$room_dir/status" 2>/dev/null || echo "unknown")
  echo "$new_status" > "$room_dir/status"
  date +%s > "$room_dir/state_changed_at"
  # Audit trail
  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "$ts STATUS $old_status -> $new_status" >> "$room_dir/audit.log"
}

# --- Check if PID is alive ---
is_pid_alive() {
  local pid_file="$1"
  [ -f "$pid_file" ] || return 1
  local pid
  pid=$(cat "$pid_file")
  kill -0 "$pid" 2>/dev/null
}

# --- Truncate text to max bytes ---
# Usage: truncate_bytes <text> <max_bytes> → prints truncated text
truncate_bytes() {
  local text="$1"
  local max_bytes="$2"
  local size=${#text}
  if [ "$size" -gt "$max_bytes" ]; then
    echo "${text:0:$max_bytes}

[TRUNCATED: original size ${size} bytes. Full content available in brief.md]"
  else
    echo "$text"
  fi
}
