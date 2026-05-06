---
name: app-control
description: Launch, quit, query frontmost app, and list running apps on macOS using osascript and open."
tags: [computer-use, automation, macos, apps]

platform: [macos]
requires_permissions: []
shell: bash
---

# app-control

## Overview

Control macOS application lifecycle: launch apps, quit gracefully, identify the frontmost app, and enumerate running apps. Uses `open -a` for launching and `osascript` + System Events for process queries.

No TCC permissions required. All operations work out of the box.

## Commands

Invoke via `ostwin mac app <cmd> [args]` or dispatch via daemon. Underlying script: `.agents/scripts/macos/app.sh`

| Command | Arguments | Description |
|---------|-----------|-------------|
| `launch` | `<AppName>` | Open an application via `open -a`. Exit 0 on success. |
| `kill` | `<AppName>` | Gracefully quit via AppleScript; falls back to `pkill -ix` if refused. |
| `frontmost` | _(none)_ | Print process name of the currently focused application. |
| `list` | _(none)_ | Print all visible (non-background) running apps, one per line. |
| `is-running` | `<AppName>` | Exit 0 + print `running` if process exists; exit 1 + `not running` otherwise. |

**`<AppName>` rules:** Must match the process name shown in Activity Monitor. Rejected characters: `"`, `\`, `` ` ``, `$`, `;`, `&`, `|`, `>`, `<`, `!`

## Usage

```bash
# Launch an application
ostwin mac app launch "Safari"
ostwin mac app launch "Visual Studio Code"

# Quit an application (graceful, fallback to force-kill)
ostwin mac app kill "Safari"

# Get the frontmost (focused) app name
ostwin mac app frontmost

# List all visible running apps (one per line)
ostwin mac app list

# Check if an app is running (exit 0 = running, exit 1 = not running)
ostwin mac app is-running "Safari" && echo "Safari is open"
```

## Daemon Dispatch

```bash
# List running apps (preferred — socat, bidirectional)
printf '{"script":"app","cmd":"list","args":""}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# Launch Safari
printf '{"script":"app","cmd":"launch","args":"Safari"}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# Check if running
printf '{"script":"app","cmd":"is-running","args":"Safari"}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# BSD nc fallback (explicit path — Homebrew GNU netcat does not support -U)
printf '{"script":"app","cmd":"list","args":""}' | /usr/bin/nc -U /tmp/ostwin-macos-host.sock
```

## Direct osascript Patterns

Use these for inline automation without calling the script:

```bash
# Launch
open -a "Safari"

# Graceful quit
osascript -e 'tell application "Safari" to quit'

# Force quit (if osascript fails)
pkill -ix "Safari"

# Frontmost app
osascript -e 'tell application "System Events" to name of first process whose frontmost is true'

# List all non-background processes
osascript -e 'tell application "System Events" to name of every process where background only is false'
# Returns: "Finder, Safari, Terminal, ..." — split on ", " to get individual names

# Check if running (returns count: 0 or 1)
osascript -e 'tell application "System Events" to count (every process whose name is "Safari")'
```

## Rules

- Always try graceful quit before force-kill. Apps may prompt to save unsaved work.
- The `list` output is comma-separated from AppleScript; `app.sh list` normalises it to one-per-line.
- App names in `open -a` are case-insensitive; in `osascript` they should match the exact process name shown in Activity Monitor.
- To bring an app to the foreground before sending keystrokes, use `osascript -e 'tell application "AppName" to activate'`.
