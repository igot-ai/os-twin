#!/usr/bin/env bash
# Test Suite: CLI Entry Point
#
# Tests the ostwin CLI dispatcher and new command scripts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CLI="$AGENTS_DIR/bin/ostwin"

PASS=0
FAIL=0

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "  [PASS] $desc"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $desc"
    echo "    Expected: $expected"
    echo "    Actual:   $actual"
    FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local desc="$1" needle="$2" haystack="$3"
  if echo "$haystack" | grep -q "$needle"; then
    echo "  [PASS] $desc"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $desc (not found: $needle)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Test Suite: CLI Entry Point ==="

# --- Test 1: Help output ---
echo ""
echo "Test 1: Help output"

HELP_OUTPUT=$("$CLI" --help 2>&1)
assert_contains "Help shows 'ostwin'" "ostwin" "$HELP_OUTPUT"
assert_contains "Help shows 'run'" "run" "$HELP_OUTPUT"
assert_contains "Help shows 'status'" "status" "$HELP_OUTPUT"
assert_contains "Help shows 'stop'" "stop" "$HELP_OUTPUT"
assert_contains "Help shows 'logs'" "logs" "$HELP_OUTPUT"
assert_contains "Help shows 'init'" "init" "$HELP_OUTPUT"
assert_contains "Help shows 'dashboard'" "dashboard" "$HELP_OUTPUT"

# --- Test 2: Version output ---
echo ""
echo "Test 2: Version output"

VERSION_OUTPUT=$("$CLI" version 2>&1)
assert_contains "Version shows v0" "v0" "$VERSION_OUTPUT"

# --- Test 3: Unknown command ---
echo ""
echo "Test 3: Unknown command"

UNKNOWN_EXIT=0
UNKNOWN_OUTPUT=$("$CLI" foobar 2>&1) || UNKNOWN_EXIT=$?
assert_eq "Unknown command exits non-zero" "1" "$UNKNOWN_EXIT"
assert_contains "Unknown command shows error" "Unknown command" "$UNKNOWN_OUTPUT"

# --- Test 4: Config command ---
echo ""
echo "Test 4: Config command"

CONFIG_OUTPUT=$("$AGENTS_DIR/config.sh" 2>&1)
assert_contains "Config shows version" "version" "$CONFIG_OUTPUT"
assert_contains "Config shows manager" "manager" "$CONFIG_OUTPUT"

CONFIG_GET=$("$AGENTS_DIR/config.sh" --get version 2>&1)
assert_contains "Config --get version" "0.1.0" "$CONFIG_GET"

# --- Test 5: Health command ---
echo ""
echo "Test 5: Health command"

HEALTH_OUTPUT=$("$AGENTS_DIR/health.sh" 2>&1)
assert_contains "Health shows status" "Status" "$HEALTH_OUTPUT"
assert_contains "Health shows Manager" "Manager" "$HEALTH_OUTPUT"

HEALTH_JSON=$("$AGENTS_DIR/health.sh" --json 2>&1)
assert_contains "Health JSON has status" "status" "$HEALTH_JSON"
assert_contains "Health JSON has rooms" "rooms" "$HEALTH_JSON"

# --- Test 6: Stop when not running ---
echo ""
echo "Test 6: Stop when not running"

STOP_OUTPUT=$("$AGENTS_DIR/stop.sh" 2>&1)
assert_contains "Stop shows no manager" "No manager" "$STOP_OUTPUT"

# --- Summary ---
echo ""
echo "CLI Tests: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
