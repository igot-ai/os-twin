#!/usr/bin/env bats
# Tests for patch-mcp.sh

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  source "$INSTALLER_DIR/lib.sh"
  source "$INSTALLER_DIR/patch-mcp.sh"
}

@test "patch-mcp.sh can be sourced without side effects" {
  [[ -n "$_PATCH_MCP_SH_LOADED" ]]
}

@test "patch_mcp_config function is defined" {
  declare -f patch_mcp_config > /dev/null
}
