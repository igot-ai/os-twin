#!/usr/bin/env bats
# Tests for setup-venv.sh

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  source "$INSTALLER_DIR/lib.sh"
  source "$INSTALLER_DIR/versions.conf"
  source "$INSTALLER_DIR/check-deps.sh"
  source "$INSTALLER_DIR/setup-venv.sh"
}

@test "setup-venv.sh can be sourced without side effects" {
  [[ -n "$_SETUP_VENV_SH_LOADED" ]]
}

@test "setup_venv function is defined" {
  declare -f setup_venv > /dev/null
}
