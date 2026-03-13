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
#   ./install.sh --help        # Show this help
#
# What gets installed:
#   - Python 3.10+       (via uv / brew / apt)
#   - PowerShell 7+      (via brew / Microsoft repos)
#   - uv                 (Python package/env manager)
#   - deepagents-cli     (Agent execution engine)
#   - Pester 5+          (PowerShell test framework)
#   - MCP dependencies   (fastapi, uvicorn, etc.)
#
# Supports: macOS (arm64/x86_64), Ubuntu/Debian, Fedora/RHEL/CentOS
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${HOME}/.ostwin"
AUTO_YES=false
SKIP_OPTIONAL=false
MIN_PYTHON_VERSION="3.10"
MIN_PWSH_VERSION="7"
PYTHON_VERSION=""
PWSH_VERSION=""

# ─── Argument parsing ────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y)       AUTO_YES=true; shift ;;
    --dir)          INSTALL_DIR="$2"; shift 2 ;;
    --skip-optional) SKIP_OPTIONAL=true; shift ;;
    --help|-h)
      head -22 "$0" | tail -20
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown option: $1" >&2
      echo "Run './install.sh --help' for usage." >&2
      exit 1
      ;;
  esac
done

VENV_DIR="$INSTALL_DIR/.venv"

# ─── Colors & formatting ─────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

header()  { echo -e "\n${BLUE}${BOLD}  $1${NC}"; }
ok()      { echo -e "    ${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "    ${YELLOW}[WARN]${NC} $1"; }
fail()    { echo -e "    ${RED}[FAIL]${NC} $1"; }
info()    { echo -e "    ${DIM}$1${NC}"; }
step()    { echo -e "  ${CYAN}→${NC} $1"; }

# ─── OS Detection ────────────────────────────────────────────────────────────

detect_os() {
  OS="unknown"
  DISTRO=""
  PKG_MGR=""
  ARCH="$(uname -m)"

  case "$(uname -s)" in
    Darwin)
      OS="macos"
      PKG_MGR="brew"
      ;;
    Linux)
      OS="linux"
      if [ -f /etc/os-release ]; then
        DISTRO=$(. /etc/os-release && echo "$ID")
      fi
      case "$DISTRO" in
        ubuntu|debian|pop|linuxmint|elementary)
          PKG_MGR="apt"
          ;;
        fedora|rhel|centos|rocky|almalinux)
          PKG_MGR="dnf"
          # Fallback to yum for older systems
          command -v dnf &>/dev/null || PKG_MGR="yum"
          ;;
        arch|manjaro)
          PKG_MGR="pacman"
          ;;
        opensuse*|sles)
          PKG_MGR="zypper"
          ;;
        *)
          PKG_MGR=""
          ;;
      esac
      ;;
  esac
}

# ─── Prompt helper ───────────────────────────────────────────────────────────

ask() {
  local prompt="$1"
  if $AUTO_YES; then
    return 0
  fi
  echo -en "    ${YELLOW}?${NC} $prompt ${DIM}[Y/n]${NC} "
  read -r answer
  case "${answer:-y}" in
    [Yy]*) return 0 ;;
    *)     return 1 ;;
  esac
}

# ─── Version comparison ─────────────────────────────────────────────────────

version_gte() {
  # Returns 0 if $1 >= $2
  printf '%s\n%s' "$2" "$1" | sort -V | head -n1 | grep -qF "$2"
}

# ─── Dependency checks ──────────────────────────────────────────────────────

