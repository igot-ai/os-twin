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
PYTHON="${AGENTS_DIR}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"
WARROOM_TOOLS="$AGENTS_DIR/war-rooms"
MANAGER_PID_FILE="$AGENTS_DIR/manager.pid"

# Ensure logs directory exists before sourcing log.sh
mkdir -p "$AGENTS_DIR/logs"

# Source shared utilities
source "$AGENTS_DIR/lib/log.sh" 2>/dev/null || true

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

# === Copy-on-write config ===
# Never modify the original config.json. Copy to a run-specific config
# and apply overrides there. All child scripts read from AGENT_OS_CONFIG.
RUN_CONFIG="$AGENTS_DIR/config.run.json"
cp "$AGENTS_DIR/config.json" "$RUN_CONFIG"

if [[ -n "$MAX_ROOMS" ]]; then
  "$PYTHON" -c "
import json
config = json.load(open('$RUN_CONFIG'))
config['manager']['max_concurrent_rooms'] = $MAX_ROOMS
json.dump(config, open('$RUN_CONFIG', 'w'), indent=2)
"
fi

export AGENT_OS_CONFIG="$RUN_CONFIG"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║          OSTWIN v0.1.0               ║"
echo "  ║   Multi-Agent War-Room Orchestrator  ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  Plan: $PLAN_FILE"
echo ""

