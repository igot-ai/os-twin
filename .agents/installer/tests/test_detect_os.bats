#!/usr/bin/env bats
# Tests for detect-os.sh

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  # Reset guard to allow fresh sourcing
  unset _DETECT_OS_SH_LOADED
  source "$INSTALLER_DIR/detect-os.sh"
}

@test "detect-os.sh can be sourced without side effects" {
  # detect_os function exists but hasn't run yet
  declare -f detect_os > /dev/null
  # OS should not be set yet (function hasn't been called)
  [[ -z "${OS:-}" ]] || [[ "$OS" == "unknown" ]]
}

@test "detect_os() sets OS variable" {
  detect_os
  [[ -n "$OS" ]]
  [[ "$OS" != "unknown" ]]
}

@test "detect_os() sets ARCH variable" {
  detect_os
  [[ -n "$ARCH" ]]
}

@test "on macOS, OS=macos and PKG_MGR=brew" {
  detect_os
  if [[ "$(uname -s)" == "Darwin" ]]; then
    [[ "$OS" == "macos" ]]
    [[ "$PKG_MGR" == "brew" ]]
  else
    skip "Not running on macOS"
  fi
}

@test "on Linux, OS=linux" {
  detect_os
  if [[ "$(uname -s)" == "Linux" ]]; then
    [[ "$OS" == "linux" ]]
  else
    skip "Not running on Linux"
  fi
}