check_python() {
  local py_cmd=""
  for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
      local ver
      ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
      if version_gte "$ver" "$MIN_PYTHON_VERSION"; then
        py_cmd="$cmd"
        PYTHON_VERSION="$ver"
        break
      fi
    fi
  done
  # Fallback: check uv-managed Python
  if [[ -z "$py_cmd" ]] && check_uv; then
    local uv_py
    uv_py=$(uv python find 2>/dev/null || true)
    if [[ -n "$uv_py" && -x "$uv_py" ]]; then
      PYTHON_VERSION=$($uv_py --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
      py_cmd="$uv_py"
    fi
  fi
  echo "$py_cmd"
}

check_pwsh() {
  if command -v pwsh &>/dev/null; then
    PWSH_VERSION=$(pwsh --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    if version_gte "$PWSH_VERSION" "$MIN_PWSH_VERSION"; then
      return 0
    fi
  fi
  return 1
}

check_uv() {
  command -v uv &>/dev/null
}

check_deepagents() {
  command -v deepagents &>/dev/null
}

check_brew() {
  command -v brew &>/dev/null
}

# ─── Installers ──────────────────────────────────────────────────────────────

install_brew() {
  step "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Add to current session
  if [[ -f /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -f /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
}

install_uv() {
  step "Installing uv (fast Python package manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Add to current session
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  if ! check_uv; then
    fail "uv installation failed"
    exit 1
  fi
  UV_VERSION=$(uv --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  ok "uv $UV_VERSION installed"
}

install_python() {
  case "$OS" in
    macos)
      if check_uv; then
        step "Installing Python 3.12 via uv..."
        uv python install 3.12
      elif check_brew; then
        step "Installing Python 3.12 via Homebrew..."
        brew install python@3.12
      else
        fail "Cannot install Python: neither uv nor brew available"
        exit 1
      fi
      ;;
    linux)
      case "$PKG_MGR" in
        apt)
          step "Installing Python 3 via apt..."
          sudo apt-get update -qq
          sudo apt-get install -y -qq python3 python3-venv python3-pip
          ;;
        dnf|yum)
          step "Installing Python 3 via $PKG_MGR..."
          sudo $PKG_MGR install -y python3 python3-pip
          ;;
        pacman)
          step "Installing Python 3 via pacman..."
          sudo pacman -S --noconfirm python python-pip
          ;;
        zypper)
          step "Installing Python 3 via zypper..."
          sudo zypper install -y python3 python3-pip
          ;;
        *)
          # Try uv as last resort (no sudo needed)
          if check_uv; then
            step "Installing Python 3.12 via uv (no sudo)..."
            uv python install 3.12
          else
            fail "Cannot install Python: no supported package manager found"
            echo "    Please install Python $MIN_PYTHON_VERSION+ manually and re-run."
            exit 1
          fi
          ;;
      esac
      ;;
  esac
}

install_pwsh() {
  case "$OS" in
    macos)
      if check_brew; then
        step "Installing PowerShell via Homebrew..."
        brew install powershell/tap/powershell
      else
        fail "Homebrew required to install PowerShell on macOS"
        echo "    Install Homebrew first: https://brew.sh"
        exit 1
      fi
      ;;
    linux)
      case "$PKG_MGR" in
        apt)
          step "Installing PowerShell via Microsoft APT repository..."
          # Install prerequisites
          sudo apt-get update -qq
          sudo apt-get install -y -qq wget apt-transport-https software-properties-common
          # Get Ubuntu/Debian version
          local distro_version
          distro_version=$(. /etc/os-release && echo "$VERSION_ID")
          local distro_id
          distro_id=$(. /etc/os-release && echo "$ID")
          # Register Microsoft repo
          local repo_url="https://packages.microsoft.com/config/${distro_id}/${distro_version}/packages-microsoft-prod.deb"
          wget -q "$repo_url" -O /tmp/packages-microsoft-prod.deb 2>/dev/null || {
            # Fallback: try snap
            step "APT repo not available, trying snap..."
            sudo snap install powershell --classic
            return
          }
          sudo dpkg -i /tmp/packages-microsoft-prod.deb
          rm -f /tmp/packages-microsoft-prod.deb
          sudo apt-get update -qq
          sudo apt-get install -y -qq powershell
          ;;
        dnf|yum)
          step "Installing PowerShell via Microsoft RPM repository..."
          local distro_version
          distro_version=$(. /etc/os-release && echo "$VERSION_ID" | cut -d. -f1)
          sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
          local repo_url="https://packages.microsoft.com/config/rhel/${distro_version}/prod.repo"
          sudo curl -sSL -o /etc/yum.repos.d/microsoft.repo "$repo_url"
          sudo $PKG_MGR install -y powershell
          ;;
        pacman)
          step "Installing PowerShell via AUR..."
          echo "    PowerShell is available via AUR: yay -S powershell-bin"
          echo "    Or snap: sudo snap install powershell --classic"
          return 1
          ;;
        *)
          step "Attempting snap install for PowerShell..."
          if command -v snap &>/dev/null; then
            sudo snap install powershell --classic
          else
            fail "Cannot install PowerShell: no supported method found"
            echo "    See: https://learn.microsoft.com/powershell/scripting/install/installing-powershell-on-linux"
            return 1
          fi
          ;;
      esac
      ;;
  esac
}

