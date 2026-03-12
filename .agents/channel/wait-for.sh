#!/usr/bin/env bash
# Block until a specific message type appears in a war-room channel
#
# Usage: wait-for.sh <war-room-dir> <type> [--from NAME] [--ref REF] [--timeout SECONDS] [--poll SECONDS]
#
# Examples:
#   wait-for.sh .agents/war-rooms/room-001 done                    # Wait for any "done"
#   wait-for.sh .agents/war-rooms/room-001 pass --from qa          # Wait for QA pass
#   wait-for.sh .agents/war-rooms/room-001 done --timeout 600      # Timeout after 10min

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${AGENTS_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"

ROOM_DIR="$1"
WAIT_TYPE="$2"
shift 2

FILTER_FROM=""
FILTER_REF=""
TIMEOUT=0
POLL_INTERVAL=3
LAST_SEEN_COUNT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)    FILTER_FROM="$2"; shift 2 ;;
    --ref)     FILTER_REF="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --poll)    POLL_INTERVAL="$2"; shift 2 ;;
    *)         echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

CHANNEL_FILE="${ROOM_DIR}/channel.jsonl"
ELAPSED=0

while true; do
  if [[ -f "$CHANNEL_FILE" ]]; then
    # Build read.sh filter args
    READ_ARGS=("$ROOM_DIR" "--type" "$WAIT_TYPE")
    [[ -n "$FILTER_FROM" ]] && READ_ARGS+=("--from" "$FILTER_FROM")
    [[ -n "$FILTER_REF" ]] && READ_ARGS+=("--ref" "$FILTER_REF")
    READ_ARGS+=("--last" "1")

    RESULT=$("$SCRIPT_DIR/read.sh" "${READ_ARGS[@]}")
    MSG_COUNT=$(echo "$RESULT" | "$PYTHON" -c "import json,sys; print(len(json.load(sys.stdin)))")

    if [[ "$MSG_COUNT" -gt 0 ]]; then
      # Return the matching message
      echo "$RESULT" | "$PYTHON" -c "import json,sys; msgs=json.load(sys.stdin); print(json.dumps(msgs[-1]))"
      exit 0
    fi
  fi

  # Check timeout
  if [[ "$TIMEOUT" -gt 0 && "$ELAPSED" -ge "$TIMEOUT" ]]; then
    echo '{"error": "timeout", "waited_seconds": '"$ELAPSED"'}' >&2
    exit 1
  fi

  sleep "$POLL_INTERVAL"
  ELAPSED=$((ELAPSED + POLL_INTERVAL))
done
