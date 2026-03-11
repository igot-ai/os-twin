#!/usr/bin/env bash
# Engineer Runner: wraps deepagents CLI for war-room execution
#
# Usage: run.sh <war-room-dir> [--timeout SECONDS]
#
# Reads the task from the war-room channel, runs deepagents in non-interactive
# mode with MCP tools, and posts the result back to the channel.
#
# Override the engineer command with ENGINEER_CMD env var (for testing with mocks).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHANNEL="$AGENTS_DIR/channel"

ROOM_DIR="$1"
shift

# Config
CONFIG="$AGENTS_DIR/config.json"
MODEL=$(python3 -c "import json; print(json.load(open('$CONFIG'))['engineer']['default_model'])")
TIMEOUT=$(python3 -c "import json; print(json.load(open('$CONFIG'))['engineer']['timeout_seconds'])")
ENGINEER_CMD="${ENGINEER_CMD:-deepagents}"

# Parse optional args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout) TIMEOUT="$2"; shift 2 ;;
    *)         shift ;;
  esac
done

# Read task ref
TASK_REF=$(cat "$ROOM_DIR/task-ref" 2>/dev/null || echo "UNKNOWN")

# Read the latest task or fix message
LATEST_MSG=$("$CHANNEL/read.sh" "$ROOM_DIR" --last 1)
LATEST_BODY=$(echo "$LATEST_MSG" | python3 -c "
import json, sys
msgs = json.load(sys.stdin)
for m in reversed(msgs):
    if m['type'] in ('task', 'fix'):
        print(m['body'])
        break
else:
    print('')
" 2>/dev/null || echo "")

# Read full task description
TASK_DESC=$(cat "$ROOM_DIR/task.md" 2>/dev/null || echo "No task description found.")

# Read role prompt
ROLE_PROMPT=$(cat "$SCRIPT_DIR/ROLE.md" 2>/dev/null || echo "")

# Build the prompt
PROMPT="$ROLE_PROMPT

---

## Your Task

$TASK_DESC

## Latest Instruction

$LATEST_BODY

## War-Room

Room: $(basename "$ROOM_DIR")
Task Ref: $TASK_REF
Working Directory: $(pwd)

## Instructions

1. Implement the task described above
2. When done, summarize your changes clearly
3. Format your summary with: Changes Made, Files Modified, How to Test
"

# Update status
echo "engineering" > "$ROOM_DIR/status"

# Run the engineer agent
OUTPUT_FILE="$ROOM_DIR/artifacts/engineer-output.txt"
mkdir -p "$ROOM_DIR/artifacts"

echo "[ENGINEER] Starting work on $TASK_REF in $(basename "$ROOM_DIR")..."

# Execute with timeout, capture output
EXIT_CODE=0
if timeout "$TIMEOUT" $ENGINEER_CMD -n "$PROMPT" \
    --auto-approve \
    --shell-allow-list all \
    --model "$MODEL" \
    > "$OUTPUT_FILE" 2>&1; then
  EXIT_CODE=0
else
  EXIT_CODE=$?
fi

# Store PID (for live agents, PID is captured before wait)
echo $$ > "$ROOM_DIR/pids/engineer.pid"

# Read output
OUTPUT=$(cat "$OUTPUT_FILE" 2>/dev/null || echo "No output captured")

# Post result to channel
if [[ $EXIT_CODE -eq 0 ]]; then
  "$CHANNEL/post.sh" "$ROOM_DIR" engineer manager done "$TASK_REF" "$OUTPUT"
  echo "[ENGINEER] Completed $TASK_REF successfully."
elif [[ $EXIT_CODE -eq 124 ]]; then
  # Timeout
  "$CHANNEL/post.sh" "$ROOM_DIR" engineer manager error "$TASK_REF" "Engineer timed out after ${TIMEOUT}s"
  echo "[ENGINEER] Timed out on $TASK_REF after ${TIMEOUT}s." >&2
else
  "$CHANNEL/post.sh" "$ROOM_DIR" engineer manager error "$TASK_REF" "Engineer exited with code $EXIT_CODE: $OUTPUT"
  echo "[ENGINEER] Failed on $TASK_REF with exit code $EXIT_CODE." >&2
fi

# Clean up PID file
rm -f "$ROOM_DIR/pids/engineer.pid"

exit $EXIT_CODE
