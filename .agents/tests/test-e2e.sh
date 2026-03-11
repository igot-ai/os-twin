#!/usr/bin/env bash
# Test Suite: End-to-End
#
# Full lifecycle test using mock agents:
# Plan → War-rooms → Engineer → QA → RELEASE.md → Signoffs → Exit

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WARROOMS="$AGENTS_DIR/war-rooms"

# Use mock agents
export ENGINEER_CMD="$SCRIPT_DIR/mock-engineer.sh"
export QA_CMD="$SCRIPT_DIR/mock-qa.sh"
export MOCK_SIGNOFF="true"
export MOCK_ENGINEER_DELAY=0
export MOCK_QA_DELAY=0
export MOCK_QA_VERDICT="pass"

# Save and restore state
BACKUP_DIR=$(mktemp -d)
if ls "$WARROOMS"/room-* 1>/dev/null 2>&1; then
  cp -r "$WARROOMS"/room-* "$BACKUP_DIR/" 2>/dev/null || true
fi

# Backup config
cp "$AGENTS_DIR/config.json" "$BACKUP_DIR/config.json.bak"

cleanup() {
  # Remove test rooms
  rm -rf "$WARROOMS"/room-* 2>/dev/null || true
  # Restore backed up rooms
  if ls "$BACKUP_DIR"/room-* 1>/dev/null 2>&1; then
    cp -r "$BACKUP_DIR"/room-* "$WARROOMS/" 2>/dev/null || true
  fi
  # Restore config
  cp "$BACKUP_DIR/config.json.bak" "$AGENTS_DIR/config.json"
  # Clean up test plan and release
  rm -f "$TEST_PLAN" "$AGENTS_DIR/RELEASE.md" "$AGENTS_DIR/release/signoffs.json" 2>/dev/null || true
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
    echo "  [FAIL] $desc (not found: $path)"
    FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local desc="$1" needle="$2" file="$3"
  if grep -q "$needle" "$file" 2>/dev/null; then
    echo "  [PASS] $desc"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $desc (not found in $file)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Test Suite: End-to-End ==="

# Fast config
python3 -c "
import json
config = json.load(open('$AGENTS_DIR/config.json'))
config['manager']['poll_interval_seconds'] = 1
config['manager']['max_concurrent_rooms'] = 10
config['manager']['max_engineer_retries'] = 2
json.dump(config, open('$AGENTS_DIR/config.json', 'w'), indent=2)
"

# --- Test 1: Dry run ---
echo ""
echo "Test 1: Dry run parses plan correctly"

TEST_PLAN=$(mktemp)
cat > "$TEST_PLAN" << 'EOF'
# Plan: E2E Test

## Config
working_dir: /tmp/test-project

## Task: TASK-001 — Create module A

Build module A with basic functionality.

Acceptance criteria:
- Module exists
- Has a main function

## Task: TASK-002 — Create module B

Build module B that depends on A.

Acceptance criteria:
- Module exists
- Imports module A
EOF

DRY_OUTPUT=$("$AGENTS_DIR/run.sh" "$TEST_PLAN" --dry-run 2>&1)
echo "$DRY_OUTPUT" | grep -q "TASK-001" && {
  echo "  [PASS] Dry run shows TASK-001"
  PASS=$((PASS + 1))
} || {
  echo "  [FAIL] Dry run missing TASK-001"
  FAIL=$((FAIL + 1))
}
echo "$DRY_OUTPUT" | grep -q "TASK-002" && {
  echo "  [PASS] Dry run shows TASK-002"
  PASS=$((PASS + 1))
} || {
  echo "  [FAIL] Dry run missing TASK-002"
  FAIL=$((FAIL + 1))
}
echo "$DRY_OUTPUT" | grep -q "DRY RUN" && {
  echo "  [PASS] Dry run does not execute"
  PASS=$((PASS + 1))
} || {
  echo "  [FAIL] Dry run missing DRY RUN indicator"
  FAIL=$((FAIL + 1))
}

# --- Test 2: Full lifecycle with mock agents ---
echo ""
echo "Test 2: Full lifecycle (plan → rooms → engineer → QA → release)"

# Clean previous rooms
rm -rf "$WARROOMS"/room-* 2>/dev/null || true
rm -f "$AGENTS_DIR/RELEASE.md" "$AGENTS_DIR/release/signoffs.json" 2>/dev/null || true

# Create a simple 2-task plan
cat > "$TEST_PLAN" << 'EOF'
# Plan: E2E Full Test

## Config
working_dir: .

## Task: TASK-001 — Build feature alpha

Create feature alpha.

## Task: TASK-002 — Build feature beta

Create feature beta.
EOF

# Run with timeout (mock agents are fast)
E2E_EXIT=0
timeout 60 "$AGENTS_DIR/run.sh" "$TEST_PLAN" > /dev/null 2>&1 || E2E_EXIT=$?

# Check results
if [[ $E2E_EXIT -eq 0 ]]; then
  echo "  [PASS] Run completed with exit 0"
  PASS=$((PASS + 1))
else
  echo "  [FAIL] Run exited with code $E2E_EXIT (expected 0)"
  FAIL=$((FAIL + 1))
fi

# Check rooms were created
ROOM_COUNT=$(ls -d "$WARROOMS"/room-* 2>/dev/null | wc -l | tr -d ' ')
assert_eq "2 war-rooms created" "2" "$ROOM_COUNT"

# Check all rooms passed
ALL_PASSED=true
for room_dir in "$WARROOMS"/room-*/; do
  [[ -d "$room_dir" ]] || continue
  status=$(cat "$room_dir/status" 2>/dev/null || echo "unknown")
  if [[ "$status" != "passed" ]]; then
    ALL_PASSED=false
    echo "  [INFO] Room $(basename "$room_dir") status: $status"
  fi
done

if $ALL_PASSED; then
  echo "  [PASS] All rooms reached 'passed' status"
  PASS=$((PASS + 1))
else
  echo "  [FAIL] Not all rooms reached 'passed'"
  FAIL=$((FAIL + 1))
fi

# Check RELEASE.md generated
assert_exists "RELEASE.md generated" "$AGENTS_DIR/RELEASE.md"

if [[ -f "$AGENTS_DIR/RELEASE.md" ]]; then
  assert_contains "RELEASE.md has TASK-001" "TASK-001" "$AGENTS_DIR/RELEASE.md"
  assert_contains "RELEASE.md has TASK-002" "TASK-002" "$AGENTS_DIR/RELEASE.md"
fi

# Check signoffs
assert_exists "Signoffs file created" "$AGENTS_DIR/release/signoffs.json"
if [[ -f "$AGENTS_DIR/release/signoffs.json" ]]; then
  SIGNOFF_COUNT=$(python3 -c "import json; print(len(json.load(open('$AGENTS_DIR/release/signoffs.json'))))")
  if [[ "$SIGNOFF_COUNT" -ge 2 ]]; then
    echo "  [PASS] Signoffs collected ($SIGNOFF_COUNT roles)"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] Only $SIGNOFF_COUNT signoffs (expected >= 2)"
    FAIL=$((FAIL + 1))
  fi
fi

# --- Summary ---
echo ""
echo "E2E Tests: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
