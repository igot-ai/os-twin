#!/usr/bin/env bash
# Mock Engineer: simulates deepagents without API calls
#
# Usage: mock-engineer.sh -n <prompt> [--auto-approve] [--shell-allow-list ...] [--model ...]
#
# Behavior:
#   - Reads the prompt
#   - Creates a dummy artifact file
#   - Outputs a structured "done" report
#   - Simulates work with a brief sleep
#
# Environment:
#   MOCK_ENGINEER_DELAY    Sleep duration in seconds (default: 1)
#   MOCK_ENGINEER_FAIL     Set to "true" to simulate failure (exit 1)
#   MOCK_ENGINEER_OUTPUT   Custom output text

set -euo pipefail

DELAY="${MOCK_ENGINEER_DELAY:-1}"
SHOULD_FAIL="${MOCK_ENGINEER_FAIL:-false}"
CUSTOM_OUTPUT="${MOCK_ENGINEER_OUTPUT:-}"

# Parse args (mirror deepagents interface)
PROMPT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n)              PROMPT="$2"; shift 2 ;;
    --auto-approve)  shift ;;
    --shell-allow-list) shift 2 ;;
    --model)         shift 2 ;;
    --mcp-config)    shift 2 ;;
    *)               shift ;;
  esac
done

# Simulate work
sleep "$DELAY"

# Check for failure mode
if [[ "$SHOULD_FAIL" == "true" ]]; then
  echo "ERROR: Mock engineer simulated failure" >&2
  exit 1
fi

# Output
if [[ -n "$CUSTOM_OUTPUT" ]]; then
  echo "$CUSTOM_OUTPUT"
else
  cat << 'EOF'
## Changes Made
- Created implementation as requested
- Added necessary supporting code

## Files Modified
- src/feature.py (created)

## How to Test
- Run: python src/feature.py
- Expected: Feature works as described in task

VERDICT: Implementation complete.
EOF
fi
