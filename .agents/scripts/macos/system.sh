#!/usr/bin/env bash
# system.sh — macOS system settings control
# Usage: system.sh <cmd> [args]
# Requires: macOS bash 3.2+, networksetup, pmset, defaults, osascript
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_lib.sh"

CMD="${1:-help}"
shift || true

# Detect active Wi-Fi interface dynamically
wifi_interface() {
  local iface
  iface=$(networksetup -listallhardwareports 2>/dev/null \
    | awk '/Wi-Fi|AirPort/{found=1; next} found && /Device:/{print $2; exit}') || true
  if [ -z "$iface" ]; then
    echo "en0"  # fallback
  else
    echo "$iface"
  fi
}

usage() {
  cat <<EOF
Usage: system.sh <cmd> [args]

Commands:
  sleep                              Put system to sleep immediately
  display-sleep <minutes>            Set display sleep timeout (0 = never)
  volume <0-100>                     Set system output volume
  volume-get                         Get current output volume
  mute <on|off>                      Toggle mute
  wifi <on|off>                      Toggle Wi-Fi
  wifi-status                        Show Wi-Fi on/off status
  notifications <on|off>             Toggle Do Not Disturb
  dark-mode <on|off>                 Toggle dark mode
  dark-mode-get                      Read current dark mode state
  clipboard-get                      Print clipboard text content
  clipboard-set <text>               Set clipboard text content
  notify <title> <message>           Show a system notification
  default-read <domain> <key>        Read a defaults key
  default-write <domain> <key> <type> <value>  Write a defaults key
  help                               Show this help

Types for default-write: -string, -int, -float, -bool, -date, -data
EOF
}

case "$CMD" in
  sleep)
    pmset sleepnow
    ;;

  display-sleep)
    MINUTES="${1:?Usage: system.sh display-sleep <minutes>}"
    validate_uint "$MINUTES" "minutes" || exit 1
    pmset -a displaysleep "$MINUTES"
    echo "Display sleep set to ${MINUTES} minutes"
    ;;

  volume)
    LEVEL="${1:?Usage: system.sh volume <0-100>}"
    validate_range "$LEVEL" 0 100 "volume" || exit 1
    run_osascript "set volume output volume $LEVEL" || exit $?
    echo "Volume set to $LEVEL"
    ;;

  volume-get)
    run_osascript 'output volume of (get volume settings)' || exit $?
    echo  # newline
    ;;

  mute)
    STATE="${1:?Usage: system.sh mute <on|off>}"
    case "$STATE" in
      on)  run_osascript 'set volume with output muted' || exit $?; echo "Muted" ;;
      off) run_osascript 'set volume without output muted' || exit $?; echo "Unmuted" ;;
      *)   echo "Invalid state: $STATE (use on or off)" >&2; exit 1 ;;
    esac
    ;;

  wifi)
    STATE="${1:?Usage: system.sh wifi <on|off>}"
    IFACE=$(wifi_interface)
    case "$STATE" in
      on|off)
        networksetup -setairportpower "$IFACE" "$STATE"
        echo "Wi-Fi ($IFACE) $STATE"
        ;;
      *)
        echo "Invalid state: $STATE (use on or off)" >&2
        exit 1
        ;;
    esac
    ;;

  wifi-status)
    IFACE=$(wifi_interface)
    networksetup -getairportpower "$IFACE"
    ;;

  notifications)
    STATE="${1:?Usage: system.sh notifications <on|off>}"
    case "$STATE" in
      off)
        defaults write com.apple.notificationcenterui doNotDisturb -bool true
        echo "Do Not Disturb enabled"
        ;;
      on)
        defaults write com.apple.notificationcenterui doNotDisturb -bool false
        echo "Do Not Disturb disabled"
        ;;
      *)
        echo "Invalid state: $STATE (use on or off)" >&2
        exit 1
        ;;
    esac
    ;;

  dark-mode)
    STATE="${1:?Usage: system.sh dark-mode <on|off>}"
    case "$STATE" in
      on)
        run_osascript 'tell application "System Events" to tell appearance preferences to set dark mode to true' || exit $?
        echo "Dark mode enabled"
        ;;
      off)
        run_osascript 'tell application "System Events" to tell appearance preferences to set dark mode to false' || exit $?
        echo "Dark mode disabled"
        ;;
      *)
        echo "Invalid state: $STATE (use on or off)" >&2
        exit 1
        ;;
    esac
    ;;

  dark-mode-get)
    run_osascript 'tell application "System Events" to dark mode of appearance preferences' || exit $?
    echo  # newline
    ;;

  clipboard-get)
    pbpaste
    ;;

  clipboard-set)
    TEXT="${1:?Usage: system.sh clipboard-set <text>}"
    printf '%s' "$TEXT" | pbcopy
    echo "Clipboard set"
    ;;

  notify)
    TITLE="${1:?Usage: system.sh notify <title> <message>}"
    MSG="${2:?Missing message}"
    validate_text "$TITLE" "title" || exit 1
    validate_text "$MSG" "message" || exit 1
    # Escape double-quotes in title and message for AppleScript string context
    SAFE_TITLE=$(printf '%s' "$TITLE" | sed 's/"/\\"/g')
    SAFE_MSG=$(printf '%s' "$MSG" | sed 's/"/\\"/g')
    run_osascript "display notification \"$SAFE_MSG\" with title \"$SAFE_TITLE\"" || exit $?
    echo "Notification sent"
    ;;

  default-read)
    DOMAIN="${1:?Usage: system.sh default-read <domain> <key>}"
    KEY="${2:?Missing key}"
    defaults read "$DOMAIN" "$KEY"
    ;;

  default-write)
    DOMAIN="${1:?Usage: system.sh default-write <domain> <key> <type> <value>}"
    KEY="${2:?Missing key}"; TYPE="${3:?Missing type}"; VALUE="${4:?Missing value}"
    defaults write "$DOMAIN" "$KEY" "$TYPE" "$VALUE"
    echo "Written: $DOMAIN $KEY $TYPE $VALUE"
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
