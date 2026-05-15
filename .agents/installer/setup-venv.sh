#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# setup-venv.sh — Python virtual environment creation and dependency sync
#
# Provides: setup_venv
#
# Requires: lib.sh, check-deps.sh (check_uv, check_python),
#           globals: INSTALL_DIR, VENV_DIR
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_SETUP_VENV_SH_LOADED:-}" ]] && return 0
_SETUP_VENV_SH_LOADED=1

setup_venv() {
  step "Setting up Python virtual environment..."

  # Pin to Python 3.12 — some deps (e.g. zvec) lack cp313 wheels
  if check_uv; then
    if [[ -d "$VENV_DIR" ]]; then
      ok "venv exists at $VENV_DIR (reusing)"
    else
      uv venv "$VENV_DIR" --python 3.12 --quiet
      ok "venv at $VENV_DIR (Python 3.12)"
    fi
  else
    local py_cmd
    py_cmd=$(check_python)
    if [[ -d "$VENV_DIR" ]]; then
      ok "venv exists at $VENV_DIR (reusing)"
    else
      "$py_cmd" -m venv "$VENV_DIR"
      ok "venv at $VENV_DIR"
    fi
  fi

  # Always sync requirements — even if the venv was reused.
  # This ensures newly added packages are installed
  # when a user re-runs install.sh after an update.

  # ── Phase 1: Dashboard project (uv sync with lockfile) ─────────────────
  # Uses pyproject.toml + uv.lock for reproducible, locked installs.
  # This replaces the old dashboard/requirements.txt approach.
  local dash_project="$INSTALL_DIR/dashboard"
  if check_uv && [[ -f "$dash_project/pyproject.toml" ]]; then
    step "Syncing dashboard dependencies (uv sync → uv.lock)..."
    local uv_sync_args=(
      sync
      --project "$dash_project"
      --no-install-project
    )
    # Use the lockfile as-is when present (--frozen skips the resolver entirely,
    # giving fast, reproducible installs). Fall back to plain sync which re-resolves.
    if [[ -f "$dash_project/uv.lock" ]]; then
      uv_sync_args+=(--frozen)
    fi
    # Include dev extras (pytest, ruff, etc.) so tests work out of the box
    uv_sync_args+=(--all-extras)
    # CPU-only PyTorch to avoid the ~2GB GPU download
    uv_sync_args+=(--extra-index-url https://download.pytorch.org/whl/cpu)
    uv_sync_args+=(--index-strategy unsafe-best-match)

    # UV_PROJECT_ENVIRONMENT tells uv sync to install into the shared venv
    # instead of creating a project-local .venv inside dashboard/
    TMPDIR=/tmp UV_PROJECT_ENVIRONMENT="$VENV_DIR" uv "${uv_sync_args[@]}" --quiet \
      && ok "Dashboard deps synced from uv.lock" \
      || {
        warn "uv sync failed — falling back to uv pip install"
        _setup_venv_pip_fallback "$dash_project/requirements.txt"
      }
  elif [[ -f "$dash_project/requirements.txt" ]]; then
    # No pyproject.toml available (legacy layout or partial install)
    _setup_venv_pip_fallback "$dash_project/requirements.txt"
  fi

  # ── Phase 2: Supplementary requirements (mcp, memory, roles) ───────────
  # These aren't part of the dashboard project, so they stay as pip installs.
  local req_args=()

  local requirements="$INSTALL_DIR/.agents/mcp/requirements.txt"
  [[ -f "$requirements" ]] && req_args+=(-r "$requirements")

  local memory_reqs="$INSTALL_DIR/dashboard/requirements.txt"
  [[ -f "$memory_reqs" ]] && req_args+=(-r "$memory_reqs")

  # Install role-specific requirements (e.g. roles/reporter/requirements.txt)
  local roles_dir="$INSTALL_DIR/.agents/roles"
  if [[ -d "$roles_dir" ]]; then
    for role_reqs in "$roles_dir"/*/requirements.txt; do
      [[ -f "$role_reqs" ]] || continue
      req_args+=(-r "$role_reqs")
    done
  fi

  if [[ ${#req_args[@]} -gt 0 ]]; then
    step "Installing supplementary Python dependencies (mcp, memory, roles)..."
    if check_uv; then
      TMPDIR=/tmp uv pip install --quiet --upgrade --prerelease=allow \
        --python "$VENV_DIR/bin/python" \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        --index-strategy unsafe-best-match \
        "${req_args[@]}"
    else
      "$VENV_DIR/bin/pip" install --quiet --upgrade \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        "${req_args[@]}"
    fi
    ok "Supplementary dependencies up to date"
  fi
}

# Fallback: install from requirements.txt when uv sync is unavailable
_setup_venv_pip_fallback() {
  local reqs_file="$1"
  if [[ ! -f "$reqs_file" ]]; then
    warn "No requirements file at $reqs_file — skipping dashboard deps"
    return
  fi
  step "Installing dashboard deps via pip fallback ($reqs_file)..."
  if check_uv; then
    TMPDIR=/tmp uv pip install --quiet --upgrade --prerelease=allow \
      --python "$VENV_DIR/bin/python" \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      --index-strategy unsafe-best-match \
      -r "$reqs_file"
  else
    "$VENV_DIR/bin/pip" install --quiet --upgrade \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      -r "$reqs_file"
  fi
  ok "Dashboard deps installed (pip fallback)"
}
