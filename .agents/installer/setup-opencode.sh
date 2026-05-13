#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# setup-opencode.sh — OpenCode permissions patching
#
# Provides: setup_opencode_permissions
#
# Requires: lib.sh, globals: VENV_DIR
#           Python script: installer/scripts/patch_opencode_permissions.py
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_SETUP_OPENCODE_SH_LOADED:-}" ]] && return 0
_SETUP_OPENCODE_SH_LOADED=1

_OPENCODE_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/scripts" 2>/dev/null && pwd || echo "")"

setup_opencode_permissions() {
  local oc_dir="$HOME/.config/opencode"
  local oc_config="$oc_dir/opencode.json"

  if ! command -v python3 &>/dev/null && ! [[ -x "$VENV_DIR/bin/python" ]]; then
    warn "Python not available — skipping OpenCode permission patch"
    return
  fi

  local py_cmd="python3"
  [[ -x "$VENV_DIR/bin/python" ]] && py_cmd="$VENV_DIR/bin/python"

  step "Patching OpenCode permissions (allow .env reads)..."
  mkdir -p "$oc_dir"

  if "$py_cmd" "${_OPENCODE_SCRIPTS_DIR}/patch_opencode_permissions.py" "$oc_config"; then
    ok "OpenCode permissions ensured at $oc_config"
  else
    warn "Failed to patch OpenCode permissions — agents may not be able to read .env files"
    info "Manually add to $oc_config:"
    info '  "permission": { "read": { "*": "allow", "*.env": "allow", "*.env.*": "allow" } }'
  fi
}
