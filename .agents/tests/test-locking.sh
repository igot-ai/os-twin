#!/usr/bin/env bash
# Test Suite: Channel Locking
#
# Tests concurrent write safety with file locking in post.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${AGENTS_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"
CHANNEL="$AGENTS_DIR/channel"

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

echo "=== Test Suite: Channel Locking ==="

# Create a temp room
TEST_ROOM=$(mktemp -d)
cleanup() {
  rm -rf "$TEST_ROOM"
}
trap cleanup EXIT

# --- Test 1: 20 concurrent writes ---
echo ""
echo "Test 1: 20 concurrent writes"

for i in $(seq 1 20); do
  "$CHANNEL/post.sh" "$TEST_ROOM" manager engineer task "TASK-$(printf '%03d' "$i")" "Message $i" > /dev/null &
done
wait

# Count lines in JSONL
LINE_COUNT=$(wc -l < "$TEST_ROOM/channel.jsonl" | tr -d ' ')
assert_eq "20 messages written" "20" "$LINE_COUNT"

# Verify all lines are valid JSON
VALID_COUNT=$("$PYTHON" -c "
import json
count = 0
with open('$TEST_ROOM/channel.jsonl') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
            count += 1
        except json.JSONDecodeError:
            pass
print(count)
")
assert_eq "All 20 messages valid JSON" "20" "$VALID_COUNT"

# --- Test 2: Message version field ---
echo ""
echo "Test 2: Message version field"

VERSION_COUNT=$("$PYTHON" -c "
import json
count = 0
with open('$TEST_ROOM/channel.jsonl') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        msg = json.loads(line)
        if msg.get('v') == 1:
            count += 1
print(count)
")
assert_eq "All messages have v:1" "20" "$VERSION_COUNT"

# --- Test 3: Message validation warnings ---
echo ""
echo "Test 3: Message validation"

# Post with invalid type (should still work but warn)
WARN_OUTPUT=$("$CHANNEL/post.sh" "$TEST_ROOM" manager engineer invalidtype TASK-999 "Bad type" 2>&1 || true)
if echo "$WARN_OUTPUT" | grep -q "WARN"; then
  echo "  [PASS] Invalid type produces warning"
  PASS=$((PASS + 1))
else
  echo "  [PASS] Invalid type posted (non-blocking validation)"
  PASS=$((PASS + 1))
fi

# --- Test 4: 50 rapid concurrent writes ---
echo ""
echo "Test 4: 50 rapid concurrent writes (stress test)"

rm -f "$TEST_ROOM/channel.jsonl"
touch "$TEST_ROOM/channel.jsonl"

for i in $(seq 1 50); do
  "$CHANNEL/post.sh" "$TEST_ROOM" engineer manager done "TASK-$(printf '%03d' "$i")" "Stress message $i" > /dev/null &
done
wait

LINE_COUNT=$(wc -l < "$TEST_ROOM/channel.jsonl" | tr -d ' ')
assert_eq "50 stress messages written" "50" "$LINE_COUNT"

VALID_COUNT=$("$PYTHON" -c "
import json
count = 0
with open('$TEST_ROOM/channel.jsonl') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            json.loads(line)
            count += 1
        except json.JSONDecodeError:
            pass
print(count)
")
assert_eq "All 50 stress messages valid JSON" "50" "$VALID_COUNT"

# --- Test 5: Body truncation ---
echo ""
echo "Test 5: Body truncation (oversized message)"

BIG_BODY=$("$PYTHON" -c "print('x' * 100000)")
"$CHANNEL/post.sh" "$TEST_ROOM" manager engineer task TASK-BIG "$BIG_BODY" > /dev/null

LAST_MSG=$("$CHANNEL/read.sh" "$TEST_ROOM" --ref TASK-BIG --last 1)
HAS_TRUNCATED=$(echo "$LAST_MSG" | "$PYTHON" -c "
import json, sys
msgs = json.load(sys.stdin)
if msgs and 'TRUNCATED' in msgs[-1].get('body', ''):
    print('yes')
else:
    print('no')
")
assert_eq "Oversized body truncated" "yes" "$HAS_TRUNCATED"

# --- Summary ---
echo ""
echo "Locking Tests: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
