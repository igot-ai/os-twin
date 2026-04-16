#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# start-dashboard.sh — Dashboard launch, health check, tunnel detection
#
# Provides: start_dashboard, publish_skills
#
# Requires: lib.sh, check-deps.sh, globals: INSTALL_DIR, VENV_DIR,
#           DASHBOARD_PORT, OSTWIN_API_KEY
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_START_DASHBOARD_SH_LOADED:-}" ]] && return 0
_START_DASHBOARD_SH_LOADED=1

start_dashboard() {
  local dashboard_script="$INSTALL_DIR/.agents/dashboard.sh"
  if [[ ! -f "$dashboard_script" ]] || [[ ! -f "$INSTALL_DIR/dashboard/api.py" ]]; then
    warn "Dashboard not found — skipping auto-start"
    info "Re-run: ./install.sh --source-dir /path/to/agent-os"
    return
  fi

  # Stop any existing process on the dashboard port
  local local_pids
  local_pids=$(lsof -ti:"$DASHBOARD_PORT" 2>/dev/null || true)
  if [[ -n "$local_pids" ]]; then
    step "Stopping existing process on :$DASHBOARD_PORT..."
    echo "$local_pids" | xargs kill 2>/dev/null || true
    sleep 2
    # Force-kill if still alive (ML models can delay graceful shutdown)
    local_pids=$(lsof -ti:"$DASHBOARD_PORT" 2>/dev/null || true)
    if [[ -n "$local_pids" ]]; then
      echo "$local_pids" | xargs kill -9 2>/dev/null || true
      sleep 1
    fi
  fi

  # Source .env so the dashboard process inherits API keys
  local env_file="$INSTALL_DIR/.env"
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$env_file"
    set +a
  fi

  mkdir -p "$INSTALL_DIR/logs"
  step "Starting dashboard on http://localhost:${DASHBOARD_PORT}..."
  # Pin --project-dir to $INSTALL_DIR so the dashboard's plan registry is
  # always ~/.ostwin/.agents/plans/, regardless of cwd when install.sh runs.
  nohup bash "$dashboard_script" \
    --background --port "$DASHBOARD_PORT" \
    --project-dir "$INSTALL_DIR" \
    > "$INSTALL_DIR/logs/dashboard.log" 2>&1 &
  DASHBOARD_PID=$!
  echo "$DASHBOARD_PID" > "$INSTALL_DIR/dashboard.pid"

  # Read OSTWIN_API_KEY for auth headers
  OSTWIN_API_KEY="${OSTWIN_API_KEY:-}"

  # Health-check: poll /api/status up to 60s
  step "Waiting for dashboard to be healthy (up to 60s)..."
  DASH_OK=false
  for _i in $(seq 1 60); do
    if [[ -n "$OSTWIN_API_KEY" ]]; then
      curl -sf -H "X-API-Key: $OSTWIN_API_KEY" "http://localhost:${DASHBOARD_PORT}/api/status" >/dev/null 2>&1 && DASH_OK=true
    else
      curl -sf "http://localhost:${DASHBOARD_PORT}/api/status" >/dev/null 2>&1 && DASH_OK=true
    fi
    if $DASH_OK; then break; fi
    sleep 1
  done

  if $DASH_OK; then
    ok "Dashboard healthy at http://localhost:${DASHBOARD_PORT} (PID $DASHBOARD_PID)"
    _check_tunnel
  else
    warn "Dashboard did not respond in 60s — check $INSTALL_DIR/logs/dashboard.log"
    info "Start manually: bash $dashboard_script"
  fi
}

publish_skills() {
  header "9b. Publishing skills to backend"
  local sync_script="$INSTALL_DIR/.agents/sync-skills.sh"
  if [[ -x "$sync_script" ]]; then
    OSTWIN_HOME="$INSTALL_DIR" DASHBOARD_PORT="$DASHBOARD_PORT" \
      bash "$sync_script" --install-from "$INSTALL_DIR/.agents"
  else
    warn "sync-skills.sh not found — skipping skill sync"
    info "Expected at $sync_script"
  fi
}

# ─── Internal helpers ────────────────────────────────────────────────────────

_check_tunnel() {
  # Check for ngrok tunnel URL
  local tunnel_url=""
  local tunnel_error=""
  local python_for_tunnel="$VENV_DIR/bin/python"
  [[ -x "$python_for_tunnel" ]] || python_for_tunnel="python3"
  local tunnel_json=""
  if [[ -n "${OSTWIN_API_KEY:-}" ]]; then
    tunnel_json=$(curl -sf -H "X-API-Key: $OSTWIN_API_KEY" \
      "http://localhost:${DASHBOARD_PORT}/api/tunnel/status" 2>/dev/null || true)
  else
    tunnel_json=$(curl -sf \
      "http://localhost:${DASHBOARD_PORT}/api/tunnel/status" 2>/dev/null || true)
  fi
  if [[ -n "$tunnel_json" ]]; then
    tunnel_url=$("$python_for_tunnel" -c "import sys,json; print(json.load(sys.stdin).get('url') or '')" <<< "$tunnel_json" 2>/dev/null || true)
    tunnel_error=$("$python_for_tunnel" -c "import sys,json; print(json.load(sys.stdin).get('error') or '')" <<< "$tunnel_json" 2>/dev/null || true)
  fi
  if [[ -n "$tunnel_url" ]]; then
    ok "Tunnel active: $tunnel_url"
    # shellcheck disable=SC2034  # consumed by verify.sh banner
    TUNNEL_URL="$tunnel_url"
  elif [[ -n "$tunnel_error" ]]; then
    warn "Tunnel failed: $tunnel_error"
  elif [[ -z "${NGROK_AUTHTOKEN:-}" ]]; then
    info "Tunnel not configured — set NGROK_AUTHTOKEN in ~/.ostwin/.env to enable port forwarding"
  else
    warn "Tunnel not active — check dashboard logs at $INSTALL_DIR/logs/dashboard.log"
  fi
}