install_deepagents() {
  step "Installing deepagents-cli..."
  if check_uv; then
    # Preferred: uv tool install creates an isolated env
    uv tool install 'deepagents-cli' 2>/dev/null || {
      # If already installed, upgrade
      uv tool upgrade deepagents-cli 2>/dev/null || true
    }
  else
    # Fallback: pip in the project venv
    local pip_cmd="$VENV_DIR/bin/pip"
    if [[ -x "$pip_cmd" ]]; then
      "$pip_cmd" install --quiet deepagents-cli
    else
      pip3 install --user deepagents-cli
    fi
  fi

  # Verify
  if check_deepagents; then
    local da_ver
    da_ver=$(deepagents --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")
    ok "deepagents-cli $da_ver installed"
  else
    # May need PATH refresh
    export PATH="$HOME/.local/bin:$HOME/.local/share/uv/tools/deepagents-cli/bin:$PATH"
    if check_deepagents; then
      ok "deepagents-cli installed (PATH updated)"
    else
      warn "deepagents-cli installed but not in PATH yet"
      info "Run: source ~/.bashrc  (or open a new terminal)"
    fi
  fi
}

install_pester() {
  if ! command -v pwsh &>/dev/null; then
    warn "Skipping Pester — PowerShell not available"
    return
  fi
  step "Installing Pester (PowerShell test framework)..."
  pwsh -NoProfile -Command '
    $installed = Get-Module -ListAvailable Pester | Where-Object { $_.Version.Major -ge 5 }
    if ($installed) {
      Write-Host "    [OK] Pester $($installed.Version) already installed"
    } else {
      Install-Module -Name Pester -Force -Scope CurrentUser -SkipPublisherCheck
      $ver = (Get-Module -ListAvailable Pester | Select-Object -First 1).Version
      Write-Host "    [OK] Pester $ver installed"
    }
  ' 2>/dev/null || warn "Pester installation failed (non-critical)"
}

# ─── Python venv & dependencies ──────────────────────────────────────────────

setup_venv() {
  step "Setting up Python virtual environment..."

  if check_uv; then
    [[ -d "$VENV_DIR" ]] || uv venv "$VENV_DIR" --quiet
  else
    local py_cmd
    py_cmd=$(check_python)
    [[ -d "$VENV_DIR" ]] || "$py_cmd" -m venv "$VENV_DIR"
  fi
  ok "venv at $VENV_DIR"

  # Install MCP requirements
  local requirements="$INSTALL_DIR/mcp/requirements.txt"
  if [[ -f "$requirements" ]]; then
    step "Installing MCP dependencies..."
    if check_uv; then
      uv pip install --quiet --python "$VENV_DIR/bin/python" -r "$requirements"
    else
      "$VENV_DIR/bin/pip" install --quiet -r "$requirements"
    fi
    ok "MCP dependencies installed"
  fi

  # Install Dashboard requirements
  local dash_reqs="$INSTALL_DIR/dashboard/requirements.txt"
  if [[ -f "$dash_reqs" ]]; then
    step "Installing dashboard dependencies (FastAPI, uvicorn, websockets)..."
    if check_uv; then
      uv pip install --quiet --python "$VENV_DIR/bin/python" -r "$dash_reqs"
    else
      "$VENV_DIR/bin/pip" install --quiet -r "$dash_reqs"
    fi
    ok "Dashboard dependencies installed"
  fi
}

# ─── File installation ───────────────────────────────────────────────────────

install_files() {
  step "Installing Agent OS to $INSTALL_DIR..."
  mkdir -p "$INSTALL_DIR"

  # Copy the entire .agents directory
  cp -r "$SCRIPT_DIR/"* "$INSTALL_DIR/" 2>/dev/null || true
  # Copy hidden files (like .claude/)
  find "$SCRIPT_DIR" -maxdepth 1 -name '.*' -not -name '.' -not -name '..' \
    -exec cp -r {} "$INSTALL_DIR/" \; 2>/dev/null || true

  # Copy dashboard (source repo layout: dashboard/ is sibling to .agents/)
  if [[ -d "$SCRIPT_DIR/../dashboard" ]] && [[ -f "$SCRIPT_DIR/../dashboard/api.py" ]]; then
    step "Copying web dashboard..."
    rm -rf "$INSTALL_DIR/dashboard" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/../dashboard" "$INSTALL_DIR/dashboard"
    ok "Dashboard copied (api.py, index.html, assets)"
  fi

  # Make scripts executable
  find "$INSTALL_DIR" -name "*.sh" -exec chmod +x {} \;
  chmod +x "$INSTALL_DIR/bin/ostwin" 2>/dev/null || true

  ok "Files installed"
}

# ─── Patch MCP config ────────────────────────────────────────────────────────

patch_mcp_config() {
  local mcp_config="$INSTALL_DIR/mcp/mcp-config.json"
  if [[ -f "$mcp_config" ]]; then
    step "Patching MCP config with venv Python path..."
    # Cross-platform sed (works on both macOS and Linux)
    if [[ "$OS" == "macos" ]]; then
      sed -i '' "s|OSTWIN_VENV_PYTHON|$VENV_DIR/bin/python|g" "$mcp_config"
    else
      sed -i "s|OSTWIN_VENV_PYTHON|$VENV_DIR/bin/python|g" "$mcp_config"
    fi
    ok "MCP config patched"
  fi
}

# ─── PATH setup ──────────────────────────────────────────────────────────────

setup_path() {
  step "Configuring PATH..."

  local shell_name
  shell_name=$(basename "${SHELL:-/bin/bash}")
  local shell_rc
  case "$shell_name" in
    zsh)   shell_rc="$HOME/.zshrc" ;;
    bash)  shell_rc="$HOME/.bashrc" ;;
    fish)  shell_rc="$HOME/.config/fish/config.fish" ;;
    *)     shell_rc="$HOME/.profile" ;;
  esac

  local path_line="export PATH=\"$INSTALL_DIR/bin:\$PATH\""

  if [[ "$shell_name" == "fish" ]]; then
    path_line="set -gx PATH $INSTALL_DIR/bin \$PATH"
  fi

  if grep -qF "ostwin" "$shell_rc" 2>/dev/null; then
    ok "PATH already configured in $shell_rc"
  else
    {
      echo ""
      echo "# Ostwin CLI (Agent OS)"
      echo "$path_line"
    } >> "$shell_rc"
    ok "Added to PATH in $shell_rc"
  fi

  # Export for current session
  export PATH="$INSTALL_DIR/bin:$PATH"
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "  ${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "  ${BOLD}║     ${CYAN}Ostwin${NC}${BOLD} — Agent OS Installer                   ║${NC}"
echo -e "  ${BOLD}║     Multi-Agent War-Room Orchestrator            ║${NC}"
echo -e "  ${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ─── 1. Detect OS ────────────────────────────────────────────────────────────

