#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# setup-models.sh — Model catalog initialization
#
# Provides: setup_models
#
# Requires: lib.sh, globals: INSTALL_DIR, VENV_DIR
#
# Usage:
#   setup_models            # Only fetch if configured_models.json is missing
#   setup_models --force    # Always fetch latest (used on first-time install)
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_SETUP_MODELS_SH_LOADED:-}" ]] && return 0
_SETUP_MODELS_SH_LOADED=1

setup_models() {
  local force=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --force) force=true; shift ;;
      *) shift ;;
    esac
  done

  local CONFIGURED_MODELS_PATH="$INSTALL_DIR/.agents/configured_models.json"
  local RAW_MODELS_PATH="$INSTALL_DIR/.agents/models_dev_raw.json"
  local OPENCODE_DIR="$HOME/.local/share/opencode"

  if [[ -f "$CONFIGURED_MODELS_PATH" ]] && ! $force; then
    ok "Models catalog already exists at $CONFIGURED_MODELS_PATH"
    return
  fi

  if $force; then
    step "First-time install detected — fetching latest models catalog from models.dev..."
  else
    step "Initializing models catalog from models.dev..."
  fi

  mkdir -p "$(dirname "$CONFIGURED_MODELS_PATH")" "$OPENCODE_DIR"

  # ── Try Python loader first (produces properly filtered configured_models) ─
  local py_cmd="$VENV_DIR/bin/python"
  if [[ ! -x "$py_cmd" ]]; then
    py_cmd=$(command -v python3 || command -v python || echo "python3")
  fi

  if PYTHONPATH="$INSTALL_DIR" "$py_cmd" -c "from dashboard.lib.settings.models_dev_loader import load_models_on_startup; load_models_on_startup()" 2>/dev/null; then
    ok "Models catalog initialized at $CONFIGURED_MODELS_PATH"
    return
  fi

  # ── Fallback: direct download of raw catalog ───────────────────────────────
  local MODELS_DEV_URL="https://models.dev/api.json"
  local raw_ok=false

  if command -v curl &>/dev/null; then
    if curl -sSL --fail -o "$RAW_MODELS_PATH" "$MODELS_DEV_URL"; then
      raw_ok=true
    fi
  elif command -v wget &>/dev/null; then
    if wget -q -O "$RAW_MODELS_PATH" "$MODELS_DEV_URL"; then
      raw_ok=true
    fi
  fi

  if $raw_ok; then
    # Distribute to all expected locations
    cp "$RAW_MODELS_PATH" "$CONFIGURED_MODELS_PATH"
    cp "$RAW_MODELS_PATH" "$OPENCODE_DIR/configured_models.json"
    cp "$RAW_MODELS_PATH" "$OPENCODE_DIR/models_dev_raw.json"
    warn "Models catalog downloaded as raw JSON (Python loader unavailable)"
  else
    warn "Failed to initialize models catalog — dashboard will fetch it on startup"
  fi
}
