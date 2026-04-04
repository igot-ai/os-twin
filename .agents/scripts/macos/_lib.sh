#!/usr/bin/env bash
# _lib.sh — Shared validation and helpers for macOS automation scripts
# Source this: . "$(dirname "$0")/_lib.sh"
# Requires: macOS bash 3.2+

# ── Input validation ─────────────────────────────────────────────────────────

# Validate an app name — reject shell/AppleScript metacharacters
# Allows: letters, digits, spaces, hyphens, dots, underscores, parens
validate_app_name() {
  local name="$1"
  if [ -z "$name" ]; then
    echo "Error: app name is empty" >&2
    return 1
  fi
  # Reject characters that could escape AppleScript string context
  case "$name" in
    *'"'*|*'\'*|*'`'*|*'$'*|*';'*|*'&'*|*'|'*|*'>'*|*'<'*|*'!'*)
      echo "Error: app name contains invalid characters: $name" >&2
      return 1
      ;;
  esac
  return 0
}

# Validate that a value is a non-negative integer
validate_int() {
  local val="$1"
  local label="${2:-value}"
  case "$val" in
    ''|*[!0-9-]*)
      echo "Error: $label must be an integer, got: '$val'" >&2
      return 1
      ;;
  esac
  return 0
}

# Validate that a value is a non-negative integer (no negatives)
validate_uint() {
  local val="$1"
  local label="${2:-value}"
  case "$val" in
    ''|*[!0-9]*)
      echo "Error: $label must be a non-negative integer, got: '$val'" >&2
      return 1
      ;;
  esac
  return 0
}

# Validate integer is within range [min, max]
validate_range() {
  local val="$1"
  local min="$2"
  local max="$3"
  local label="${4:-value}"
  validate_int "$val" "$label" || return 1
  if [ "$val" -lt "$min" ] || [ "$val" -gt "$max" ]; then
    echo "Error: $label must be $min-$max, got: $val" >&2
    return 1
  fi
  return 0
}

# Validate text for safe embedding in AppleScript double-quoted strings.
# More permissive than validate_app_name — allows !, ?, etc.
# Rejects only characters that break AppleScript string syntax.
validate_text() {
  local text="$1"
  local label="${2:-text}"
  if [ -z "$text" ]; then
    echo "Error: $label is empty" >&2
    return 1
  fi
  # Reject only AppleScript string-breaking and shell-injection characters
  case "$text" in
    *'\'*|*'`'*|*'$('*)
      echo "Error: $label contains unsafe characters (backslash, backtick, or \$()" >&2
      return 1
      ;;
  esac
  return 0
}

# ── TCC permission checks ───────────────────────────────────────────────────

# Check if Accessibility (GUI scripting) is granted.
# Returns 0 if granted, 1 if denied.
check_accessibility() {
  osascript -e 'tell application "System Events" to name of first process whose frontmost is true' >/dev/null 2>&1
}

# Print a TCC error message and exit
require_accessibility() {
  if ! check_accessibility; then
    echo "Error: Accessibility permission required." >&2
    echo "Grant in: System Settings > Privacy & Security > Accessibility" >&2
    echo "Add Terminal (or your shell) to the allowed list." >&2
    exit 126
  fi
}

# ── osascript error wrapper ──────────────────────────────────────────────────

# Run osascript and capture errors instead of silencing them.
# Usage: run_osascript "tell application ..." || handle_error
run_osascript() {
  local script="$1"
  local output
  local rc
  output=$(osascript -e "$script" 2>&1) && rc=0 || rc=$?
  if [ "$rc" -ne 0 ]; then
    # Check for common TCC denial patterns
    case "$output" in
      *"not allowed assistive access"*|*"osascript is not allowed"*|*"1002"*)
        echo "Error: Accessibility permission denied for this operation." >&2
        echo "Grant in: System Settings > Privacy & Security > Accessibility" >&2
        return 126
        ;;
      *"execution error"*)
        echo "Error: AppleScript execution failed: $output" >&2
        return 1
        ;;
    esac
    echo "Error: osascript failed (exit $rc): $output" >&2
    return "$rc"
  fi
  printf '%s' "$output"
  return 0
}
