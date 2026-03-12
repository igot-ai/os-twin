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
PYTHON="${AGENTS_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"
CHANNEL="$AGENTS_DIR/channel"

# Source shared utilities
source "$AGENTS_DIR/lib/utils.sh" 2>/dev/null || true
source "$AGENTS_DIR/lib/log.sh" 2>/dev/null || true

ROOM_DIR="$1"
shift

# Config
CONFIG="${AGENT_OS_CONFIG:-$AGENTS_DIR/config.json}"
MODEL=$("$PYTHON" -c "import json; print(json.load(open('$CONFIG'))['engineer']['default_model'])")
TIMEOUT=$("$PYTHON" -c "import json; print(json.load(open('$CONFIG'))['engineer']['timeout_seconds'])")
MAX_PROMPT_BYTES=$("$PYTHON" -c "import json; c=json.load(open('$CONFIG')); print(c['engineer'].get('max_prompt_bytes', 102400))")
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

# Detect Epic vs Task
IS_EPIC=false
case "$TASK_REF" in
  EPIC-*) IS_EPIC=true ;;
esac

# Read the latest task or fix message
LATEST_MSG=$("$CHANNEL/read.sh" "$ROOM_DIR" --last 1)
LATEST_BODY=$(echo "$LATEST_MSG" | "$PYTHON" -c "
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
TASK_DESC=$(cat "$ROOM_DIR/brief.md" 2>/dev/null || echo "No task description found.")

# Parse working_dir from brief.md metadata (first line matching "working_dir:" or from config)
WORKING_DIR=$("$PYTHON" -c "
import re
with open('$ROOM_DIR/brief.md', 'r') as f:
    content = f.read()
m = re.search(r'working_dir:\s*(.+)', content)
if m:
    print(m.group(1).strip())
else:
    print('$(pwd)')
" 2>/dev/null || echo "$(pwd)")

# Read role prompt
ROLE_PROMPT=$(cat "$SCRIPT_DIR/ROLE.md" 2>/dev/null || echo "")

# Build instructions based on Epic vs Task
ROOM_NAME=$(basename "$ROOM_DIR")

if [[ "$IS_EPIC" == "true" ]]; then
  ENG_INSTRUCTIONS="You are working on an EPIC — a high-level feature that you must plan and implement yourself.

### Phase 1 — Planning
1. Analyze the brief above and break it into concrete sub-tasks
2. Create a file called TASKS.md at: $ROOM_DIR/TASKS.md
   - Use markdown checkboxes: - [ ] TASK-001 — Description
   - Each sub-task should be independently testable
   - Include acceptance criteria for each sub-task
3. Save TASKS.md before proceeding to implementation

### Phase 2 — Implementation
1. Work through each sub-task in TASKS.md sequentially
2. After completing each sub-task, check it off: - [x] TASK-001 — Description
3. Write tests as you go — each sub-task should be verified before moving on

### Phase 3 — Reporting
1. Ensure all checkboxes in TASKS.md are checked
2. Summarize your changes with:
   - Epic overview: what was delivered
   - Sub-tasks completed (include the final TASKS.md checklist)
   - Files modified/created
   - How to test the full epic"
else
  ENG_INSTRUCTIONS="1. Implement the task described above
2. When done, summarize your changes clearly
3. Format your summary with: Changes Made, Files Modified, How to Test"
fi

# Build the prompt
PROMPT="$ROLE_PROMPT

---

## Your Task

$TASK_DESC

## Latest Instruction

$LATEST_BODY

## War-Room

Room: $ROOM_NAME
Task Ref: $TASK_REF
Working Directory: $WORKING_DIR

## Instructions

$ENG_INSTRUCTIONS
"

# Prompt size guard — truncate if exceeds max
PROMPT_SIZE=${#PROMPT}
if [ "$PROMPT_SIZE" -gt "$MAX_PROMPT_BYTES" ]; then
  PROMPT="${PROMPT:0:$MAX_PROMPT_BYTES}

[TRUNCATED: prompt was ${PROMPT_SIZE} bytes, max is ${MAX_PROMPT_BYTES}. Full task description in: $ROOM_DIR/brief.md]"
  log WARN "Prompt truncated from $PROMPT_SIZE to $MAX_PROMPT_BYTES bytes for $TASK_REF" 2>/dev/null || true
fi

# NOTE: Status is set by the manager (loop.sh), not here — avoids race condition

# Run the engineer agent
OUTPUT_FILE="$ROOM_DIR/artifacts/engineer-output.txt"
mkdir -p "$ROOM_DIR/artifacts" "$ROOM_DIR/pids"

# Write PID BEFORE execution so manager can track the running process
echo $$ > "$ROOM_DIR/pids/engineer.pid"

log INFO "Starting work on $TASK_REF in $(basename "$ROOM_DIR")..." 2>/dev/null || echo "[ENGINEER] Starting work on $TASK_REF in $(basename "$ROOM_DIR")..."

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

# Read output
OUTPUT=$(cat "$OUTPUT_FILE" 2>/dev/null || echo "No output captured")

# Post result to channel
if [[ $EXIT_CODE -eq 0 ]]; then
  "$CHANNEL/post.sh" "$ROOM_DIR" engineer manager done "$TASK_REF" "$OUTPUT"
  log INFO "Completed $TASK_REF successfully." 2>/dev/null || echo "[ENGINEER] Completed $TASK_REF successfully."
elif [[ $EXIT_CODE -eq 124 ]]; then
  # Timeout
  "$CHANNEL/post.sh" "$ROOM_DIR" engineer manager error "$TASK_REF" "Engineer timed out after ${TIMEOUT}s"
  log ERROR "Timed out on $TASK_REF after ${TIMEOUT}s." 2>/dev/null || echo "[ENGINEER] Timed out on $TASK_REF after ${TIMEOUT}s." >&2
else
  "$CHANNEL/post.sh" "$ROOM_DIR" engineer manager error "$TASK_REF" "Engineer exited with code $EXIT_CODE: $OUTPUT"
  log ERROR "Failed on $TASK_REF with exit code $EXIT_CODE." 2>/dev/null || echo "[ENGINEER] Failed on $TASK_REF with exit code $EXIT_CODE." >&2
fi

# Clean up PID file
rm -f "$ROOM_DIR/pids/engineer.pid"

exit $EXIT_CODE
