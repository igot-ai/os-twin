#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# detect-os.sh — OS / platform detection
#
# Sets: OS, DISTRO, PKG_MGR, ARCH
#
# Usage:  source "$(dirname "$0")/installer/detect-os.sh"
#         detect_os
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_DETECT_OS_SH_LOADED:-}" ]] && return 0
_DETECT_OS_SH_LOADED=1

# shellcheck disable=SC2034  # OS, DISTRO, PKG_MGR, ARCH are consumed by callers
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
        # shellcheck disable=SC1091
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
