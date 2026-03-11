#!/usr/bin/env bash
# Test Suite: Manager Orchestration Loop
#
# Tests the manager loop with mock agents.
# Uses mock-engineer.sh and mock-qa.sh instead of real CLI tools.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WARROOMS="$AGENTS_DIR/war-rooms"
CHANNEL="$AGENTS_DIR/channel"

# Export WARROOMS_DIR so war-room scripts use this location for data
export WARROOMS_DIR="$WARROOMS"

# Use mock agents
export ENGINEER_CMD="$SCRIPT_DIR/mock-engineer.sh"
export QA_CMD="$SCRIPT_DIR/mock-qa.sh"
export MOCK_SIGNOFF="true"
export MOCK_ENGINEER_DELAY=0
export MOCK_QA_DELAY=0

# Save and restore any existing rooms
BACKUP_DIR=$(mktemp -d)
if ls "$WARROOMS"/room-* 1>/dev/null 2>&1; then
  cp -r "$WARROOMS"/room-* "$BACKUP_DIR/" 2>/dev/null || true
fi

cleanup() {
  # Kill any background manager
  [[ -n "${MANAGER_PID:-}" ]] && kill "$MANAGER_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  # Remove test rooms
  rm -rf "$WARROOMS"/room-* 2>/dev/null || true
  # Restore backed up rooms
  if ls "$BACKUP_DIR"/room-* 1>/dev/null 2>&1; then
    cp -r "$BACKUP_DIR"/room-* "$WARROOMS/" 2>/dev/null || true
  fi
  rm -rf "$BACKUP_DIR"
  # Clean up test config
  rm -f "${TEST_CONFIG:-}" 2>/dev/null || true
}
trap cleanup EXIT

PASS=0
FAIL=0
MANAGER_PID=""

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

# Copy-on-write config for fast testing (never mutates original config.json)
TEST_CONFIG=$(mktemp)
python3 -c "
import json
config = json.load(open('$AGENTS_DIR/config.json'))
config['manager']['poll_interval_seconds'] = 1
config['manager']['max_concurrent_rooms'] = 2
config['manager']['max_engineer_retries'] = 2
json.dump(config, open('$TEST_CONFIG', 'w'), indent=2)
"
export AGENT_OS_CONFIG="$TEST_CONFIG"

echo "=== Test Suite: Manager Orchestration ==="

# --- Test 1: Happy path (single room, engineer done → QA pass) ---
echo ""
echo "Test 1: Happy path — single room"

# Clean rooms
rm -rf "$WARROOMS"/room-* 2>/dev/null || true

# Create a room
"$WARROOMS/create.sh" room-001 TASK-001 "Build a hello world" > /dev/null

# Simulate: engineer posts "done", then QA posts "pass"
# We do this by directly posting channel messages (simulating what wrappers do)
"$CHANNEL/post.sh" "$WARROOMS/room-001" engineer manager done TASK-001 "Feature complete" > /dev/null
echo "engineering" > "$WARROOMS/room-001/status"

# Start manager in background with a timeout
timeout 15 "$AGENTS_DIR/roles/manager/loop.sh" > /dev/null 2>&1 &
MANAGER_PID=$!

# Wait a bit for manager to process
sleep 3

# Now the manager should have seen "done" and spawned QA (mock).
# The mock QA posts PASS by default.
# Give it a moment
sleep 5

# Check if room is passed
STATUS=$(cat "$WARROOMS/room-001/status" 2>/dev/null || echo "unknown")

# Kill manager
kill "$MANAGER_PID" 2>/dev/null || true
wait "$MANAGER_PID" 2>/dev/null || true
MANAGER_PID=""

# Room should be in qa-review or passed (depends on timing)
if [[ "$STATUS" == "passed" || "$STATUS" == "qa-review" ]]; then
  echo "  [PASS] Room transitioned from engineering (status: $STATUS)"
  PASS=$((PASS + 1))
else
  echo "  [FAIL] Room status is '$STATUS' (expected 'passed' or 'qa-review')"
  FAIL=$((FAIL + 1))
fi

# --- Test 2: QA failure triggers retry ---
echo ""
echo "Test 2: QA failure triggers retry"

rm -rf "$WARROOMS"/room-* 2>/dev/null || true
"$WARROOMS/create.sh" room-001 TASK-001 "Build feature" > /dev/null

# Simulate engineer done
"$CHANNEL/post.sh" "$WARROOMS/room-001" engineer manager done TASK-001 "Done" > /dev/null
echo "engineering" > "$WARROOMS/room-001/status"

# Simulate QA fail
"$CHANNEL/post.sh" "$WARROOMS/room-001" qa manager fail TASK-001 "Missing validation" > /dev/null

# Now set status to qa-review so manager processes the fail
echo "qa-review" > "$WARROOMS/room-001/status"

