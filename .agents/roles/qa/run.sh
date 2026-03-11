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

# Source shared utilities
source "$AGENTS_DIR/lib/utils.sh" 2>/dev/null || true
source "$AGENTS_DIR/lib/log.sh" 2>/dev/null || true

ROOM_DIR="$1"
shift

# Config
CONFIG="${AGENT_OS_CONFIG:-$AGENTS_DIR/config.json}"
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

# Detect Epic vs Task
IS_EPIC=false
case "$TASK_REF" in
  EPIC-*) IS_EPIC=true ;;
esac

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
TASK_DESC=$(cat "$ROOM_DIR/brief.md" 2>/dev/null || echo "No task description found.")

# Read TASKS.md for Epic reviews
TASKS_MD=""
if [[ "$IS_EPIC" == "true" ]]; then
  TASKS_MD=$(cat "$ROOM_DIR/TASKS.md" 2>/dev/null || echo "")
fi

# Read role prompt
ROLE_PROMPT=$(cat "$SCRIPT_DIR/ROLE.md" 2>/dev/null || echo "")

# Build the prompt
PROMPT="$ROLE_PROMPT

---

## Original Assignment

$TASK_DESC

## Engineer's Report

$ENGINEER_REPORT
$(if [[ "$IS_EPIC" == "true" ]] && [[ -n "$TASKS_MD" ]]; then
cat << TASKSECTION

## Engineer's Task Breakdown (TASKS.md)

$TASKS_MD
TASKSECTION
fi)

## Instructions

$(if [[ "$IS_EPIC" == "true" ]]; then
cat << 'EPICQA'
You are reviewing an EPIC — a complete feature delivered by the engineer.

1. Review ALL code changes holistically across the full epic
2. Verify the TASKS.md checklist is complete — all sub-tasks must be checked off
3. Verify each sub-task was actually implemented (not just checked off)
4. Run the project's test suite
5. Validate the epic delivers the feature described in the brief
6. Provide your verdict
EPICQA
else
cat << 'TASKQA'
1. Review the code changes described in the engineer's report
2. Verify the implementation meets the task requirements
3. Run tests if applicable
4. Provide your verdict
TASKQA
fi)

IMPORTANT: Your response MUST include exactly one of these lines:
  VERDICT: PASS
  VERDICT: FAIL

Follow with detailed reasoning.
"

# NOTE: Status is set by the manager (loop.sh), not here — avoids race condition

# Run the QA agent
OUTPUT_FILE="$ROOM_DIR/artifacts/qa-output.txt"
mkdir -p "$ROOM_DIR/artifacts" "$ROOM_DIR/pids"

# Write PID BEFORE execution so manager can track the running process
echo $$ > "$ROOM_DIR/pids/qa.pid"

log INFO "Starting review of $TASK_REF in $(basename "$ROOM_DIR")..." 2>/dev/null || echo "[QA] Starting review of $TASK_REF in $(basename "$ROOM_DIR")..."

# Execute with timeout
EXIT_CODE=0
if timeout "$TIMEOUT" $QA_CMD -p "$PROMPT" \
    --yolo \
    > "$OUTPUT_FILE" 2>&1; then
  EXIT_CODE=0
else
  EXIT_CODE=$?
fi

# Read output
OUTPUT=$(cat "$OUTPUT_FILE" 2>/dev/null || echo "No output captured")

# Parse verdict from output — multi-strategy for robustness:
# 1. Try strict match: line starts with VERDICT:
# 2. Fallback: VERDICT: anywhere in line
# 3. Last resort: scan for standalone PASS/FAIL keywords in first 20 lines
VERDICT=$(echo "$OUTPUT" | grep -i "^VERDICT:" | head -1 | awk '{print toupper($2)}' || echo "")

if [[ -z "$VERDICT" ]]; then
  # Fallback: VERDICT: anywhere in a line
  VERDICT=$(echo "$OUTPUT" | grep -i "VERDICT:" | head -1 | sed 's/.*VERDICT:\s*//' | awk '{print toupper($1)}' || echo "")
fi

if [[ -z "$VERDICT" ]]; then
  # Last resort: look for standalone PASS or FAIL in first 20 lines
  VERDICT=$(echo "$OUTPUT" | head -20 | grep -iow 'PASS\|FAIL' | head -1 | awk '{print toupper($0)}' || echo "")
fi

if [[ $EXIT_CODE -eq 124 ]]; then
  # Timeout
  "$CHANNEL/post.sh" "$ROOM_DIR" qa manager error "$TASK_REF" "QA timed out after ${TIMEOUT}s"
  log ERROR "Timed out on $TASK_REF after ${TIMEOUT}s." 2>/dev/null || echo "[QA] Timed out on $TASK_REF after ${TIMEOUT}s." >&2
elif [[ "$VERDICT" == "PASS" ]]; then
  "$CHANNEL/post.sh" "$ROOM_DIR" qa manager pass "$TASK_REF" "$OUTPUT"
  log INFO "PASSED $TASK_REF." 2>/dev/null || echo "[QA] PASSED $TASK_REF."
elif [[ "$VERDICT" == "FAIL" ]]; then
  "$CHANNEL/post.sh" "$ROOM_DIR" qa manager fail "$TASK_REF" "$OUTPUT"
  log INFO "FAILED $TASK_REF." 2>/dev/null || echo "[QA] FAILED $TASK_REF."
else
  # Could not parse verdict — post as 'error' type so manager can distinguish
  # from a real QA rejection (saves retry budget)
  "$CHANNEL/post.sh" "$ROOM_DIR" qa manager error "$TASK_REF" "Could not parse QA verdict. Full output: $OUTPUT"
  log WARN "Could not parse verdict for $TASK_REF — posting as error." 2>/dev/null || echo "[QA] Could not parse verdict for $TASK_REF — posting as error." >&2
fi

# Clean up PID file
rm -f "$ROOM_DIR/pids/qa.pid"

exit $EXIT_CODE
