#!/usr/bin/env bash
# Create a new war-room
#
# Usage: create.sh <room-id> <task-ref> <task-description> [--working-dir PATH]
#
# Example:
#   create.sh room-001 TASK-001 "Implement user authentication module"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHANNEL="$AGENTS_DIR/channel"

ROOM_ID="$1"
TASK_REF="$2"
TASK_DESC="$3"
WORKING_DIR="${4:-.}"
DEPENDENCIES="${5:-}"

# War-room data location (project-scoped via WARROOMS_DIR, fallback to script dir)
WARROOMS_DATA="${WARROOMS_DIR:-$SCRIPT_DIR}"
mkdir -p "$WARROOMS_DATA"
ROOM_DIR="$WARROOMS_DATA/$ROOM_ID"

# Prevent overwriting existing room
if [[ -d "$ROOM_DIR" ]]; then
  echo "[ERROR] War-room '$ROOM_ID' already exists at $ROOM_DIR" >&2
  exit 1
fi

# Create room structure
mkdir -p "$ROOM_DIR"/{pids,artifacts}

# Initialize channel (with flock for concurrent safety)
touch "$ROOM_DIR/channel.jsonl"

# Write assignment brief
cat > "$ROOM_DIR/brief.md" << EOF
# $TASK_REF

$TASK_DESC

## Working Directory
$WORKING_DIR

## Created
$(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF

# Initialize status
echo "pending" > "$ROOM_DIR/status"

# Initialize retry counter
echo "0" > "$ROOM_DIR/retries"

# Store task ref for quick lookup
echo "$TASK_REF" > "$ROOM_DIR/task-ref"

# Post initial task message to channel
"$CHANNEL/post.sh" "$ROOM_DIR" manager engineer task "$TASK_REF" "$TASK_DESC"

echo "[CREATED] War-room '$ROOM_ID' for $TASK_REF"
echo "  Path: $ROOM_DIR"
echo "  Status: pending"
