#!/usr/bin/env bats
# Tests for lib.sh — shared utilities

setup() {
  INSTALLER_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
  source "$INSTALLER_DIR/lib.sh"
}

@test "lib.sh can be sourced without side effects" {
  # Just sourcing should succeed (setup already did)
  [[ -n "$_LIB_SH_LOADED" ]]
}

@test "header() outputs formatted text" {
  run header "Test Header"
  [[ "$status" -eq 0 ]]
  [[ "$output" == *"Test Header"* ]]
}

@test "ok() outputs green OK marker" {
  run ok "everything fine"
  [[ "$status" -eq 0 ]]
  [[ "$output" == *"[OK]"* ]]
  [[ "$output" == *"everything fine"* ]]
}

@test "warn() outputs yellow WARN marker" {
  run warn "caution ahead"
  [[ "$status" -eq 0 ]]
  [[ "$output" == *"[WARN]"* ]]
}

@test "fail() outputs red FAIL marker" {
  run fail "something broke"
  [[ "$status" -eq 0 ]]
  [[ "$output" == *"[FAIL]"* ]]
}

@test "info() outputs dimmed text" {
  run info "some detail"
  [[ "$status" -eq 0 ]]
  [[ "$output" == *"some detail"* ]]
}

@test "step() outputs arrow" {
  run step "doing something"
  [[ "$status" -eq 0 ]]
  [[ "$output" == *"doing something"* ]]
}

@test "ask() returns 0 when AUTO_YES is true" {
  AUTO_YES=true
  run ask "continue?"
  [[ "$status" -eq 0 ]]
}

@test "version_gte() returns 0 for equal versions" {
  run version_gte "3.10" "3.10"
  [[ "$status" -eq 0 ]]
}

@test "version_gte() returns 0 for greater version" {
  run version_gte "3.12" "3.10"
  [[ "$status" -eq 0 ]]
}

@test "version_gte() returns 1 for lesser version" {
  run version_gte "3.8" "3.10"
  [[ "$status" -ne 0 ]]
}

@test "double-sourcing is safe (guard works)" {
  source "$INSTALLER_DIR/lib.sh"
  source "$INSTALLER_DIR/lib.sh"
  [[ -n "$_LIB_SH_LOADED" ]]
}
