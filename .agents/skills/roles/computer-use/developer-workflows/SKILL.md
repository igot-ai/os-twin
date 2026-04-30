---
name: developer-workflows
description: Build Xcode projects, manage simulators, verify code signatures, access keychains, and manage Homebrew packages on macOS."
tags: [computer-use, automation, macos, xcode, developer, homebrew, codesign]

platform: [macos]
requires_permissions: []
shell: bash
---

# developer-workflows

## Overview

Automate macOS developer tasks: build/test Xcode projects, manage iOS simulators, verify/inspect code signatures, read keychain passwords, and manage Homebrew packages. Uses `xcodebuild`, `xcrun`, `codesign`, `security`, and `brew`.

Requires Xcode CLI tools (`xcode-select --install`). Homebrew commands require Homebrew (`brew`).

## Commands

Invoke via `ostwin mac devtools <cmd> [args]`. Underlying script: `.agents/scripts/macos/devtools.sh`

> **Note:** `devtools` (and `axbridge`) are not exposed via the daemon — invoke directly via `ostwin mac`.

| Command | Arguments | Description |
|---------|-----------|-------------|
| `xcode-build` | `<project_dir> [scheme]` | Build an Xcode project or workspace. Auto-detects `.xcworkspace` (preferred) or `.xcodeproj`. |
| `xcode-test` | `<project_dir> [scheme]` | Run the Xcode test suite. Same auto-detection as `xcode-build`. |
| `xcode-list` | `<project_dir>` | List all schemes in a project or workspace. |
| `xcrun` | `<tool> [args...]` | Run any Xcode toolchain tool directly (e.g., `swift`, `clang`, `otool`). Pass-through. |
| `simctl-list` | _(none)_ | List all available iOS/watchOS/tvOS simulators and their UDIDs. |
| `simctl-boot` | `<device_id>` | Boot a simulator by its UDID. |
| `simctl-shutdown` | `<device_id>` | Shutdown a running simulator by its UDID. |
| `codesign-verify` | `<path>` | Verify code signature of a binary or app bundle. |
| `codesign-info` | `<path>` | Print detailed signing identity, entitlements, and certificate info. |
| `keychain-list` | _(none)_ | List all keychains on the system. |
| `keychain-find` | `<service>` | Find a generic keychain password by service name (`-w` flag, prints password only). |
| `brew-list` | _(none)_ | List all installed Homebrew formulae. |
| `brew-install` | `<formula>` | Install a Homebrew formula. |
| `brew-outdated` | _(none)_ | List installed formulae with available updates. |
| `open-xcode` | `[project_dir]` | Open Xcode, or open a specific project/workspace from a directory. |

**Argument constraints:**
- `<project_dir>` — path to a directory containing `.xcworkspace` or `.xcodeproj`. Script auto-detects workspace over project.
- `[scheme]` — optional Xcode scheme name. If omitted, `xcodebuild` uses its default scheme. Use `xcode-list` to discover schemes.
- `<tool>` for `xcrun` — Xcode toolchain binary name: `swift`, `clang`, `otool`, `nm`, `lipo`, `install_name_tool`, etc.
- `<device_id>` — iOS Simulator UDID (e.g., `A1B2C3D4-...`). Obtain with `simctl-list`.
- `<path>` for codesign — absolute or relative path to a binary, `.app`, `.framework`, or `.dylib`. Must exist.
- `<service>` — keychain service name (e.g., `ostwin-mcp`, `github-token`).
- `<formula>` — Homebrew formula name (e.g., `jq`, `cliclick`, `gh`).

## Usage

```bash
# ── Xcode ──
ostwin mac devtools xcode-list ~/MyApp
ostwin mac devtools xcode-build ~/MyApp              # default scheme
ostwin mac devtools xcode-build ~/MyApp MyApp        # specific scheme
ostwin mac devtools xcode-test  ~/MyApp MyAppTests
ostwin mac devtools open-xcode  ~/MyApp
ostwin mac devtools open-xcode                       # open Xcode itself

# ── xcrun (pass-through to any Xcode tool) ──
ostwin mac devtools xcrun swift --version
ostwin mac devtools xcrun otool -L /usr/bin/swift
ostwin mac devtools xcrun clang --version

# ── iOS Simulators ──
ostwin mac devtools simctl-list
ostwin mac devtools simctl-boot  "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
ostwin mac devtools simctl-shutdown "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"

# ── Code Signing ──
ostwin mac devtools codesign-verify /Applications/Safari.app
ostwin mac devtools codesign-info   ~/MyApp/build/MyApp.app

# ── Keychain ──
ostwin mac devtools keychain-list
ostwin mac devtools keychain-find "ostwin-mcp"

# ── Homebrew ──
ostwin mac devtools brew-list
ostwin mac devtools brew-install jq
ostwin mac devtools brew-install cliclick
ostwin mac devtools brew-outdated
```

## Direct CLI Patterns

```bash
# Build from command line
xcodebuild -workspace MyApp.xcworkspace -scheme MyApp build
xcodebuild -workspace MyApp.xcworkspace -scheme MyApp test

# List simulators
xcrun simctl list devices available

# Verify code signature
codesign --verify --verbose=2 /path/to/app
codesign -d --entitlements - /path/to/app   # print entitlements

# Find keychain password
security find-generic-password -s "service-name" -w

# Xcode version
xcodebuild -version

# Swift version
xcrun swift --version
```

## Rules

- `xcodebuild` requires Xcode CLI tools — run `xcode-select --install` if not present.
- Always run `xcode-list` first to confirm the scheme exists before calling `xcode-build` or `xcode-test`.
- Xcode builds can take significant time — print progress to stdout and do not set a short timeout.
- `keychain-find` may trigger a macOS keychain access dialog on first use if the keychain is locked.
- `codesign-verify` returns exit 0 for valid signatures, non-zero for invalid or unsigned.
- Homebrew commands require `brew` in PATH — typically `/opt/homebrew/bin/brew` on Apple Silicon.
- This script is **not exposed via the daemon** — call it directly with `ostwin mac devtools`.
