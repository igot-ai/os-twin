#!/usr/bin/env bash
# Manager Orchestration Loop
#
# The brain of Agent OS. Monitors all war-rooms, routes work between
# engineers and QA, handles retries, and manages the release cycle.
#
# Usage: loop.sh [--config PATH]
#
# Environment:
#   ENGINEER_CMD  Override engineer command (default: deepagents)
#   QA_CMD        Override QA command (default: gemini)
#
# Portable: works with bash 3.2+ (no associative arrays).
# State is read from war-room files each iteration (crash-resilient).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHANNEL="$AGENTS_DIR/channel"
WARROOMS="$AGENTS_DIR/war-rooms"
RELEASE_DIR="$AGENTS_DIR/release"

# === BASH POWER: Graceful shutdown via trap ===
SHUTTING_DOWN=false
cleanup() {
  SHUTTING_DOWN=true
  echo ""
  echo "[MANAGER] Shutting down all war-rooms..."
  for pid_file in "$WARROOMS"/room-*/pids/*.pid; do
    [ -f "$pid_file" ] || continue
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  Stopping PID $pid..."
      kill "$pid" 2>/dev/null || true
    fi
  done
  sleep 2
  for pid_file in "$WARROOMS"/room-*/pids/*.pid; do
    [ -f "$pid_file" ] || continue
    pid=$(cat "$pid_file")
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    rm -f "$pid_file"
  done
  echo "[MANAGER] Shutdown complete."
  exit 0
}
trap cleanup SIGTERM SIGINT

# === Config ===
CONFIG="$AGENTS_DIR/config.json"
MAX_CONCURRENT=$(python3 -c "import json; print(json.load(open('$CONFIG'))['manager']['max_concurrent_rooms'])")
POLL_INTERVAL=$(python3 -c "import json; print(json.load(open('$CONFIG'))['manager']['poll_interval_seconds'])")
MAX_RETRIES=$(python3 -c "import json; print(json.load(open('$CONFIG'))['manager']['max_engineer_retries'])")

echo "[MANAGER] Starting Agent OS Manager Loop"
echo "  Max concurrent rooms: $MAX_CONCURRENT"
echo "  Poll interval: ${POLL_INTERVAL}s"
echo "  Max retries per task: $MAX_RETRIES"
echo ""

# === Helper: count active rooms by scanning status files ===
active_count() {
  local count=0
  for room_dir in "$WARROOMS"/room-*/; do
    [ -d "$room_dir" ] || continue
    local s
    s=$(cat "$room_dir/status" 2>/dev/null || echo "pending")
    case "$s" in
      engineering|qa-review|fixing) count=$((count + 1)) ;;
    esac
  done
  echo "$count"
}

# === Helper: count messages of a type ===
msg_count() {
  local room_dir="$1"
  local msg_type="$2"
  "$CHANNEL/read.sh" "$room_dir" --type "$msg_type" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0"
}

# === Helper: get latest message body of a type ===
latest_body() {
  local room_dir="$1"
  local msg_type="$2"
  "$CHANNEL/read.sh" "$room_dir" --type "$msg_type" --last 1 | python3 -c "
import json, sys
msgs = json.load(sys.stdin)
if msgs:
    print(msgs[-1].get('body', ''))
else:
    print('')
" 2>/dev/null || echo ""
}

# === Helper: check if PID is still alive ===
is_alive() {
  local pid_file="$1"
  [ -f "$pid_file" ] || return 1
  local pid
  pid=$(cat "$pid_file")
  kill -0 "$pid" 2>/dev/null
}

