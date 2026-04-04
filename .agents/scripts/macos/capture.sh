#!/usr/bin/env bash
# capture.sh — macOS screenshot capture via screencapture
# Usage: capture.sh <cmd> [args]
# Requires: macOS bash 3.2+, screencapture (built-in), Screen Recording TCC permission
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_lib.sh"

CMD="${1:-help}"
shift || true

# Default output path with timestamp
default_out() {
  echo "/tmp/ostwin-capture-$(date +%s).png"
}

usage() {
  cat <<EOF
Usage: capture.sh <cmd> [args]

Commands:
  full [outfile]                    Capture entire screen
  region <x> <y> <w> <h> [outfile] Capture a screen region
  window <AppName> [outfile]        Capture front window of an app
  clipboard                         Capture screen to clipboard
  help                              Show this help

Examples:
  capture.sh full /tmp/screen.png
  capture.sh region 0 0 1280 800 /tmp/region.png
  capture.sh window Safari /tmp/safari.png
  capture.sh clipboard

Note: Requires Screen Recording permission in System Settings > Privacy & Security.
Output files are saved as PNG.
EOF
}

# Ensure output directory exists
ensure_dir() {
  local dir
  dir=$(dirname "$1")
  if [ ! -d "$dir" ]; then
    mkdir -p "$dir" || { echo "Error: cannot create output directory: $dir" >&2; return 1; }
  fi
}

case "$CMD" in
  full)
    OUT="${1:-$(default_out)}"
    ensure_dir "$OUT" || exit 1
    screencapture -x "$OUT" || { echo "Error: screencapture failed (Screen Recording permission may be required)" >&2; exit 1; }
    echo "Captured full screen: $OUT"
    ;;

  region)
    X="${1:?Usage: capture.sh region <x> <y> <w> <h> [outfile]}"
    Y="${2:?Missing y}"; W="${3:?Missing width}"; H="${4:?Missing height}"
    validate_uint "$X" "x" || exit 1
    validate_uint "$Y" "y" || exit 1
    validate_uint "$W" "width" || exit 1
    validate_uint "$H" "height" || exit 1
    OUT="${5:-$(default_out)}"
    ensure_dir "$OUT" || exit 1
    screencapture -x -R "$X,$Y,$W,$H" "$OUT" || { echo "Error: screencapture failed" >&2; exit 1; }
    echo "Captured region ${W}x${H} at $X,$Y: $OUT"
    ;;

  window)
    APP="${1:?Usage: capture.sh window <AppName> [outfile]}"
    validate_app_name "$APP" || exit 1
    OUT="${2:-$(default_out)}"
    ensure_dir "$OUT" || exit 1
    # Get the CGWindowID for the front window of the app via System Events
    WIN_ID=$(run_osascript "
      tell application \"System Events\"
        tell process \"$APP\"
          set w to front window
          return id of w
        end tell
      end tell
    ") || WIN_ID=""
    if [ -n "$WIN_ID" ] && [ "$WIN_ID" != "missing value" ]; then
      screencapture -x -l "$WIN_ID" "$OUT" || { echo "Error: screencapture -l failed for window ID $WIN_ID" >&2; exit 1; }
    else
      # Fallback: activate app and capture frontmost window
      echo "Warning: could not get window ID, capturing frontmost window" >&2
      run_osascript "tell application \"$APP\" to activate" 2>/dev/null || true
      sleep 0.3
      screencapture -x -o "$OUT" || { echo "Error: screencapture failed" >&2; exit 1; }
    fi
    echo "Captured $APP window: $OUT"
    ;;

  clipboard)
    screencapture -x -c || { echo "Error: screencapture to clipboard failed" >&2; exit 1; }
    echo "Captured screen to clipboard"
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
