#!/usr/bin/env bash
# Teardown a war-room: kill processes, clean up, optionally archive
#
# Usage: teardown.sh <room-id> [--archive] [--force]
#
# Example:
#   teardown.sh room-001              # Graceful shutdown
#   teardown.sh room-001 --archive    # Archive channel log before cleanup
#   teardown.sh room-001 --force      # Force kill (SIGKILL)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

ROOM_ID="$1"
shift

ARCHIVE=false
FORCE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive) ARCHIVE=true; shift ;;
    --force)   FORCE=true; shift ;;
    *)         shift ;;
  esac
done

ROOM_DIR="$SCRIPT_DIR/$ROOM_ID"

if [[ ! -d "$ROOM_DIR" ]]; then
  echo "[ERROR] War-room '$ROOM_ID' not found at $ROOM_DIR" >&2
  exit 1
fi

echo "[TEARDOWN] Shutting down war-room '$ROOM_ID'..."

# 1. Kill all tracked processes
SIGNAL="TERM"
$FORCE && SIGNAL="KILL"

for pid_file in "$ROOM_DIR"/pids/*.pid; do
  [[ -f "$pid_file" ]] || continue
  pid=$(cat "$pid_file")
  if kill -0 "$pid" 2>/dev/null; then
    echo "  Killing PID $pid (SIG$SIGNAL)..."
    kill -"$SIGNAL" "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
done

# 2. Wait briefly for graceful shutdown
if ! $FORCE; then
  sleep 2
  # Force kill any remaining
  for pid_file in "$ROOM_DIR"/pids/*.pid; do
    [[ -f "$pid_file" ]] || continue
    pid=$(cat "$pid_file")
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    rm -f "$pid_file"
  done
fi

# 3. Archive channel log if requested
if $ARCHIVE && [[ -f "$ROOM_DIR/channel.jsonl" ]]; then
  ARCHIVE_DIR="$SCRIPT_DIR/../.archives"
  mkdir -p "$ARCHIVE_DIR"
  ARCHIVE_FILE="$ARCHIVE_DIR/${ROOM_ID}-$(date +%Y%m%d-%H%M%S).jsonl"
  cp "$ROOM_DIR/channel.jsonl" "$ARCHIVE_FILE"
  echo "  Archived channel to: $ARCHIVE_FILE"
fi

# 4. Clean up room directory
rm -rf "$ROOM_DIR"

echo "[TEARDOWN] War-room '$ROOM_ID' removed."