# === MAIN LOOP ===
ITERATION=0
while true; do
  if $SHUTTING_DOWN; then break; fi
  ITERATION=$((ITERATION + 1))

  ROOM_COUNT=0
  ALL_PASSED=true

  for room_dir in "$WARROOMS"/room-*/; do
    [ -d "$room_dir" ] || continue
    if $SHUTTING_DOWN; then break; fi

    ROOM_COUNT=$((ROOM_COUNT + 1))
    room_id=$(basename "$room_dir")
    status=$(cat "$room_dir/status" 2>/dev/null || echo "pending")
    task_ref=$(cat "$room_dir/task-ref" 2>/dev/null || echo "UNKNOWN")
    retries=$(cat "$room_dir/retries" 2>/dev/null || echo "0")

    case "$status" in
      pending)
        ALL_PASSED=false
        if [ "$(active_count)" -lt "$MAX_CONCURRENT" ]; then
          echo "[MANAGER] [$task_ref] Spawning engineer in $room_id..."
          "$AGENTS_DIR/roles/engineer/run.sh" "$room_dir" &
          echo "engineering" > "$room_dir/status"
        fi
        ;;

      engineering|fixing)
        ALL_PASSED=false
        done_count=$(msg_count "$room_dir" "done")
        expected=$((retries + 1))

        if [ "$done_count" -ge "$expected" ]; then
          echo "[MANAGER] [$task_ref] Engineer done. Routing to QA..."
          "$AGENTS_DIR/roles/qa/run.sh" "$room_dir" &
          echo "qa-review" > "$room_dir/status"
        else
          # Check if engineer process died
          if [ -f "$room_dir/pids/engineer.pid" ] && ! is_alive "$room_dir/pids/engineer.pid"; then
            error_count=$(msg_count "$room_dir" "error")
            if [ "$error_count" -gt 0 ]; then
              error_body=$(latest_body "$room_dir" "error")
              echo "[MANAGER] [$task_ref] Engineer error: $error_body" >&2
              if [ "$retries" -lt "$MAX_RETRIES" ]; then
                echo "[MANAGER] [$task_ref] Retrying (attempt $((retries + 1))/$MAX_RETRIES)..."
                echo $((retries + 1)) > "$room_dir/retries"
                "$CHANNEL/post.sh" "$room_dir" manager engineer fix "$task_ref" "Previous attempt failed: $error_body. Please try again."
                "$AGENTS_DIR/roles/engineer/run.sh" "$room_dir" &
                echo "fixing" > "$room_dir/status"
              else
                echo "[MANAGER] [$task_ref] Max retries exceeded. Marking as failed." >&2
                echo "failed-final" > "$room_dir/status"
              fi
            fi
          fi
        fi
        ;;

      qa-review)
        ALL_PASSED=false
        pass_count=$(msg_count "$room_dir" "pass")
        if [ "$pass_count" -gt 0 ]; then
          echo "[MANAGER] [$task_ref] QA PASSED! Room $room_id complete."
          echo "passed" > "$room_dir/status"
        else
          fail_count=$(msg_count "$room_dir" "fail")
          if [ "$fail_count" -gt 0 ]; then
            feedback=$(latest_body "$room_dir" "fail")
            if [ "$retries" -lt "$MAX_RETRIES" ]; then
              echo "[MANAGER] [$task_ref] QA FAILED. Routing feedback to engineer (retry $((retries + 1))/$MAX_RETRIES)..."
              echo $((retries + 1)) > "$room_dir/retries"
              "$CHANNEL/post.sh" "$room_dir" manager engineer fix "$task_ref" "$feedback"
              "$AGENTS_DIR/roles/engineer/run.sh" "$room_dir" &
              echo "fixing" > "$room_dir/status"
            else
              echo "[MANAGER] [$task_ref] Max retries exceeded after QA failure. Marking as failed." >&2
              echo "failed-final" > "$room_dir/status"
            fi
          else
            # Check if QA process died
            if [ -f "$room_dir/pids/qa.pid" ] && ! is_alive "$room_dir/pids/qa.pid"; then
              echo "[MANAGER] [$task_ref] QA process died without verdict. Treating as fail." >&2
              "$CHANNEL/post.sh" "$room_dir" qa manager fail "$task_ref" "QA process terminated without verdict"
            fi
          fi
        fi
        ;;

      passed)
        # Good — this room is done
        ;;

      failed-final)
        ALL_PASSED=false
        ;;

      *)
        echo "[MANAGER] Unknown status '$status' for $room_id" >&2
        ALL_PASSED=false
        ;;
    esac
  done

  # === Release check ===
  if [ "$ROOM_COUNT" -gt 0 ] && $ALL_PASSED; then
    echo ""
    echo "[MANAGER] All $ROOM_COUNT rooms PASSED! Drafting release..."
    "$RELEASE_DIR/draft.sh" "$AGENTS_DIR"

    echo "[MANAGER] Collecting signoffs..."
    if "$RELEASE_DIR/signoff.sh" "$AGENTS_DIR"; then
      echo ""
      echo "============================================"
      echo "[MANAGER] RELEASE COMPLETE!"
      echo "  Release notes: $AGENTS_DIR/RELEASE.md"
      echo "============================================"
      break
    else
      echo "[MANAGER] Signoff failed. Continuing loop..." >&2
    fi
  fi

  # Status summary (every 10 iterations)
  if [ $((ITERATION % 10)) -eq 0 ] && [ "$ROOM_COUNT" -gt 0 ]; then
    passed_count=0
    for room_dir2 in "$WARROOMS"/room-*/; do
      [ -d "$room_dir2" ] || continue
      s2=$(cat "$room_dir2/status" 2>/dev/null || echo "")
      if [ "$s2" = "passed" ]; then
        passed_count=$((passed_count + 1))
      fi
    done
    echo "[MANAGER] Progress: $passed_count/$ROOM_COUNT rooms passed (iteration $ITERATION)"
  fi

  sleep "$POLL_INTERVAL"
done
