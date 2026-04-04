#!/usr/bin/env bash
# install.sh — Install the OSTwin macOS host daemon as a LaunchAgent
# Run this script once to set up persistent desktop automation support.
#
# What it does:
#   1. Creates log directory
#   2. Substitutes OSTWIN_HOME in the plist and copies to ~/Library/LaunchAgents/
#   3. Loads the LaunchAgent via launchctl (starts on login)
#   4. Opens System Settings to Accessibility pane for TCC grants
#
# Usage: bash .agents/daemons/macos-host/install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OSTWIN_HOME="${OSTWIN_HOME:-$HOME/.ostwin}"
PLIST_NAME="com.ostwin.macos-host.plist"
PLIST_SRC="$SCRIPT_DIR/$PLIST_NAME"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_DEST="$LAUNCH_AGENTS_DIR/$PLIST_NAME"
LOGS_DIR="$OSTWIN_HOME/logs"

info()  { echo "[ostwin] $*"; }
error() { echo "[ostwin] ERROR: $*" >&2; exit 1; }

# ── Preflight checks ─────────────────────────────────────────────────────────

[[ "$(uname -s)" == "Darwin" ]] || error "This installer is macOS-only."
[[ -f "$PLIST_SRC" ]] || error "Plist not found: $PLIST_SRC"

# ── 1. Create directories ─────────────────────────────────────────────────────

mkdir -p "$LOGS_DIR"
mkdir -p "$LAUNCH_AGENTS_DIR"
info "Log directory: $LOGS_DIR"

# ── 2. Substitute OSTWIN_HOME placeholder and install plist ──────────────────

# macOS sed requires empty string after -i for in-place without backup
sed "s|OSTWIN_HOME|${OSTWIN_HOME}|g" "$PLIST_SRC" > "$PLIST_DEST"
chmod 644 "$PLIST_DEST"
info "Installed plist: $PLIST_DEST"

# Make daemon script executable
chmod +x "$SCRIPT_DIR/host-daemon.sh"

# ── 3. Load (or reload) the LaunchAgent ──────────────────────────────────────

# Unload first in case it was already loaded (ignore error if not loaded)
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load -w "$PLIST_DEST"
info "LaunchAgent loaded: com.ostwin.macos-host"

# ── 4. Verify it started ──────────────────────────────────────────────────────

sleep 1
if launchctl list | grep -q "com.ostwin.macos-host"; then
  info "Daemon is running."
else
  info "Warning: daemon may not have started yet. Check logs:"
  info "  tail -f $LOGS_DIR/macos-host-err.log"
fi

# ── 5. TCC permission guidance ────────────────────────────────────────────────

info ""
info "NEXT STEP: Grant the following permissions in System Settings:"
info "  - Accessibility     (required for window control and input simulation)"
info "  - Screen Recording  (required for screenshots)"
info ""
info "Opening Accessibility pane now..."
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" 2>/dev/null || \
  open "/System/Library/PreferencePanes/Security.prefPane" 2>/dev/null || true

info ""
info "To test: printf '{\"script\":\"app\",\"cmd\":\"list\",\"args\":\"\"}' | nc -U /tmp/ostwin-macos-host.sock"
info "To view logs: tail -f $LOGS_DIR/macos-host.log"
