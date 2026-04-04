#!/usr/bin/env bash
# devtools.sh — macOS developer workflow automation
# Usage: devtools.sh <cmd> [args]
# Requires: macOS bash 3.2+, Xcode CLI tools (for xcodebuild/xcrun)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/_lib.sh"

CMD="${1:-help}"
shift || true

usage() {
  cat <<EOF
Usage: devtools.sh <cmd> [args]

Commands:
  xcode-build <project_dir> [scheme]  Build an Xcode project
  xcode-test <project_dir> [scheme]   Run Xcode tests
  xcode-list <project_dir>            List schemes in a project
  xcrun <tool> [args...]              Run an Xcode toolchain tool
  simctl-list                         List available iOS simulators
  simctl-boot <device_id>             Boot a simulator
  simctl-shutdown <device_id>         Shutdown a simulator
  codesign-verify <path>              Verify code signature
  codesign-info <path>                Show signing identity info
  keychain-list                       List keychains
  keychain-find <service>             Find a keychain password by service name
  brew-list                           List installed Homebrew formulae
  brew-install <formula>              Install a Homebrew formula
  brew-outdated                       List outdated formulae
  open-xcode [project_dir]            Open Xcode or a project in Xcode
  help                                Show this help

Examples:
  devtools.sh xcode-build ~/MyApp MyApp
  devtools.sh xcrun swift --version
  devtools.sh simctl-list
  devtools.sh codesign-verify /Applications/Safari.app
  devtools.sh brew-install jq
  devtools.sh keychain-find "ostwin-mcp"
EOF
}

