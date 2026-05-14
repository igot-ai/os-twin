#!/usr/bin/env bats
# Tests for install-deps.sh — verifies functions are defined (does NOT actually install)

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  source "$INSTALLER_DIR/lib.sh"
  source "$INSTALLER_DIR/versions.conf"
  source "$INSTALLER_DIR/detect-os.sh"
  source "$INSTALLER_DIR/check-deps.sh"
  source "$INSTALLER_DIR/install-deps.sh"
}

@test "install-deps.sh can be sourced without side effects" {
  [[ -n "$_INSTALL_DEPS_SH_LOADED" ]]
}

@test "install_brew function is defined" {
  declare -f install_brew > /dev/null
}

@test "install_uv function is defined" {
  declare -f install_uv > /dev/null
}

@test "install_python function is defined" {
  declare -f install_python > /dev/null
}

@test "install_pwsh function is defined" {
  declare -f install_pwsh > /dev/null
}

@test "install_node function is defined" {
  declare -f install_node > /dev/null
}

@test "install_opencode function is defined" {
  declare -f install_opencode > /dev/null
}

@test "install_obscura function is defined" {
  declare -f install_obscura > /dev/null
}

@test "install_obscura does not enable stealth by default" {
  local body
  body=$(declare -f install_obscura)
  [[ "$body" != *"OBSCURA_ARGS"* ]]
  [[ "$body" != *"--stealth"* ]]
}

@test "install_obscura preserves obscura-worker companion binary" {
  local body
  body=$(declare -f install_obscura)
  [[ "$body" == *"obscura-worker"* ]]
}

@test "install_pester function is defined" {
  declare -f install_pester > /dev/null
}

@test "install_node uses version from versions.conf" {
  # Verify the function body references NODE_VER
  local body
  body=$(declare -f install_node)
  [[ "$body" == *"NODE_VER"* ]]
}
