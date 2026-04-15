#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# start-channels.sh — Channel connector install + launch (Telegram, Discord, Slack)
#
# Provides: install_channels, start_channels
#
# Requires: lib.sh, check-deps.sh (check_node),
#           globals: INSTALL_DIR, SOURCE_DIR, SCRIPT_DIR
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_START_CHANNELS_SH_LOADED:-}" ]] && return 0
_START_CHANNELS_SH_LOADED=1

# ─── install_channels ────────────────────────────────────────────────────────
# Installs channel connector Node.js dependencies.

install_channels() {
  # Locate the channel connector directory
  CHAN_DIR=""
  for candidate in \
    "${SOURCE_DIR}/bot" \
    "${SCRIPT_DIR}/../bot"; do
    if [[ -d "$candidate" ]] && [[ -f "$candidate/package.json" ]]; then
      CHAN_DIR="$(cd "$candidate" && pwd)"
      break
    fi
  done

  if [[ -z "$CHAN_DIR" ]]; then
    warn "channel connector dir (bot/) not found — skipping"
    info "Expected at bot/package.json relative to the repo root"
    return
  elif ! check_node; then
    warn "Node.js not found — cannot install channel connectors"
    info "Install Node.js and re-run"
    return
  elif ! command -v pnpm &>/dev/null; then
    warn "pnpm not found — cannot install channel connectors"
    info "Install pnpm and re-run"
    return
  fi

  step "Installing channel dependencies in $CHAN_DIR with pnpm..."
  # shellcheck disable=SC2015
  (cd "$CHAN_DIR" && pnpm install) \
    && ok "Channel dependencies installed" || warn "Channel dependency install failed"

  # tsx should come from bot/package.json devDependencies after install.
  if [[ ! -f "$CHAN_DIR/node_modules/.bin/tsx" ]]; then
    warn "tsx not found after pnpm install"
  else
    ok "tsx available"
  fi

  ok "Channel connector dir: $CHAN_DIR"
  info "Start with: (cd \"$CHAN_DIR\" && npm start)"
}

# ─── start_channels ─────────────────────────────────────────────────────────
# Starts channel connectors in the background.

start_channels() {
  if [[ -z "${CHAN_DIR:-}" ]]; then
    return
  fi

  local env_file="$INSTALL_DIR/.env"
  local project_root_env
  project_root_env="$(cd "$CHAN_DIR/.." && pwd)/.env"
  # shellcheck disable=SC1090
  [[ -f "$env_file" ]] && { set -a; source "$env_file"; set +a; }
  # shellcheck disable=SC1090
  [[ -f "$project_root_env" ]] && { set -a; source "$project_root_env"; set +a; }

  local chan_pid_file="$INSTALL_DIR/.agents/channel.pid"
  if [[ -f "$chan_pid_file" ]]; then
    local old_pid
    old_pid=$(cat "$chan_pid_file" 2>/dev/null || true)
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
      step "Stopping previous channel process (PID $old_pid)..."
      kill "$old_pid" 2>/dev/null || true; sleep 1
    fi
  fi

  if [[ -n "${DISCORD_TOKEN:-}" ]] && [[ -n "${DISCORD_CLIENT_ID:-}" ]]; then
    step "Registering Discord slash commands..."
    # shellcheck disable=SC2015
    (cd "$CHAN_DIR" && npx tsx src/deploy-commands.ts 2>/dev/null) \
      && ok "Discord commands registered" || warn "Discord command registration failed (non-critical)"
  fi

  mkdir -p "$INSTALL_DIR/logs"
  step "Starting channels from $CHAN_DIR..."
  (
    cd "$CHAN_DIR" || exit
    # shellcheck disable=SC1090
    [[ -f "$project_root_env" ]] && { set -a; source "$project_root_env"; set +a; }
    nohup npm start > "$INSTALL_DIR/logs/channel.log" 2>&1 &
    echo $! > "$chan_pid_file"
    echo "$!"
  ) | { read -r chan_pid; ok "Channels started (PID $chan_pid) — log: $INSTALL_DIR/logs/channel.log"; }

  # shellcheck disable=SC2015
  [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]] && ok "Telegram: enabled" || info "Telegram: disabled (set TELEGRAM_BOT_TOKEN)"
  # shellcheck disable=SC2015
  [[ -n "${DISCORD_TOKEN:-}" ]] && ok "Discord: enabled" || info "Discord: disabled (set DISCORD_TOKEN)"
  # shellcheck disable=SC2015
  [[ -n "${SLACK_BOT_TOKEN:-}" ]] && ok "Slack: enabled" || info "Slack: disabled (set SLACK_BOT_TOKEN)"
}
