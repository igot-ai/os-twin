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
  #
  # Performance: all requirements files are collected and installed in a
  # single pip/uv call so the resolver runs once instead of N times.
  # We also keep the default cache (no --no-cache) to skip re-downloads
  # on repeated runs, and use CPU-only torch to avoid the ~2GB GPU download.

  local req_args=()

  # Collect all requirements files that exist
  local requirements="$INSTALL_DIR/.agents/mcp/requirements.txt"
  [[ -f "$requirements" ]] && req_args+=(-r "$requirements")

  local dash_reqs="$INSTALL_DIR/dashboard/requirements.txt"
  [[ -f "$dash_reqs" ]] && req_args+=(-r "$dash_reqs")

  local memory_reqs="$INSTALL_DIR/.agents/memory/requirements.txt"
  [[ -f "$memory_reqs" ]] && req_args+=(-r "$memory_reqs")

  # Install role-specific requirements (e.g. roles/reporter/requirements.txt)
  local roles_dir="$INSTALL_DIR/.agents/roles"
  if [[ -d "$roles_dir" ]]; then
    for role_reqs in "$roles_dir"/*/requirements.txt; do
      [[ -f "$role_reqs" ]] || continue
      req_args+=(-r "$role_reqs")
    done
  fi

  if [[ ${#req_args[@]} -eq 0 ]]; then
    warn "No requirements files found — skipping dependency sync"
  else
    step "Syncing all Python dependencies (single resolver pass)..."
    if check_uv; then
      # Use CPU-only PyTorch index to avoid downloading ~2GB GPU builds.
      # Packages that don't exist in the CPU index fall through to PyPI.
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
    ok "All Python dependencies up to date"
  fi
}
