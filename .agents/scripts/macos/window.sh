#!/usr/bin/env bash
# window.sh — macOS window geometry control via osascript
# Usage: window.sh <cmd> <AppName> [args]
# Requires: macOS bash 3.2+, osascript, Accessibility TCC permission
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_lib.sh"

CMD="${1:-help}"
shift || true

usage() {
  cat <<EOF
Usage: window.sh <cmd> <AppName> [args]

Commands:
  move <AppName> <x> <y>                Move front window (top-left corner)
  resize <AppName> <w> <h>              Resize front window
  set-bounds <AppName> <x> <y> <w> <h>  Set position and size
  minimize <AppName>                    Minimize front window to Dock
  restore <AppName>                     Restore minimized front window
  fullscreen <AppName>                  Toggle fullscreen (Ctrl+Cmd+F)
  get-bounds <AppName>                  Print current front window bounds
  help                                  Show this help

Note: Requires Accessibility permission in System Settings > Privacy & Security.
EOF
}

# Parse and validate bounds returned by osascript: "left, top, right, bottom"
parse_bounds() {
  local bounds="$1"
  if [ -z "$bounds" ]; then
    echo "Error: could not read window bounds (app not running or no window open)" >&2
    return 1
  fi
  # Validate format — must contain 3 commas and only digits/commas/spaces/minus
  case "$bounds" in
    *,*,*,*)  ;;  # has at least 3 commas — ok
    *)
      echo "Error: unexpected bounds format: $bounds" >&2
      return 1
      ;;
  esac
}

case "$CMD" in
  move)
    APP="${1:?Usage: window.sh move <AppName> <x> <y>}"
    X="${2:?Missing x}"; Y="${3:?Missing y}"
    validate_app_name "$APP" || exit 1
    validate_int "$X" "x" || exit 1
    validate_int "$Y" "y" || exit 1
    require_accessibility
    # Get current size to preserve it during move
    BOUNDS=$(run_osascript "tell application \"$APP\" to get bounds of front window") || exit $?
    parse_bounds "$BOUNDS" || exit 1
    CUR_LEFT=$(echo "$BOUNDS" | awk -F', ' '{print $1}')
    CUR_TOP=$(echo "$BOUNDS" | awk -F', ' '{print $2}')
    RIGHT=$(echo "$BOUNDS" | awk -F', ' '{print $3}')
    BOTTOM=$(echo "$BOUNDS" | awk -F', ' '{print $4}')
    W=$((RIGHT - CUR_LEFT))
    H=$((BOTTOM - CUR_TOP))
    NEW_RIGHT=$((X + W))
    NEW_BOTTOM=$((Y + H))
    run_osascript "tell application \"$APP\" to set bounds of front window to {$X, $Y, $NEW_RIGHT, $NEW_BOTTOM}" || exit $?
    echo "Moved $APP to $X,$Y (size ${W}x${H})"
    ;;

  resize)
    APP="${1:?Usage: window.sh resize <AppName> <w> <h>}"
    W="${2:?Missing width}"; H="${3:?Missing height}"
    validate_app_name "$APP" || exit 1
    validate_uint "$W" "width" || exit 1
    validate_uint "$H" "height" || exit 1
    require_accessibility
    BOUNDS=$(run_osascript "tell application \"$APP\" to get bounds of front window") || exit $?
    parse_bounds "$BOUNDS" || exit 1
    LEFT=$(echo "$BOUNDS" | awk -F', ' '{print $1}')
    TOP=$(echo "$BOUNDS" | awk -F', ' '{print $2}')
    NEW_RIGHT=$((LEFT + W))
    NEW_BOTTOM=$((TOP + H))
    run_osascript "tell application \"$APP\" to set bounds of front window to {$LEFT, $TOP, $NEW_RIGHT, $NEW_BOTTOM}" || exit $?
    echo "Resized $APP to ${W}x${H}"
    ;;

  set-bounds)
    APP="${1:?Usage: window.sh set-bounds <AppName> <x> <y> <w> <h>}"
    X="${2:?Missing x}"; Y="${3:?Missing y}"; W="${4:?Missing width}"; H="${5:?Missing height}"
    validate_app_name "$APP" || exit 1
    validate_int "$X" "x" || exit 1
    validate_int "$Y" "y" || exit 1
    validate_uint "$W" "width" || exit 1
    validate_uint "$H" "height" || exit 1
    require_accessibility
    RIGHT=$((X + W))
    BOTTOM=$((Y + H))
    run_osascript "tell application \"$APP\" to set bounds of front window to {$X, $Y, $RIGHT, $BOTTOM}" || exit $?
    echo "Set $APP bounds: origin=$X,$Y size=${W}x${H}"
    ;;

  minimize)
    APP="${1:?Usage: window.sh minimize <AppName>}"
    validate_app_name "$APP" || exit 1
    require_accessibility
    run_osascript "tell application \"$APP\" to set miniaturized of front window to true" || exit $?
    echo "Minimized: $APP"
    ;;

  restore)
    APP="${1:?Usage: window.sh restore <AppName>}"
    validate_app_name "$APP" || exit 1
    require_accessibility
    run_osascript "tell application \"$APP\" to set miniaturized of front window to false" || exit $?
    echo "Restored: $APP"
    ;;

  fullscreen)
    APP="${1:?Usage: window.sh fullscreen <AppName>}"
    validate_app_name "$APP" || exit 1
    require_accessibility
    run_osascript "tell application \"$APP\" to activate" || exit $?
    run_osascript 'tell application "System Events" to keystroke "f" using {control down, command down}' || exit $?
    echo "Toggled fullscreen: $APP"
    ;;

  get-bounds)
    APP="${1:?Usage: window.sh get-bounds <AppName>}"
    validate_app_name "$APP" || exit 1
    BOUNDS=$(run_osascript "tell application \"$APP\" to get bounds of front window") || exit $?
    echo "$BOUNDS"
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
