---
name: axbridge
description: Inspect and interact with macOS Accessibility (AX) UI elements via JXA: dump UI trees, read text, find/click buttons, click menus, and read attributes."
tags: [macos-automation-engineer, automation, macos, accessibility, jxa, ui-elements]
: core
platform: [macos]
requires_permissions: [Accessibility]
shell: bash
---

# axbridge

## Overview

Bridge to the macOS Accessibility API via JXA (JavaScript for Automation). Use when AppleScript `tell application` cannot reach custom controls, non-standard text fields, toolbar items, or deeply nested UI elements.

**Required TCC permission:** Accessibility (`System Settings > Privacy & Security > Accessibility`)

> **When to use axbridge vs. other skills:**
> - `app-control` / `window-management` — standard app lifecycle and window geometry
> - `input-capture` — blind mouse clicks / keystrokes at known coordinates
> - **`axbridge`** — inspect the UI element tree, read text from arbitrary elements, click buttons by label, navigate menus programmatically

## Commands

Invoke via `ostwin mac axbridge <cmd> [args]`. Underlying script: `.agents/scripts/macos/axbridge.sh`

> **Note:** `axbridge` (and `devtools`) are not exposed via the daemon — invoke directly via `ostwin mac`.

| Command | Arguments | Description |
|---------|-----------|-------------|
| `ui-tree` | `<AppName> [depth]` | Dump the full UI element tree of all open windows. Depth defaults to `3`. |
| `read-text` | `<AppName> <role>` | Read text/value from the first UI element matching a given AX role. |
| `find-button` | `<AppName> <label>` | Find all buttons whose title/description contains `label`. Prints title + position + size. |
| `click-button` | `<AppName> <label>` | Click the first button whose title/description contains `label` via `AXPress`. |
| `read-focused` | _(none)_ | Read the role, title, and value of the currently focused UI element (system-wide). |
| `menu-click` | `<AppName> <menu> <item>` | Click a menu bar item. Activates the app first. |
| `window-list` | `<AppName>` | List all windows with their index, title, position, and size. |
| `element-attrs` | `<AppName> <path>` | Read all AX attributes of a UI element identified by a JXA path expression. |

**Argument constraints:**
- `<AppName>` — String (same validation rules as app-control). Must match Activity Monitor process name.
- `[depth]` — Non-negative integer. Controls recursion depth of `ui-tree`. Higher values are slower. Default: `3`.
- `<role>` — AX role string: `AXButton`, `AXTextField`, `AXStaticText`, `AXCheckBox`, `AXRadioButton`, `AXPopUpButton`, `AXSlider`, `AXTable`, `AXScrollArea`, `AXGroup`, `AXImage`, `AXTextArea`, `AXWebArea`.
- `<label>` — Substring to match against button title or description (case-sensitive partial match).
- `<menu>` — Menu bar title exactly as displayed, e.g. `"File"`, `"Edit"`, `"View"`.
- `<item>` — Menu item title exactly as displayed, e.g. `"New Window"`, `"Save As..."`.
- `<path>` — JXA path relative to the process object, e.g. `windows[0].buttons[0]`, `windows[0].groups[0].textFields[0]`.

## Usage

```bash
# Dump UI tree (discover element structure first)
ostwin mac axbridge ui-tree "Safari"
ostwin mac axbridge ui-tree "Safari" 2          # shallower tree
ostwin mac axbridge ui-tree "Safari" 5          # deep tree (slower)

# Read text from elements by AX role
ostwin mac axbridge read-text "TextEdit" AXTextArea
ostwin mac axbridge read-text "Safari" AXStaticText

# Find buttons by label (returns position + size)
ostwin mac axbridge find-button "Safari" "Downloads"
ostwin mac axbridge find-button "System Settings" "General"

# Click a button by label
ostwin mac axbridge click-button "System Settings" "General"

# Read the currently focused element (system-wide)
ostwin mac axbridge read-focused

# Click menu bar items (activates app first)
ostwin mac axbridge menu-click "Safari" "File" "New Window"
ostwin mac axbridge menu-click "TextEdit" "Format" "Make Plain Text"

# List all windows with positions
ostwin mac axbridge window-list "Safari"

# Read attributes of a specific element by path
ostwin mac axbridge element-attrs "Safari" "windows[0].buttons[0]"
ostwin mac axbridge element-attrs "Terminal" "windows[0].groups[0].textFields[0]"

# Show all subcommands
ostwin mac axbridge help
```

## Discovery Workflow

Always run `ui-tree` first to discover the element structure, then target specific elements:

```bash
# Step 1: Discover the UI tree
ostwin mac axbridge ui-tree "Safari" 3
# Output shows: AXWindow "Safari" → AXGroup → AXButton "Downloads" @ 500,40 [80,30]

# Step 2: Click the discovered button
ostwin mac axbridge click-button "Safari" "Downloads"

# Step 3: Verify the result
ostwin mac capture window "Safari" /tmp/verify.png
```

## Direct JXA Patterns

```bash
# Run raw JXA (JavaScript for Automation)
osascript -l JavaScript -e '
  var app = Application("System Events").processes["Safari"];
  var wins = app.windows();
  for (var i = 0; i < wins.length; i++) {
    wins[i].title();
  }
'

# Read all AX attributes of an element
osascript -l JavaScript -e '
  var app = Application("System Events").processes["Safari"];
  var el = app.windows[0].buttons[0];
  var attrs = el.attributes();
  for (var i = 0; i < attrs.length; i++) {
    attrs[i].name() + " = " + attrs[i].value();
  }
'

# Click a menu item
osascript -l JavaScript -e '
  var se = Application("System Events");
  var proc = se.processes["Safari"];
  proc.menuBars[0].menuBarItems["File"].menus[0].menuItems["New Window"].click();
'
```

## Common AX Roles

| Role | Typical Elements |
|------|-----------------|
| `AXButton` | Toolbar buttons, dialog buttons, close/minimize/zoom |
| `AXTextField` | Text input fields, search bars |
| `AXTextArea` | Multi-line text areas (editors, notes) |
| `AXStaticText` | Labels, status text, non-editable text |
| `AXCheckBox` | Checkboxes, toggles |
| `AXRadioButton` | Radio buttons |
| `AXPopUpButton` | Dropdown menus, select boxes |
| `AXSlider` | Volume sliders, progress bars |
| `AXTable` | Data tables, list views |
| `AXScrollArea` | Scrollable containers |
| `AXGroup` | Container groups, toolbar groups |
| `AXWebArea` | Web content in browser windows |

## Rules

- Always run `ui-tree` first to discover element paths before using `click-button` or `element-attrs`.
- Depth > 5 in `ui-tree` can be very slow for complex apps — start with depth 2-3.
- `click-button` uses `AXPress` action — this works for standard buttons but may not work for custom controls; fall back to `input-capture click` at the button's coordinates.
- `menu-click` activates the app first (brings it to foreground) — menu bar must be visible.
- `element-attrs` path syntax follows JXA: `windows[0].buttons[0]`, `windows[0].groups[0].textFields[0]`.
- `read-focused` reads the system-wide focused element — useful for determining which field has keyboard focus.
- All AX operations require the Accessibility TCC permission. If denied, the script returns exit 126 with instructions.