header "1. Detecting platform"
detect_os

case "$OS" in
  macos) ok "macOS ($ARCH)" ;;
  linux) ok "Linux — $DISTRO ($ARCH) [pkg: $PKG_MGR]" ;;
  *)     fail "Unsupported OS: $(uname -s)"; exit 1 ;;
esac

# ─── 2. Check & install dependencies ─────────────────────────────────────────

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

# --- PowerShell ---
if check_pwsh; then
  ok "PowerShell $PWSH_VERSION"
else
  warn "PowerShell 7+ not found"
  if ask "Install PowerShell? (required for PS modules)"; then
    install_pwsh
    if check_pwsh; then
      ok "PowerShell $PWSH_VERSION installed"
    else
      warn "PowerShell installation may need a shell restart"
    fi
  else
    warn "Skipping PowerShell — bash-only mode (some features unavailable)"
  fi
fi

# --- deepagents-cli ---
if check_deepagents; then
  DA_VERSION=$(deepagents --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "installed")
  ok "deepagents-cli $DA_VERSION"
else
  warn "deepagents-cli not found"
  if ask "Install deepagents-cli? (agent execution engine)"; then
    install_deepagents
  else
    warn "Skipping — agents won't run without deepagents-cli"
    info "Install later: pip install deepagents-cli"
  fi
fi

echo ""

# ─── 3. Install files ────────────────────────────────────────────────────────

header "3. Installing Agent OS"
install_files

# ─── 4. Python environment ───────────────────────────────────────────────────

header "4. Setting up Python environment"
setup_venv
patch_mcp_config

# ─── 5. PowerShell extras ────────────────────────────────────────────────────

if ! $SKIP_OPTIONAL && command -v pwsh &>/dev/null; then
  header "5. PowerShell modules"
  install_pester
else
  header "5. PowerShell modules (skipped)"
  info "PowerShell not available or --skip-optional set"
fi

