#!/usr/bin/env bash
# Agent OS Test Runner
#
# Runs all test suites and reports overall pass/fail.
#
# Usage:
#   run-all.sh [--verbose] [--suite NAME]
#
# Examples:
#   run-all.sh                    # Run all suites
#   run-all.sh --suite channel    # Run only channel tests
#   run-all.sh --verbose          # Show full output

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

VERBOSE=false
SUITE_FILTER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verbose) VERBOSE=true; shift ;;
    --suite)   SUITE_FILTER="$2"; shift 2 ;;
    *)         shift ;;
  esac
done

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║     Ostwin Test Runner v0.1.0         ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

TOTAL_PASSED=0
TOTAL_FAILED=0
SUITE_RESULTS=()

for test_file in "$SCRIPT_DIR"/test-*.sh; do
  [[ -f "$test_file" ]] || continue

  suite_name=$(basename "$test_file" .sh | sed 's/^test-//')

  # Filter if specified
  if [[ -n "$SUITE_FILTER" && "$suite_name" != "$SUITE_FILTER" ]]; then
    continue
  fi

  echo "=== Running: $suite_name ==="

  SUITE_EXIT=0
  if $VERBOSE; then
    bash "$test_file" || SUITE_EXIT=$?
  else
    OUTPUT=$(bash "$test_file" 2>&1) || SUITE_EXIT=$?
    # Show only summary line
    SUMMARY_LINE=$(echo "$OUTPUT" | tail -1)
    echo "  $SUMMARY_LINE"
  fi

  if [[ $SUITE_EXIT -eq 0 ]]; then
    SUITE_RESULTS+=("  [PASS] $suite_name")
    TOTAL_PASSED=$((TOTAL_PASSED + 1))
  else
    SUITE_RESULTS+=("  [FAIL] $suite_name")
    TOTAL_FAILED=$((TOTAL_FAILED + 1))
    if ! $VERBOSE; then
      # On failure, show full output for debugging
      echo ""
      echo "  --- Full output ---"
      echo "$OUTPUT" | sed 's/^/  /'
      echo "  ---"
    fi
  fi

  echo ""
done

# Final summary
echo "╔══════════════════════════════════════╗"
echo "║           TEST RESULTS               ║"
echo "╠══════════════════════════════════════╣"
for result in "${SUITE_RESULTS[@]}"; do
  echo "║ $result"
done
echo "╠══════════════════════════════════════╣"
TOTAL=$((TOTAL_PASSED + TOTAL_FAILED))
echo "║  Total: $TOTAL suites | $TOTAL_PASSED passed | $TOTAL_FAILED failed"
echo "╚══════════════════════════════════════╝"
echo ""

if [[ $TOTAL_FAILED -eq 0 ]]; then
  echo "All tests passed!"
  exit 0
else
  echo "$TOTAL_FAILED suite(s) failed."
  exit 1
fi