# Parse plan file: extract ## Epic: or ## Task: sections
# Each section becomes a war-room (one room per epic or task)
TASKS=$("$PYTHON" -c "
import re, json, sys

with open('$PLAN_FILE', 'r') as f:
    content = f.read()

# Extract working dir from config section
working_dir = '$WORKING_DIR' or '.'
config_match = re.search(r'working_dir:\s*(.+)', content)
if config_match and not '$WORKING_DIR':
    working_dir = config_match.group(1).strip()

# Detect format: Epic or Task (reject mixed)
has_epics = bool(re.search(r'^## Epic:', content, re.MULTILINE))
has_tasks = bool(re.search(r'^## Task:', content, re.MULTILINE))

if has_epics and has_tasks:
    print('ERROR: Plan mixes ## Epic: and ## Task: sections. Use one format.', file=sys.stderr)
    sys.exit(1)

if has_epics:
    split_pattern = r'^## Epic:\s*'
    ref_pattern = r'(EPIC-\d+)\s*[—\-]\s*(.*)'
    default_prefix = 'EPIC'
else:
    split_pattern = r'^## Task:\s*'
    ref_pattern = r'(TASK-\d+)\s*[—\-]\s*(.*)'
    default_prefix = 'TASK'

items = []
parts = re.split(split_pattern, content, flags=re.MULTILINE)

for i, part in enumerate(parts[1:], 1):
    lines = part.strip().split('\n')
    header = lines[0].strip()

    ref_match = re.match(ref_pattern, header)
    if ref_match:
        item_ref = ref_match.group(1)
        item_title = ref_match.group(2).strip()
    else:
        item_ref = f'{default_prefix}-{i:03d}'
        item_title = header

    item_body = '\n'.join(lines[1:]).strip()
    
    # Extract Dependencies
    dependencies = []
    dep_match = re.search(r'^Dependencies:\s*(.+)$', item_body, flags=re.MULTILINE | re.IGNORECASE)
    if dep_match:
        deps_str = dep_match.group(1).strip()
        if deps_str.lower() != 'none':
            # Split by commas and clean up
            dependencies = [d.strip() for d in deps_str.split(',')]
    
    room_id = f'room-{i:03d}'

    items.append({
        'room_id': room_id,
        'task_ref': item_ref,
        'title': item_title,
        'body': item_body,
        'working_dir': working_dir,
        'dependencies': ','.join(dependencies)
    })

print(json.dumps(items))
")

TASK_COUNT=$(echo "$TASKS" | "$PYTHON" -c "import json,sys; print(len(json.load(sys.stdin)))")

if [[ "$TASK_COUNT" -eq 0 ]]; then
  echo "[ERROR] No items found in plan file. Expected '## Epic: EPIC-XXX — Title' or '## Task: TASK-XXX — Title' sections." >&2
  exit 1
fi

# === Plan validation ===
VALIDATION_WARNINGS=$(echo "$TASKS" | "$PYTHON" -c "
import json, sys, os

tasks = json.load(sys.stdin)
warnings = []

# Check for duplicate task IDs
refs = [t['task_ref'] for t in tasks]
seen = set()
for r in refs:
    if r in seen:
        warnings.append(f'Duplicate task ID: {r}')
    seen.add(r)

# Check for empty descriptions
for t in tasks:
    if not t['body'].strip():
        warnings.append(f'{t[\"task_ref\"]}: Empty task description')

# Check working directory
wd = tasks[0]['working_dir'] if tasks else '.'
if wd != '.' and not os.path.isdir(wd):
    warnings.append(f'Working directory does not exist: {wd}')

for w in warnings:
    print(w)
" 2>/dev/null || echo "")

if [[ -n "$VALIDATION_WARNINGS" ]]; then
  echo "  [WARN] Plan validation warnings:"
  echo "$VALIDATION_WARNINGS" | while IFS= read -r warning; do
    echo "    - $warning"
  done
  echo ""
fi

echo "  Found $TASK_COUNT task(s):"
echo ""

# Display tasks
echo "$TASKS" | "$PYTHON" -c "
import json, sys
tasks = json.load(sys.stdin)
for t in tasks:
    print(f\"  [{t['room_id']}] {t['task_ref']} — {t['title']}\")
"
echo ""

# Dry run: just show what would happen
if $DRY_RUN; then
  echo "[DRY RUN] Would create $TASK_COUNT war-rooms. No actions taken."
  rm -f "$RUN_CONFIG"
  exit 0
fi

# Resolve project-scoped war-rooms directory
PROJECT_DIR=$(echo "$TASKS" | "$PYTHON" -c "
import json, sys, os
tasks = json.load(sys.stdin)
wd = tasks[0]['working_dir'] if tasks else '.'
print(os.path.abspath(wd))
" 2>/dev/null || echo "$(pwd)")
export WARROOMS_DIR="${WARROOMS_DIR:-$PROJECT_DIR/.war-rooms}"
mkdir -p "$WARROOMS_DIR"
echo "[SETUP] War-rooms directory: $WARROOMS_DIR"

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
if ls "$WARROOMS_DIR"/room-* 1>/dev/null 2>&1; then
  echo "[SETUP] Cleaning previous war-rooms..."
  for old_room in "$WARROOMS_DIR"/room-*/; do
    [[ -d "$old_room" ]] && "$WARROOM_TOOLS/teardown.sh" "$(basename "$old_room")" --force 2>/dev/null || true
  done
fi

# Clean previous release artifacts
rm -f "$AGENTS_DIR/RELEASE.md" "$AGENTS_DIR/release/signoffs.json" 2>/dev/null || true

# Create war-rooms for each task
echo "[SETUP] Creating war-rooms..."
echo "$TASKS" | "$PYTHON" -c "
import json, sys, subprocess

tasks = json.load(sys.stdin)
for t in tasks:
    full_desc = f\"{t['title']}\n\n{t['body']}\"
    subprocess.run([
        '$WARROOM_TOOLS/create.sh',
        t['room_id'],
        t['task_ref'],
        full_desc,
        t['working_dir'],
    ], check=True)
"

echo ""
echo "[LAUNCH] Starting manager loop..."
echo "  Monitor with: ostwin status --watch"
echo "  Stop with: Ctrl+C"
echo ""

# Launch the manager loop
exec "$AGENTS_DIR/roles/manager/loop.sh"
/roles/manager/loop.sh"
