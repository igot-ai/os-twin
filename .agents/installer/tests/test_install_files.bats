#!/usr/bin/env bats
# Tests for install-files.sh

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  source "$INSTALLER_DIR/lib.sh"
  source "$INSTALLER_DIR/versions.conf"
  source "$INSTALLER_DIR/detect-os.sh"
  source "$INSTALLER_DIR/check-deps.sh"
  source "$INSTALLER_DIR/install-files.sh"
}

@test "install-files.sh can be sourced without side effects" {
  [[ -n "$_INSTALL_FILES_SH_LOADED" ]]
}

@test "install_files function is defined" {
  declare -f install_files > /dev/null
}

@test "compute_build_hash function is defined" {
  declare -f compute_build_hash > /dev/null
}

@test "internal helpers are defined" {
  declare -f _seed_mcp_config > /dev/null
  declare -f _sync_amem > /dev/null
  declare -f _setup_mcp_symlink > /dev/null
  declare -f _migrate_mcp_config > /dev/null
  declare -f _sync_dashboard > /dev/null
  declare -f _load_contributed_roles > /dev/null
}
