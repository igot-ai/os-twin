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

# ─── Configuration ────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${HOME}/.ostwin"
# SOURCE_DIR: root of the agent-os repo (to locate dashboard/ source).
# Auto-detected as SCRIPT_DIR parent; override with --source-dir.
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd || echo "")"
AUTO_YES=false
SKIP_OPTIONAL=false
DASHBOARD_ONLY=false
START_CHANNEL=true
DASHBOARD_PORT=9000
MIN_PYTHON_VERSION="3.10"
MIN_PWSH_VERSION="7"
PYTHON_VERSION=""
PWSH_VERSION=""

# ─── Argument parsing ────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y)        AUTO_YES=true; shift ;;
    --dir)           INSTALL_DIR="$2"; shift 2 ;;
    --source-dir)    SOURCE_DIR="$2"; shift 2 ;;
    --port)          DASHBOARD_PORT="$2"; shift 2 ;;
    --skip-optional) SKIP_OPTIONAL=true; shift ;;
    --dashboard-only) DASHBOARD_ONLY=true; AUTO_YES=true; shift ;;
    --channel)       START_CHANNEL=true; shift ;;
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

check_node() {
  command -v node &>/dev/null
}

check_uv() {
  command -v uv &>/dev/null
}

check_opencode() {
  command -v opencode &>/dev/null
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
      # Try Homebrew first, fall back to direct tar.gz install
      if check_brew; then
        step "Installing PowerShell via Homebrew..."
        if brew install powershell/tap/powershell 2>/dev/null; then
          return
        fi
        warn "Homebrew formula failed — falling back to direct install"
      fi

      # Direct install from GitHub release (no sudo needed)
      local pwsh_ver="7.4.7"
      local arch_tag
      arch_tag=$( [[ "$ARCH" == "arm64" ]] && echo "osx-arm64" || echo "osx-x64" )
      local url="https://github.com/PowerShell/PowerShell/releases/download/v${pwsh_ver}/powershell-${pwsh_ver}-${arch_tag}.tar.gz"

      step "Installing PowerShell ${pwsh_ver} from GitHub (${arch_tag})..."
      local pwsh_dir="$HOME/.local/powershell/7"
      mkdir -p "$pwsh_dir" "$HOME/.local/bin"
      curl -sSL "$url" -o /tmp/powershell.tar.gz
      tar -xzf /tmp/powershell.tar.gz -C "$pwsh_dir"
      chmod +x "$pwsh_dir/pwsh"
      ln -sf "$pwsh_dir/pwsh" "$HOME/.local/bin/pwsh"
      rm -f /tmp/powershell.tar.gz
      export PATH="$HOME/.local/bin:$PATH"
      ok "PowerShell ${pwsh_ver} installed to $pwsh_dir"
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

install_node() {
  local NODE_VER="v25.8.1"
  step "Installing Node.js $NODE_VER..."
  local node_dir="$HOME/.local/node"
  mkdir -p "$node_dir" "$HOME/.local/bin"

  local os_type arch_type
  case "$OS" in
    macos) os_type="darwin" ;;
    linux) os_type="linux" ;;
  esac

  case "$ARCH" in
    arm64|aarch64) arch_type="arm64" ;;
    x86_64|amd64) arch_type="x64" ;;
    *) fail "Unsupported architecture for Node direct download: $ARCH"; exit 1 ;;
  esac

  local url="https://nodejs.org/dist/${NODE_VER}/node-${NODE_VER}-${os_type}-${arch_type}.tar.gz"
  step "Downloading from $url..."
  curl -sSL "$url" -o /tmp/node.tar.gz || { fail "Failed to download Node.js $NODE_VER"; exit 1; }
  tar -xzf /tmp/node.tar.gz -C "$node_dir" --strip-components=1
  ln -sf "$node_dir/bin/node" "$HOME/.local/bin/node"
  ln -sf "$node_dir/bin/npm" "$HOME/.local/bin/npm"
  ln -sf "$node_dir/bin/npx" "$HOME/.local/bin/npx"
  rm -f /tmp/node.tar.gz
  export PATH="$HOME/.local/bin:$PATH"
  ok "Node.js $NODE_VER installed to $node_dir"
}

