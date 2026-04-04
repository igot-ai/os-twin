#!/usr/bin/env bash
# host-daemon.sh — macOS host automation daemon
# Listens on a Unix domain socket and dispatches JSON task payloads to
# the appropriate .agents/scripts/macos/*.sh script.
#
# Communication protocol:
#   Request:  {"script":"app","cmd":"launch","args":"Safari"}
#   Response: {"status":"ok","exit_code":0,"output":"Launched: Safari"}
#
# Uses socat for concurrent connections when available, falls back to nc loop.
#
# To send a task:
#   printf '{"script":"app","cmd":"list","args":""}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock
#   # or with BSD nc (use explicit path — Homebrew GNU netcat does not support -U):
#   printf '{"script":"app","cmd":"list","args":""}' | /usr/bin/nc -U /tmp/ostwin-macos-host.sock
#
# Requires: macOS, bash 3.2+, socat (preferred) or nc (fallback)
set -uo pipefail
# NOTE: no -e — long-running loop must not exit on transient errors

SOCKET_PATH="${OSTWIN_SOCKET:-/tmp/ostwin-macos-host.sock}"
OSTWIN_HOME="${OSTWIN_HOME:-$HOME/.ostwin}"
SCRIPTS_DIR="${OSTWIN_HOME}/.agents/scripts/macos"
LOG_PREFIX="[ostwin-macos-host]"

log() {
  echo "$LOG_PREFIX $(date '+%Y-%m-%d %H:%M:%S') $*"
}

# ── Safe JSON string extraction ──────────────────────────────────────────────
# Extract a string value for a key from a flat JSON object.
# Uses grep + cut instead of sed to avoid regex injection.
json_get() {
  local json="$1"
  local key="$2"
  local pair
  pair=$(printf '%s' "$json" | grep -o "\"$key\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" 2>/dev/null | head -1) || {
    echo ""
    return
  }
  printf '%s' "$pair" | rev | cut -d'"' -f2 | rev
}

# ── JSON response builder ───────────────────────────────────────────────────
# Escapes output for embedding in a JSON string value, then prints a JSON envelope.
json_response() {
  local status="$1"    # "ok" or "error"
  local exit_code="$2"
  local output="$3"
  # Escape backslashes, double-quotes, newlines, tabs for JSON
  local escaped
  escaped=$(printf '%s' "$output" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ' | tr '\t' ' ')
  printf '{"status":"%s","exit_code":%d,"output":"%s"}\n' "$status" "$exit_code" "$escaped"
}

# ── Validate script name — strict whitelist ──────────────────────────────────
valid_script() {
  case "$1" in
    app|window|click|type|capture|system|finder|axbridge|devtools) return 0 ;;
    *) return 1 ;;
  esac
}

# ── Validate command name — reject shell metacharacters ──────────────────────
valid_cmd() {
  local cmd="$1"
  case "$cmd" in
    *[!a-z0-9-]*) return 1 ;;
    "") return 1 ;;
    *) return 0 ;;
  esac
}

# ── Validate args — reject dangerous shell characters ────────────────────────
valid_args() {
  local args="$1"
  [ -z "$args" ] && return 0
  case "$args" in
    *';'*|*'&'*|*'|'*|*'`'*|*'$('*|*'>'*|*'<'*|*'!'*)
      return 1
      ;;
    *) return 0 ;;
  esac
}

# ── Handle one request ──────────────────────────────────────────────────────
# Reads a single JSON payload from stdin, dispatches it, writes JSON response to stdout.
# Used by both socat (per-fork) and nc (inline) modes.
handle_request() {
  local PAYLOAD
  PAYLOAD=$(cat)
  [ -z "$PAYLOAD" ] && return

  log "Received: $PAYLOAD"

  local SCRIPT CMD ARGS
  SCRIPT=$(json_get "$PAYLOAD" "script")
  CMD=$(json_get "$PAYLOAD" "cmd")
  ARGS=$(json_get "$PAYLOAD" "args")

  # Validate all fields before dispatch
  if ! valid_script "$SCRIPT"; then
    log "REJECTED: unknown or invalid script: '$SCRIPT'"
    json_response "error" 1 "unknown script: $SCRIPT"
    return
  fi

  if ! valid_cmd "$CMD"; then
    log "REJECTED: invalid command: '$CMD'"
    json_response "error" 1 "invalid command: $CMD"
    return
  fi

  if ! valid_args "$ARGS"; then
    log "REJECTED: dangerous characters in args: '$ARGS'"
    json_response "error" 1 "invalid characters in args"
    return
  fi

  local SCRIPT_PATH="$SCRIPTS_DIR/${SCRIPT}.sh"
  if [ ! -f "$SCRIPT_PATH" ]; then
    log "ERROR: Script not found: $SCRIPT_PATH"
    json_response "error" 127 "script not found: $SCRIPT"
    return
  fi

  log "Dispatching: bash $SCRIPT_PATH $CMD $ARGS"

  local OUTPUT EXIT_CODE
  # shellcheck disable=SC2086
  OUTPUT=$(bash "$SCRIPT_PATH" "$CMD" $ARGS 2>&1) && EXIT_CODE=0 || EXIT_CODE=$?

  log "Exit: $EXIT_CODE | Output: $OUTPUT"

  if [ "$EXIT_CODE" -eq 0 ]; then
    json_response "ok" 0 "$OUTPUT"
  else
    json_response "error" "$EXIT_CODE" "$OUTPUT"
  fi
}

# ── Export for socat fork mode ──────────────────────────────────────────────
export -f handle_request json_get json_response valid_script valid_cmd valid_args log
export SCRIPTS_DIR OSTWIN_HOME LOG_PREFIX

# ── Main ────────────────────────────────────────────────────────────────────

log "Starting daemon on socket: $SOCKET_PATH"

# Remove stale socket file
rm -f "$SOCKET_PATH"

# Verify scripts directory exists
if [ ! -d "$SCRIPTS_DIR" ]; then
  log "ERROR: Scripts directory not found: $SCRIPTS_DIR"
  exit 1
fi

# Prefer socat (concurrent connections) over nc (serial)
if command -v socat >/dev/null 2>&1; then
  log "Using socat (concurrent mode)"
  # socat forks a new process per connection.
  # Each fork reads stdin (the client payload) and writes stdout (the response).
  socat UNIX-LISTEN:"$SOCKET_PATH",fork,reuseaddr \
    SYSTEM:"bash -c handle_request" &
  SOCAT_PID=$!

  # Trap SIGTERM/SIGINT to clean up socat and the socket
  cleanup() {
    log "Shutting down..."
    kill "$SOCAT_PID" 2>/dev/null || true
    rm -f "$SOCKET_PATH"
    exit 0
  }
  trap cleanup SIGTERM SIGINT

  log "Listening on $SOCKET_PATH (PID $SOCAT_PID)"
  wait "$SOCAT_PID"

else
  log "Using nc (serial mode — install socat for concurrent connections)"
  # BSD netcat fallback: one connection at a time, loop.
  while true; do
    PAYLOAD=$(nc -lU "$SOCKET_PATH" 2>/dev/null) || {
      rm -f "$SOCKET_PATH"
      sleep 0.2
      continue
    }

    [ -z "$PAYLOAD" ] && continue

    # Process inline (no fork — serial)
    RESPONSE=$(echo "$PAYLOAD" | handle_request)

    log "Response: $RESPONSE"
    # NOTE: nc already closed the connection before we get here in BSD mode.
    # The response is logged but not sent back to the client.
    # This is a known nc limitation — socat is the recommended mode.
  done
fi
