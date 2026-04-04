#!/usr/bin/env bash
# uninstall.sh — Remove the OSTwin macOS host daemon
# Usage: bash .agents/daemons/macos-host/uninstall.sh
set -euo pipefail

PLIST_NAME="com.ostwin.macos-host.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"
SOCKET_PATH="/tmp/ostwin-macos-host.sock"

info()  { echo "[ostwin] $*"; }

[[ "$(uname -s)" == "Darwin" ]] || { echo "macOS only." >&2; exit 1; }

# Unload if loaded
if launchctl list 2>/dev/null | grep -q "com.ostwin.macos-host"; then
  launchctl unload -w "$PLIST_DEST" 2>/dev/null || true
  info "LaunchAgent unloaded."
else
  info "LaunchAgent was not loaded."
fi

# Remove plist
if [ -f "$PLIST_DEST" ]; then
  rm -f "$PLIST_DEST"
  info "Removed: $PLIST_DEST"
fi

# Remove socket
if [ -S "$SOCKET_PATH" ]; then
  rm -f "$SOCKET_PATH"
  info "Removed socket: $SOCKET_PATH"
fi

info "OSTwin macOS host daemon uninstalled."
