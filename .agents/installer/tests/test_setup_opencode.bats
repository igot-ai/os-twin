#!/usr/bin/env bats
# Tests for setup-opencode.sh

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  source "$INSTALLER_DIR/lib.sh"
  source "$INSTALLER_DIR/setup-opencode.sh"
}

@test "setup-opencode.sh can be sourced without side effects" {
  [[ -n "$_SETUP_OPENCODE_SH_LOADED" ]]
}

@test "setup_opencode_permissions function is defined" {
  declare -f setup_opencode_permissions > /dev/null
}
