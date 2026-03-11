#!/usr/bin/env bash
# Mock QA: simulates gemini CLI without API calls
#
# Usage: mock-qa.sh -p <prompt> [--yolo] [--model ...]
#
# Behavior:
#   - Reads the prompt (review request)
#   - Outputs PASS or FAIL verdict
#   - Simulates review with a brief sleep
#
# Environment:
#   MOCK_QA_DELAY    Sleep duration in seconds (default: 1)
#   MOCK_QA_VERDICT  Force verdict: "pass" or "fail" (default: "pass")
#   MOCK_QA_OUTPUT   Custom output text

set -euo pipefail

DELAY="${MOCK_QA_DELAY:-1}"
VERDICT="${MOCK_QA_VERDICT:-pass}"
CUSTOM_OUTPUT="${MOCK_QA_OUTPUT:-}"

# Parse args (mirror gemini interface)
PROMPT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p)           PROMPT="$2"; shift 2 ;;
    --yolo)       shift ;;
    --model)      shift 2 ;;
    --mcp-config) shift 2 ;;
    *)            shift ;;
  esac
done

# Simulate review
sleep "$DELAY"

# Output
if [[ -n "$CUSTOM_OUTPUT" ]]; then
  echo "$CUSTOM_OUTPUT"
elif [[ "$VERDICT" == "fail" ]]; then
  cat << 'EOF'
VERDICT: FAIL

## Issues Found
1. [MAJOR] Missing input validation
   - Expected: Function validates input types
   - Actual: No validation present
   - Suggested fix: Add type checks at function entry

## Tests
- Existing tests pass but new functionality lacks coverage
EOF
elif [[ "$VERDICT" == "pass" ]]; then
  cat << 'EOF'
VERDICT: PASS

## Summary
Implementation meets all acceptance criteria. Code is clean and well-structured.

## Tests
- [X] All tests pass (3 tests, 5 assertions)

## Notes
- Minor: Consider adding docstrings (non-blocking)
EOF
else
  echo "VERDICT: $VERDICT"
fi
