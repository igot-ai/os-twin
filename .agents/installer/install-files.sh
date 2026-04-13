#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# install-files.sh — File installation, rsync, MCP seeding, symlinks, migrations
#
# Provides: install_files, compute_build_hash
#
# Requires: lib.sh, versions.conf, detect-os.sh (OS),
#           check-deps.sh, globals: INSTALL_DIR, SCRIPT_DIR, SOURCE_DIR,
#           VENV_DIR, PYTHON_CMD
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_INSTALL_FILES_SH_LOADED:-}" ]] && return 0
_INSTALL_FILES_SH_LOADED=1

# Installer scripts dir for Python helpers
_INSTALLER_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/scripts" 2>/dev/null && pwd || echo "")"

install_files() {
  step "Installing OS Twin to $INSTALL_DIR..."
  mkdir -p "$INSTALL_DIR/.agents"

  # Ensure clean slate for core roles (remove old core roles before syncing)
  rm -rf "$INSTALL_DIR/.agents/roles"

  # Sync SCRIPT_DIR contents (agents, scripts, config) — skip runtime state
  # NOTE: MCP config files are excluded to preserve user's installed extensions and config
  # User plans live in $INSTALL_DIR/.agents/plans/ — do NOT overwrite them
  # with whatever happens to be in the source repo's plans/ directory.
  # PLAN.template.md is seeded separately below if missing.
  rsync -a \
    --exclude='.venv/' --exclude='*.pid' --exclude='dashboard.pid' \
    --exclude='logs/' --exclude='__pycache__/' --exclude='*.pyc' \
    --exclude='mcp/config.json' --exclude='mcp/.env.mcp' \
    --exclude='plans/' \
    "$SCRIPT_DIR/" "$INSTALL_DIR/.agents/" 2>/dev/null || {
      # rsync fallback to cp (exclude mcp/ and plans/ manually)
      find "$SCRIPT_DIR" -maxdepth 1 -not -name 'mcp' -not -name 'plans' -not -name '.' \
        -exec cp -r {} "$INSTALL_DIR/.agents/" \; 2>/dev/null || true
    }

  # Seed plans/ on first install (or if PLAN.template.md is missing) — never overwrite
  mkdir -p "$INSTALL_DIR/.agents/plans"
  if [[ ! -f "$INSTALL_DIR/.agents/plans/PLAN.template.md" ]] \
     && [[ -f "$SCRIPT_DIR/plans/PLAN.template.md" ]]; then
    cp "$SCRIPT_DIR/plans/PLAN.template.md" "$INSTALL_DIR/.agents/plans/PLAN.template.md"
  fi

  # ── MCP: seed config on first install, never overwrite ─────────────────────
  _seed_mcp_config

  # ── A-mem-sys: copy agentic memory system ─────────────────────────────────
  _sync_amem

  # ── Symlink ~/.ostwin/mcp -> ~/.ostwin/.agents/mcp ────────────────────────
  _setup_mcp_symlink

  # ── MCP: migrate legacy mcp-config.json → config.json ─────────────────────
  _migrate_mcp_config

  # ── Dashboard: always override from source repo ───────────────────────────
  _sync_dashboard

  # ── Contributed roles ─────────────────────────────────────────────────────
  _load_contributed_roles

  # Make scripts executable
  find "$INSTALL_DIR/.agents" -name "*.sh" -exec chmod +x {} \;
  chmod +x "$INSTALL_DIR/.agents/bin/ostwin" 2>/dev/null || true

  ok "Files installed"
}

# ─── Internal helpers ────────────────────────────────────────────────────────

