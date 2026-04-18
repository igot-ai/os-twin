#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# setup-models.sh — Model catalog initialization
#
# Provides: setup_models
#
# Requires: lib.sh, globals: INSTALL_DIR, VENV_DIR
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_SETUP_MODELS_SH_LOADED:-}" ]] && return 0
_SETUP_MODELS_SH_LOADED=1

setup_models() {
  local CONFIGURED_MODELS_PATH="$INSTALL_DIR/.agents/configured_models.json"
  
  if [[ -f "$CONFIGURED_MODELS_PATH" ]]; then
    ok "Models catalog already exists at $CONFIGURED_MODELS_PATH"
    return
  fi

  step "Initializing models catalog from models.dev..."

  # Ensure we use the venv python
  local py_cmd="$VENV_DIR/bin/python"
  if [[ ! -x "$py_cmd" ]]; then
    # Fallback to system python if venv not yet ready (though it should be)
    py_cmd=$(command -v python3 || command -v python || echo "python3")
  fi

  # Call the dashboard's loader to bootstrap the file.
  # We set PYTHONPATH to include the project root so 'dashboard' is importable.
  # We redirect stderr to /dev/null to keep the installer output clean, 
  # as it might log warnings if providers aren't configured yet.
  if PYTHONPATH="$INSTALL_DIR" "$py_cmd" -c "from dashboard.lib.settings.models_dev_loader import load_models_on_startup; load_models_on_startup()" 2>/dev/null; then
    ok "Models catalog initialized at $CONFIGURED_MODELS_PATH"
  else
    # Last-ditch effort: use curl/wget to at least get the raw catalog
    # if the Python import fails (e.g. missing dependencies).
    local MODELS_DEV_URL="https://models.dev/api.json"
    local OPENCODE_DIR="$HOME/.local/share/opencode"
    local raw_ok=false
    
    mkdir -p "$OPENCODE_DIR"
    
    if command -v curl &>/dev/null; then
      if curl -sSL --fail -o "$CONFIGURED_MODELS_PATH" "$MODELS_DEV_URL"; then
        raw_ok=true
      fi
    elif command -v wget &>/dev/null; then
      if wget -q -O "$CONFIGURED_MODELS_PATH" "$MODELS_DEV_URL"; then
        raw_ok=true
      fi
    fi

    if $raw_ok; then
      # Feed to both files in both locations
      cp "$CONFIGURED_MODELS_PATH" "$(dirname "$CONFIGURED_MODELS_PATH")/models_dev_raw.json"
      cp "$CONFIGURED_MODELS_PATH" "$OPENCODE_DIR/configured_models.json"
      cp "$CONFIGURED_MODELS_PATH" "$OPENCODE_DIR/models_dev_raw.json"
      warn "Models catalog downloaded as raw JSON to multiple locations (Python loader failed)"
    else
      warn "Failed to initialize models catalog — dashboard will fetch it on startup"
    fi
  fi
}
