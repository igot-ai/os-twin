#!/usr/bin/env bash
# type.sh — macOS keyboard input simulation via osascript
# Usage: type.sh <cmd> [args]
# Requires: macOS bash 3.2+, osascript, Accessibility TCC permission
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_lib.sh"

CMD="${1:-help}"
shift || true

usage() {
  cat <<EOF
Usage: type.sh <cmd> [args]

Commands:
  text <string>                   Type a string of text (keystroke)
  key <keycode>                   Press a key by numeric key code
  combo <key> [mod mod ...]       Key + modifiers (command, option, control, shift)
  hold <keycode> <ms>             Hold a key for N milliseconds
  help                            Show this help

Examples:
  type.sh text "Hello, World!"
  type.sh key 36                  # Enter
  type.sh key 53                  # Escape
  type.sh combo c command         # Cmd+C (copy)
  type.sh combo z command         # Cmd+Z (undo)
  type.sh combo tab control       # Ctrl+Tab
  type.sh combo s command shift   # Cmd+Shift+S (Save As)
  type.sh hold 49 500             # Hold Space for 500ms

Common key codes:
  36=Return  48=Tab  49=Space  51=Delete  53=Escape
  123=Left   124=Right  125=Down  126=Up
EOF
}

# Escape a string for safe embedding in AppleScript double-quoted context.
# Handles: backslash, double-quote, and rejects control characters.
escape_for_applescript() {
  local text="$1"
  # Reject strings containing newlines or control characters (can't be typed via keystroke)
  case "$text" in
    *"$(printf '\n')"*|*"$(printf '\r')"*|*"$(printf '\t')"*)
      echo "Error: text contains control characters (newline/tab); use 'key' command instead" >&2
      return 1
      ;;
  esac
  # Escape backslashes first, then double-quotes
  printf '%s' "$text" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g'
}

case "$CMD" in
  text)
    TEXT="${1:?Usage: type.sh text <string>}"
    require_accessibility
    ESCAPED=$(escape_for_applescript "$TEXT") || exit 1
    run_osascript "tell application \"System Events\" to keystroke \"$ESCAPED\"" || exit $?
    echo "Typed: $TEXT"
    ;;

  key)
    KEYCODE="${1:?Usage: type.sh key <keycode>}"
    validate_uint "$KEYCODE" "keycode" || exit 1
    require_accessibility
    run_osascript "tell application \"System Events\" to key code $KEYCODE" || exit $?
    echo "Key code: $KEYCODE"
    ;;

  combo)
    KEY="${1:?Usage: type.sh combo <key> [mod ...]}"
    shift || true
    require_accessibility
    # Build modifier list: "command down, option down" etc.
    # bash 3.2 safe — string concatenation, no arrays
    MODS=""
    for MOD in "$@"; do
      case "$MOD" in
        command|cmd)   PART="command down" ;;
        option|alt)    PART="option down" ;;
        control|ctrl)  PART="control down" ;;
        shift)         PART="shift down" ;;
        *)
          echo "Unknown modifier: $MOD (valid: command, option, control, shift)" >&2
          exit 1
          ;;
      esac
      if [ -z "$MODS" ]; then
        MODS="$PART"
      else
        MODS="$MODS, $PART"
      fi
    done

    # Escape the key for AppleScript
    ESCAPED_KEY=$(escape_for_applescript "$KEY") || exit 1

    if [ -z "$MODS" ]; then
      run_osascript "tell application \"System Events\" to keystroke \"$ESCAPED_KEY\"" || exit $?
    else
      run_osascript "tell application \"System Events\" to keystroke \"$ESCAPED_KEY\" using {$MODS}" || exit $?
    fi
    echo "Combo: $KEY + {$MODS}"
    ;;

  hold)
    KEYCODE="${1:?Usage: type.sh hold <keycode> <ms>}"
    MS="${2:?Missing duration in milliseconds}"
    validate_uint "$KEYCODE" "keycode" || exit 1
    validate_uint "$MS" "duration" || exit 1
    require_accessibility
    SECS=$(awk "BEGIN {printf \"%.3f\", $MS/1000}")
    run_osascript "tell application \"System Events\" to key down $KEYCODE" || exit $?
    sleep "$SECS"
    run_osascript "tell application \"System Events\" to key up $KEYCODE" || exit $?
    echo "Held key $KEYCODE for ${MS}ms"
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
