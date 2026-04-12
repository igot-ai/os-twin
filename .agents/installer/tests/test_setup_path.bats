#!/usr/bin/env bats
# Tests for setup-path.sh

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  source "$INSTALLER_DIR/lib.sh"
  source "$INSTALLER_DIR/setup-path.sh"
}

@test "setup-path.sh can be sourced without side effects" {
  [[ -n "$_SETUP_PATH_SH_LOADED" ]]
}

@test "setup_path function is defined" {
  declare -f setup_path > /dev/null
}
