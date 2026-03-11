#!/usr/bin/env bash
# Dashboard: show status of all war-rooms
#
# Usage: status.sh [--json] [--watch]
#
# Example:
#   status.sh                # Table view
#   status.sh --json         # JSON output
#   status.sh --watch        # Live refresh every 3s

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JSON_MODE=false
WATCH_MODE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)  JSON_MODE=true; shift ;;
    --watch) WATCH_MODE=true; shift ;;
    *)       shift ;;
  esac
done

print_status() {
  local rooms=()
  local total=0 pending=0 engineering=0 qa_review=0 fixing=0 passed=0 failed=0

  for room_dir in "$SCRIPT_DIR"/room-*/; do
    [[ -d "$room_dir" ]] || continue
    total=$((total + 1))

    room_id=$(basename "$room_dir")
    status=$(cat "$room_dir/status" 2>/dev/null || echo "unknown")
    task_ref=$(cat "$room_dir/task-ref" 2>/dev/null || echo "N/A")
    retries=$(cat "$room_dir/retries" 2>/dev/null || echo "0")
    msg_count=0
    last_activity="N/A"

    if [[ -f "$room_dir/channel.jsonl" ]]; then
      msg_count=$(wc -l < "$room_dir/channel.jsonl" | tr -d ' ')
      last_activity=$(tail -1 "$room_dir/channel.jsonl" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('ts','N/A'))" 2>/dev/null || echo "N/A")
    fi

    # Check active PIDs
    active_pids=""
    for pid_file in "$room_dir"/pids/*.pid; do
      [[ -f "$pid_file" ]] || continue
      pid=$(cat "$pid_file")
      if kill -0 "$pid" 2>/dev/null; then
        active_pids="${active_pids:+$active_pids,}$pid"
      fi
    done
    [[ -z "$active_pids" ]] && active_pids="-"

    # Count by status
    case "$status" in
      pending)      pending=$((pending + 1)) ;;
      engineering)  engineering=$((engineering + 1)) ;;
      qa-review)    qa_review=$((qa_review + 1)) ;;
      fixing)       fixing=$((fixing + 1)) ;;
      passed)       passed=$((passed + 1)) ;;
      failed-final) failed=$((failed + 1)) ;;
    esac

    rooms+=("$room_id|$task_ref|$status|$retries|$msg_count|$active_pids|$last_activity")
  done

  if $JSON_MODE; then
    python3 -c "
import json
rooms = []
for r in '''$(printf '%s\n' "${rooms[@]}")'''.strip().split('\n'):
    if not r: continue
    parts = r.split('|')
    rooms.append({
        'room_id': parts[0], 'task_ref': parts[1], 'status': parts[2],
        'retries': int(parts[3]), 'messages': int(parts[4]),
        'active_pids': parts[5], 'last_activity': parts[6]
    })
print(json.dumps({
    'rooms': rooms,
    'summary': {
        'total': $total, 'pending': $pending, 'engineering': $engineering,
        'qa_review': $qa_review, 'fixing': $fixing, 'passed': $passed, 'failed': $failed
    }
}, indent=2))
"
  else
    echo ""
    echo "=== Ostwin War-Room Dashboard ==="
    echo ""

    if [[ $total -eq 0 ]]; then
      echo "  No war-rooms found."
      echo ""
      return
    fi

    # Header
    printf "  %-12s %-10s %-14s %-8s %-6s %-10s %s\n" \
      "ROOM" "REF" "STATUS" "RETRIES" "MSGS" "PIDS" "LAST ACTIVITY"
    printf "  %-12s %-10s %-14s %-8s %-6s %-10s %s\n" \
      "----" "---" "------" "-------" "----" "----" "-------------"

    for entry in "${rooms[@]}"; do
      IFS='|' read -r room_id task_ref status retries msg_count active_pids last_activity <<< "$entry"
      printf "  %-12s %-10s %-14s %-8s %-6s %-10s %s\n" \
        "$room_id" "$task_ref" "$status" "$retries" "$msg_count" "$active_pids" "$last_activity"
    done

    echo ""
    echo "  Summary: $total total | $pending pending | $engineering engineering | $qa_review qa-review | $fixing fixing | $passed passed | $failed failed"
    echo ""
  fi
}

if $WATCH_MODE; then
  while true; do
    clear
    print_status
    sleep 3
  done
else
  print_status
fi