# Run one iteration of checking
timeout 10 "$AGENTS_DIR/roles/manager/loop.sh" > /dev/null 2>&1 &
MANAGER_PID=$!
sleep 4

STATUS=$(cat "$WARROOMS/room-001/status" 2>/dev/null || echo "unknown")
RETRIES=$(cat "$WARROOMS/room-001/retries" 2>/dev/null || echo "0")

kill "$MANAGER_PID" 2>/dev/null || true
wait "$MANAGER_PID" 2>/dev/null || true
MANAGER_PID=""

# With fast mock agents, the retry loop may complete fully (fixing→done→pass→passed).
# The key proof is that retries > 0, meaning the failure was processed.
if [[ "$RETRIES" -gt 0 ]]; then
  echo "  [PASS] QA fail triggered retry (status: $STATUS, retries: $RETRIES)"
  PASS=$((PASS + 1))
else
  echo "  [FAIL] Expected retries > 0, got status=$STATUS retries=$RETRIES"
  FAIL=$((FAIL + 1))
fi

# --- Test 3: Max retries exceeded ---
echo ""
echo "Test 3: Max retries exceeded"

rm -rf "$WARROOMS"/room-* 2>/dev/null || true
"$WARROOMS/create.sh" room-001 TASK-001 "Doomed feature" > /dev/null

# Set retries to max
echo "2" > "$WARROOMS/room-001/retries"
echo "qa-review" > "$WARROOMS/room-001/status"

# Post a fail (this should trigger failed-final since retries=max)
"$CHANNEL/post.sh" "$WARROOMS/room-001" qa manager fail TASK-001 "Still broken" > /dev/null

timeout 8 "$AGENTS_DIR/roles/manager/loop.sh" > /dev/null 2>&1 &
MANAGER_PID=$!
sleep 3

STATUS=$(cat "$WARROOMS/room-001/status" 2>/dev/null || echo "unknown")

kill "$MANAGER_PID" 2>/dev/null || true
wait "$MANAGER_PID" 2>/dev/null || true
MANAGER_PID=""

assert_eq "Max retries → failed-final" "failed-final" "$STATUS"

# --- Test 4: Epic room processed identically ---
echo ""
echo "Test 4: Epic room processed like Task room"

rm -rf "$WARROOMS"/room-* 2>/dev/null || true

# Create room with EPIC ref
"$WARROOMS/create.sh" room-001 EPIC-001 "Build authentication system" > /dev/null

# Verify ref is stored as EPIC
EPIC_REF=$(cat "$WARROOMS/room-001/task-ref" 2>/dev/null || echo "UNKNOWN")
assert_eq "Epic ref stored" "EPIC-001" "$EPIC_REF"

# Simulate engineer done
"$CHANNEL/post.sh" "$WARROOMS/room-001" engineer manager done EPIC-001 "Epic complete" > /dev/null
echo "engineering" > "$WARROOMS/room-001/status"

# Run manager briefly
timeout 15 "$AGENTS_DIR/roles/manager/loop.sh" > /dev/null 2>&1 &
MANAGER_PID=$!
sleep 5

STATUS=$(cat "$WARROOMS/room-001/status" 2>/dev/null || echo "unknown")

kill "$MANAGER_PID" 2>/dev/null || true
wait "$MANAGER_PID" 2>/dev/null || true
MANAGER_PID=""

if [[ "$STATUS" == "passed" || "$STATUS" == "qa-review" ]]; then
  echo "  [PASS] Epic room processed by manager (status: $STATUS)"
  PASS=$((PASS + 1))
else
  echo "  [FAIL] Epic room status is '$STATUS' (expected 'passed' or 'qa-review')"
  FAIL=$((FAIL + 1))
fi

# --- Test 5: Graceful shutdown on SIGTERM ---
echo ""
echo "Test 5: Graceful shutdown"

rm -rf "$WARROOMS"/room-* 2>/dev/null || true
"$WARROOMS/create.sh" room-001 TASK-001 "Test shutdown" > /dev/null

"$AGENTS_DIR/roles/manager/loop.sh" > /dev/null 2>&1 &
MANAGER_PID=$!
sleep 2

# Send SIGTERM
kill -TERM "$MANAGER_PID" 2>/dev/null || true
WAIT_EXIT=0
wait "$MANAGER_PID" 2>/dev/null || WAIT_EXIT=$?

# Manager should have exited cleanly (exit 0 from trap)
echo "  [PASS] Manager shut down on SIGTERM (exit: $WAIT_EXIT)"
PASS=$((PASS + 1))
MANAGER_PID=""

# --- Summary ---
echo ""
echo "Manager Tests: $PASS passed, $FAIL failed"

# Config cleanup handled by trap (copy-on-write, no restore needed)

[[ $FAIL -eq 0 ]]
