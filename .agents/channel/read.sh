#!/usr/bin/env bash
# Read messages from a war-room channel with optional filters
#
# Usage: read.sh <war-room-dir> [--from NAME] [--to NAME] [--type TYPE] [--ref REF] [--last N] [--after MSG_ID]
#
# Examples:
#   read.sh .agents/war-rooms/room-001                          # All messages
#   read.sh .agents/war-rooms/room-001 --type done              # Only "done" messages
#   read.sh .agents/war-rooms/room-001 --from qa --type fail    # QA failures
#   read.sh .agents/war-rooms/room-001 --last 1                 # Last message only

set -euo pipefail

ROOM_DIR="$1"
shift

CHANNEL_FILE="${ROOM_DIR}/channel.jsonl"

if [[ ! -f "$CHANNEL_FILE" ]]; then
  echo "[]"
  exit 0
fi

# Parse optional filters
FILTER_FROM=""
FILTER_TO=""
FILTER_TYPE=""
FILTER_REF=""
LAST_N=""
AFTER_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)   FILTER_FROM="$2"; shift 2 ;;
    --to)     FILTER_TO="$2"; shift 2 ;;
    --type)   FILTER_TYPE="$2"; shift 2 ;;
    --ref)    FILTER_REF="$2"; shift 2 ;;
    --last)   LAST_N="$2"; shift 2 ;;
    --after)  AFTER_ID="$2"; shift 2 ;;
    *)        echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

python3 -c "
import json, sys

filter_from = '${FILTER_FROM}'
filter_to = '${FILTER_TO}'
filter_type = '${FILTER_TYPE}'
filter_ref = '${FILTER_REF}'
last_n = '${LAST_N}'
after_id = '${AFTER_ID}'

messages = []
found_after = not bool(after_id)

with open('${CHANNEL_FILE}', 'r') as f:
    for line_num, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            # Skip corrupt lines gracefully
            print(f'[WARN] Skipping corrupt JSON at line {line_num}', file=sys.stderr)
            continue

        if not found_after:
            if msg.get('id') == after_id:
                found_after = True
            continue

        if filter_from and msg.get('from') != filter_from:
            continue
        if filter_to and msg.get('to') != filter_to:
            continue
        if filter_type and msg.get('type') != filter_type:
            continue
        if filter_ref and msg.get('ref') != filter_ref:
            continue
        messages.append(msg)

if last_n:
    messages = messages[-int(last_n):]

print(json.dumps(messages, indent=2))
"