# ─── 6. PATH ─────────────────────────────────────────────────────────────────

header "6. Configuring PATH"
setup_path

# ─── 7. Verification ─────────────────────────────────────────────────────────

header "7. Verification"

echo ""
echo -e "  ${BOLD}Component Status:${NC}"
echo -e "    bash:             ${GREEN}✅ $BASH_VER${NC}"

PYTHON_CMD=$(check_python)
if [[ -n "$PYTHON_CMD" ]]; then
  echo -e "    python:           ${GREEN}✅ $PYTHON_VERSION${NC}"
else
  echo -e "    python:           ${RED}❌ not found${NC}"
fi

if check_pwsh; then
  echo -e "    powershell:       ${GREEN}✅ $PWSH_VERSION${NC}"
else
  echo -e "    powershell:       ${YELLOW}⚠️  not installed${NC}"
fi

if check_uv; then
  echo -e "    uv:               ${GREEN}✅ $(uv --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)${NC}"
else
  echo -e "    uv:               ${YELLOW}⚠️  not installed${NC}"
fi

if check_deepagents; then
  echo -e "    deepagents-cli:   ${GREEN}✅ $(deepagents --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo 'installed')${NC}"
else
  echo -e "    deepagents-cli:   ${YELLOW}⚠️  not in PATH${NC}"
fi

if [[ -d "$VENV_DIR" ]]; then
  echo -e "    venv:             ${GREEN}✅ $VENV_DIR${NC}"
else
  echo -e "    venv:             ${RED}❌ not created${NC}"
fi

# ─── 8. Start Dashboard ──────────────────────────────────────────────────────

header "8. Starting dashboard"

DASHBOARD_SCRIPT="$INSTALL_DIR/dashboard.sh"
if [[ -f "$DASHBOARD_SCRIPT" ]] && [[ -f "$INSTALL_DIR/dashboard/api.py" ]]; then
  # Kill any existing dashboard on :9000
  if lsof -ti:9000 >/dev/null 2>&1; then
    step "Stopping existing process on :9000..."
    kill "$(lsof -ti:9000)" 2>/dev/null || true
    sleep 1
  fi

  step "Starting dashboard on http://localhost:9000..."
  nohup bash "$DASHBOARD_SCRIPT" --background > "$INSTALL_DIR/logs/dashboard.log" 2>&1 &
  DASHBOARD_PID=$!
  echo "$DASHBOARD_PID" > "$INSTALL_DIR/dashboard.pid"
  sleep 2

  if kill -0 "$DASHBOARD_PID" 2>/dev/null; then
    ok "Dashboard running on http://localhost:9000 (PID $DASHBOARD_PID)"
  else
    warn "Dashboard failed to start — check $INSTALL_DIR/logs/dashboard.log"
  fi
else
  warn "Dashboard not found — skipping auto-start"
  info "Re-run install or copy dashboard/ manually"
fi

# ─── Done! ────────────────────────────────────────────────────────────────────

SHELL_NAME=$(basename "${SHELL:-/bin/bash}")
SHELL_RC="$HOME/.${SHELL_NAME}rc"

echo ""
echo -e "  ${GREEN}${BOLD}Installation complete! ✅${NC}"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo ""
echo -e "    ${CYAN}1.${NC} Reload your shell:        ${DIM}source $SHELL_RC${NC}"
echo -e "    ${CYAN}2.${NC} Verify installation:       ${DIM}ostwin health${NC}"
echo -e "    ${CYAN}3.${NC} Initialize a project:      ${DIM}ostwin init ~/my-project${NC}"
echo -e "    ${CYAN}4.${NC} Set your API key:          ${DIM}export GOOGLE_API_KEY=\"your-key\"${NC}"
echo -e "    ${CYAN}5.${NC} Run your first plan:       ${DIM}ostwin run plans/my-plan.md${NC}"
echo ""
echo -e "  ${BOLD}Dashboard:${NC}"
echo -e "    ${DIM}Dashboard running at http://localhost:9000${NC}"
echo -e "    ${DIM}Stop with: ostwin stop${NC}"
echo ""
echo -e "  ${BOLD}API Key Setup:${NC}"
echo -e "    ${DIM}# Google (default model: gemini-3-flash-preview)${NC}"
echo -e "    export GOOGLE_API_KEY=\"your-api-key\""
echo -e "    ${DIM}# Or use OpenAI/Anthropic — see: ostwin config${NC}"
echo ""
