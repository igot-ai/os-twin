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

  # Detect OS for sed compatibility
  local sed_opts=()
  if [[ "$(uname -s)" == "Darwin" ]]; then
    sed_opts=("-i" "")
  else
    sed_opts=("-i")
  fi

  # 1. Ensure critical path env vars are set in .env
  # These are required for {env:AGENT_DIR} and {env:OSTWIN_PYTHON} resolution
  # Using 'export' so they're available to child processes (opencode, MCP servers)
  local venv_python="$VENV_DIR/bin/python"

  # Remove any existing entries (with or without export) and add fresh ones
  for key in AGENT_DIR OSTWIN_PYTHON; do
    if [[ -f "$env_file" ]]; then
      # Remove lines starting with optional 'export ' followed by the key
      sed "${sed_opts[@]}" "/^export ${key}=/d" "$env_file"
      sed "${sed_opts[@]}" "/^${key}=/d" "$env_file"
    fi
  done

  # Append the new entries
  {
    echo "export AGENT_DIR=$INSTALL_DIR"
    echo "export OSTWIN_PYTHON=$venv_python"
  } >> "$env_file"

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
