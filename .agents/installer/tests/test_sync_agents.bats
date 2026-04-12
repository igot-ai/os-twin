#!/usr/bin/env bats
# Tests for sync-agents.sh

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  source "$INSTALLER_DIR/lib.sh"
  source "$INSTALLER_DIR/sync-agents.sh"
}

@test "sync-agents.sh can be sourced without side effects" {
  [[ -n "$_SYNC_AGENTS_SH_LOADED" ]]
}

@test "sync_opencode_agents function is defined" {
  declare -f sync_opencode_agents > /dev/null
}
