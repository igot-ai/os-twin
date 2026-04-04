#!/usr/bin/env bash
# axbridge.sh — macOS Accessibility API bridge via JXA (JavaScript for Automation)
# Reaches into UI elements that AppleScript's "tell application" cannot access:
# custom controls, non-standard text fields, toolbar items, menus, etc.
#
# Usage: axbridge.sh <cmd> [args]
# Requires: macOS bash 3.2+, osascript -l JavaScript, Accessibility TCC permission
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_lib.sh"

CMD="${1:-help}"
shift || true

usage() {
  cat <<EOF
Usage: axbridge.sh <cmd> [args]

Commands:
  ui-tree <AppName> [depth]         Dump the UI element tree (default depth 3)
  read-text <AppName> <role>        Read text from first element matching AX role
  find-button <AppName> <label>     Find a button by title/label
  click-button <AppName> <label>    Click a button by title/label
  read-focused                      Read the focused UI element's value
  menu-click <AppName> <menu> <item>  Click a menu bar item
  window-list <AppName>             List all windows with titles and positions
  element-attrs <AppName> <path>    Get attributes of a UI element by path
  help                              Show this help

Roles: AXButton, AXTextField, AXStaticText, AXCheckBox, AXRadioButton,
       AXPopUpButton, AXSlider, AXTable, AXScrollArea, AXGroup, AXImage

Examples:
  axbridge.sh ui-tree Safari 2
  axbridge.sh read-text "TextEdit" AXTextArea
  axbridge.sh find-button Safari "Downloads"
  axbridge.sh click-button "System Preferences" "General"
  axbridge.sh menu-click Safari File "New Window"
  axbridge.sh window-list Safari
EOF
}

# Run a JXA (JavaScript for Automation) script via osascript -l JavaScript
run_jxa() {
  local script="$1"
  local output rc
  output=$(osascript -l JavaScript -e "$script" 2>&1) && rc=0 || rc=$?
  if [ "$rc" -ne 0 ]; then
    case "$output" in
      *"not allowed assistive access"*|*"AXError"*|*"kAXError"*)
        echo "Error: Accessibility permission required for AX API." >&2
        echo "Grant in: System Settings > Privacy & Security > Accessibility" >&2
        return 126
        ;;
    esac
    echo "Error: JXA failed (exit $rc): $output" >&2
    return "$rc"
  fi
  printf '%s\n' "$output"
  return 0
}

