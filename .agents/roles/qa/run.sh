#!/usr/bin/env bash
# QA Runner: wraps gemini CLI for war-room code review
#
# Usage: run.sh <war-room-dir> [--timeout SECONDS]
#
# Reads the engineer's "done" message, runs gemini in non-interactive
# mode to review, and posts pass/fail back to the channel.
#
# Override the QA command with QA_CMD env var (for testing with mocks).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHANNEL="$AGENTS_DIR/channel"

ROOM_DIR="$1"
shift

# Config
CONFIG="$AGENTS_DIR/config.json"
TIMEOUT=$(python3 -c "import json; print(json.load(open('$CONFIG'))['qa']['timeout_seconds'])")
QA_CMD="${QA_CMD:-gemini}"

# Parse optional args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout) TIMEOUT="$2"; shift 2 ;;
    *)         shift ;;
  esac
done

# Read task ref
TASK_REF=$(cat "$ROOM_DIR/task-ref" 2>/dev/null || echo "UNKNOWN")

# Read the engineer's "done" message
DONE_MSG=$("$CHANNEL/read.sh" "$ROOM_DIR" --type done --last 1)
ENGINEER_REPORT=$(echo "$DONE_MSG" | python3 -c "
import json, sys
msgs = json.load(sys.stdin)
if msgs:
    print(msgs[-1]['body'])
else:
    print('No engineer report found.')
" 2>/dev/null || echo "No engineer report found.")

# Read original task
TASK_DESC=$(cat "$ROOM_DIR/task.md" 2>/dev/null || echo "No task description found.")

# Read role prompt
ROLE_PROMPT=$(cat "$SCRIPT_DIR/ROLE.md" 2>/dev/null || echo "")

# Build the prompt
PROMPT="$ROLE_PROMPT

---

## Original Task

$TASK_DESC

## Engineer's Report

$ENGINEER_REPORT

## Instructions

1. Review the code changes described in the engineer's report
2. Verify the implementation meets the task requirements
3. Run tests if applicable
4. Provide your verdict

IMPORTANT: Your response MUST start with exactly one of these lines:
  VERDICT: PASS
  VERDICT: FAIL

Follow with detailed reasoning.
"

# Update status
echo "qa-review" > "$ROOM_DIR/status"

# Run the QA agent
OUTPUT_FILE="$ROOM_DIR/artifacts/qa-output.txt"
mkdir -p "$ROOM_DIR/artifacts"

echo "[QA] Starting review of $TASK_REF in $(basename "$ROOM_DIR")..."

# Execute with timeout
EXIT_CODE=0
if timeout "$TIMEOUT" $QA_CMD -p "$PROMPT" \
    --yolo \
    > "$OUTPUT_FILE" 2>&1; then
  EXIT_CODE=0
else
  EXIT_CODE=$?
fi

# Store PID
echo $$ > "$ROOM_DIR/pids/qa.pid"

# Read output
OUTPUT=$(cat "$OUTPUT_FILE" 2>/dev/null || echo "No output captured")

# Parse verdict from output
VERDICT=$(echo "$OUTPUT" | grep -i "^VERDICT:" | head -1 | awk '{print toupper($2)}' || echo "")

if [[ $EXIT_CODE -eq 124 ]]; then
  # Timeout
  "$CHANNEL/post.sh" "$ROOM_DIR" qa manager error "$TASK_REF" "QA timed out after ${TIMEOUT}s"
  echo "[QA] Timed out on $TASK_REF after ${TIMEOUT}s." >&2
elif [[ "$VERDICT" == "PASS" ]]; then
  "$CHANNEL/post.sh" "$ROOM_DIR" qa manager pass "$TASK_REF" "$OUTPUT"
  echo "[QA] PASSED $TASK_REF."
elif [[ "$VERDICT" == "FAIL" ]]; then
  "$CHANNEL/post.sh" "$ROOM_DIR" qa manager fail "$TASK_REF" "$OUTPUT"
  echo "[QA] FAILED $TASK_REF."
else
  # Could not parse verdict — treat as fail with the full output
  "$CHANNEL/post.sh" "$ROOM_DIR" qa manager fail "$TASK_REF" "Could not parse QA verdict. Full output: $OUTPUT"
  echo "[QA] Could not parse verdict for $TASK_REF — treating as FAIL." >&2
fi

# Clean up PID file
rm -f "$ROOM_DIR/pids/qa.pid"

exit $EXIT_CODE
