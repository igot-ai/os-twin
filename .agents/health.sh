#!/usr/bin/env bash
# Agent OS — Health Check
#
# Checks the health of a running Agent OS instance.
#
# Usage: health.sh [--json]
#
# Checks:
#   - Manager process status
#   - War-room states (stuck rooms, stale states)
#   - Agent CLI availability
#   - Disk space

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR"
WARROOMS="${WARROOMS_DIR:-$AGENTS_DIR/war-rooms}"
CONFIG="${AGENT_OS_CONFIG:-$AGENTS_DIR/config.json}"
MANAGER_PID_FILE="$AGENTS_DIR/manager.pid"

JSON_MODE=false
[[ "${1:-}" == "--json" ]] && JSON_MODE=true

# Check manager
MANAGER_PID=""
MANAGER_ALIVE=false
if [[ -f "$MANAGER_PID_FILE" ]]; then
  MANAGER_PID=$(cat "$MANAGER_PID_FILE")
  if kill -0 "$MANAGER_PID" 2>/dev/null; then
    MANAGER_ALIVE=true
  fi
fi

# Check rooms
TOTAL_ROOMS=0
PASSED_ROOMS=0
FAILED_ROOMS=0
ACTIVE_ROOMS=0
STUCK_ROOMS=0
STATE_TIMEOUT=$(python3 -c "import json; c=json.load(open('$CONFIG')); print(c['manager'].get('state_timeout_seconds', 900))" 2>/dev/null || echo "900")
NOW=$(date +%s)

for room_dir in "$WARROOMS"/room-*/; do
  [ -d "$room_dir" ] || continue
  TOTAL_ROOMS=$((TOTAL_ROOMS + 1))
  status=$(cat "$room_dir/status" 2>/dev/null || echo "unknown")

  case "$status" in
    passed) PASSED_ROOMS=$((PASSED_ROOMS + 1)) ;;
    failed-final) FAILED_ROOMS=$((FAILED_ROOMS + 1)) ;;
    engineering|qa-review|fixing)
      ACTIVE_ROOMS=$((ACTIVE_ROOMS + 1))
      # Check if stuck (active but no PID alive)
      has_alive_pid=false
      for pid_file in "$room_dir/pids/"*.pid; do
        [ -f "$pid_file" ] || continue
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
          has_alive_pid=true
          break
        fi
      done
      if ! $has_alive_pid; then
        # Check if state is stale
        changed_at=$(cat "$room_dir/state_changed_at" 2>/dev/null || echo "0")
        elapsed=$((NOW - changed_at))
        if [ "$elapsed" -gt "$STATE_TIMEOUT" ]; then
          STUCK_ROOMS=$((STUCK_ROOMS + 1))
        fi
      fi
      ;;
  esac
done

# Check agent CLI availability
ENGINEER_CMD="${ENGINEER_CMD:-deepagents}"
QA_CMD="${QA_CMD:-deepagents}"
ENGINEER_AVAILABLE=$(command -v "$ENGINEER_CMD" &>/dev/null && echo "available" || echo "not found")
QA_AVAILABLE=$(command -v "$QA_CMD" &>/dev/null && echo "available" || echo "not found")
PYTHON_AVAILABLE=$(command -v python3 &>/dev/null && echo "available" || echo "not found")

# Determine overall health
HEALTH="healthy"
if [ "$STUCK_ROOMS" -gt 0 ]; then
  HEALTH="degraded"
fi
if [[ "$PYTHON_AVAILABLE" != "available" ]]; then
  HEALTH="unhealthy"
fi
if [[ "$MANAGER_ALIVE" == "false" ]] && [ "$ACTIVE_ROOMS" -gt 0 ]; then
  HEALTH="unhealthy"
fi

if $JSON_MODE; then
  python3 -c "
import json
print(json.dumps({
    'status': '$HEALTH',
    'manager': {
        'pid': '$MANAGER_PID' or None,
        'alive': $( $MANAGER_ALIVE && echo 'True' || echo 'False' ),
    },
    'rooms': {
        'total': $TOTAL_ROOMS,
        'passed': $PASSED_ROOMS,
        'failed': $FAILED_ROOMS,
        'active': $ACTIVE_ROOMS,
        'stuck': $STUCK_ROOMS,
    },
    'agents': {
        'engineer': {'cmd': '$ENGINEER_CMD', 'status': '$ENGINEER_AVAILABLE'},
        'qa': {'cmd': '$QA_CMD', 'status': '$QA_AVAILABLE'},
        'python3': '$PYTHON_AVAILABLE',
    },
    'config': {
        'state_timeout_seconds': $STATE_TIMEOUT,
    },
}, indent=2))
"
else
  echo ""
  echo "  Ostwin Health Check"
  echo "  ====================="
  echo ""

  # Status indicator
  case "$HEALTH" in
    healthy)   echo "  Status: HEALTHY" ;;
    degraded)  echo "  Status: DEGRADED" ;;
    unhealthy) echo "  Status: UNHEALTHY" ;;
  esac
  echo ""

  # Manager
  echo "  Manager:"
  if $MANAGER_ALIVE; then
    echo "    PID $MANAGER_PID — running"
  elif [[ -n "$MANAGER_PID" ]]; then
    echo "    PID $MANAGER_PID — NOT running (stale PID file)"
  else
    echo "    Not started"
  fi
  echo ""

  # Rooms
  echo "  War-Rooms:"
  echo "    Total:   $TOTAL_ROOMS"
  echo "    Passed:  $PASSED_ROOMS"
  echo "    Failed:  $FAILED_ROOMS"
  echo "    Active:  $ACTIVE_ROOMS"
  if [ "$STUCK_ROOMS" -gt 0 ]; then
    echo "    Stuck:   $STUCK_ROOMS (no PID alive, state timeout exceeded)"
  fi
  echo ""

  # Agents
  echo "  Agent CLIs:"
  echo "    Engineer ($ENGINEER_CMD): $ENGINEER_AVAILABLE"
  echo "    QA ($QA_CMD): $QA_AVAILABLE"
  echo "    Python3: $PYTHON_AVAILABLE"
  echo ""
fi