install_opencode() {
  step "Installing opencode..."

  # Preferred: brew (macOS and Linux, always up to date)
  if command -v brew &>/dev/null; then
    brew install anomalyco/tap/opencode 2>/dev/null || brew upgrade anomalyco/tap/opencode 2>/dev/null || true
  else
    # Fallback: official install script
    curl -fsSL https://opencode.ai/install | bash
  fi

  # Verify
  if check_opencode; then
    local oc_ver
    oc_ver=$(opencode --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "installed")
    ok "opencode $oc_ver installed"
  else
    # PATH may need refreshing
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if check_opencode; then
      ok "opencode installed (PATH updated)"
    else
      warn "opencode installed but not in PATH yet"
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

  # Install MCP requirements
  local requirements="$INSTALL_DIR/.agents/mcp/requirements.txt"
  if [[ -f "$requirements" ]]; then
    step "Syncing MCP dependencies..."
    if check_uv; then
      TMPDIR=/tmp uv pip install --quiet --upgrade --no-cache --prerelease=allow \
        --python "$VENV_DIR/bin/python" -r "$requirements"
    else
      "$VENV_DIR/bin/pip" install --quiet --upgrade -r "$requirements"
    fi
    ok "MCP dependencies up to date"
  fi

  # Install Dashboard requirements
  local dash_reqs="$INSTALL_DIR/dashboard/requirements.txt"
  if [[ -f "$dash_reqs" ]]; then
    step "Syncing dashboard dependencies..."
    if check_uv; then
      TMPDIR=/tmp uv pip install --quiet --upgrade --no-cache --prerelease=allow \
        --python "$VENV_DIR/bin/python" -r "$dash_reqs"
    else
      "$VENV_DIR/bin/pip" install --quiet --upgrade -r "$dash_reqs"
    fi
    ok "Dashboard dependencies up to date"
  fi

  # Install Memory/indexing requirements (CocoIndex, pgvector, etc.)
  local memory_reqs="$INSTALL_DIR/.agents/memory/requirements.txt"
  if [[ -f "$memory_reqs" ]]; then
    step "Syncing memory/indexing dependencies..."
    if check_uv; then
      TMPDIR=/tmp uv pip install --quiet --upgrade --no-cache \
        --python "$VENV_DIR/bin/python" -r "$memory_reqs"
    else
      "$VENV_DIR/bin/pip" install --quiet --upgrade -r "$memory_reqs"
    fi
    ok "Memory/indexing dependencies up to date"
  fi

  # Install role-specific requirements (e.g. roles/reporter/requirements.txt)
  local roles_dir="$INSTALL_DIR/.agents/roles"
  if [[ -d "$roles_dir" ]]; then
    for role_reqs in "$roles_dir"/*/requirements.txt; do
      [[ -f "$role_reqs" ]] || continue
      local role_name
      role_name=$(basename "$(dirname "$role_reqs")")
      step "Syncing $role_name role dependencies..."
      if check_uv; then
        TMPDIR=/tmp uv pip install --quiet --upgrade --no-cache --prerelease=allow \
          --python "$VENV_DIR/bin/python" -r "$role_reqs"
      else
        "$VENV_DIR/bin/pip" install --quiet --upgrade -r "$role_reqs"
      fi
      ok "$role_name role dependencies up to date"
    done
  fi
}

# ─── .env setup ───────────────────────────────────────────────────────────────
# Creates ~/.ostwin/.env on first install so the dashboard and agents can
# read API keys without requiring them to be exported in every shell session.

setup_env() {
  local env_file="$INSTALL_DIR/.env"

  if [[ -f "$env_file" ]]; then
    ok ".env already exists at $env_file"
    return
  fi

  step "Creating .env file at $env_file..."
  mkdir -p "$INSTALL_DIR"

  # Generate a secure API key for dashboard auth
  local generated_api_key
  generated_api_key="ostwin_$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)"

  cat > "$env_file" << ENVEOF
# Ostwin — Environment Variables
# Edit this file and re-start the dashboard (ostwin stop && ostwin start)
# Lines starting with # are comments.

# ── AI Provider Keys (set at least one) ────────────────────────────────────
# GOOGLE_API_KEY=your-google-api-key-here
# OPENAI_API_KEY=your-openai-api-key-here
# ANTHROPIC_API_KEY=your-anthropic-api-key-here
# OPENROUTER_API_KEY=your-openrouter-api-key-here
# AZURE_OPENAI_API_KEY=your-azure-openai-api-key-here
# BASETEN_API_KEY=your-baseten-api-key-here
# AWS_ACCESS_KEY_ID=your-aws-access-key-id-here
# AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key-here

# ── Dashboard settings ──────────────────────────────────────────────────────
# DASHBOARD_PORT=9000
# DASHBOARD_HOST=0.0.0.0

# ── Dashboard Authentication ────────────────────────────────────────────────
# API key for CLI ↔ Dashboard communication. Auto-generated on first install.
OSTWIN_API_KEY=${generated_api_key}

# ── ngrok Tunnel (auto-starts when NGROK_AUTHTOKEN is set) ─────────────────
# NGROK_AUTHTOKEN=
# NGROK_DOMAIN=              # Optional: custom/static domain (paid ngrok plans)

# ── Agent OS settings ───────────────────────────────────────────────────────
# OSTWIN_LOG_LEVEL=INFO
ENVEOF

  chmod 600 "$env_file"   # Protect API keys
  ok ".env created — edit $env_file to add your API keys"

  # Create a companion .env.sh hook for dynamic env logic (subshells,
  # token refresh, etc.) that .env can't express. Sourced by every
  # generated run-agent.sh wrapper before the agent execs.
  local env_sh="$INSTALL_DIR/.env.sh"
  if [[ ! -f "$env_sh" ]]; then
    cat > "$env_sh" << 'ENVSHEOF'
# Ostwin — dynamic environment hook
# Sourced by every generated run-agent.sh wrapper before the agent execs.
# Use this for env vars that require shell logic (subshells, conditionals,
# token refresh, etc.). Static KEY=VALUE pairs belong in ~/.ostwin/.env.

# Refresh a Vertex AI access token from the active gcloud account.
# The OpenAI-compatible Vertex endpoint expects this as a Bearer token,
# and access tokens expire ~1h, so re-mint per agent launch.
if command -v gcloud >/dev/null 2>&1; then
  VERTEX_API_KEY="$(gcloud auth print-access-token 2>/dev/null)"
  export VERTEX_API_KEY
fi
ENVSHEOF
    chmod 600 "$env_sh"
    ok ".env.sh created — add dynamic env hooks (e.g. token refresh) here"
  fi

  # Migrate any existing exported key from the current shell environment
  local migrated=false
  for key in GOOGLE_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY AZURE_OPENAI_API_KEY BASETEN_API_KEY AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY NGROK_AUTHTOKEN; do
    if [[ -n "${!key:-}" ]]; then
      # Uncomment and fill the matching line
      if [[ "$OS" == "macos" ]]; then
        sed -i '' "s|^# ${key}=.*|${key}=${!key}|" "$env_file"
      else
        sed -i "s|^# ${key}=.*|${key}=${!key}|" "$env_file"
      fi
      ok "Migrated \$${key} into .env"
      migrated=true
    fi
  done

  if ! $migrated; then
    warn "No API keys found in current shell."
    if ! $AUTO_YES; then
      echo -e "    ${CYAN}Which AI Provider would you like to configure now?${NC}"
      echo -e "      1) Google (Gemini)\t5) Azure OpenAI"
      echo -e "      2) OpenAI\t\t6) Baseten"
      echo -e "      3) Anthropic\t\t7) AWS Bedrock"
      echo -e "      4) OpenRouter"
      echo -e "      0) Skip for now"
      echo -en "    ${YELLOW}?${NC} Select an option ${DIM}[0-7]${NC}: "
      read -r provider_choice

      local selected_keys=()
      case "$provider_choice" in
        1) selected_keys=("GOOGLE_API_KEY") ;;
        2) selected_keys=("OPENAI_API_KEY") ;;
        3) selected_keys=("ANTHROPIC_API_KEY") ;;
        4) selected_keys=("OPENROUTER_API_KEY") ;;
        5) selected_keys=("AZURE_OPENAI_API_KEY") ;;
        6) selected_keys=("BASETEN_API_KEY") ;;
        7) selected_keys=("AWS_ACCESS_KEY_ID" "AWS_SECRET_ACCESS_KEY") ;;
        *) info "Skipped API key setup. Please edit $env_file later." ;;
      esac

      for key_name in "${selected_keys[@]}"; do
        echo -en "    ${CYAN}→${NC} Enter $key_name: "
        read -s -r user_val
        echo ""
        if [[ -n "$user_val" ]]; then
          if [[ "$OS" == "macos" ]]; then
            sed -i '' "s|^# ${key_name}=.*|${key_name}=${user_val}|" "$env_file"
          else
            sed -i "s|^# ${key_name}=.*|${key_name}=${user_val}|" "$env_file"
          fi
          ok "Saved $key_name into .env"
        fi
      done
    else
      info "Non-interactive mode (-y). Edit $env_file later to add your API keys."
    fi
  fi

  # Prompt for ngrok tunnel token (optional)
  if ! $AUTO_YES && [[ -z "${NGROK_AUTHTOKEN:-}" ]]; then
    echo ""
    echo -en "    ${CYAN}→${NC} Enter NGROK_AUTHTOKEN for dashboard port-forwarding (or press Enter to skip): "
    read -r ngrok_token
    if [[ -n "$ngrok_token" ]]; then
      if [[ "$OS" == "macos" ]]; then
        sed -i '' "s|^# NGROK_AUTHTOKEN=.*|NGROK_AUTHTOKEN=${ngrok_token}|" "$env_file"
      else
        sed -i "s|^# NGROK_AUTHTOKEN=.*|NGROK_AUTHTOKEN=${ngrok_token}|" "$env_file"
      fi
      ok "Saved NGROK_AUTHTOKEN — tunnel will auto-start with dashboard"
    fi
  fi
}

# ─── Next.js dashboard build ────────────────────────────────────────────────

build_nextjs() {
  # Locate the nextjs directory relative to the source repo
  local nextjs_dir=""
  for candidate in \
    "${SOURCE_DIR}/dashboard/nextjs" \
    "${SCRIPT_DIR}/../dashboard/nextjs" \
    "${SCRIPT_DIR}/dashboard/nextjs"; do
    if [[ -d "$candidate" ]] && [[ -f "$candidate/package.json" ]]; then
      nextjs_dir="$(cd "$candidate" && pwd)"
      break
    fi
  done

  if [[ -z "$nextjs_dir" ]]; then
    warn "Next.js dashboard not found — skipping build"
    info "Expected at dashboard/nextjs/package.json"
    return
  fi

  # Pick installed package manager (prefer bun for speed)
  local pm=""
  for tool in bun pnpm npm yarn; do
    if command -v "$tool" &>/dev/null; then
      pm="$tool"
      break
    fi
  done

  if [[ -z "$pm" ]]; then
    warn "No package manager (bun/pnpm/npm/yarn) found — skipping Next.js build"
    info "Install Node.js and a package manager to enable the dashboard UI"
    return
  fi

  step "Building Next.js dashboard ($pm) at $nextjs_dir..."
  (
    cd "$nextjs_dir"
    # Install deps if node_modules missing
    if [[ ! -d node_modules ]]; then
      step "Installing npm dependencies..."
      "$pm" install --frozen-lockfile 2>/dev/null || "$pm" install
    fi
    "$pm" run build
  ) && ok "Next.js build complete" || warn "Next.js build failed — dashboard UI may be outdated"
}

# ─── Dashboard FE build (dashboard/fe) ───────────────────────────────────────

build_dashboard_fe() {
  # Locate the fe directory relative to the source repo
  local fe_dir=""
  for candidate in \
    "${SOURCE_DIR}/dashboard/fe" \
    "${SCRIPT_DIR}/../dashboard/fe" \
    "${SCRIPT_DIR}/dashboard/fe"; do
    if [[ -d "$candidate" ]] && [[ -f "$candidate/package.json" ]]; then
      fe_dir="$(cd "$candidate" && pwd)"
      break
    fi
  done

  if [[ -z "$fe_dir" ]]; then
    warn "Dashboard frontend not found — skipping build"
    info "Expected at dashboard/fe/package.json"
    return
  fi

  # Pick installed package manager (prefer bun for speed)
  local pm=""
  for tool in bun pnpm npm yarn; do
    if command -v "$tool" &>/dev/null; then
      pm="$tool"
      break
    fi
  done

  if [[ -z "$pm" ]]; then
    warn "No package manager (bun/pnpm/npm/yarn) found — skipping FE build"
    info "Install Node.js and a package manager to enable the dashboard frontend"
    return
  fi

  step "Building dashboard frontend ($pm) at $fe_dir..."
  (
    cd "$fe_dir"
    # Install deps if node_modules missing
    if [[ ! -d node_modules ]]; then
      step "Installing npm dependencies..."
      "$pm" install --frozen-lockfile 2>/dev/null || "$pm" install
    fi
    "$pm" run build
  ) && ok "Dashboard FE build complete" || warn "Dashboard FE build failed"
}

# ─── File installation ───────────────────────────────────────────────────────

install_files() {
  step "Installing OS Twin to $INSTALL_DIR..."
  mkdir -p "$INSTALL_DIR/.agents"

  # Ensure clean slate for core roles (remove old core roles before syncing)
  rm -rf "$INSTALL_DIR/.agents/roles"

  # Sync SCRIPT_DIR contents (agents, scripts, config) — skip runtime state
  # NOTE: MCP config files are excluded to preserve user's installed extensions and config
  rsync -a \
    --exclude='.venv/' --exclude='*.pid' --exclude='dashboard.pid' \
    --exclude='logs/' --exclude='__pycache__/' --exclude='*.pyc' \
    --exclude='mcp/config.json' --exclude='mcp/.env.mcp' \
    "$SCRIPT_DIR/" "$INSTALL_DIR/.agents/" 2>/dev/null || {
      # rsync fallback to cp (exclude mcp/ manually)
      find "$SCRIPT_DIR" -maxdepth 1 -not -name 'mcp' -not -name '.' \
        -exec cp -r {} "$INSTALL_DIR/.agents/" \; 2>/dev/null || true
    }

  # ── MCP: seed config on first install, never overwrite ─────────────────────
  if [[ ! -f "$INSTALL_DIR/.agents/mcp/mcp-config.json" ]]; then
    step "Seeding mcp-config.json (first install)..."
    cp "$SCRIPT_DIR/mcp/mcp-config.json" "$INSTALL_DIR/.agents/mcp/mcp-config.json"
    ok "mcp-config.json seeded"
  else
    # Always update the builtin template so new built-in servers are available
    if [[ -f "$SCRIPT_DIR/mcp/mcp-builtin.json" ]]; then
      cp "$SCRIPT_DIR/mcp/mcp-builtin.json" "$INSTALL_DIR/.agents/mcp/mcp-builtin.json"
    fi
    # Always update catalog so new packages are available
    if [[ -f "$SCRIPT_DIR/mcp/mcp-catalog.json" ]]; then
      cp "$SCRIPT_DIR/mcp/mcp-catalog.json" "$INSTALL_DIR/.agents/mcp/mcp-catalog.json"
    fi
    # Merge new built-in servers into mcp-config.json (never overwrite existing)
    local mcp_cfg="$INSTALL_DIR/.agents/mcp/mcp-config.json"
    local mcp_builtin="$INSTALL_DIR/.agents/mcp/mcp-builtin.json"
    if [[ -f "$mcp_cfg" ]] && [[ -f "$mcp_builtin" ]]; then
      python3 - "$mcp_cfg" "$mcp_builtin" <<'MERGE_EOF' && ok "Merged new built-in MCP servers" || true
import json, sys

cfg_path, builtin_path = sys.argv[1], sys.argv[2]

with open(cfg_path) as f:
    config = json.load(f)
with open(builtin_path) as f:
    builtin = json.load(f)

cfg_servers = config.setdefault("mcpServers", {})
builtin_servers = builtin.get("mcpServers", {})

added = []
for name, server in builtin_servers.items():
    if name not in cfg_servers:
        cfg_servers[name] = server
        added.append(name)

if added:
    with open(cfg_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    print(f"    Added {len(added)} new server(s): {', '.join(added)}")
else:
    print("    All built-in servers already present")
MERGE_EOF
    fi
    # Sync MCP server scripts (channel-server.py, warroom-server.py, etc.)
    for f in "$SCRIPT_DIR"/mcp/*.py "$SCRIPT_DIR"/mcp/*.sh "$SCRIPT_DIR"/mcp/requirements.txt; do
      [[ -f "$f" ]] && cp "$f" "$INSTALL_DIR/.agents/mcp/"
    done
    ok "mcp/ preserved (scripts + catalog updated, new servers merged)"
  fi

  # ── A-mem-sys: copy agentic memory system ─────────────────────────────────
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

  # ── Symlink ~/.ostwin/mcp -> ~/.ostwin/.agents/mcp ────────────────────────
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
    # Copy any files from old dir that don't exist in .agents/mcp (preserve user additions)
    for f in "$mcp_link"/*; do
      [[ -f "$f" ]] && [[ ! -f "$mcp_real/$(basename "$f")" ]] && cp "$f" "$mcp_real/"
    done
    rm -rf "$mcp_link"
    ln -s "$mcp_real" "$mcp_link"
    ok "Migrated $mcp_link -> .agents/mcp (symlink)"
  else
    ln -s "$mcp_real" "$mcp_link"
  fi

  # ── MCP: migrate legacy mcp-config.json → config.json ─────────────────────
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

  # ── Dashboard: always override from source repo ───────────────────────────
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
  # ── Contributed roles: copy from repo's contributes/roles/ ────────────────
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
  # Make scripts executable
  find "$INSTALL_DIR/.agents" -name "*.sh" -exec chmod +x {} \;
  chmod +x "$INSTALL_DIR/.agents/bin/ostwin" 2>/dev/null || true

  ok "Files installed"
}

# ─── Build hash ─────────────────────────────────────────────────────────────

compute_build_hash() {
  step "Computing build hash..."

  # Prefer shasum (macOS), fall back to sha256sum (Linux)
  local sha_cmd="shasum -a 256"
  if ! command -v shasum &>/dev/null; then
    sha_cmd="sha256sum"
  fi

  local hash
  hash=$(
    find "$INSTALL_DIR" \
      -type f \
      ! -path "$INSTALL_DIR/.venv/*" \
      ! -path "$INSTALL_DIR/logs/*" \
      ! -path "$INSTALL_DIR/node_modules/*" \
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

# ─── Patch MCP config ────────────────────────────────────────────────────────

patch_mcp_config() {
  local mcp_config="$INSTALL_DIR/.agents/mcp/config.json"
  local env_file="$INSTALL_DIR/.env"

  if [[ ! -f "$mcp_config" ]]; then
    return
  fi

  step "Patching MCP config..."

  # 1. Ensure OSTWIN_PYTHON is set in .env (used by {env:OSTWIN_PYTHON} in config)
  if [[ -f "$env_file" ]]; then
    if ! grep -q "^OSTWIN_PYTHON=" "$env_file"; then
      echo "OSTWIN_PYTHON=$VENV_DIR/bin/python" >> "$env_file"
    fi
  else
    echo "OSTWIN_PYTHON=$VENV_DIR/bin/python" > "$env_file"
  fi

  # 2. Inject all .env variables into every MCP server's "environment" block
  if [[ -f "$env_file" ]]; then
    "$VENV_DIR/bin/python" - "$mcp_config" "$env_file" <<'PYEOF'
import json, sys, os

mcp_path, env_path = sys.argv[1], sys.argv[2]

# Parse .env file into a dict
env_vars = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, _, val = line.partition('=')
        key = key.strip()
        # Strip surrounding quotes
        val = val.strip().strip('"').strip("'")
        if key:
            env_vars[key] = val

if not env_vars:
    sys.exit(0)

# Read and patch MCP config
with open(mcp_path) as f:
    config = json.load(f)

import re
# Support both OpenCode 'mcp' and legacy 'mcpServers' keys
servers = config.get('mcp', config.get('mcpServers', {}))
for name, server in servers.items():
    # Only inject environment into local servers (OpenCode spec)
    if server.get('type') == 'remote':
        continue
    # Support both 'environment' (OpenCode) and 'env' (legacy)
    env_key = 'environment' if 'environment' in server else 'env' if 'env' in server else 'environment'
    if env_key not in server:
        server[env_key] = {}
    # Find ${VAR} or {env:VAR} references in this server's config
    server_str = json.dumps(server)
    server_refs = set(re.findall(r'\$\{(\w+)(?:[:-][^}]*)?\}', server_str))
    server_refs |= set(re.findall(r'\{env:(\w+)\}', server_str))
    # Only inject vars that this server references, or resolve existing placeholder env values
    for k, v in env_vars.items():
        if k in server[env_key]:
            cur = server[env_key][k]
            if isinstance(cur, str) and ('${' in cur or '{env:' in cur) and v:
                server[env_key][k] = v
        elif k in server_refs and v:
            server[env_key][k] = v

with open(mcp_path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')

print(f"    Injected {len(env_vars)} env var(s) into {len(servers)} MCP server(s)")
PYEOF
  fi

  # 3. Normalize + validate + merge MCP servers into ~/.config/opencode/opencode.json
  #    - Normalizes from any format (legacy mcpServers, shell ${VAR}, etc.) to OpenCode.
  #    - Validates each server against OpenCode MCP spec.
  #    - Ensures each server has "enabled": true.
  #    - Builds a "tools" deny block: "<server>*": false for each server.
  #    - Preserves existing user settings (theme, model, keybinds).
  local opencode_home="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
  mkdir -p "$opencode_home"
  "$VENV_DIR/bin/python" - "$mcp_config" "$opencode_home/opencode.json" "$INSTALL_DIR/.agents/mcp" <<'PYEOF'
import json, sys, os

mcp_source, opencode_file, mcp_module_dir = sys.argv[1], sys.argv[2], sys.argv[3]

# Import from the shared module (.agents/mcp/validate_mcp.py)
sys.path.insert(0, mcp_module_dir)
from validate_mcp import normalize_mcp_config, validate_mcp_config, build_opencode_config

# Read the MCP source config (may be OpenCode or legacy format)
with open(mcp_source) as f:
    source = json.load(f)

# Normalize: legacy mcpServers → mcp, shell ${VAR} → {env:VAR},
#            string command → array, env → environment, httpUrl → url
normalized = normalize_mcp_config(source)

# Validate against OpenCode spec
validated_mcp, skipped_names, results = validate_mcp_config(normalized)

for name, is_valid, errors, warnings in results:
    for w in warnings:
        print(f"    [WARN] '{name}': {w}", file=sys.stderr)
    if not is_valid:
        for e in errors:
            print(f"    [ERROR] '{name}': {e} — skipping", file=sys.stderr)

# Reference-aware filtering: drop any environment entries that still contain
# unresolved {env:VAR} references so OpenCode never sees a literal placeholder
# as an env value. (Resolved values were already injected upstream from .env.)
import re as _re
_env_ref = _re.compile(r'\{env:\w+\}')
for _name, _cfg in validated_mcp.items():
    _envblock = _cfg.get('environment')
    if isinstance(_envblock, dict):
        _cfg['environment'] = {
            k: v for k, v in _envblock.items()
            if not (isinstance(v, str) and _env_ref.search(v))
        }

# Build tools deny + agent config:
#   - Global tools deny: blocks all MCP tools EXCEPT core servers
#     (channel, warroom, memory are available to ALL agents)
#   - Agent config: privileged agents (manager, architect, qa, audit,
#     reporter) get ALL tools enabled
tools_deny, agent_config = build_opencode_config(validated_mcp)

# Load existing opencode.json if present (preserve user settings)
existing = {}
if os.path.exists(opencode_file):
    try:
        with open(opencode_file) as f:
            existing = json.load(f)
    except (json.JSONDecodeError, ValueError):
        existing = {}

# Merge: replace only the managed keys (mcp, tools, agent)
existing["$schema"] = "https://opencode.ai/config.json"
existing["mcp"] = validated_mcp
existing["tools"] = tools_deny
existing["agent"] = agent_config

with open(opencode_file, 'w') as f:
    json.dump(existing, f, indent=2)
    f.write('\n')

core_count = len([n for n in validated_mcp if n in {"channel", "warroom", "memory"}])
print(f"    Merged {len(validated_mcp)} MCP server(s) into {opencode_file}")
if skipped_names:
    print(f"    Skipped {len(skipped_names)} invalid server(s): {', '.join(skipped_names)}")
print(f"    Tools deny block: {len(tools_deny)} server(s) globally disabled")
print(f"    Core servers (channel/warroom/memory): {core_count} available to all agents")
print(f"    Agent config: {len(agent_config)} privileged agent(s) with full tool access")
PYEOF

  ok "MCP config patched"
}

# ─── Sync roles to OpenCode agents dir ───────────────────────────────────────
# Copies ROLE.md from each role directory to ~/.config/opencode/agents/<role>.md
# so the OpenCode CLI can discover and invoke them as named agents.

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

  local path_line="export PATH=\"$INSTALL_DIR/.agents/bin:\$PATH\""

  if [[ "$shell_name" == "fish" ]]; then
    path_line="set -gx PATH $INSTALL_DIR/.agents/bin \$PATH"
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
  export PATH="$INSTALL_DIR/.agents/bin:$PATH"
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
    if ! command -v pnpm &>/dev/null && command -v npm &>/dev/null; then
      step "Installing pnpm..."
      npm install -g pnpm 2>/dev/null || sudo npm install -g pnpm 2>/dev/null || true
    fi
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

# --- opencode ---
if check_opencode; then
  OC_VERSION=$(opencode --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "installed")
  ok "opencode $OC_VERSION"
else
  install_opencode
fi

# --- Node.js ---
if check_node; then
  NODE_VERSION=$(node --version 2>&1 | head -1)
  ok "Node.js $NODE_VERSION"
  if ! command -v pnpm &>/dev/null && command -v npm &>/dev/null; then
    step "Installing pnpm..."
    npm install -g pnpm 2>/dev/null || sudo npm install -g pnpm 2>/dev/null || true
  fi
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
      if ! command -v pnpm &>/dev/null && command -v npm &>/dev/null; then
        step "Installing pnpm..."
        npm install -g pnpm 2>/dev/null || sudo npm install -g pnpm 2>/dev/null || true
      fi
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

echo ""

# ─── 3. Build Next.js dashboard ─────────────────────────────────────────────

if ! $DASHBOARD_ONLY; then
  header "3. Building Next.js dashboard"
  build_nextjs
  header "3b. Building dashboard frontend (fe)"
  build_dashboard_fe
else
  header "3. Building dashboard frontend (fe)"
  build_dashboard_fe
fi

# ─── 4. Install files ────────────────────────────────────────────────────────

header "4. Installing Agent OS"
install_files

# ─── 4b. macOS host daemon (optional, desktop automation support) ─────────────

if [[ "$OS" == "macos" ]]; then
  DAEMON_INSTALL="$INSTALL_DIR/.agents/daemons/macos-host/install.sh"
  if [[ -f "$DAEMON_INSTALL" ]]; then
    if ask "Install macOS host daemon? (enables desktop automation: windows, clicks, screenshots)"; then
      bash "$DAEMON_INSTALL"
    else
      info "Skipped macOS daemon. Run manually later: bash $DAEMON_INSTALL"
    fi
  fi
fi

# ─── 5. Python environment ───────────────────────────────────────────────────

header "5. Setting up Python environment"
setup_venv
patch_mcp_config
sync_opencode_agents
compute_build_hash

# ─── 5b. Environment variables (.env) ────────────────────────────────────────

header "5b. Setting up .env"
setup_env

# ─── 6. PowerShell extras ────────────────────────────────────────────────────

if $DASHBOARD_ONLY; then
  header "6. PowerShell modules (skipped — dashboard-only)"
  info "Skipping in dashboard-only mode"
elif ! $SKIP_OPTIONAL && command -v pwsh &>/dev/null; then
  header "6. PowerShell modules"
  install_pester
else
  header "6. PowerShell modules (skipped)"
  info "PowerShell not available or --skip-optional set"
fi

# ─── 7. PATH ─────────────────────────────────────────────────────────────────

if ! $DASHBOARD_ONLY; then
  header "7. Configuring PATH"
  setup_path
else
  header "7. PATH (skipped — dashboard-only)"
  info "Skipping PATH setup in dashboard-only mode"
  # Still ensure INSTALL_DIR/bin is in current session
  export PATH="$INSTALL_DIR/.agents/bin:$PATH"
fi

# ─── 8. Verification ─────────────────────────────────────────────────────────

header "8. Verification"

echo ""
if $DASHBOARD_ONLY; then
  echo -e "  ${BOLD}Dashboard-Only Component Status:${NC}"
  PYTHON_CMD=$(check_python)
  if [[ -n "$PYTHON_CMD" ]]; then
    echo -e "    python:           ${GREEN}✅ $PYTHON_VERSION${NC}"
  else
    echo -e "    python:           ${RED}❌ not found${NC}"
  fi
  if [[ -d "$VENV_DIR" ]]; then
    echo -e "    venv:             ${GREEN}✅ $VENV_DIR${NC}"
  else
    echo -e "    venv:             ${RED}❌ not created${NC}"
  fi
  if [[ -f "$INSTALL_DIR/dashboard/api.py" ]]; then
    echo -e "    dashboard api:    ${GREEN}✅ installed${NC}"
  else
    echo -e "    dashboard api:    ${RED}❌ not found${NC}"
  fi
else
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

  if check_opencode; then
    echo -e "    opencode:         ${GREEN}✅ $(opencode --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo 'installed')${NC}"
  else
    echo -e "    opencode:         ${YELLOW}⚠️  not in PATH${NC}"
  fi

  if [[ -d "$VENV_DIR" ]]; then
    echo -e "    venv:             ${GREEN}✅ $VENV_DIR${NC}"
  else
    echo -e "    venv:             ${RED}❌ not created${NC}"
  fi
fi

# ─── 8. Start Dashboard ──────────────────────────────────────────────────────

header "9. Starting dashboard"

DASHBOARD_SCRIPT="$INSTALL_DIR/.agents/dashboard.sh"
if [[ -f "$DASHBOARD_SCRIPT" ]] && [[ -f "$INSTALL_DIR/dashboard/api.py" ]]; then

  # Stop any existing process on the dashboard port
  local_pids=$(lsof -ti:"$DASHBOARD_PORT" 2>/dev/null || true)
  if [[ -n "$local_pids" ]]; then
    step "Stopping existing process on :$DASHBOARD_PORT..."
    echo "$local_pids" | xargs kill 2>/dev/null || true
    sleep 1
  fi

  # Source .env so the dashboard process inherits API keys
  ENV_FILE="$INSTALL_DIR/.env"
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
  fi

  mkdir -p "$INSTALL_DIR/logs"
  step "Starting dashboard on http://localhost:${DASHBOARD_PORT}..."
  nohup bash "$DASHBOARD_SCRIPT" \
    --background --port "$DASHBOARD_PORT" \
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
    # Check for ngrok tunnel URL
    TUNNEL_URL=""
    TUNNEL_ERROR=""
    PYTHON_FOR_TUNNEL="$VENV_DIR/bin/python"
    [[ -x "$PYTHON_FOR_TUNNEL" ]] || PYTHON_FOR_TUNNEL="python3"
    TUNNEL_JSON=""
    if [[ -n "$OSTWIN_API_KEY" ]]; then
      TUNNEL_JSON=$(curl -sf -H "X-API-Key: $OSTWIN_API_KEY" \
        "http://localhost:${DASHBOARD_PORT}/api/tunnel/status" 2>/dev/null || true)
    else
      TUNNEL_JSON=$(curl -sf \
        "http://localhost:${DASHBOARD_PORT}/api/tunnel/status" 2>/dev/null || true)
    fi
    if [[ -n "$TUNNEL_JSON" ]]; then
      TUNNEL_URL=$("$PYTHON_FOR_TUNNEL" -c "import sys,json; print(json.load(sys.stdin).get('url') or '')" <<< "$TUNNEL_JSON" 2>/dev/null || true)
      TUNNEL_ERROR=$("$PYTHON_FOR_TUNNEL" -c "import sys,json; print(json.load(sys.stdin).get('error') or '')" <<< "$TUNNEL_JSON" 2>/dev/null || true)
    fi
    if [[ -n "$TUNNEL_URL" ]]; then
      ok "Tunnel active: $TUNNEL_URL"
    elif [[ -n "$TUNNEL_ERROR" ]]; then
      warn "Tunnel failed: $TUNNEL_ERROR"
    elif [[ -z "${NGROK_AUTHTOKEN:-}" ]]; then
      info "Tunnel not configured — set NGROK_AUTHTOKEN in ~/.ostwin/.env to enable port forwarding"
    else
      warn "Tunnel not active — check dashboard logs at $INSTALL_DIR/logs/dashboard.log"
    fi
  else
    warn "Dashboard did not respond in 60s — check $INSTALL_DIR/logs/dashboard.log"
    info "Start manually: bash $DASHBOARD_SCRIPT"
  fi

  # ─── 9b. Publish skills to backend ───────────────────────────────────────
  header "9b. Publishing skills to backend"
  SYNC_SCRIPT="$INSTALL_DIR/.agents/sync-skills.sh"
  if [[ -x "$SYNC_SCRIPT" ]]; then
    OSTWIN_HOME="$INSTALL_DIR" DASHBOARD_PORT="$DASHBOARD_PORT" \
      bash "$SYNC_SCRIPT" --install-from "$INSTALL_DIR/.agents"
  else
    warn "sync-skills.sh not found — skipping skill sync"
    info "Expected at $SYNC_SCRIPT"
  fi
else
  warn "Dashboard not found — skipping auto-start"
  info "Re-run: ./install.sh --source-dir /path/to/agent-os"
fi

# ─── 9c. Install channel dependencies ────────────────────────────────────

header "9c. Installing channel dependencies (Telegram + Discord + Slack)"

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
elif ! check_node; then
  warn "Node.js not found — cannot install channel connectors"
  info "Install Node.js and re-run"
elif ! command -v pnpm &>/dev/null; then
  warn "pnpm not found — cannot install channel connectors"
  info "Install pnpm and re-run"
else
  step "Installing channel dependencies in $CHAN_DIR with pnpm..."
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
fi

# ─── 9d. Start channel connectors (optional, --channel flag) ─────────────────

if $START_CHANNEL && [[ -n "${CHAN_DIR:-}" ]]; then
  header "9d. Starting channel connectors"

  ENV_FILE="$INSTALL_DIR/.env"
  PROJECT_ROOT_ENV="$(cd "$CHAN_DIR/.." && pwd)/.env"
  [[ -f "$ENV_FILE" ]] && { set -a; source "$ENV_FILE"; set +a; }
  [[ -f "$PROJECT_ROOT_ENV" ]] && { set -a; source "$PROJECT_ROOT_ENV"; set +a; }

  CHAN_PID_FILE="$INSTALL_DIR/.agents/channel.pid"
  if [[ -f "$CHAN_PID_FILE" ]]; then
    OLD_PID=$(cat "$CHAN_PID_FILE" 2>/dev/null || true)
    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
      step "Stopping previous channel process (PID $OLD_PID)..."
      kill "$OLD_PID" 2>/dev/null || true; sleep 1
    fi
  fi

  if [[ -n "${DISCORD_TOKEN:-}" ]] && [[ -n "${DISCORD_CLIENT_ID:-}" ]]; then
    step "Registering Discord slash commands..."
    (cd "$CHAN_DIR" && npx tsx src/deploy-commands.ts 2>/dev/null) \
      && ok "Discord commands registered" || warn "Discord command registration failed (non-critical)"
  fi

  mkdir -p "$INSTALL_DIR/logs"
  step "Starting channels from $CHAN_DIR..."
  (
    cd "$CHAN_DIR"
    [[ -f "$PROJECT_ROOT_ENV" ]] && { set -a; source "$PROJECT_ROOT_ENV"; set +a; }
    nohup npm start > "$INSTALL_DIR/logs/channel.log" 2>&1 &
    echo $! > "$CHAN_PID_FILE"
    echo "$!"
  ) | { read -r CHAN_PID; ok "Channels started (PID $CHAN_PID) — log: $INSTALL_DIR/logs/channel.log"; }

  [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]] && ok "Telegram: enabled" || info "Telegram: disabled (set TELEGRAM_BOT_TOKEN)"
  [[ -n "${DISCORD_TOKEN:-}" ]] && ok "Discord: enabled" || info "Discord: disabled (set DISCORD_TOKEN)"
  [[ -n "${SLACK_BOT_TOKEN:-}" ]] && ok "Slack: enabled" || info "Slack: disabled (set SLACK_BOT_TOKEN)"
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
if [[ -n "${TUNNEL_URL:-}" ]]; then
  echo -e "    ${DIM}Local:  http://localhost:${DASHBOARD_PORT}${NC}"
  echo -e "    ${DIM}Public: ${TUNNEL_URL}${NC}"
else
  echo -e "    ${DIM}Dashboard running at http://localhost:${DASHBOARD_PORT}${NC}"
fi
echo -e "    ${DIM}Stop with: ostwin stop${NC}"
if $START_CHANNEL; then
echo -e ""
echo -e "  ${BOLD}Channels (Telegram + Discord + Slack):${NC}"
echo -e "    ${DIM}Running in background — log: $INSTALL_DIR/logs/channel.log${NC}"
echo -e "    ${DIM}Stop with: ostwin channel stop${NC}"
fi
echo ""

# Display OSTWIN_API_KEY for frontend authentication
OSTWIN_API_KEY="${OSTWIN_API_KEY:-}"
if [[ -z "$OSTWIN_API_KEY" ]]; then
  # Try reading from .env
  OSTWIN_API_KEY=$(grep -E '^OSTWIN_API_KEY=' "${INSTALL_DIR}/.env" 2>/dev/null | cut -d'=' -f2-)
fi
if [[ -n "$OSTWIN_API_KEY" ]]; then
  echo -e "  ${BOLD}🔑 Dashboard Authentication Key:${NC}"
  echo ""
  echo -e "    ${YELLOW}${BOLD}${OSTWIN_API_KEY}${NC}"
  echo ""
  echo -e "    ${DIM}Use this key to authenticate with the dashboard frontend.${NC}"
  echo -e "    ${DIM}The frontend will prompt you to enter this key on first visit.${NC}"
  echo -e "    ${DIM}Stored in: ${INSTALL_DIR}/.env${NC}"
  echo ""
fi

echo -e "  ${BOLD}AI Provider Keys:${NC}"
echo -e "    ${DIM}Edit your .env file (keys auto-migrated if already in shell):${NC}"
echo -e "    nano ${INSTALL_DIR}/.env"
echo -e "    ${DIM}Then restart dashboard: ostwin stop && ostwin start${NC}"
echo -e "    ${DIM}# Or export directly (not persisted): export GOOGLE_API_KEY=\"your-key\"${NC}"
echo -e "    ${DIM}# Or use OpenAI/Anthropic — see: ostwin config${NC}"
echo ""
