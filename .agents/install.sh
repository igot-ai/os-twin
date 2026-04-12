#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Agent OS (Ostwin) — Cross-Platform Installer
#
# Installs all dependencies and the ostwin CLI on macOS and Linux.
#
# Usage:
#   ./install.sh               # Interactive mode — prompts before each step
#   ./install.sh --yes         # Non-interactive — auto-approve all installs
#   ./install.sh --dir /path   # Install to custom location (default: ~/.ostwin)
#   ./install.sh --channel        # Also install & start the channel connectors (Telegram + Discord + Slack)
#   ./install.sh --dashboard-only  # Install dashboard API + frontend only
#   ./install.sh --help        # Show this help
#
# What gets installed:
#   - Python 3.10+       (via uv / brew / apt)
#   - PowerShell 7+      (via brew / Microsoft repos)
#   - uv                 (Python package/env manager)
#   - opencode            (Agent execution engine)
#   - Pester 5+          (PowerShell test framework)
#   - MCP dependencies   (fastapi, uvicorn, etc.)
#
# Supports: macOS (arm64/x86_64), Ubuntu/Debian, Fedora/RHEL/CentOS
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALLER_DIR="$SCRIPT_DIR/installer"
INSTALL_DIR="${HOME}/.ostwin"
# shellcheck disable=SC2034  # consumed by sourced modules
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd || echo "")"
# shellcheck disable=SC2034
AUTO_YES=false; SKIP_OPTIONAL=false; DASHBOARD_ONLY=false
START_CHANNEL=true; DASHBOARD_PORT=9000
# shellcheck disable=SC2034
PYTHON_VERSION=""
# shellcheck disable=SC2034
PWSH_VERSION=""

# shellcheck disable=SC2034  # globals are consumed by sourced modules
while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y)         AUTO_YES=true; shift ;;
    --dir)            INSTALL_DIR="$2"; shift 2 ;;
    --source-dir)     SOURCE_DIR="$2"; shift 2 ;;
    --port)           DASHBOARD_PORT="$2"; shift 2 ;;
    --skip-optional)  SKIP_OPTIONAL=true; shift ;;
    --dashboard-only) DASHBOARD_ONLY=true; AUTO_YES=true; shift ;;
    --channel)        START_CHANNEL=true; shift ;;
    --help|-h)        head -22 "$0" | tail -20; exit 0 ;;
    *)  echo "[ERROR] Unknown option: $1" >&2
        echo "Run './install.sh --help' for usage." >&2; exit 1 ;;
  esac
done
# shellcheck disable=SC2034
VENV_DIR="$INSTALL_DIR/.venv"

# ─── Source all modules ──────────────────────────────────────────────────────
for _mod in lib.sh versions.conf detect-os.sh check-deps.sh install-deps.sh \
            install-files.sh setup-venv.sh setup-env.sh patch-mcp.sh \
            build-frontend.sh setup-path.sh setup-opencode.sh sync-agents.sh \
            start-dashboard.sh start-channels.sh verify.sh; do
  # shellcheck disable=SC1090
  source "$INSTALLER_DIR/$_mod"
done

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "  ${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "  ${BOLD}║     ${CYAN}Ostwin${NC}${BOLD} — Agent OS Installer                   ║${NC}"
echo -e "  ${BOLD}║     Multi-Agent War-Room Orchestrator            ║${NC}"
echo -e "  ${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""

header "1. Detecting platform"
detect_os
case "$OS" in
  macos) ok "macOS ($ARCH)" ;;
  linux) ok "Linux — $DISTRO ($ARCH) [pkg: $PKG_MGR]" ;;
  *)     fail "Unsupported OS: $(uname -s)"; exit 1 ;;
esac

# shellcheck disable=SC1091
source "$INSTALLER_DIR/_orchestrate-deps.sh"
echo ""

if ! $DASHBOARD_ONLY; then
  header "3. Building dashboards (parallel)"
  build_frontend "dashboard/nextjs" "Next.js dashboard" & pid_nextjs=$!
  build_frontend "dashboard/fe" "Dashboard FE" & pid_fe=$!
  # shellcheck disable=SC2015  # intentional: ok() is side-effect-free
  wait "$pid_nextjs" 2>/dev/null && ok "Next.js build finished" || warn "Next.js build had issues"
  # shellcheck disable=SC2015
  wait "$pid_fe"     2>/dev/null && ok "FE build finished"      || warn "FE build had issues"
else
  header "3. Building dashboard frontend (fe)"
  build_frontend "dashboard/fe" "Dashboard FE"
fi

header "4. Installing Agent OS"
install_files
if [[ "$OS" == "..." ]]; then
  DAEMON_INSTALL="$INSTALL_DIR/.agents/daemons/macos-host/install.sh"
  # shellcheck disable=SC2015
  [[ -f "$DAEMON_INSTALL" ]] && {
    ask "Install macOS host daemon? (desktop automation)" && bash "$DAEMON_INSTALL" \
      || info "Skipped macOS daemon. Run manually later: bash $DAEMON_INSTALL"
  }
fi

header "5. Setting up Python environment"
setup_venv
header "5b. Setting up .env"
setup_env
patch_mcp_config; sync_opencode_agents; compute_build_hash
header "5c. OpenCode agent permissions"
setup_opencode_permissions

if $DASHBOARD_ONLY; then
  header "6. PowerShell modules (skipped — dashboard-only)"; info "Skipping in dashboard-only mode"
elif ! $SKIP_OPTIONAL && command -v pwsh &>/dev/null; then
  header "6. PowerShell modules"; install_pester
else
  header "6. PowerShell modules (skipped)"; info "PowerShell not available or --skip-optional set"
fi

if ! $DASHBOARD_ONLY; then
  header "7. Configuring PATH"; setup_path
else
  header "7. PATH (skipped — dashboard-only)"; info "Skipping PATH setup in dashboard-only mode"
  export PATH="$INSTALL_DIR/.agents/bin:$PATH"
fi

header "8. Verification"
verify_components
header "9. Starting dashboard"
start_dashboard; publish_skills
header "9c. Installing channel dependencies (Telegram + Discord + Slack)"
install_channels
if $START_CHANNEL && [[ -n "${CHAN_DIR:-}" ]]; then
  header "9d. Starting channel connectors"; start_channels
fi
print_completion_banner
