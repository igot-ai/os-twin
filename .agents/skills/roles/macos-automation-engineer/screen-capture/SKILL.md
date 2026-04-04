---
name: screen-capture
description: "Take full-screen, region, window, or clipboard screenshots on macOS using screencapture. Primary verification layer for automation."
tags: [macos-automation-engineer, automation, macos, screenshot, vision, verification]
trust_level: core
platform: [macos]
requires_permissions: [ScreenCapture]
shell: bash
---

# screen-capture

## Overview

Capture the macOS screen to a PNG file or clipboard. This is the **verification layer** in the OSTwin automation architecture — use it after every state-changing action (`window-management`, `input-capture`, `app-control`) to confirm the expected result.

**Required TCC permission:** Screen Recording (`System Settings > Privacy & Security > Screen Recording`)

## Commands

Invoke via `ostwin mac capture <cmd> [args]` or dispatch via daemon. Underlying script: `.agents/scripts/macos/capture.sh`

| Command | Arguments | Description |
|---------|-----------|-------------|
| `full` | `[outfile]` | Capture entire primary screen to PNG. |
| `region` | `<x> <y> <w> <h> [outfile]` | Capture a rectangular screen region. |
| `window` | `<AppName> [outfile]` | Capture the front window of an app by CGWindowID. |
| `clipboard` | _(none)_ | Capture full screen to the system clipboard (`screencapture -c`). |

**Argument constraints:**
- `[outfile]` — optional path; defaults to `/tmp/ostwin-capture-<unix-timestamp>.png`. Parent directories are created automatically.
- `<x>`, `<y>` — non-negative integer; top-left pixel of capture region (logical pixels, not physical/Retina).
- `<w>`, `<h>` — non-negative integer; width and height in logical pixels.
- `<AppName>` — must be running with an open window (same rules as app-control).

## Usage

```bash
# Full screen — explicit path
ostwin mac capture full /tmp/screen.png

# Full screen — auto-named in /tmp/
ostwin mac capture full

# Region capture
ostwin mac capture region 0 0 1280 800 /tmp/region.png

# Window capture (front window of app)
ostwin mac capture window "Safari" /tmp/safari.png

# Capture to clipboard (no file)
ostwin mac capture clipboard
```

## Daemon Dispatch

```bash
# Full screen
printf '{"script":"capture","cmd":"full","args":"/tmp/screen.png"}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# Region
printf '{"script":"capture","cmd":"region","args":"0 0 1280 800 /tmp/region.png"}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# Window
printf '{"script":"capture","cmd":"window","args":"Safari /tmp/safari.png"}' | socat - UNIX-CONNECT:/tmp/ostwin-macos-host.sock

# BSD nc fallback
printf '{"script":"capture","cmd":"full","args":"/tmp/screen.png"}' | /usr/bin/nc -U /tmp/ostwin-macos-host.sock
```

## Direct screencapture Patterns

```bash
# Full screen (no shutter sound — always use -x in automation)
screencapture -x /tmp/screen.png

# Region: -R x,y,width,height
screencapture -x -R 0,0,1280,800 /tmp/region.png

# Specific window by CGWindowID (-l)
WIN_ID=$(osascript -e 'tell application "System Events" to tell process "Safari" to id of front window')
screencapture -x -l "$WIN_ID" /tmp/window.png

# To clipboard
screencapture -x -c

# Convert PNG to JPEG with sips (if needed)
sips -s format jpeg /tmp/screen.png --out /tmp/screen.jpg
```

## Verification Workflow

```bash
# Pattern: Act → Capture → Inspect
ostwin mac app launch "TextEdit"
sleep 1  # allow window to appear
ostwin mac capture window "TextEdit" /tmp/verify.png
# Pass /tmp/verify.png to vision model or open to inspect
```

## Rules

- Always use `-x` (no sound) in automated captures.
- Output is always PNG. Use `sips` to convert: `sips -s format jpeg /tmp/screen.png --out /tmp/screen.jpg`
- Region coordinates are in **logical pixels** (not physical/Retina). On Retina displays, physical pixel count is 2×.
- Window capture by CGWindowID works for most apps. Sandboxed App Store apps may return a blank black window — fall back to `region` capture.
- `screencapture -c` captures to clipboard (full screen only); no built-in region-to-clipboard flag.
- This skill is the verification layer — use it after `input-capture` or `window-management` actions to confirm state changes.
