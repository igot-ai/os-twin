#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# patch-mcp.sh — MCP config patching, env injection, OpenCode merge
#
# Provides: patch_mcp_config
#
# Requires: lib.sh, globals: INSTALL_DIR, VENV_DIR
#           Python scripts in installer/scripts/
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_PATCH_MCP_SH_LOADED:-}" ]] && return 0
_PATCH_MCP_SH_LOADED=1

# Installer scripts dir for Python helpers
_PATCH_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/scripts" 2>/dev/null && pwd || echo "")"

patch_mcp_config() {
  local mcp_config="$INSTALL_DIR/.agents/mcp/config.json"
  local env_file="$INSTALL_DIR/.env"

  if [[ ! -f "$mcp_config" ]]; then
    return
  fi

  step "Patching MCP config..."

  # 1. Ensure OSTWIN_PYTHON is set in .env (used by {env:OSTWIN_PYTHON} in config)
  if [[ -f "$env_file" ]]; then
    if ! grep -q "^OSTWIN_PYTHON=" "$env_file"; then
      echo "OSTWIN_PYTHON=$VENV_DIR/bin/python" >> "$env_file"
    fi
  else
    echo "OSTWIN_PYTHON=$VENV_DIR/bin/python" > "$env_file"
  fi

  # 2. Inject all .env variables into every MCP server's "environment" block
  if [[ -f "$env_file" ]]; then
    "$VENV_DIR/bin/python" "${_PATCH_SCRIPTS_DIR}/inject_env_to_mcp.py" \
      "$mcp_config" "$env_file"
  fi

  # 3. Normalize + validate + merge MCP servers into ~/.config/opencode/opencode.json
  local opencode_home="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
  mkdir -p "$opencode_home"
  OSTWIN_VENV_DIR="$VENV_DIR" OSTWIN_INSTALL_DIR="$INSTALL_DIR" \
    "$VENV_DIR/bin/python" "${_PATCH_SCRIPTS_DIR}/merge_mcp_to_opencode.py" \
    "$mcp_config" "$opencode_home/opencode.json" "$INSTALL_DIR/.agents/mcp"

  ok "MCP config patched"
}
