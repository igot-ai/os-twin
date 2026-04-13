#!/usr/bin/env bats
# Tests for start-dashboard.sh

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  source "$INSTALLER_DIR/lib.sh"
  source "$INSTALLER_DIR/check-deps.sh"
  source "$INSTALLER_DIR/start-dashboard.sh"
}

@test "start-dashboard.sh can be sourced without side effects" {
  [[ -n "$_START_DASHBOARD_SH_LOADED" ]]
}

@test "start_dashboard function is defined" {
  declare -f start_dashboard > /dev/null
}

@test "publish_skills function is defined" {
  declare -f publish_skills > /dev/null
}
