#!/usr/bin/env bash
# Test Suite: War-Room Lifecycle
#
# Tests war-room creation, status, status transitions, and teardown.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${AGENTS_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"
WARROOMS="$AGENTS_DIR/war-rooms"

# Export WARROOMS_DIR so war-room scripts use this location for data
export WARROOMS_DIR="$WARROOMS"

# Save and restore any existing rooms
BACKUP_DIR=$(mktemp -d)
if ls "$WARROOMS"/room-* 1>/dev/null 2>&1; then
  cp -r "$WARROOMS"/room-* "$BACKUP_DIR/" 2>/dev/null || true
fi

# Clean test rooms on exit
cleanup() {
  # Remove test rooms
  rm -rf "$WARROOMS"/room-test-* 2>/dev/null || true
  # Restore backed up rooms
  if ls "$BACKUP_DIR"/room-* 1>/dev/null 2>&1; then
    cp -r "$BACKUP_DIR"/room-* "$WARROOMS/" 2>/dev/null || true
  fi
  rm -rf "$BACKUP_DIR"
}
trap cleanup EXIT

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

assert_exists() {
  local desc="$1" path="$2"
  if [[ -e "$path" ]]; then
    echo "  [PASS] $desc"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $desc (path not found: $path)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Test Suite: War-Room Lifecycle ==="

# --- Test 1: Create produces correct structure ---
echo ""
echo "Test 1: create.sh produces correct directory structure"
"$WARROOMS/create.sh" room-test-001 TASK-001 "Test task description" > /dev/null

ROOM="$WARROOMS/room-test-001"
assert_exists "Room directory created" "$ROOM"
assert_exists "channel.jsonl created" "$ROOM/channel.jsonl"
assert_exists "brief.md created" "$ROOM/brief.md"
assert_exists "status file created" "$ROOM/status"
assert_exists "retries file created" "$ROOM/retries"
assert_exists "pids directory created" "$ROOM/pids"
assert_exists "artifacts directory created" "$ROOM/artifacts"
assert_exists "task-ref file created" "$ROOM/task-ref"

STATUS=$(cat "$ROOM/status")
assert_eq "Initial status is pending" "pending" "$STATUS"

RETRIES=$(cat "$ROOM/retries")
assert_eq "Initial retries is 0" "0" "$RETRIES"

TASK_REF=$(cat "$ROOM/task-ref")
assert_eq "Task ref stored correctly" "TASK-001" "$TASK_REF"

# --- Test 2: Initial channel message ---
echo ""
echo "Test 2: Initial channel has task message"
MSG_COUNT=$(wc -l < "$ROOM/channel.jsonl" | tr -d ' ')
assert_eq "Channel has 1 initial message" "1" "$MSG_COUNT"

MSG_TYPE=$("$PYTHON" -c "import json; print(json.loads(open('$ROOM/channel.jsonl').readline())['type'])")
assert_eq "Initial message type is 'task'" "task" "$MSG_TYPE"

# --- Test 3: Duplicate room prevention ---
echo ""
echo "Test 3: Cannot create duplicate room"
DUP_EXIT=0
"$WARROOMS/create.sh" room-test-001 TASK-001 "Duplicate" > /dev/null 2>&1 || DUP_EXIT=$?
assert_eq "Duplicate creation fails" "1" "$DUP_EXIT"

# --- Test 4: Status transitions ---
echo ""
echo "Test 4: Status transitions"
echo "engineering" > "$ROOM/status"
assert_eq "Can set status to engineering" "engineering" "$(cat "$ROOM/status")"

echo "qa-review" > "$ROOM/status"
assert_eq "Can set status to qa-review" "qa-review" "$(cat "$ROOM/status")"

echo "fixing" > "$ROOM/status"
assert_eq "Can set status to fixing" "fixing" "$(cat "$ROOM/status")"

echo "passed" > "$ROOM/status"
assert_eq "Can set status to passed" "passed" "$(cat "$ROOM/status")"

# --- Test 5: Retry counter ---
echo ""
echo "Test 5: Retry counter"
echo "1" > "$ROOM/retries"
assert_eq "Retry counter can be set to 1" "1" "$(cat "$ROOM/retries")"

echo "3" > "$ROOM/retries"
assert_eq "Retry counter can be set to 3" "3" "$(cat "$ROOM/retries")"

# --- Test 6: Status dashboard (with rooms) ---
echo ""
echo "Test 6: Status dashboard"
echo "passed" > "$ROOM/status"
"$WARROOMS/create.sh" room-test-002 TASK-002 "Second task" > /dev/null

DASHBOARD=$("$WARROOMS/status.sh" 2>/dev/null)
echo "$DASHBOARD" | grep -q "room-test-001" && {
  echo "  [PASS] Dashboard shows room-test-001"
  PASS=$((PASS + 1))
} || {
  echo "  [FAIL] Dashboard missing room-test-001"
  FAIL=$((FAIL + 1))
}

echo "$DASHBOARD" | grep -q "room-test-002" && {
  echo "  [PASS] Dashboard shows room-test-002"
  PASS=$((PASS + 1))
} || {
  echo "  [FAIL] Dashboard missing room-test-002"
  FAIL=$((FAIL + 1))
}

# --- Test 7: JSON dashboard ---
echo ""
echo "Test 7: JSON dashboard"
JSON_STATUS=$("$WARROOMS/status.sh" --json 2>/dev/null)
ROOM_COUNT=$(echo "$JSON_STATUS" | "$PYTHON" -c "import json,sys; print(len(json.load(sys.stdin)['rooms']))")
# At least 2 test rooms
if [[ "$ROOM_COUNT" -ge 2 ]]; then
  echo "  [PASS] JSON dashboard shows at least 2 rooms"
  PASS=$((PASS + 1))
else
  echo "  [FAIL] JSON dashboard shows $ROOM_COUNT rooms (expected >= 2)"
  FAIL=$((FAIL + 1))
fi

# --- Test 8: Epic ref support ---
echo ""
echo "Test 8: Epic ref support"
"$WARROOMS/create.sh" room-test-003 EPIC-001 "Build authentication system" > /dev/null

EPIC_ROOM="$WARROOMS/room-test-003"
assert_exists "Epic room created" "$EPIC_ROOM"
assert_exists "Epic brief.md created" "$EPIC_ROOM/brief.md"

EPIC_REF=$(cat "$EPIC_ROOM/task-ref")
assert_eq "Epic ref stored correctly" "EPIC-001" "$EPIC_REF"

# Verify brief contains epic ref
EPIC_HEADER=$(head -1 "$EPIC_ROOM/brief.md" | sed 's/^# //')
assert_eq "Brief header has epic ref" "EPIC-001" "$EPIC_HEADER"

# --- Test 9: Teardown ---
echo ""
echo "Test 9: Teardown"
"$WARROOMS/teardown.sh" room-test-002 --force > /dev/null 2>&1
if [[ ! -d "$WARROOMS/room-test-002" ]]; then
  echo "  [PASS] Teardown removes room directory"
  PASS=$((PASS + 1))
else
  echo "  [FAIL] Teardown did not remove room directory"
  FAIL=$((FAIL + 1))
fi

# --- Summary ---
echo ""
echo "War-Room Tests: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
