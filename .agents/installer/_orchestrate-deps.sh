#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# _orchestrate-deps.sh — Dependency check & install orchestration (step 2)
#
# This is sourced inline by install.sh to handle the branching logic for
# --dashboard-only vs full install. It uses functions from check-deps.sh
# and install-deps.sh.
#
# Not a standalone module — requires all globals set by install.sh.
# ──────────────────────────────────────────────────────────────────────────────

ensure_pnpm() {
  local current_pnpm=""
  local target_pnpm="${PNPM_INSTALL_VERSION:-10.26.0}"
  export OSTWIN_PNPM_CMD="pnpm"
  if command -v pnpm &>/dev/null; then
    current_pnpm="$(pnpm --version 2>/dev/null | head -1 || true)"
  fi

  if [[ -n "$current_pnpm" ]] && [[ "$current_pnpm" == "$target_pnpm" ]]; then
    ok "pnpm $current_pnpm"
    return 0
  fi

  if ! command -v npm &>/dev/null; then
    warn "npm not found — cannot install pinned pnpm ${PNPM_INSTALL_VERSION:-10.26.0}"
    return 1
  fi

  if [[ -n "$current_pnpm" ]]; then
    step "Switching pnpm from $current_pnpm to pinned $target_pnpm..."
  else
    step "Installing pnpm $target_pnpm..."
  fi

  npm install -g "pnpm@${target_pnpm}" 2>/dev/null || sudo npm install -g "pnpm@${target_pnpm}" 2>/dev/null || true
  hash -r 2>/dev/null || rehash 2>/dev/null || true

  current_pnpm=""
  if command -v pnpm &>/dev/null; then
    current_pnpm="$(pnpm --version 2>/dev/null | head -1 || true)"
  fi

  if [[ -n "$current_pnpm" ]] && [[ "$current_pnpm" == "$target_pnpm" ]]; then
    export OSTWIN_PNPM_CMD="pnpm"
    ok "pnpm $current_pnpm"
    return 0
  fi

  if command -v npx &>/dev/null; then
    export OSTWIN_PNPM_CMD="npx -y pnpm@${target_pnpm}"
    if [[ -n "$current_pnpm" ]]; then
      warn "Pinned pnpm $target_pnpm was requested, but pnpm $current_pnpm is still on PATH; using npx fallback"
    else
      warn "Pinned pnpm $target_pnpm was requested, but pnpm is not on PATH; using npx fallback"
    fi
    return 0
  fi

  if [[ -n "$current_pnpm" ]]; then
    warn "Pinned pnpm $target_pnpm was requested, but pnpm $current_pnpm is available and npx fallback is unavailable"
  else
    warn "Pinned pnpm $target_pnpm was requested, but pnpm is still not available and npx fallback is unavailable"
  fi
  return 1
}

if $DASHBOARD_ONLY; then
  header "2. Checking dependencies (dashboard-only — minimal)"
  # Only ensure uv + Python are available (needed for dashboard venv)
  BASH_VER=$(bash --version | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
  ok "bash $BASH_VER"
  if ! check_uv; then
    install_uv
  fi
  PYTHON_CMD=$(check_python)
  if [[ -z "$PYTHON_CMD" ]]; then
    install_python
    PYTHON_CMD=$(check_python)
    [[ -z "$PYTHON_CMD" ]] && { fail "Python required for dashboard"; exit 1; }
  fi
  ok "Python $PYTHON_VERSION ($PYTHON_CMD)"

  # --- Node.js ---
  if ! check_node; then
    install_node
  fi
  if check_node; then
    NODE_VERSION=$(node --version 2>&1 | head -1)
    ok "Node.js $NODE_VERSION"
    ensure_pnpm || true
    if ! command -v clawhub &>/dev/null && command -v npm &>/dev/null; then
      step "Installing clawhub CLI..."
      npm install -g clawhub 2>/dev/null || sudo npm install -g clawhub 2>/dev/null || true
    fi
  else
    fail "Node.js required for dashboard"
    exit 1
  fi
else

header "2. Checking dependencies"

# --- Bash ---
BASH_VER=$(bash --version | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
ok "bash $BASH_VER"

# --- uv ---
if check_uv; then
  UV_VERSION=$(uv --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  ok "uv $UV_VERSION"
else
  warn "uv not found"
  if ask "Install uv? (recommended — fast Python package manager)"; then
    install_uv
  else
    info "Skipping uv — will use pip fallback"
  fi
fi

# --- Python ---
PYTHON_CMD=$(check_python)
if [[ -n "$PYTHON_CMD" ]]; then
  ok "Python $PYTHON_VERSION ($PYTHON_CMD)"
else
  warn "Python $MIN_PYTHON_VERSION+ not found"
  if ask "Install Python?"; then
    install_python
    PYTHON_CMD=$(check_python)
    if [[ -n "$PYTHON_CMD" ]]; then
      ok "Python $PYTHON_VERSION installed"
    else
      fail "Python installation failed"
      exit 1
    fi
  else
    fail "Python $MIN_PYTHON_VERSION+ is required"
    exit 1
  fi
fi

# --- PowerShell (REQUIRED — ostwin CLI delegates to ostwin.ps1) ---
if check_pwsh; then
  ok "PowerShell $PWSH_VERSION"
else
  warn "PowerShell 7+ not found (REQUIRED for ostwin CLI)"
  if ask "Install PowerShell? (REQUIRED — ostwin CLI will not work without it)"; then
    install_pwsh
    if check_pwsh; then
      ok "PowerShell $PWSH_VERSION installed"
    else
      fail "PowerShell installation failed — ostwin CLI requires pwsh"
      echo "  Try: brew install powershell (macOS) or see https://aka.ms/install-powershell" >&2
      exit 1
    fi
  else
    fail "PowerShell 7+ is required for the ostwin CLI"
    echo "  Install manually: brew install powershell (macOS) or see https://aka.ms/install-powershell" >&2
    exit 1
  fi
fi

# --- opencode ---
if check_opencode; then
  OC_VERSION=$(opencode --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "installed")
  ok "opencode $OC_VERSION"
else
  install_opencode
fi

# --- Ollama ---
if check_ollama; then
  OLLAMA_VER=$(ollama --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "installed")
  ok "Ollama $OLLAMA_VER"
else
  warn "Ollama not found (local LLM host — optional, needed for local models)"
  if ask "Install Ollama? (recommended for running local LLMs)"; then
    install_ollama
  else
    info "Skipping Ollama — install later from https://ollama.com"
  fi
fi

# --- Node.js ---
if check_node; then
  NODE_VERSION=$(node --version 2>&1 | head -1)
  ok "Node.js $NODE_VERSION"
  ensure_pnpm || true
  if ! command -v clawhub &>/dev/null && command -v npm &>/dev/null; then
    step "Installing clawhub CLI..."
    npm install -g clawhub 2>/dev/null || sudo npm install -g clawhub 2>/dev/null || true
  fi
else
  warn "Node.js not found"
  if ask "Install Node.js? (required for Dashboard UI)"; then
    install_node
    if check_node; then
      NODE_VERSION=$(node --version 2>&1 | head -1)
      ok "Node.js $NODE_VERSION installed"
      ensure_pnpm || true
      if ! command -v clawhub &>/dev/null && command -v npm &>/dev/null; then
        step "Installing clawhub CLI..."
        npm install -g clawhub 2>/dev/null || sudo npm install -g clawhub 2>/dev/null || true
      fi
    else
      warn "Node.js installation failed"
    fi
  else
    warn "Skipping Node.js — dashboard UI will not be built"
  fi
fi

fi  # end: ! DASHBOARD_ONLY
