#!/usr/bin/env bash
# Agent OS — Channel Log Viewer
#
# View and filter JSONL channel messages across war-rooms.
#
# Usage:
#   logs.sh [room-id] [--follow] [--type TYPE] [--from ROLE] [--last N]
#
# Examples:
#   logs.sh                          # Latest messages from all rooms
#   logs.sh room-001                 # Messages from room-001
#   logs.sh room-001 --follow        # Tail -f style
#   logs.sh --type fail              # All failure messages
#   logs.sh --last 20                # Last 20 messages across all rooms

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR"
PYTHON="${AGENTS_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"
WARROOMS="${WARROOMS_DIR:-$AGENTS_DIR/war-rooms}"
CHANNEL="$AGENTS_DIR/channel"

ROOM_ID=""
FOLLOW=false
FILTER_TYPE=""
FILTER_FROM=""
LAST_N=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --follow|-f) FOLLOW=true; shift ;;
    --type)      FILTER_TYPE="$2"; shift 2 ;;
    --from)      FILTER_FROM="$2"; shift 2 ;;
    --last)      LAST_N="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: logs.sh [room-id] [--follow] [--type TYPE] [--from ROLE] [--last N]"
      exit 0
      ;;
    room-*)      ROOM_ID="$1"; shift ;;
    *)           ROOM_ID="$1"; shift ;;
  esac
done

# Format a message for display
format_msg() {
  "$PYTHON" -c "
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        continue

    # Apply filters
    filter_type = '${FILTER_TYPE}'
    filter_from = '${FILTER_FROM}'
    if filter_type and msg.get('type') != filter_type:
        continue
    if filter_from and msg.get('from') != filter_from:
        continue

    # Format output
    ts = msg.get('ts', '?')[:19]
    from_r = msg.get('from', '?')
    to_r = msg.get('to', '?')
    mtype = msg.get('type', '?')
    ref = msg.get('ref', '?')
    body = msg.get('body', '')

    # Type icons
    icons = {'task': 'TASK', 'done': ' OK ', 'review': ' QA ', 'pass': 'PASS', 'fail': 'FAIL', 'fix': ' FIX', 'error': ' ERR', 'signoff': 'SIGN', 'release': ' REL'}
    icon = icons.get(mtype, mtype.upper()[:4])

    # Truncate body for display
    body_preview = body.replace('\n', ' ')[:120]
    print(f'{ts} [{icon}] {from_r}->{to_r} {ref}: {body_preview}')
"
}

if [[ -n "$ROOM_ID" ]]; then
  # Single room
  ROOM_DIR="$WARROOMS/$ROOM_ID"
  if [[ ! -d "$ROOM_DIR" ]]; then
    echo "[ERROR] Room not found: $ROOM_ID" >&2
    exit 1
  fi

  CHANNEL_FILE="$ROOM_DIR/channel.jsonl"
  if [[ ! -f "$CHANNEL_FILE" ]]; then
    echo "[INFO] No messages in $ROOM_ID."
    exit 0
  fi

  if $FOLLOW; then
    echo "[LOGS] Following $ROOM_ID (Ctrl+C to stop)..."
    tail -f "$CHANNEL_FILE" 2>/dev/null | format_msg
  else
    if [[ -n "$LAST_N" ]]; then
      tail -n "$LAST_N" "$CHANNEL_FILE" | format_msg
    else
      cat "$CHANNEL_FILE" | format_msg
    fi
  fi
else
  # All rooms
  ALL_LINES=""
  for room_dir in "$WARROOMS"/room-*/; do
    [ -d "$room_dir" ] || continue
    channel_file="$room_dir/channel.jsonl"
    [ -f "$channel_file" ] || continue
    room_id=$(basename "$room_dir")
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      # Prepend room_id to each line for context
      echo "$line"
    done < "$channel_file"
  done | "$PYTHON" -c "
import json, sys

messages = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
        messages.append(msg)
    except (json.JSONDecodeError, ValueError):
        continue

# Sort by timestamp
messages.sort(key=lambda m: m.get('ts', ''))

# Apply last_n
last_n = '${LAST_N}'
if last_n:
    messages = messages[-int(last_n):]

for msg in messages:
    print(json.dumps(msg))
" | format_msg
fi
