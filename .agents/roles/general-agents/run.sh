#!/usr/bin/env bash
# [ROLE_NAME] Runner: wraps deepagents CLI for war-room execution
#
# Usage: run.sh <war-room-dir> [--timeout SECONDS]
#
# Reads the necessary context from the war-room channel, runs deepagents 
# in non-interactive mode with MCP tools, and posts the result back.
#
# Override the command with [ROLE]_CMD env var (for testing with mocks).

set -euo pipefail

# --- 1. System & Environment Setup ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHANNEL="$AGENTS_DIR/channel"

# Source shared utilities
source "$AGENTS_DIR/lib/utils.sh" 2>/dev/null || true
source "$AGENTS_DIR/lib/log.sh" 2>/dev/null || true

ROOM_DIR="${1:-}"
if [ -z "$ROOM_DIR" ]; then
  echo "Error: Must provide <war-room-dir>"
  exit 1
fi
shift

# --- 2. Configuration Parsing ---
# Load role-specific settings from config.json
CONFIG="${AGENT_OS_CONFIG:-$AGENTS_DIR/config.json}"
# TODO: Replace '[role]' with the actual role key in config.json (e.g., 'engineer', 'qa')
TIMEOUT=$(python3 -c "import json; print(json.load(open('$CONFIG'))['[role]']['timeout_seconds'])" 2>/dev/null || echo "300")
# TODO: Replace '[ROLE]' with the environment variable prefix for this role
ROLE_CMD="${[ROLE]_CMD:-deepagents}"

# Parse optional command-line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --timeout) TIMEOUT="$2"; shift 2 ;;
    *)         shift ;;
  esac
done

# --- 3. Gather War-Room Context ---
# Determine task reference and type (Epic vs Task)
TASK_REF=$(cat "$ROOM_DIR/task-ref" 2>/dev/null || echo "UNKNOWN")
IS_EPIC=false
case "$TASK_REF" in
  EPIC-*) IS_EPIC=true ;;
esac

# Read the core task description
TASK_DESC=$(cat "$ROOM_DIR/brief.md" 2>/dev/null || echo "No task description found.")

# Read the ROLE.md prompt for this specific role
ROLE_PROMPT=$(cat "$SCRIPT_DIR/ROLE.md" 2>/dev/null || echo "")

# --- 4. Role-Specific Input Gathering ---
# TODO: Insert logic to read the latest relevant messages from the channel for this role
# e.g., for an engineer reading 'task'/'fix', or QA reading 'done'
LATEST_MSG_BODY=$("$CHANNEL/read.sh" "$ROOM_DIR" --last 1 | python3 -c "
import json, sys
try:
    msgs = json.load(sys.stdin)
    # Customize the message types this role cares about
    target_types = ['[target_type]'] 
    for m in reversed(msgs):
        if m.get('type') in target_types:
            print(m.get('body', ''))
            break
    else:
        print('')
except:
    print('')
" 2>/dev/null || echo "")

# --- 5. Build the Prompt ---
# Construct the final prompt instructions to pass to the agent
# TODO: Inject role-specific instructions, especially handling EPIC vs TASK differences
ROLE_INSTRUCTIONS=""
if [[ "$IS_EPIC" == "true" ]]; then
  ROLE_INSTRUCTIONS="[Epic-specific instructions for this role]"
else
  ROLE_INSTRUCTIONS="[Task-specific instructions for this role]"
fi

PROMPT="$ROLE_PROMPT

---

## Task Context
$TASK_DESC

---

## Latest Updates
$LATEST_MSG_BODY

---

## Instructions
$ROLE_INSTRUCTIONS"

# --- 6. Execution ---
# Execute the deepagents CLI with the constructed prompt
# TODO: Pass any additional flags or environment variables required by the specific role
export OS_TWIN_WAR_ROOM="$ROOM_DIR"

log INFO "Running [ROLE_NAME] in $ROOM_DIR (Timeout: ${TIMEOUT}s)" 2>/dev/null || echo "Running [ROLE_NAME] in $ROOM_DIR..."

set +e
# Run the agent in non-interactive mode. Assuming deepagents takes a prompt via stdin or file.
echo "$PROMPT" | $ROLE_CMD --non-interactive --timeout "$TIMEOUT"
EXIT_CODE=$?
set -e

# --- 7. Post-Execution Cleanup/Reporting ---
# TODO: Handle exit codes or post-run logging specific to the role
if [ $EXIT_CODE -ne 0 ]; then
  log ERROR "[ROLE_NAME] failed with exit code $EXIT_CODE" 2>/dev/null || echo "Error: [ROLE_NAME] failed ($EXIT_CODE)"
  exit $EXIT_CODE
fi

exit 0