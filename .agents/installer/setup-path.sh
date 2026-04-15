#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# setup-path.sh — PATH configuration, shell RC detection
#
# Provides: setup_path
#
# Requires: lib.sh, globals: INSTALL_DIR
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_SETUP_PATH_SH_LOADED:-}" ]] && return 0
_SETUP_PATH_SH_LOADED=1

setup_path() {
  step "Configuring PATH..."

  local shell_name
  shell_name=$(basename "${SHELL:-/bin/bash}")
  local shell_rc
  case "$shell_name" in
    zsh)   shell_rc="$HOME/.zshrc" ;;
    bash)  shell_rc="$HOME/.bashrc" ;;
    fish)  shell_rc="$HOME/.config/fish/config.fish" ;;
    *)     shell_rc="$HOME/.profile" ;;
  esac

  local path_line="export PATH=\"$INSTALL_DIR/.agents/bin:\$PATH\""

  if [[ "$shell_name" == "fish" ]]; then
    path_line="set -gx PATH $INSTALL_DIR/.agents/bin \$PATH"
  fi

  if grep -qF "ostwin" "$shell_rc" 2>/dev/null; then
    ok "PATH already configured in $shell_rc"
  else
    {
      echo ""
      echo "# Ostwin CLI (Agent OS)"
      echo "$path_line"
    } >> "$shell_rc"
    ok "Added to PATH in $shell_rc"
  fi

  # Export for current session
  export PATH="$INSTALL_DIR/.agents/bin:$PATH"
}