case "$CMD" in
  ui-tree)
    APP="${1:?Usage: axbridge.sh ui-tree <AppName> [depth]}"
    DEPTH="${2:-3}"
    validate_app_name "$APP" || exit 1
    validate_uint "$DEPTH" "depth" || exit 1
    require_accessibility
    run_jxa "
      var app = Application('System Events').processes['$APP'];
      function dump(el, depth, maxDepth, indent) {
        if (depth > maxDepth) return '';
        var role = '', title = '', val = '';
        try { role = el.role(); } catch(e) {}
        try { title = el.title() || el.name() || ''; } catch(e) {}
        try { val = el.value(); if (val && String(val).length > 80) val = String(val).substring(0,80)+'...'; } catch(e) {}
        var line = indent + role;
        if (title) line += ' \"' + title + '\"';
        if (val) line += ' = ' + val;
        var out = line + '\\n';
        try {
          var kids = el.uiElements();
          for (var i = 0; i < kids.length; i++) {
            out += dump(kids[i], depth+1, maxDepth, indent+'  ');
          }
        } catch(e) {}
        return out;
      }
      var wins = app.windows();
      var result = '';
      for (var w = 0; w < wins.length; w++) {
        result += dump(wins[w], 0, $DEPTH, '');
      }
      result;
    " || exit $?
    ;;

  read-text)
    APP="${1:?Usage: axbridge.sh read-text <AppName> <role>}"
    ROLE="${2:?Missing AX role (e.g. AXTextArea, AXStaticText)}"
    validate_app_name "$APP" || exit 1
    require_accessibility
    run_jxa "
      var app = Application('System Events').processes['$APP'];
      function findFirst(el, targetRole) {
        try {
          if (el.role() === '$ROLE') {
            try { return el.value() || el.title() || ''; } catch(e) { return ''; }
          }
        } catch(e) {}
        try {
          var kids = el.uiElements();
          for (var i = 0; i < kids.length; i++) {
            var r = findFirst(kids[i], targetRole);
            if (r !== null && r !== '') return r;
          }
        } catch(e) {}
        return null;
      }
      var wins = app.windows();
      var result = null;
      for (var w = 0; w < wins.length && result === null; w++) {
        result = findFirst(wins[w], '$ROLE');
      }
      result || '(no matching element found)';
    " || exit $?
    ;;

  find-button)
    APP="${1:?Usage: axbridge.sh find-button <AppName> <label>}"
    LABEL="${2:?Missing button label}"
    validate_app_name "$APP" || exit 1
    require_accessibility
    run_jxa "
      var app = Application('System Events').processes['$APP'];
      var results = [];
      function findButtons(el) {
        try {
          if (el.role() === 'AXButton') {
            var t = '';
            try { t = el.title() || el.description() || ''; } catch(e) {}
            if (t.indexOf('$LABEL') !== -1) {
              var pos = '', size = '';
              try { pos = el.position(); } catch(e) {}
              try { size = el.size(); } catch(e) {}
              results.push(t + ' @ ' + pos + ' [' + size + ']');
            }
          }
        } catch(e) {}
        try {
          var kids = el.uiElements();
          for (var i = 0; i < kids.length; i++) findButtons(kids[i]);
        } catch(e) {}
      }
      var wins = app.windows();
      for (var w = 0; w < wins.length; w++) findButtons(wins[w]);
      results.length ? results.join('\\n') : '(no buttons matching \"$LABEL\")';
    " || exit $?
    ;;

  click-button)
    APP="${1:?Usage: axbridge.sh click-button <AppName> <label>}"
    LABEL="${2:?Missing button label}"
    validate_app_name "$APP" || exit 1
    require_accessibility
    run_jxa "
      var app = Application('System Events').processes['$APP'];
      function clickFirst(el) {
        try {
          if (el.role() === 'AXButton') {
            var t = '';
            try { t = el.title() || el.description() || ''; } catch(e) {}
            if (t.indexOf('$LABEL') !== -1) {
              el.actions['AXPress'].perform();
              return true;
            }
          }
        } catch(e) {}
        try {
          var kids = el.uiElements();
          for (var i = 0; i < kids.length; i++) {
            if (clickFirst(kids[i])) return true;
          }
        } catch(e) {}
        return false;
      }
      var wins = app.windows();
      var clicked = false;
      for (var w = 0; w < wins.length && !clicked; w++) {
        clicked = clickFirst(wins[w]);
      }
      clicked ? 'Clicked: $LABEL' : 'Button not found: $LABEL';
    " || exit $?
    ;;

  read-focused)
    require_accessibility
    run_jxa "
      var se = Application('System Events');
      var focused = se.focusedUIElement();
      var role = '', val = '', title = '';
      try { role = focused.role(); } catch(e) {}
      try { title = focused.title() || focused.name() || ''; } catch(e) {}
      try { val = focused.value() || ''; } catch(e) {}
      role + ' \"' + title + '\" = ' + val;
    " || exit $?
    ;;

  menu-click)
    APP="${1:?Usage: axbridge.sh menu-click <AppName> <menu> <item>}"
    MENU="${2:?Missing menu name}"
    ITEM="${3:?Missing menu item name}"
    validate_app_name "$APP" || exit 1
    require_accessibility
    # Activate the app first so its menu bar is visible
    run_osascript "tell application \"$APP\" to activate" || exit $?
    sleep 0.3
    run_jxa "
      var se = Application('System Events');
      var proc = se.processes['$APP'];
      proc.menuBars[0].menuBarItems['$MENU'].menus[0].menuItems['$ITEM'].click();
      'Clicked: $APP > $MENU > $ITEM';
    " || exit $?
    ;;

  window-list)
    APP="${1:?Usage: axbridge.sh window-list <AppName>}"
    validate_app_name "$APP" || exit 1
    require_accessibility
    run_jxa "
      var app = Application('System Events').processes['$APP'];
      var wins = app.windows();
      var lines = [];
      for (var i = 0; i < wins.length; i++) {
        var title = '', pos = '', size = '';
        try { title = wins[i].title() || '(untitled)'; } catch(e) {}
        try { pos = wins[i].position(); } catch(e) {}
        try { size = wins[i].size(); } catch(e) {}
        lines.push('[' + i + '] \"' + title + '\" pos=' + pos + ' size=' + size);
      }
      lines.length ? lines.join('\\n') : '(no windows)';
    " || exit $?
    ;;

  element-attrs)
    APP="${1:?Usage: axbridge.sh element-attrs <AppName> <path>}"
    ELEMPATH="${2:?Missing element path (e.g. 'windows[0].buttons[0]')}"
    validate_app_name "$APP" || exit 1
    require_accessibility
    run_jxa "
      var app = Application('System Events').processes['$APP'];
      var el = app.$ELEMPATH;
      var attrs = el.attributes();
      var lines = [];
      for (var i = 0; i < attrs.length; i++) {
        var name = attrs[i].name();
        var val = '';
        try { val = attrs[i].value(); } catch(e) { val = '(error)'; }
        lines.push(name + ' = ' + val);
      }
      lines.join('\\n');
    " || exit $?
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
