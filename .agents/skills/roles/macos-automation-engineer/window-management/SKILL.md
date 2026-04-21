---
name: window-management
description: Move, resize, minimize, restore, fullscreen, and inspect macOS application windows via osascript."
tags: [macos-automation-engineer, automation, macos, windows]
: core
platform: [macos]
requires_permissions: [Accessibility]
shell: bash
---

# window-management

## Overview

Control macOS window geometry and state: move, resize, set exact bounds, minimize, restore, toggle fullscreen, and read current bounds. Uses AppleScript `bounds` property and System Events keystroke for fullscreen.

**Required TCC permission:** Accessibility (`System Settings > Privacy & Security > Accessibility`)

## Commands

Invoke via `ostwin mac window <cmd> [args]` or dispatch via daemon. Underlying script: `.agents/scripts/macos/window.sh`

| Command | Arguments | Description |
|---------|-----------|-------------|
| `move` | `<AppName> <x> <y>` | Move front window top-left corner to (x, y) while preserving current size. |
| `resize` | `<AppName> <w> <h>` | Resize front window to (w × h) while preserving current position. |
| `set-bounds` | `<AppName> <x> <y> <w> <h>` | Set both position and size in one operation. |
| `minimize` | `<AppName>` | Minimize front window to the Dock. |
| `restore` | `<AppName>` | Restore the minimized front window. |
| `fullscreen` | `<AppName>` | Toggle fullscreen via Ctrl+Cmd+F keystroke. |
| `get-bounds` | `<AppName>` | Print current front window bounds as `left, top, right, bottom`. |

**Argument constraints:**
- `<AppName>` — must match Activity Monitor process name (same rules as app-control)
- `<x>`, `<y>` — integer (can be negative for multi-monitor); origin is top-left of primary display
- `<w>`, `<h>` — non-negative integer in pixels; zero is rejected

## Usage

```bash
# Move front window (preserves current size)
ostwin mac window move "Safari" 100 200

# Resize front window (preserves current position)
ostwin mac window resize "Safari" 1280 800

# Set exact position + size in one call
ostwin mac window set-bounds "Safari" 0 25 1440 875

# Minimize / restore
ostwin mac window minimize "Terminal"
ostwin mac window restore "Terminal"

# Toggle fullscreen (Ctrl+Cmd+F)
ostwin mac window fullscreen "Safari"

# Read current bounds
ostwin mac window get-bounds "Safari"
# Output: 0, 25, 1440, 875
```

## Daemon Dispatch

```bash
# Move window
printf '{"script":"window","cmd":"move","args":"Safari 100 200"}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# Get bounds
printf '{"script":"window","cmd":"get-bounds","args":"Safari"}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# BSD nc fallback
printf '{"script":"window","cmd":"resize","args":"Safari 1280 800"}' | /usr/bin/nc -U /tmp/ostwin-macos-host.sock
```

## Direct osascript Patterns

```bash
# Get current window bounds (returns "left, top, right, bottom")
osascript -e 'tell application "Safari" to get bounds of front window'

# Set window bounds — format is {left, top, right, bottom} NOT {x, y, width, height}
# To place at x=100 y=100 with size 1280x800:
#   right  = 100 + 1280 = 1380
#   bottom = 100 +  800 =  900
osascript -e 'tell application "Safari" to set bounds of front window to {100, 100, 1380, 900}'

# Minimize / restore
osascript -e 'tell application "Safari" to set miniaturized of front window to true'
osascript -e 'tell application "Safari" to set miniaturized of front window to false'

# Fullscreen via keystroke (must activate app first)
osascript -e 'tell application "Safari" to activate'
osascript -e 'tell application "System Events" to keystroke "f" using {control down, command down}'
```

## Coordinate System

- Origin (0, 0) is **top-left** of the primary display.
- Bounds format: `{left, top, right, bottom}` — `right = left + width`, `bottom = top + height`.
- Menu bar height is ~28px on non-Retina, ~44px on Retina displays (y=0 is behind the menu bar; use y≥28).
- Multi-monitor: secondary display coordinates depend on arrangement in System Settings > Displays. Negative x/y values are valid for displays to the left/above the primary.

## Rules

- Activate the target app before sending keystrokes: `tell application "AppName" to activate`.
- AppleScript window manipulation silently fails without Accessibility permission — grant it in System Settings.
- `miniaturized` only works on standard windows; sheet dialogs and panels cannot be minimized.
- Fullscreen is a toggle — calling it twice returns to windowed mode.
- `set-bounds` is preferred over separate `move` + `resize` to avoid two round trips.
