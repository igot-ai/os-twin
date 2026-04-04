#!/usr/bin/env bash
# click.sh — macOS mouse input simulation via osascript
# Usage: click.sh <cmd> [args]
# Requires: macOS bash 3.2+, osascript, Accessibility TCC permission
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_lib.sh"

CMD="${1:-help}"
shift || true

usage() {
  cat <<EOF
Usage: click.sh <cmd> [args]

Commands:
  click <x> <y>             Single left click at screen coordinates
  double-click <x> <y>      Double click at screen coordinates
  right-click <x> <y>       Right (secondary) click at screen coordinates
  move <x> <y>              Move cursor to coordinates without clicking
  help                      Show this help

Note: Requires Accessibility permission in System Settings > Privacy & Security.
Coordinates are in screen pixels, origin at top-left.
EOF
}

validate_coords() {
  validate_uint "$1" "x" || return 1
  validate_uint "$2" "y" || return 1
}

case "$CMD" in
  click)
    X="${1:?Usage: click.sh click <x> <y>}"; Y="${2:?Missing y}"
    validate_coords "$X" "$Y" || exit 1
    require_accessibility
    run_osascript "tell application \"System Events\" to click at {$X, $Y}" || exit $?
    echo "Clicked at $X,$Y"
    ;;

  double-click)
    X="${1:?Usage: click.sh double-click <x> <y>}"; Y="${2:?Missing y}"
    validate_coords "$X" "$Y" || exit 1
    require_accessibility
    run_osascript "tell application \"System Events\" to double click at {$X, $Y}" || exit $?
    echo "Double-clicked at $X,$Y"
    ;;

  right-click)
    X="${1:?Usage: click.sh right-click <x> <y>}"; Y="${2:?Missing y}"
    validate_coords "$X" "$Y" || exit 1
    require_accessibility
    run_osascript "tell application \"System Events\" to secondary click at {$X, $Y}" || exit $?
    echo "Right-clicked at $X,$Y"
    ;;

  move)
    X="${1:?Usage: click.sh move <x> <y>}"; Y="${2:?Missing y}"
    validate_coords "$X" "$Y" || exit 1
    if command -v cliclick >/dev/null 2>&1; then
      cliclick "m:$X,$Y"
    else
      # CoreGraphics warp — no click, just move cursor
      run_osascript "
        use framework \"CoreGraphics\"
        use scripting additions
        set pt to current application's CGPointMake($X, $Y)
        current application's CGWarpMouseCursorPosition(pt)
      " 2>/dev/null || {
        echo "Warning: cursor move requires cliclick (brew install cliclick) for reliable support" >&2
        exit 1
      }
    fi
    echo "Moved cursor to $X,$Y"
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
