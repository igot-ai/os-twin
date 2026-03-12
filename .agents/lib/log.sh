#!/usr/bin/env bash
# Agent OS — Structured Logging
#
# Source this from any Agent OS script:
#   source "$AGENTS_DIR/lib/log.sh"
#
# Usage:
#   log INFO "Manager started"
#   log WARN "Room stuck" room_id=room-001
#   log ERROR "Engineer crashed" task_ref=TASK-001

# Self-resolve installation folder from this file's location
# so logs always land inside .agents/logs/ even if AGENTS_DIR is unset.
_LOG_SH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_LOG_AGENTS_DIR="$(cd "$_LOG_SH_DIR/.." && pwd)"
LOG_DIR="${AGENT_OS_LOG_DIR:-${AGENTS_DIR:-$_LOG_AGENTS_DIR}/logs}"
mkdir -p "$LOG_DIR" 2>/dev/null || true

LOG_LEVEL="${AGENT_OS_LOG_LEVEL:-INFO}"
LOG_FILE="${LOG_DIR}/ostwin.log"
PYTHON="${_LOG_AGENTS_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"

_log_level_num() {
  case "$1" in
    DEBUG) echo 0 ;; INFO) echo 1 ;; WARN) echo 2 ;; ERROR) echo 3 ;;
    *) echo 1 ;;
  esac
}

log() {
  local level="$1"; shift
  local current
  current=$(_log_level_num "$LOG_LEVEL")
  local msg_level
  msg_level=$(_log_level_num "$level")
  [[ "$msg_level" -lt "$current" ]] && return

  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  local caller="${FUNCNAME[1]:-main}"
  local line="[$ts] [$level] [$caller] $*"

  echo "$line" >&2
  if [[ -d "$LOG_DIR" ]]; then
    echo "$line" >> "$LOG_FILE" 2>/dev/null || true
  fi
}

log_json() {
  local level="$1"; shift
  local event="$1"; shift
  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  if [[ -d "$LOG_DIR" ]]; then
    "$PYTHON" -c "
import json, sys
data = {}
args = sys.argv[1:]
for i in range(0, len(args)-1, 2):
    data[args[i]] = args[i+1]
print(json.dumps({'ts': '$ts', 'level': '$level', 'event': '$event', 'data': data}))
" "$@" >> "$LOG_DIR/ostwin.jsonl" 2>/dev/null || true
  fi
}