_seed_mcp_config() {
  # Source of truth file was renamed mcp-config.json → config.json during the
  # OpenCode migration (April 2026). Honor either name in the source repo.
  local seed_src=""
  if [[ -f "$SCRIPT_DIR/mcp/config.json" ]]; then
    seed_src="$SCRIPT_DIR/mcp/config.json"
  elif [[ -f "$SCRIPT_DIR/mcp/mcp-config.json" ]]; then
    seed_src="$SCRIPT_DIR/mcp/mcp-config.json"
  fi
  if [[ ! -f "$INSTALL_DIR/.agents/mcp/config.json" ]]; then
    if [[ -n "$seed_src" ]]; then
      step "Seeding mcp/config.json (first install)..."
      cp "$seed_src" "$INSTALL_DIR/.agents/mcp/config.json"
      ok "mcp/config.json seeded from $(basename "$seed_src")"
    else
      warn "No source mcp config found in $SCRIPT_DIR/mcp/ — skipping seed"
    fi
  else
    # Always update the builtin template so new built-in servers are available
    if [[ -f "$SCRIPT_DIR/mcp/mcp-builtin.json" ]]; then
      cp "$SCRIPT_DIR/mcp/mcp-builtin.json" "$INSTALL_DIR/.agents/mcp/mcp-builtin.json"
    fi
    # Always update catalog so new packages are available
    if [[ -f "$SCRIPT_DIR/mcp/mcp-catalog.json" ]]; then
      cp "$SCRIPT_DIR/mcp/mcp-catalog.json" "$INSTALL_DIR/.agents/mcp/mcp-catalog.json"
    fi
    # Merge new built-in servers into config.json (never overwrite existing)
    local mcp_cfg="$INSTALL_DIR/.agents/mcp/config.json"
    local mcp_builtin="$INSTALL_DIR/.agents/mcp/mcp-builtin.json"
    if [[ -f "$mcp_cfg" ]] && [[ -f "$mcp_builtin" ]]; then
      # Prefer the managed venv python (exists on re-installs); fall back to system python
      local _merge_py="$VENV_DIR/bin/python"
      [[ -x "$_merge_py" ]] || _merge_py="${PYTHON_CMD:-python3}"
      "$_merge_py" "${_INSTALLER_SCRIPTS_DIR}/merge_mcp_builtin.py" \
        "$mcp_cfg" "$mcp_builtin" \
        && ok "Merged new built-in MCP servers" || true
    fi
    # Sync MCP server scripts (channel-server.py, warroom-server.py, etc.)
    for f in "$SCRIPT_DIR"/mcp/*.py "$SCRIPT_DIR"/mcp/*.sh "$SCRIPT_DIR"/mcp/requirements.txt; do
      [[ -f "$f" ]] && cp "$f" "$INSTALL_DIR/.agents/mcp/"
    done
    ok "mcp/ preserved (scripts + catalog updated, new servers merged)"
  fi
}

_sync_amem() {
  local amem_src="${SOURCE_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}/A-mem-sys"
  local amem_dst="$INSTALL_DIR/A-mem-sys"
  if [[ -d "$amem_src" ]]; then
    step "Syncing A-mem-sys (agentic memory)..."
    mkdir -p "$amem_dst"
    rsync -a --exclude='__pycache__/' --exclude='*.pyc' --exclude='.memory/' \
      "$amem_src/" "$amem_dst/" 2>/dev/null || {
      cp -r "$amem_src/"* "$amem_dst/" 2>/dev/null || true
    }
    ok "A-mem-sys synced to $amem_dst"
  fi
}

_setup_mcp_symlink() {
  local mcp_link="$INSTALL_DIR/mcp"
  local mcp_real="$INSTALL_DIR/.agents/mcp"
  if [[ -L "$mcp_link" ]]; then
    # Already a symlink — update if target changed
    if [[ "$(readlink "$mcp_link")" != "$mcp_real" ]]; then
      ln -sfn "$mcp_real" "$mcp_link"
    fi
  elif [[ -d "$mcp_link" ]]; then
    # Legacy real directory — migrate: merge any user files, then replace with symlink
    step "Migrating $mcp_link to symlink..."
    for f in "$mcp_link"/*; do
      [[ -f "$f" ]] && [[ ! -f "$mcp_real/$(basename "$f")" ]] && cp "$f" "$mcp_real/"
    done
    rm -rf "$mcp_link"
    ln -s "$mcp_real" "$mcp_link"
    ok "Migrated $mcp_link -> .agents/mcp (symlink)"
  else
    ln -s "$mcp_real" "$mcp_link"
  fi
}

_migrate_mcp_config() {
  local installed_mcp_dir="$INSTALL_DIR/.agents/mcp"
  if [[ -f "$installed_mcp_dir/mcp-config.json" && ! -f "$installed_mcp_dir/config.json" ]]; then
    step "Migrating mcp-config.json → config.json..."
    mv "$installed_mcp_dir/mcp-config.json" "$installed_mcp_dir/config.json"
    ok "Renamed mcp-config.json → config.json"
  elif [[ -f "$installed_mcp_dir/mcp-config.json" && -f "$installed_mcp_dir/config.json" ]]; then
    # Both exist — remove legacy, config.json takes precedence
    rm -f "$installed_mcp_dir/mcp-config.json"
    ok "Removed legacy mcp-config.json (config.json exists)"
  fi
}

_sync_dashboard() {
  local dash_src=""
  for candidate in \
    "${SOURCE_DIR}/dashboard" \
    "${SCRIPT_DIR}/../dashboard" \
    "${SCRIPT_DIR}/dashboard"; do
    if [[ -n "$candidate" ]] && [[ -f "$candidate/api.py" ]]; then
      dash_src="$(cd "$candidate" && pwd)"
      break
    fi
  done

  if [[ -n "$dash_src" ]]; then
    step "Syncing dashboard from $dash_src (override)..."
    rm -rf "$INSTALL_DIR/dashboard"
    mkdir -p "$INSTALL_DIR/dashboard"
    rsync -a \
      --exclude='__pycache__/' --exclude='*.pyc' --exclude='.DS_Store' \
      "$dash_src/" "$INSTALL_DIR/dashboard/"
    ok "Dashboard → $INSTALL_DIR/dashboard/"
  else
    warn "Dashboard source not found — dashboard/ not updated"
    info "Pass the repo root: ./install.sh --source-dir /path/to/agent-os"
  fi
}

_load_contributed_roles() {
  local contributes_roles=""
  for candidate in \
    "${SOURCE_DIR}/contributes/roles" \
    "${SCRIPT_DIR}/../contributes/roles"; do
    if [[ -d "$candidate" ]]; then
      contributes_roles="$(cd "$candidate" && pwd)"
      break
    fi
  done
  if [[ -n "$contributes_roles" ]]; then
    step "Loading contributed roles..."
    mkdir -p "$INSTALL_DIR/.agents/roles"
    local loaded=0
    for role_dir in "$contributes_roles"/*/; do
      [[ -d "$role_dir" ]] || continue
      local role_name
      role_name="$(basename "$role_dir")"
      local target_role="$INSTALL_DIR/.agents/roles/$role_name"
      if [[ ! -d "$target_role" ]]; then
        cp -r "$role_dir" "$target_role"
        loaded=$((loaded + 1))
      fi
    done
    ok "$loaded contributed role(s) loaded"
  fi
}

# ─── Build hash ──────────────────────────────────────────────────────────────

compute_build_hash() {
  step "Computing build hash..."

  # Prefer shasum (macOS), fall back to sha256sum (Linux)
  local sha_cmd="shasum -a 256"
  if ! command -v shasum &>/dev/null; then
    sha_cmd="sha256sum"
  fi

  local hash
  # shellcheck disable=SC2086  # sha_cmd intentionally word-splits ("shasum -a 256")
  hash=$(
    find "$INSTALL_DIR" \
      -type f \
      ! -path "$INSTALL_DIR/.venv/*" \
      ! -path "*/.venv/*" \
      ! -path "$INSTALL_DIR/.zvec/*" \
      ! -path "$INSTALL_DIR/logs/*" \
      ! -path "$INSTALL_DIR/node_modules/*" \
      ! -path "*/node_modules/*" \
      ! -path "*/__pycache__/*" \
      ! -name "*.pid" \
      ! -name ".env" \
      ! -name ".build-hash" \
      -print0 \
      | sort -z \
      | xargs -0 $sha_cmd \
      | $sha_cmd \
      | cut -c1-8
  )
  echo "$hash" > "$INSTALL_DIR/.build-hash"
  ok "Build hash: $hash"
}
