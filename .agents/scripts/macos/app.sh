#!/usr/bin/env bash
# app.sh — macOS application lifecycle control via osascript
# Usage: app.sh <cmd> [args]
# Requires: macOS bash 3.2+, osascript
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_lib.sh"

CMD="${1:-help}"
shift || true

usage() {
  cat <<EOF
Usage: app.sh <cmd> [args]

Commands:
  launch <AppName>      Open an application
  kill <AppName>        Gracefully quit, fallback to force-kill
  frontmost             Print name of frontmost application
  list                  Print all visible (non-background) running apps, one per line
  is-running <AppName>  Exit 0 if running, 1 if not
  help                  Show this help
EOF
}

case "$CMD" in
  launch)
    APP="${1:?Usage: app.sh launch <AppName>}"
    validate_app_name "$APP" || exit 1
    open -a "$APP"
    ;;

  kill)
    APP="${1:?Usage: app.sh kill <AppName>}"
    validate_app_name "$APP" || exit 1
    # Try graceful quit first
    if run_osascript "tell application \"$APP\" to quit"; then
      echo "Quit: $APP"
    else
      # Fallback to pkill
      pkill -ix "$APP" 2>/dev/null && echo "Force-killed: $APP" || echo "Not running: $APP"
    fi
    ;;

  frontmost)
    run_osascript 'tell application "System Events" to name of first process whose frontmost is true'
    echo  # newline after output
    ;;

  list)
    # AppleScript returns a comma-separated list; split to one-per-line
    RESULT=$(run_osascript 'tell application "System Events" to name of every process where background only is false') || exit $?
    echo "$RESULT" | tr ',' '\n' | sed 's/^ //' | sed 's/ $//'
    ;;

  is-running)
    APP="${1:?Usage: app.sh is-running <AppName>}"
    validate_app_name "$APP" || exit 1
    COUNT=$(run_osascript "tell application \"System Events\" to count (every process whose name is \"$APP\")") || COUNT=0
    if [ "$COUNT" -gt 0 ] 2>/dev/null; then
      echo "running"
      exit 0
    else
      echo "not running"
      exit 1
    fi
    ;;

  help|--help|-h)
    usage
    ;;

  *)
    echo "Unknown command: $CMD" >&2
    usage >&2
    exit 1
    ;;
esac
