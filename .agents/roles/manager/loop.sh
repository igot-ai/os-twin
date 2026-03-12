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
#   QA_CMD        Override QA command (default: deepagents)
#
# Portable: works with bash 3.2+ (no associative arrays).
# State is read from war-room files each iteration (crash-resilient).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHANNEL="$AGENTS_DIR/channel"
# War-room data from env (set by run.sh), fallback to $AGENTS_DIR/war-rooms
WARROOMS="${WARROOMS_DIR:-$AGENTS_DIR/war-rooms}"
RELEASE_DIR="$AGENTS_DIR/release"
MANAGER_PID_FILE="$AGENTS_DIR/manager.pid"

# Source shared utilities
source "$AGENTS_DIR/lib/utils.sh" 2>/dev/null || true
source "$AGENTS_DIR/lib/log.sh" 2>/dev/null || true

# Write our PID so run.sh / api.py can kill us cleanly
echo $$ > "$MANAGER_PID_FILE"

# === BASH POWER: Graceful shutdown via trap ===
SHUTTING_DOWN=false
cleanup() {
  SHUTTING_DOWN=true
  rm -f "$MANAGER_PID_FILE"
  echo ""
  log INFO "Shutting down all war-rooms..." 2>/dev/null || echo "[MANAGER] Shutting down all war-rooms..."
  for pid_file in "$WARROOMS"/room-*/pids/*.pid; do
    [ -f "$pid_file" ] || continue
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      log INFO "Stopping PID $pid..." 2>/dev/null || echo "  Stopping PID $pid..."
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
  log INFO "Shutdown complete." 2>/dev/null || echo "[MANAGER] Shutdown complete."
  exit 0
}
trap cleanup SIGTERM SIGINT

# === Config ===
CONFIG="${AGENT_OS_CONFIG:-$AGENTS_DIR/config.json}"
MAX_CONCURRENT=$(python3 -c "import json; print(json.load(open('$CONFIG'))['manager']['max_concurrent_rooms'])")
POLL_INTERVAL=$(python3 -c "import json; print(json.load(open('$CONFIG'))['manager']['poll_interval_seconds'])")
MAX_RETRIES=$(python3 -c "import json; print(json.load(open('$CONFIG'))['manager']['max_engineer_retries'])")
STATE_TIMEOUT=$(python3 -c "import json; c=json.load(open('$CONFIG')); print(c['manager'].get('state_timeout_seconds', 900))")

log INFO "Starting Ostwin Manager Loop" 2>/dev/null || echo "[MANAGER] Starting Ostwin Manager Loop"
echo "  Max concurrent rooms: $MAX_CONCURRENT"
echo "  Poll interval: ${POLL_INTERVAL}s"
echo "  Max retries per task: $MAX_RETRIES"
echo "  State timeout: ${STATE_TIMEOUT}s"
echo ""

log_json INFO "manager_started" \
  max_concurrent "$MAX_CONCURRENT" \
  poll_interval "$POLL_INTERVAL" \
  max_retries "$MAX_RETRIES" \
  state_timeout "$STATE_TIMEOUT" 2>/dev/null || true

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

# === Helper: check if state has timed out ===
is_state_timed_out() {
  local room_dir="$1"
  local changed_at_file="$room_dir/state_changed_at"
  [ -f "$changed_at_file" ] || return 1
  local changed_at
  changed_at=$(cat "$changed_at_file" 2>/dev/null || echo "0")
  local now
  now=$(date +%s)
  local elapsed=$((now - changed_at))
  [ "$elapsed" -gt "$STATE_TIMEOUT" ]
}

# === Helper: kill a room's running processes ===
kill_room_processes() {
  local room_dir="$1"
  for pid_file in "$room_dir/pids/"*.pid; do
    [ -f "$pid_file" ] || continue
    local pid
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  done
}

# === Helper: write status with audit trail ===
write_status() {
  local room_dir="$1"
  local new_status="$2"
  local old_status
  old_status=$(cat "$room_dir/status" 2>/dev/null || echo "unknown")
  echo "$new_status" > "$room_dir/status"
  date +%s > "$room_dir/state_changed_at"
  # Audit trail
  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "$ts STATUS $old_status -> $new_status" >> "$room_dir/audit.log" 2>/dev/null || true
}

# === MAIN LOOP ===
ITERATION=0
STALL_CYCLES=0
while true; do
  if $SHUTTING_DOWN; then break; fi
  ITERATION=$((ITERATION + 1))

  ROOM_COUNT=0
  ALL_PASSED=true
  ACTIVE_WITH_NO_PID=0
  TOTAL_ACTIVE=0

  for room_dir in "$WARROOMS"/room-*/; do
    [ -d "$room_dir" ] || continue
    if $SHUTTING_DOWN; then break; fi

    ROOM_COUNT=$((ROOM_COUNT + 1))
    room_id=$(basename "$room_dir")
    status=$(cat "$room_dir/status" 2>/dev/null || echo "pending")
    task_ref=$(cat "$room_dir/task-ref" 2>/dev/null || echo "")
    # Fallback: extract ref from TASKS.md header when task-ref file is missing
    if [ -z "$task_ref" ] && [ -f "$room_dir/TASKS.md" ]; then
      task_ref=$(head -1 "$room_dir/TASKS.md" | grep -oE '(EPIC|TASK)-[0-9]+' | head -1)
    fi
    task_ref="${task_ref:-UNKNOWN}"
    retries=$(cat "$room_dir/retries" 2>/dev/null || echo "0")

    case "$status" in
      pending)
        ALL_PASSED=false
        if [ "$(active_count)" -lt "$MAX_CONCURRENT" ]; then
          log INFO "[$task_ref] Spawning engineer in $room_id..." 2>/dev/null || echo "[MANAGER] [$task_ref] Spawning engineer in $room_id..."
          # IMPORTANT: Write status BEFORE spawning to prevent race condition
          write_status "$room_dir" "engineering"
          "$AGENTS_DIR/roles/engineer/run.sh" "$room_dir" &
        fi
        ;;

      engineering|fixing)
        ALL_PASSED=false
        TOTAL_ACTIVE=$((TOTAL_ACTIVE + 1))

        # Check for state timeout
        if is_state_timed_out "$room_dir"; then
          log ERROR "[$task_ref] State '$status' timed out after ${STATE_TIMEOUT}s." 2>/dev/null || echo "[MANAGER] [$task_ref] State '$status' timed out after ${STATE_TIMEOUT}s." >&2
          kill_room_processes "$room_dir"
          if [ "$retries" -lt "$MAX_RETRIES" ]; then
            echo $((retries + 1)) > "$room_dir/retries"
            "$CHANNEL/post.sh" "$room_dir" manager engineer fix "$task_ref" "Previous attempt timed out after ${STATE_TIMEOUT}s. Please try again."
            write_status "$room_dir" "fixing"
            "$AGENTS_DIR/roles/engineer/run.sh" "$room_dir" &
          else
            log ERROR "[$task_ref] Max retries exceeded after timeout." 2>/dev/null || echo "[MANAGER] [$task_ref] Max retries exceeded after timeout." >&2
            write_status "$room_dir" "failed-final"
          fi
          continue
        fi

        done_count=$(msg_count "$room_dir" "done")
        expected=$((retries + 1))

        if [ "$done_count" -ge "$expected" ]; then
          log INFO "[$task_ref] Engineer done. Routing to QA..." 2>/dev/null || echo "[MANAGER] [$task_ref] Engineer done. Routing to QA..."
          # IMPORTANT: Write status BEFORE spawning to prevent race condition
          write_status "$room_dir" "qa-review"
          "$AGENTS_DIR/roles/qa/run.sh" "$room_dir" &
        else
          # Check if engineer process died
          if [ -f "$room_dir/pids/engineer.pid" ] && ! is_pid_alive "$room_dir/pids/engineer.pid" 2>/dev/null; then
            # Check for error messages (from engineer or QA parse failures)
            error_count=$(msg_count "$room_dir" "error")
            if [ "$error_count" -gt 0 ]; then
              error_body=$(latest_body "$room_dir" "error")
              log ERROR "[$task_ref] Engineer error: $error_body" 2>/dev/null || echo "[MANAGER] [$task_ref] Engineer error: $error_body" >&2
              if [ "$retries" -lt "$MAX_RETRIES" ]; then
                log INFO "[$task_ref] Retrying (attempt $((retries + 1))/$MAX_RETRIES)..." 2>/dev/null || echo "[MANAGER] [$task_ref] Retrying (attempt $((retries + 1))/$MAX_RETRIES)..."
                echo $((retries + 1)) > "$room_dir/retries"
                "$CHANNEL/post.sh" "$room_dir" manager engineer fix "$task_ref" "Previous attempt failed: $error_body. Please try again."
                write_status "$room_dir" "fixing"
                "$AGENTS_DIR/roles/engineer/run.sh" "$room_dir" &
              else
                log ERROR "[$task_ref] Max retries exceeded. Marking as failed." 2>/dev/null || echo "[MANAGER] [$task_ref] Max retries exceeded. Marking as failed." >&2
                write_status "$room_dir" "failed-final"
              fi
            else
              # PID dead, no error, no done — track for deadlock detection
              ACTIVE_WITH_NO_PID=$((ACTIVE_WITH_NO_PID + 1))
            fi
          fi
        fi
        ;;

      qa-review)
        ALL_PASSED=false
        TOTAL_ACTIVE=$((TOTAL_ACTIVE + 1))

        # Check for state timeout
        if is_state_timed_out "$room_dir"; then
          log ERROR "[$task_ref] QA review timed out after ${STATE_TIMEOUT}s." 2>/dev/null || echo "[MANAGER] [$task_ref] QA review timed out after ${STATE_TIMEOUT}s." >&2
          kill_room_processes "$room_dir"
          if [ "$retries" -lt "$MAX_RETRIES" ]; then
            echo $((retries + 1)) > "$room_dir/retries"
            "$CHANNEL/post.sh" "$room_dir" manager engineer fix "$task_ref" "QA review timed out. Please review and fix."
            write_status "$room_dir" "fixing"
            "$AGENTS_DIR/roles/engineer/run.sh" "$room_dir" &
          else
            write_status "$room_dir" "failed-final"
          fi
          continue
        fi

        pass_count=$(msg_count "$room_dir" "pass")
        if [ "$pass_count" -gt 0 ]; then
          log INFO "[$task_ref] QA PASSED! Room $room_id complete." 2>/dev/null || echo "[MANAGER] [$task_ref] QA PASSED! Room $room_id complete."
          write_status "$room_dir" "passed"
        else
          fail_count=$(msg_count "$room_dir" "fail")
          if [ "$fail_count" -gt 0 ]; then
            feedback=$(latest_body "$room_dir" "fail")
            if [ "$retries" -lt "$MAX_RETRIES" ]; then
              log INFO "[$task_ref] QA FAILED. Routing feedback to engineer (retry $((retries + 1))/$MAX_RETRIES)..." 2>/dev/null || echo "[MANAGER] [$task_ref] QA FAILED. Routing feedback to engineer (retry $((retries + 1))/$MAX_RETRIES)..."
              echo $((retries + 1)) > "$room_dir/retries"
              "$CHANNEL/post.sh" "$room_dir" manager engineer fix "$task_ref" "$feedback"
              write_status "$room_dir" "fixing"
              "$AGENTS_DIR/roles/engineer/run.sh" "$room_dir" &
            else
              log ERROR "[$task_ref] Max retries exceeded after QA failure. Marking as failed." 2>/dev/null || echo "[MANAGER] [$task_ref] Max retries exceeded after QA failure. Marking as failed." >&2
              write_status "$room_dir" "failed-final"
            fi
          else
            # Check for error messages from QA (verdict parse failure)
            error_count=$(msg_count "$room_dir" "error")
            if [ "$error_count" -gt 0 ]; then
              error_body=$(latest_body "$room_dir" "error")
              log WARN "[$task_ref] QA error (verdict parse failure): $error_body" 2>/dev/null || echo "[MANAGER] [$task_ref] QA error: $error_body" >&2
              # Re-run QA instead of burning engineer retry
              if [ "$retries" -lt "$MAX_RETRIES" ]; then
                log INFO "[$task_ref] Re-running QA review..." 2>/dev/null || echo "[MANAGER] [$task_ref] Re-running QA review..."
                write_status "$room_dir" "qa-review"
                "$AGENTS_DIR/roles/qa/run.sh" "$room_dir" &
              else
                write_status "$room_dir" "failed-final"
              fi
            else
              # Check if QA process died
              if [ -f "$room_dir/pids/qa.pid" ] && ! is_pid_alive "$room_dir/pids/qa.pid" 2>/dev/null; then
                log WARN "[$task_ref] QA process died without verdict. Treating as error." 2>/dev/null || echo "[MANAGER] [$task_ref] QA process died without verdict. Treating as error." >&2
                "$CHANNEL/post.sh" "$room_dir" qa manager error "$task_ref" "QA process terminated without verdict"
              else
                ACTIVE_WITH_NO_PID=$((ACTIVE_WITH_NO_PID + 1))
              fi
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
        log WARN "Unknown status '$status' for $room_id" 2>/dev/null || echo "[MANAGER] Unknown status '$status' for $room_id" >&2
        ALL_PASSED=false
        ;;
    esac
  done

  # === Deadlock detection ===
  if [ "$TOTAL_ACTIVE" -gt 0 ] && [ "$ACTIVE_WITH_NO_PID" -eq "$TOTAL_ACTIVE" ]; then
    STALL_CYCLES=$((STALL_CYCLES + 1))
    if [ "$STALL_CYCLES" -ge 2 ]; then
      log WARN "Deadlock detected: $TOTAL_ACTIVE rooms active but no PIDs alive for 2 cycles. Attempting recovery..." 2>/dev/null || echo "[MANAGER] WARNING: Deadlock detected. Attempting recovery..." >&2
      for room_dir in "$WARROOMS"/room-*/; do
        [ -d "$room_dir" ] || continue
        local_status=$(cat "$room_dir/status" 2>/dev/null || echo "")
        local_task_ref=$(cat "$room_dir/task-ref" 2>/dev/null || echo "")
        if [ -z "$local_task_ref" ] && [ -f "$room_dir/TASKS.md" ]; then
          local_task_ref=$(head -1 "$room_dir/TASKS.md" | grep -oE '(EPIC|TASK)-[0-9]+' | head -1)
        fi
        local_task_ref="${local_task_ref:-UNKNOWN}"
        local_retries=$(cat "$room_dir/retries" 2>/dev/null || echo "0")
        case "$local_status" in
          engineering|fixing)
            if [ "$local_retries" -lt "$MAX_RETRIES" ]; then
              echo $((local_retries + 1)) > "$room_dir/retries"
              "$CHANNEL/post.sh" "$room_dir" manager engineer fix "$local_task_ref" "Deadlock recovery: restarting engineer."
              write_status "$room_dir" "fixing"
              "$AGENTS_DIR/roles/engineer/run.sh" "$room_dir" &
            else
              write_status "$room_dir" "failed-final"
            fi
            ;;
          qa-review)
            write_status "$room_dir" "qa-review"
            "$AGENTS_DIR/roles/qa/run.sh" "$room_dir" &
            ;;
        esac
      done
      STALL_CYCLES=0
    fi
  else
    STALL_CYCLES=0
  fi

  # === Release check ===
  if [ "$ROOM_COUNT" -gt 0 ] && $ALL_PASSED; then
    echo ""
    log INFO "All $ROOM_COUNT rooms PASSED! Drafting release..." 2>/dev/null || echo "[MANAGER] All $ROOM_COUNT rooms PASSED! Drafting release..."
    "$RELEASE_DIR/draft.sh" "$AGENTS_DIR"

    log INFO "Collecting signoffs..." 2>/dev/null || echo "[MANAGER] Collecting signoffs..."
    if "$RELEASE_DIR/signoff.sh" "$AGENTS_DIR"; then
      echo ""
      echo "============================================"
      log INFO "RELEASE COMPLETE! Release notes: $AGENTS_DIR/RELEASE.md" 2>/dev/null || echo "[MANAGER] RELEASE COMPLETE!"
      echo "  Release notes: $AGENTS_DIR/RELEASE.md"
      echo "============================================"
      log_json INFO "release_complete" rooms "$ROOM_COUNT" 2>/dev/null || true
      rm -f "$MANAGER_PID_FILE"
      break
    else
      log ERROR "Signoff failed. Continuing loop..." 2>/dev/null || echo "[MANAGER] Signoff failed. Continuing loop..." >&2
    fi
  fi

  # Status summary (every 10 iterations)
  if [ $((ITERATION % 10)) -eq 0 ] && [ "$ROOM_COUNT" -gt 0 ]; then
    passed_count=0
    failed_count=0
    for room_dir2 in "$WARROOMS"/room-*/; do
      [ -d "$room_dir2" ] || continue
      s2=$(cat "$room_dir2/status" 2>/dev/null || echo "")
      case "$s2" in
        passed) passed_count=$((passed_count + 1)) ;;
        failed-final) failed_count=$((failed_count + 1)) ;;
      esac
    done
    log INFO "Progress: $passed_count/$ROOM_COUNT passed, $failed_count failed (iteration $ITERATION)" 2>/dev/null || echo "[MANAGER] Progress: $passed_count/$ROOM_COUNT rooms passed, $failed_count failed (iteration $ITERATION)"
  fi

  sleep "$POLL_INTERVAL"
done
