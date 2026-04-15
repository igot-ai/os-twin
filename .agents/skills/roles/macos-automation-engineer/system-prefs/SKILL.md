---
name: system-prefs
description: Control macOS system settings: network, power, volume, dark mode, clipboard, notifications, and defaults."
tags: [macos-automation-engineer, automation, macos, system, settings, clipboard, notifications]
trust_level: core
platform: [macos]
requires_permissions: [SystemPolicyAllFiles]
shell: bash
---

# system-prefs

## Overview

Read and write macOS system preferences using `networksetup`, `pmset`, `defaults`, and `osascript`. Covers Wi-Fi, sleep/power, volume, mute, dark mode, Do Not Disturb, clipboard, system notifications, and arbitrary `defaults` keys.

**Required TCC permission:** Full Disk Access for some `defaults` domains (`System Settings > Privacy & Security > Full Disk Access`). Volume and dark mode work without special permissions.

## Commands

Invoke via `ostwin mac system <cmd> [args]` or dispatch via daemon. Underlying script: `.agents/scripts/macos/system.sh`

| Command | Arguments | Description |
|---------|-----------|-------------|
| `sleep` | _(none)_ | Put the system to sleep immediately (`pmset sleepnow`). |
| `display-sleep` | `<minutes>` | Set display sleep timeout. Use `0` to disable auto-sleep. |
| `volume` | `<0-100>` | Set system output volume level. |
| `volume-get` | _(none)_ | Print current output volume (0–100). |
| `mute` | `<on\|off>` | Mute (`on`) or unmute (`off`) the system output. |
| `wifi` | `<on\|off>` | Enable or disable Wi-Fi (auto-detects the active interface). |
| `wifi-status` | _(none)_ | Print Wi-Fi power state. |
| `notifications` | `<on\|off>` | Toggle Do Not Disturb. `off` = enable DND, `on` = disable DND. |
| `dark-mode` | `<on\|off>` | Enable or disable system dark mode via System Events. |
| `dark-mode-get` | _(none)_ | Print current dark mode state (`true` or `false`). |
| `clipboard-get` | _(none)_ | Print clipboard text content (`pbpaste`). |
| `clipboard-set` | `<text>` | Set clipboard to a text string (`pbcopy`). |
| `notify` | `<title> <message>` | Display a macOS user notification banner. |
| `default-read` | `<domain> <key>` | Read a `defaults` preference key for a domain. |
| `default-write` | `<domain> <key> <type> <value>` | Write a `defaults` preference key. |

**Argument constraints:**
- `<minutes>` — non-negative integer; `0` = never sleep
- `<0-100>` — integer in range 0–100
- `<on|off>` — literal string `on` or `off`
- `<title>`, `<message>` — string (backslash, backtick, and `$()` rejected)
- `<domain>` — e.g., `com.apple.dock`, `com.apple.finder`, `NSGlobalDomain`
- `<key>` — preference key name, e.g., `autohide`, `AppleShowAllFiles`
- `<type>` — one of: `-string`, `-int`, `-float`, `-bool`, `-date`, `-data`

## Usage

```bash
# Sleep
ostwin mac system sleep

# Display sleep timer
ostwin mac system display-sleep 10    # sleep display after 10 min
ostwin mac system display-sleep 0     # never sleep

# Volume
ostwin mac system volume 50
ostwin mac system volume-get
ostwin mac system mute on
ostwin mac system mute off

# Wi-Fi
ostwin mac system wifi off
ostwin mac system wifi on
ostwin mac system wifi-status

# Do Not Disturb
ostwin mac system notifications off   # enable DND
ostwin mac system notifications on    # disable DND

# Dark mode
ostwin mac system dark-mode on
ostwin mac system dark-mode off
ostwin mac system dark-mode-get       # returns true/false

# Clipboard
ostwin mac system clipboard-get
ostwin mac system clipboard-set "paste me"

# Notification banner
ostwin mac system notify "Build Done" "Your project compiled successfully."

# Defaults read/write
ostwin mac system default-read com.apple.dock autohide
ostwin mac system default-write com.apple.dock autohide -bool true
```

## Daemon Dispatch

```bash
# Volume
printf '{"script":"system","cmd":"volume","args":"60"}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock
printf '{"script":"system","cmd":"volume-get","args":""}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# Dark mode
printf '{"script":"system","cmd":"dark-mode","args":"on"}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# Clipboard
printf '{"script":"system","cmd":"clipboard-get","args":""}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# BSD nc fallback
printf '{"script":"system","cmd":"wifi-status","args":""}' | /usr/bin/nc -U /tmp/ostwin-macos-host.sock
```

## Direct CLI Patterns

```bash
# Volume via osascript
osascript -e 'set volume output volume 50'
osascript -e 'output volume of (get volume settings)'

# Wi-Fi — detect interface first
IFACE=$(networksetup -listallhardwareports | awk '/Wi-Fi|AirPort/{found=1;next} found{print $2;exit}')
networksetup -setairportpower "$IFACE" off
networksetup -getairportpower "$IFACE"

# Display sleep
pmset -a displaysleep 15   # -a = all power sources

# Dark mode via System Events
osascript -e 'tell application "System Events" to tell appearance preferences to set dark mode to true'
osascript -e 'tell application "System Events" to dark mode of appearance preferences'  # true/false

# Clipboard
pbpaste
echo "text to copy" | pbcopy

# Defaults
defaults read com.apple.dock autohide
defaults write com.apple.dock autohide -bool true
killall Dock   # required to apply dock changes
```

## After Defaults Write

Many `defaults write` changes require killing the affected process:

| Domain | Process to kill |
|--------|----------------|
| `com.apple.dock` | `Dock` |
| `com.apple.finder` | `Finder` |
| `com.apple.SystemUIServer` | `SystemUIServer` |
| `NSGlobalDomain` | varies by key |

## Rules

- `pmset` requires no special permissions for `-a displaysleep`; `pmset sleepnow` works in a user session without sudo.
- `networksetup` commands require no sudo when operating on the current user's network services.
- `defaults write` can write to any app's preferences container owned by the current user.
- After toggling dark mode via AppleScript, the change is immediate and system-wide — no killall needed.
- Always verify changes with a `default-read` or `volume-get` after writing.
