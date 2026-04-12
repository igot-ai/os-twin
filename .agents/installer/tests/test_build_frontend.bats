#!/usr/bin/env bats
# Tests for build-frontend.sh

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  source "$INSTALLER_DIR/lib.sh"
  source "$INSTALLER_DIR/build-frontend.sh"
}

@test "build-frontend.sh can be sourced without side effects" {
  [[ -n "$_BUILD_FRONTEND_SH_LOADED" ]]
}

@test "build_frontend function is defined (unified)" {
  declare -f build_frontend > /dev/null
}

@test "build_frontend accepts subdir and label args" {
  # Should gracefully handle a nonexistent dir
  SOURCE_DIR="/nonexistent"
  SCRIPT_DIR="/nonexistent"
  run build_frontend "nonexistent/dir" "Test Build"
  [[ "$output" == *"Test Build not found"* ]]
}

@test "old build_nextjs and build_dashboard_fe are NOT defined" {
  # Ensure the old functions don't exist
  ! declare -f build_nextjs > /dev/null 2>&1
  ! declare -f build_dashboard_fe > /dev/null 2>&1
}
