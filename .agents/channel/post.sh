#!/usr/bin/env bash
# Post a message to a war-room channel
#
# Usage: post.sh <war-room-dir> <from> <to> <type> <ref> <body>
#
# Example:
#   post.sh .agents/war-rooms/room-001 manager engineer task TASK-001 "Implement auth"

set -euo pipefail

ROOM_DIR="$1"
FROM="$2"
TO="$3"
TYPE="$4"
REF="$5"
BODY="$6"

CHANNEL_FILE="${ROOM_DIR}/channel.jsonl"

# Ensure channel file exists
mkdir -p "$ROOM_DIR"
touch "$CHANNEL_FILE"

# Generate timestamp
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Generate message ID
MSG_ID="${FROM}-${TYPE}-$(date +%s%N 2>/dev/null || date +%s)-$$"

# Build JSON message (using python for safe JSON encoding)
python3 -c "
import json, sys
msg = {
    'id': sys.argv[1],
    'ts': sys.argv[2],
    'from': sys.argv[3],
    'to': sys.argv[4],
    'type': sys.argv[5],
    'ref': sys.argv[6],
    'body': sys.argv[7]
}
print(json.dumps(msg))
" "$MSG_ID" "$TS" "$FROM" "$TO" "$TYPE" "$REF" "$BODY" >> "$CHANNEL_FILE"

echo "$MSG_ID"
