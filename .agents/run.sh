#!/usr/bin/env bash
# Agent OS Entry Point
#
# Parses a plan file into war-rooms and launches the manager loop.
#
# Usage:
#   run.sh <plan-file> [OPTIONS]
#
# Options:
#   --dry-run         Show what rooms would be created, don't execute
#   --max-rooms N     Override max concurrent rooms from config
#   --working-dir P   Override working directory for all tasks
#
# Environment:
#   ENGINEER_CMD      Override engineer command (for mocks)
#   QA_CMD            Override QA command (for mocks)
#   MOCK_SIGNOFF      Set to "true" for auto-signoff (testing)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR"
WARROOMS="$AGENTS_DIR/war-rooms"
MANAGER_PID_FILE="$AGENTS_DIR/manager.pid"

# Parse args
PLAN_FILE=""
DRY_RUN=false
MAX_ROOMS=""
WORKING_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)      DRY_RUN=true; shift ;;
    --max-rooms)    MAX_ROOMS="$2"; shift 2 ;;
    --working-dir)  WORKING_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: run.sh <plan-file> [--dry-run] [--max-rooms N] [--working-dir PATH]"
      exit 0
      ;;
    *)
      if [[ -z "$PLAN_FILE" ]]; then
        PLAN_FILE="$1"
      fi
      shift
      ;;
  esac
done

if [[ -z "$PLAN_FILE" ]]; then
  echo "[ERROR] No plan file specified." >&2
  echo "Usage: run.sh <plan-file> [--dry-run] [--max-rooms N] [--working-dir PATH]" >&2
  exit 1
fi

if [[ ! -f "$PLAN_FILE" ]]; then
  echo "[ERROR] Plan file not found: $PLAN_FILE" >&2
  exit 1
fi

# Override max rooms if specified
if [[ -n "$MAX_ROOMS" ]]; then
  python3 -c "
import json
config = json.load(open('$AGENTS_DIR/config.json'))
config['manager']['max_concurrent_rooms'] = $MAX_ROOMS
json.dump(config, open('$AGENTS_DIR/config.json', 'w'), indent=2)
"
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║          AGENT OS v0.1.0             ║"
echo "  ║   Multi-Agent War-Room Orchestrator  ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  Plan: $PLAN_FILE"
echo ""

# Parse plan file: extract ## Task: sections
# Each "## Task: TASK-XXX — Title" becomes a war-room
TASKS=$(python3 -c "
import re, json, sys

with open('$PLAN_FILE', 'r') as f:
    content = f.read()

# Extract working dir from config section
working_dir = '$WORKING_DIR' or '.'
config_match = re.search(r'working_dir:\s*(.+)', content)
if config_match and not '$WORKING_DIR':
    working_dir = config_match.group(1).strip()

# Extract tasks
tasks = []
# Split on ## Task: headers
parts = re.split(r'^## Task:\s*', content, flags=re.MULTILINE)

for i, part in enumerate(parts[1:], 1):  # Skip everything before first task
    lines = part.strip().split('\n')
    header = lines[0].strip()

    # Parse: TASK-XXX — Title  or  TASK-XXX - Title
    ref_match = re.match(r'(TASK-\d+)\s*[—\-]\s*(.*)', header)
    if ref_match:
        task_ref = ref_match.group(1)
        task_title = ref_match.group(2).strip()
    else:
        task_ref = f'TASK-{i:03d}'
        task_title = header

    # Body is everything after the header
    task_body = '\n'.join(lines[1:]).strip()
    room_id = f'room-{i:03d}'

    tasks.append({
        'room_id': room_id,
        'task_ref': task_ref,
        'title': task_title,
        'body': task_body,
        'working_dir': working_dir,
    })

print(json.dumps(tasks))
")

TASK_COUNT=$(echo "$TASKS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")

if [[ "$TASK_COUNT" -eq 0 ]]; then
  echo "[ERROR] No tasks found in plan file. Expected '## Task: TASK-XXX — Title' sections." >&2
  exit 1
fi

echo "  Found $TASK_COUNT task(s):"
echo ""

# Display tasks
echo "$TASKS" | python3 -c "
import json, sys
tasks = json.load(sys.stdin)
for t in tasks:
    print(f\"  [{t['room_id']}] {t['task_ref']} — {t['title']}\")
"
echo ""

# Dry run: just show what would happen
if $DRY_RUN; then
  echo "[DRY RUN] Would create $TASK_COUNT war-rooms. No actions taken."
  exit 0
fi

# Kill any running manager loop
if [[ -f "$MANAGER_PID_FILE" ]]; then
  old_pid=$(cat "$MANAGER_PID_FILE")
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "[SETUP] Stopping running manager (PID $old_pid)..."
    kill "$old_pid" 2>/dev/null || true
    sleep 1
    kill -0 "$old_pid" 2>/dev/null && kill -9 "$old_pid" 2>/dev/null || true
  fi
  rm -f "$MANAGER_PID_FILE"
fi

# Clean up any previous rooms
if ls "$WARROOMS"/room-* 1>/dev/null 2>&1; then
  echo "[SETUP] Cleaning previous war-rooms..."
  for old_room in "$WARROOMS"/room-*/; do
    [[ -d "$old_room" ]] && "$WARROOMS/teardown.sh" "$(basename "$old_room")" --force 2>/dev/null || true
  done
fi

# Clean previous release artifacts
rm -f "$AGENTS_DIR/RELEASE.md" "$AGENTS_DIR/release/signoffs.json" 2>/dev/null || true

# Create war-rooms for each task
echo "[SETUP] Creating war-rooms..."
echo "$TASKS" | python3 -c "
import json, sys, subprocess

tasks = json.load(sys.stdin)
for t in tasks:
    full_desc = f\"{t['title']}\n\n{t['body']}\"
    subprocess.run([
        '$WARROOMS/create.sh',
        t['room_id'],
        t['task_ref'],
        full_desc,
        t['working_dir'],
    ], check=True)
"

echo ""
echo "[LAUNCH] Starting manager loop..."
echo "  Monitor with: $WARROOMS/status.sh --watch"
echo "  Stop with: Ctrl+C"
echo ""

# Launch the manager loop
exec "$AGENTS_DIR/roles/manager/loop.sh"
