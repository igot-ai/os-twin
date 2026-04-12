#!/usr/bin/env bats
# Tests for start-channels.sh

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  source "$INSTALLER_DIR/lib.sh"
  source "$INSTALLER_DIR/check-deps.sh"
  source "$INSTALLER_DIR/start-channels.sh"
}

@test "start-channels.sh can be sourced without side effects" {
  [[ -n "$_START_CHANNELS_SH_LOADED" ]]
}

@test "install_channels function is defined" {
  declare -f install_channels > /dev/null
}

@test "start_channels function is defined" {
  declare -f start_channels > /dev/null
}