case "$CMD" in
  xcode-build)
    PROJECT_DIR="${1:?Usage: devtools.sh xcode-build <project_dir> [scheme]}"
    SCHEME="${2:-}"
    [ -d "$PROJECT_DIR" ] || { echo "Error: directory not found: $PROJECT_DIR" >&2; exit 1; }
    # Detect workspace vs project
    WS=$(find "$PROJECT_DIR" -maxdepth 1 -name "*.xcworkspace" -print -quit 2>/dev/null)
    PROJ=$(find "$PROJECT_DIR" -maxdepth 1 -name "*.xcodeproj" -print -quit 2>/dev/null)
    if [ -n "$WS" ]; then
      CMD_ARGS="-workspace $WS"
    elif [ -n "$PROJ" ]; then
      CMD_ARGS="-project $PROJ"
    else
      echo "Error: no .xcworkspace or .xcodeproj found in $PROJECT_DIR" >&2; exit 1
    fi
    if [ -n "$SCHEME" ]; then
      CMD_ARGS="$CMD_ARGS -scheme $SCHEME"
    fi
    # shellcheck disable=SC2086
    xcodebuild $CMD_ARGS build 2>&1
    ;;

  xcode-test)
    PROJECT_DIR="${1:?Usage: devtools.sh xcode-test <project_dir> [scheme]}"
    SCHEME="${2:-}"
    [ -d "$PROJECT_DIR" ] || { echo "Error: directory not found: $PROJECT_DIR" >&2; exit 1; }
    WS=$(find "$PROJECT_DIR" -maxdepth 1 -name "*.xcworkspace" -print -quit 2>/dev/null)
    PROJ=$(find "$PROJECT_DIR" -maxdepth 1 -name "*.xcodeproj" -print -quit 2>/dev/null)
    if [ -n "$WS" ]; then
      CMD_ARGS="-workspace $WS"
    elif [ -n "$PROJ" ]; then
      CMD_ARGS="-project $PROJ"
    else
      echo "Error: no .xcworkspace or .xcodeproj found in $PROJECT_DIR" >&2; exit 1
    fi
    if [ -n "$SCHEME" ]; then
      CMD_ARGS="$CMD_ARGS -scheme $SCHEME"
    fi
    # shellcheck disable=SC2086
    xcodebuild $CMD_ARGS test 2>&1
    ;;

  xcode-list)
    PROJECT_DIR="${1:?Usage: devtools.sh xcode-list <project_dir>}"
    [ -d "$PROJECT_DIR" ] || { echo "Error: directory not found: $PROJECT_DIR" >&2; exit 1; }
    WS=$(find "$PROJECT_DIR" -maxdepth 1 -name "*.xcworkspace" -print -quit 2>/dev/null)
    PROJ=$(find "$PROJECT_DIR" -maxdepth 1 -name "*.xcodeproj" -print -quit 2>/dev/null)
    if [ -n "$WS" ]; then
      xcodebuild -workspace "$WS" -list 2>&1
    elif [ -n "$PROJ" ]; then
      xcodebuild -project "$PROJ" -list 2>&1
    else
      echo "Error: no .xcworkspace or .xcodeproj found in $PROJECT_DIR" >&2; exit 1
    fi
    ;;

  xcrun)
    TOOL="${1:?Usage: devtools.sh xcrun <tool> [args...]}"
    shift
    xcrun "$TOOL" "$@"
    ;;

  simctl-list)
    xcrun simctl list devices 2>&1
    ;;

  simctl-boot)
    DEVICE_ID="${1:?Usage: devtools.sh simctl-boot <device_id>}"
    xcrun simctl boot "$DEVICE_ID" 2>&1 && echo "Booted: $DEVICE_ID" || echo "Error booting: $DEVICE_ID" >&2
    ;;

  simctl-shutdown)
    DEVICE_ID="${1:?Usage: devtools.sh simctl-shutdown <device_id>}"
    xcrun simctl shutdown "$DEVICE_ID" 2>&1 && echo "Shutdown: $DEVICE_ID" || echo "Error shutting down: $DEVICE_ID" >&2
    ;;

  codesign-verify)
    FILEPATH="${1:?Usage: devtools.sh codesign-verify <path>}"
    [ -e "$FILEPATH" ] || { echo "Error: path not found: $FILEPATH" >&2; exit 1; }
    codesign --verify --verbose=2 "$FILEPATH" 2>&1 && echo "Signature valid" || echo "Signature INVALID or unsigned" >&2
    ;;

  codesign-info)
    FILEPATH="${1:?Usage: devtools.sh codesign-info <path>}"
    [ -e "$FILEPATH" ] || { echo "Error: path not found: $FILEPATH" >&2; exit 1; }
    codesign -dvvv "$FILEPATH" 2>&1
    ;;

  keychain-list)
    security list-keychains 2>&1
    ;;

  keychain-find)
    SERVICE="${1:?Usage: devtools.sh keychain-find <service>}"
    # -w prints only the password; 2>&1 captures errors like "not found"
    security find-generic-password -s "$SERVICE" -w 2>&1 || echo "Not found: $SERVICE"
    ;;

  brew-list)
    if ! command -v brew >/dev/null 2>&1; then
      echo "Error: Homebrew is not installed" >&2; exit 1
    fi
    brew list --formulae 2>&1
    ;;

  brew-install)
    FORMULA="${1:?Usage: devtools.sh brew-install <formula>}"
    if ! command -v brew >/dev/null 2>&1; then
      echo "Error: Homebrew is not installed" >&2; exit 1
    fi
    brew install "$FORMULA" 2>&1
    ;;

  brew-outdated)
    if ! command -v brew >/dev/null 2>&1; then
      echo "Error: Homebrew is not installed" >&2; exit 1
    fi
    brew outdated 2>&1
    ;;

  open-xcode)
    PROJECT_DIR="${1:-}"
    if [ -n "$PROJECT_DIR" ]; then
      WS=$(find "$PROJECT_DIR" -maxdepth 1 -name "*.xcworkspace" -print -quit 2>/dev/null)
      PROJ=$(find "$PROJECT_DIR" -maxdepth 1 -name "*.xcodeproj" -print -quit 2>/dev/null)
      if [ -n "$WS" ]; then
        open "$WS"
      elif [ -n "$PROJ" ]; then
        open "$PROJ"
      else
        echo "Error: no .xcworkspace or .xcodeproj found in $PROJECT_DIR" >&2; exit 1
      fi
    else
      open -a "Xcode"
    fi
    echo "Opened Xcode"
    ;;

  help|--help|-h)
    usage
    ;;

  *)
    echo "Unknown command: $CMD" >&2
    usage >&2
    exit 1
    ;;
esac
