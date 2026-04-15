#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# sync-agents.sh — Sync roles to OpenCode agents directory
#
# Copies ROLE.md from each role directory to ~/.config/opencode/agents/<role>.md
# so the OpenCode CLI can discover and invoke them as named agents.
#
# Provides: sync_opencode_agents
#
# Requires: lib.sh, globals: INSTALL_DIR
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_SYNC_AGENTS_SH_LOADED:-}" ]] && return 0
_SYNC_AGENTS_SH_LOADED=1

sync_opencode_agents() {
  local opencode_home="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
  local agents_dir="$opencode_home/agents"
  local roles_dirs=(
    "$INSTALL_DIR/.agents/roles"
    "$INSTALL_DIR/contributes/roles"
  )

  step "Syncing agent definitions to $agents_dir..."
  mkdir -p "$agents_dir"

  local synced=0
  local skipped=0

  for roles_dir in "${roles_dirs[@]}"; do
    [[ -d "$roles_dir" ]] || continue

    for role_dir in "$roles_dir"/*/; do
      [[ -d "$role_dir" ]] || continue

      local role_name
      role_name="$(basename "$role_dir")"

      # Skip _base (infrastructure scripts, not a role)
      if [[ "$role_name" == "_base" ]]; then
        continue
      fi

      # Must have role.json to be a valid role
      if [[ ! -f "$role_dir/role.json" ]]; then
        skipped=$((skipped + 1))
        continue
      fi

      # Copy ROLE.md as <role-name>.md (built-in roles take precedence over contributes)
      local role_md="$role_dir/ROLE.md"
      if [[ -f "$role_md" ]]; then
        cp "$role_md" "$agents_dir/${role_name}.md"
        synced=$((synced + 1))
      else
        skipped=$((skipped + 1))
      fi
    done
  done

  ok "$synced agent(s) synced to $agents_dir ($skipped skipped — no ROLE.md)"
}
