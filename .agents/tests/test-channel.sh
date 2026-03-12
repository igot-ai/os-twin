#!/usr/bin/env bash
# Test Suite: Channel Protocol
#
# Tests the JSONL message channel: post, read, filter, wait-for.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${AGENTS_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"
CHANNEL="$AGENTS_DIR/channel"

# Create temp test directory
TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

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
    echo "  [FAIL] $desc"
    echo "    Expected to contain: $needle"
    echo "    Actual: $haystack"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Test Suite: Channel Protocol ==="

# --- Test 1: Post and read round-trip ---
echo ""
echo "Test 1: Post and read round-trip"
ROOM="$TEST_DIR/room-test1"
mkdir -p "$ROOM"
touch "$ROOM/channel.jsonl"

MSG_ID=$("$CHANNEL/post.sh" "$ROOM" manager engineer task TASK-001 "Build feature X")
RESULT=$("$CHANNEL/read.sh" "$ROOM")

assert_contains "Message posted and readable" "TASK-001" "$RESULT"
assert_contains "Body preserved" "Build feature X" "$RESULT"
assert_contains "From field set" '"from": "manager"' "$RESULT"
assert_contains "To field set" '"to": "engineer"' "$RESULT"

# --- Test 2: Filter by --type ---
echo ""
echo "Test 2: Filter by type"
"$CHANNEL/post.sh" "$ROOM" engineer manager done TASK-001 "Feature complete" > /dev/null
"$CHANNEL/post.sh" "$ROOM" manager qa review TASK-001 "Please review" > /dev/null

DONE_MSGS=$("$CHANNEL/read.sh" "$ROOM" --type done)
DONE_COUNT=$(echo "$DONE_MSGS" | "$PYTHON" -c "import json,sys; print(len(json.load(sys.stdin)))")
assert_eq "Filter by type=done returns 1" "1" "$DONE_COUNT"

TASK_MSGS=$("$CHANNEL/read.sh" "$ROOM" --type task)
TASK_COUNT=$(echo "$TASK_MSGS" | "$PYTHON" -c "import json,sys; print(len(json.load(sys.stdin)))")
assert_eq "Filter by type=task returns 1" "1" "$TASK_COUNT"

# --- Test 3: Filter by --from ---
echo ""
echo "Test 3: Filter by from"
MGR_MSGS=$("$CHANNEL/read.sh" "$ROOM" --from manager)
MGR_COUNT=$(echo "$MGR_MSGS" | "$PYTHON" -c "import json,sys; print(len(json.load(sys.stdin)))")
assert_eq "Filter by from=manager returns 2" "2" "$MGR_COUNT"

# --- Test 4: --last N ---
echo ""
echo "Test 4: --last N"
LAST_1=$("$CHANNEL/read.sh" "$ROOM" --last 1)
LAST_COUNT=$(echo "$LAST_1" | "$PYTHON" -c "import json,sys; print(len(json.load(sys.stdin)))")
assert_eq "--last 1 returns 1 message" "1" "$LAST_COUNT"

LAST_TYPE=$(echo "$LAST_1" | "$PYTHON" -c "import json,sys; print(json.load(sys.stdin)[0]['type'])")
assert_eq "--last 1 returns most recent" "review" "$LAST_TYPE"

# --- Test 5: Combined filters ---
echo ""
echo "Test 5: Combined filters"
COMBINED=$("$CHANNEL/read.sh" "$ROOM" --from manager --type task)
COMB_COUNT=$(echo "$COMBINED" | "$PYTHON" -c "import json,sys; print(len(json.load(sys.stdin)))")
assert_eq "Combined filter (from=manager, type=task)" "1" "$COMB_COUNT"

# --- Test 6: Empty channel ---
echo ""
echo "Test 6: Empty channel"
EMPTY_ROOM="$TEST_DIR/room-empty"
mkdir -p "$EMPTY_ROOM"
touch "$EMPTY_ROOM/channel.jsonl"

EMPTY_RESULT=$("$CHANNEL/read.sh" "$EMPTY_ROOM")
EMPTY_COUNT=$(echo "$EMPTY_RESULT" | "$PYTHON" -c "import json,sys; print(len(json.load(sys.stdin)))")
assert_eq "Empty channel returns 0 messages" "0" "$EMPTY_COUNT"

# --- Test 7: Non-existent channel ---
echo ""
echo "Test 7: Non-existent channel"
NO_ROOM="$TEST_DIR/room-nonexistent"
NO_RESULT=$("$CHANNEL/read.sh" "$NO_ROOM")
assert_eq "Non-existent room returns empty array" "[]" "$NO_RESULT"

# --- Test 8: Concurrent writes ---
echo ""
echo "Test 8: Concurrent writes"
CONC_ROOM="$TEST_DIR/room-concurrent"
mkdir -p "$CONC_ROOM"
touch "$CONC_ROOM/channel.jsonl"

for i in $(seq 1 10); do
  "$CHANNEL/post.sh" "$CONC_ROOM" "agent-$i" manager task "TASK-$i" "Concurrent task $i" > /dev/null &
done
wait

CONC_COUNT=$(wc -l < "$CONC_ROOM/channel.jsonl" | tr -d ' ')
assert_eq "10 concurrent writes all persisted" "10" "$CONC_COUNT"

# Verify all are valid JSON
VALID_JSON=$("$PYTHON" -c "
import json
count = 0
with open('$CONC_ROOM/channel.jsonl') as f:
    for line in f:
        json.loads(line.strip())
        count += 1
print(count)
")
assert_eq "All concurrent messages are valid JSON" "10" "$VALID_JSON"

# --- Summary ---
echo ""
echo "Channel Tests: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
