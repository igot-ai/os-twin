#!/usr/bin/env bash
# test-subcommands.sh — Smoke-test suite for macos-automation-engineer subcommands
#
# Usage:
#   bash test-subcommands.sh              # read-only, safe tests
#   bash test-subcommands.sh --tcc        # include TCC-gated tests (Accessibility + Screen Recording)
#   bash test-subcommands.sh --destructive# include state-changing tests (volume, dark-mode, etc.)
#   bash test-subcommands.sh --all        # run everything
#   bash test-subcommands.sh --verbose    # show full command output on failure
#
# Test tiers:
#   SAFE        — pure reads, no TCC, no state changes — always run
#   TCC         — requires Accessibility or Screen Recording permission
#   DESTRUCTIVE — changes system state but restores it (volume, dark-mode, clipboard)
#
# Exit codes:  0 = all ran tests passed  |  1 = one or more failures

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Walk up from SCRIPT_DIR to find <project>/.agents/bin/ostwin
_find_ostwin() {
  local d="$SCRIPT_DIR"
  while [[ "$d" != "/" ]]; do
    if [[ -x "$d/bin/ostwin" ]]; then       # inside .agents/
      echo "$d/bin/ostwin"; return
    fi
    if [[ -x "$d/.agents/bin/ostwin" ]]; then  # project root
      echo "$d/.agents/bin/ostwin"; return
    fi
    d="$(dirname "$d")"
  done
  # Fallback: rely on PATH
  if command -v ostwin &>/dev/null; then
    command -v ostwin; return
  fi
  echo "ostwin"  # last resort
}
OSTWIN="$(_find_ostwin)"

# ── Flags ────────────────────────────────────────────────────────────────────
RUN_TCC=false
RUN_DESTRUCTIVE=false
VERBOSE=false
for arg in "$@"; do
  case "$arg" in
    --tcc)         RUN_TCC=true ;;
    --destructive) RUN_DESTRUCTIVE=true ;;
    --all)         RUN_TCC=true; RUN_DESTRUCTIVE=true ;;
    --verbose|-v)  VERBOSE=true ;;
  esac
done

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
PASS=0; FAIL=0; SKIP=0

_pass() { echo -e "  ${GREEN}✓${RESET} $1"; ((PASS++)) || true; }
_fail() { echo -e "  ${RED}✗${RESET} $1"; ((FAIL++)) || true; }
_skip() { echo -e "  ${YELLOW}⊘${RESET} $1 ${YELLOW}[skipped — needs $2]${RESET}"; ((SKIP++)) || true; }
_section() { echo -e "\n${BOLD}${CYAN}▶ $1${RESET}"; }

# Run a command and check it exits 0 and (optionally) its stdout matches a pattern.
# Usage: assert_cmd <label> <pattern|""> ostwin mac <args...>
assert_cmd() {
  local label="$1"; local pattern="$2"; shift 2
  local out rc
  out=$("$OSTWIN" "$@" 2>&1) && rc=0 || rc=$?
  if [[ $rc -ne 0 ]]; then
    _fail "$label (exit $rc)"
    $VERBOSE && echo "    Output: $out"
    return
  fi
  if [[ -n "$pattern" && ! "$out" =~ $pattern ]]; then
    _fail "$label (output did not match /$pattern/)"
    $VERBOSE && echo "    Output: $out"
    return
  fi
  _pass "$label"
}

# Assert that a command exits NON-zero (useful for bad-arg tests).
assert_fails() {
  local label="$1"; shift
  local out rc
  out=$("$OSTWIN" "$@" 2>&1) && rc=0 || rc=$?
  if [[ $rc -eq 0 ]]; then
    _fail "$label (expected failure but exited 0)"
    return
  fi
  _pass "$label"
}

echo -e "${BOLD}macOS Automation Engineer — Subcommand Test Suite${RESET}"
echo    "ostwin: $OSTWIN"
echo    "Flags : TCC=$RUN_TCC  DESTRUCTIVE=$RUN_DESTRUCTIVE"
echo    "────────────────────────────────────────────────────"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIER 0 — help text (always safe, no TCC)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_section "HELP — all scripts respond to 'help'"
assert_cmd "app help"      "launch"    mac app help
assert_cmd "window help"   "move"      mac window help
assert_cmd "click help"    "click"     mac click help
assert_cmd "type help"     "text"      mac type help
assert_cmd "capture help"  "full"      mac capture help
assert_cmd "system help"   "volume"    mac system help
assert_cmd "finder help"   "search"    mac finder help
assert_cmd "axbridge help" "ui-tree"   mac axbridge help
assert_cmd "devtools help" "xcode"     mac devtools help

_section "HELP — invalid subcommand exits non-zero"
assert_fails "app unknown-cmd"     mac app INVALID_CMD_XYZ
assert_fails "system unknown-cmd"  mac system INVALID_CMD_XYZ

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIER 1 — SAFE read-only (no TCC, no state changes)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_section "APP — read-only"
assert_cmd "app list"               "Finder"         mac app list
assert_cmd "app frontmost"          "."              mac app frontmost
assert_cmd "app is-running Finder"  "running"        mac app is-running Finder
# Verify exit 1 when app is not running
(bash "$OSTWIN" mac app is-running totally-fake-app-xyz-99 &>/dev/null) && \
  _fail "app is-running fake-app should exit 1" || _pass "app is-running fake-app exits 1"

_section "APP — input validation (should fail cleanly)"
assert_fails "app launch missing-arg" mac app launch
assert_fails "app launch injection attempt" mac app launch 'Evil"App'
assert_fails "app is-running missing-arg" mac app is-running

_section "SYSTEM — read-only"
assert_cmd "system volume-get"    "[0-9]"   mac system volume-get
assert_cmd "system dark-mode-get" "true|false" mac system dark-mode-get
assert_cmd "system wifi-status"   "Wi-Fi|AirPort" mac system wifi-status
assert_cmd "system clipboard-get" ""        mac system clipboard-get

_section "SYSTEM — default-read (built-in domain)"
assert_cmd "system default-read NSGlobalDomain AppleLanguages" "\(" \
           mac system default-read NSGlobalDomain AppleLanguages

_section "FINDER — read-only Spotlight"
assert_cmd "finder search-name subcommands.json $PWD" "subcommands" \
           mac finder search-name "subcommands.json" "$(pwd)"
assert_cmd "finder search 'kind:json' $PWD"  "" \
           mac finder search "kind:json" "$(pwd)/.agents"
assert_cmd "finder search-kind image ~/Pictures" "" \
           mac finder search-kind image "$HOME/Pictures"

_section "FINDER — xattr round-trip on /tmp test file"
XTEST="/tmp/ostwin-xattr-test-$$.txt"
echo "xattr test" > "$XTEST"
assert_cmd "finder xattr-list (empty file)" "" mac finder xattr-list "$XTEST"
assert_cmd "finder xattr-set"  "Set"  mac finder xattr-set "$XTEST" "user.ostwin.test" "hello"
assert_cmd "finder xattr-get"  "hello" mac finder xattr-get "$XTEST" "user.ostwin.test"
assert_cmd "finder xattr-rm"   "Removed" mac finder xattr-rm "$XTEST" "user.ostwin.test"
rm -f "$XTEST"

_section "FINDER — copy & restore"
SRC="/tmp/ostwin-copy-src-$$.txt"
DST="/tmp/ostwin-copy-dst-$$.txt"
echo "copy test" > "$SRC"
assert_cmd "finder copy" "Copied" mac finder copy "$SRC" "$DST"
[[ -f "$DST" ]] && _pass "finder copy dest file exists" || _fail "finder copy dest missing"
rm -f "$SRC" "$DST"

_section "DEVTOOLS — read-only"
assert_cmd "devtools keychain-list"  "keychain"  mac devtools keychain-list
if xcrun simctl list &>/dev/null 2>&1; then
  assert_cmd "devtools simctl-list" "Devices" mac devtools simctl-list
else
  _skip "devtools simctl-list" "Xcode simctl (not installed)"
fi
assert_cmd "devtools xcrun swift --version" "Swift" mac devtools xcrun swift --version
assert_cmd "devtools codesign-verify Safari.app" "" \
           mac devtools codesign-verify /Applications/Safari.app
assert_cmd "devtools brew-list" "." mac devtools brew-list 2>/dev/null || \
  _skip "devtools brew-list" "Homebrew"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIER 2 — TCC-gated (Accessibility + Screen Recording)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if $RUN_TCC; then
  _section "WINDOW — read-only (needs Accessibility)"
  assert_cmd "window get-bounds Finder" "[0-9]" mac window get-bounds Finder

  _section "AXBRIDGE — read-only (needs Accessibility)"
  assert_cmd "axbridge window-list Finder" "" mac axbridge window-list Finder
  assert_cmd "axbridge read-focused"       "" mac axbridge read-focused
  assert_cmd "axbridge ui-tree Finder 1"   "AX" mac axbridge ui-tree Finder 1

  _section "CAPTURE — screen capture (needs Screen Recording)"
  CAPFILE="/tmp/ostwin-capture-test-$$.png"
  assert_cmd "capture full" "Captured" mac capture full "$CAPFILE"
  [[ -f "$CAPFILE" && -s "$CAPFILE" ]] && _pass "capture full file exists and non-empty" \
    || _fail "capture full file missing or empty"
  rm -f "$CAPFILE"

  REGFILE="/tmp/ostwin-capture-region-$$.png"
  assert_cmd "capture region 0 0 200 200" "Captured" mac capture region 0 0 200 200 "$REGFILE"
  [[ -f "$REGFILE" && -s "$REGFILE" ]] && _pass "capture region file exists" \
    || _fail "capture region file missing"
  rm -f "$REGFILE"

  assert_cmd "capture clipboard" "clipboard" mac capture clipboard
else
  _skip "window get-bounds"    "--tcc"
  _skip "axbridge window-list" "--tcc"
  _skip "axbridge ui-tree"     "--tcc"
  _skip "capture full"         "--tcc"
  _skip "capture region"       "--tcc"
  _skip "capture clipboard"    "--tcc"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIER 3 — DESTRUCTIVE (restores original state)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if $RUN_DESTRUCTIVE; then
  _section "SYSTEM — volume (save → set → restore)"
  ORIG_VOL=$(bash "$OSTWIN" mac system volume-get 2>/dev/null | tr -d '[:space:]')
  assert_cmd "system volume 50" "Volume set" mac system volume 50
  CHECK_VOL=$(bash "$OSTWIN" mac system volume-get 2>/dev/null | tr -d '[:space:]')
  [[ "$CHECK_VOL" == "50" ]] && _pass "volume round-trip to 50" \
    || _fail "volume did not set to 50 (got $CHECK_VOL)"
  bash "$OSTWIN" mac system volume "$ORIG_VOL" &>/dev/null
  _pass "volume restored to $ORIG_VOL"

  _section "SYSTEM — dark-mode toggle (save → flip → restore)"
  ORIG_DM=$(bash "$OSTWIN" mac system dark-mode-get 2>/dev/null | tr -d '[:space:]')
  [[ "$ORIG_DM" == "true" ]] && FLIP="off" || FLIP="on"
  assert_cmd "system dark-mode $FLIP" "" mac system dark-mode "$FLIP"
  sleep 0.5
  assert_cmd "system dark-mode $([ "$FLIP" = "on" ] && echo off || echo on) (restore)" "" \
             mac system dark-mode "$([[ "$ORIG_DM" == "true" ]] && echo on || echo off)"

  _section "SYSTEM — clipboard round-trip"
  ORIG_CLIP=$(bash "$OSTWIN" mac system clipboard-get 2>/dev/null || echo "")
  assert_cmd "system clipboard-set"  "Clipboard set" mac system clipboard-set "ostwin-test-$$"
  CHECK_CLIP=$(bash "$OSTWIN" mac system clipboard-get 2>/dev/null | tr -d '[:space:]')
  [[ "$CHECK_CLIP" == "ostwin-test-$$" ]] && _pass "clipboard round-trip" \
    || _fail "clipboard mismatch (got '$CHECK_CLIP')"
  printf '%s' "$ORIG_CLIP" | pbcopy
  _pass "clipboard restored"

  _section "SYSTEM — notify (sends a macOS notification)"
  assert_cmd "system notify" "Notification sent" \
             mac system notify "ostwin test" "Subcommand smoke test completed"

  if $RUN_TCC; then
    _section "APP — launch + is-running + kill (TextEdit)"
    assert_cmd "app launch TextEdit"      "."       mac app launch TextEdit
    sleep 1.5
    assert_cmd "app is-running TextEdit"  "running" mac app is-running TextEdit
    assert_cmd "app kill TextEdit"        "Quit"    mac app kill TextEdit
    sleep 0.5
    (bash "$OSTWIN" mac app is-running TextEdit &>/dev/null) && \
      _fail "TextEdit still running after kill" || _pass "TextEdit killed cleanly"

    _section "WINDOW — set-bounds + get-bounds + restore (Finder)"
    ORIG_BOUNDS=$(bash "$OSTWIN" mac window get-bounds Finder 2>/dev/null || echo "")
    if [[ -n "$ORIG_BOUNDS" ]]; then
      assert_cmd "window move Finder 100 100"  "Moved"  mac window move Finder 100 100
      assert_cmd "window resize Finder 800 600" "Resized" mac window resize Finder 800 600
      sleep 0.3
      NEW_BOUNDS=$(bash "$OSTWIN" mac window get-bounds Finder 2>/dev/null || echo "")
      [[ "$NEW_BOUNDS" != "$ORIG_BOUNDS" ]] && _pass "window bounds changed" \
        || _fail "window bounds unchanged"
      # Restore: parse original bounds (left, top, right, bottom) → x y w h
      IFS=', ' read -r L T R B <<< "$ORIG_BOUNDS"
      bash "$OSTWIN" mac window set-bounds Finder "$L" "$T" "$((R-L))" "$((B-T))" &>/dev/null
      _pass "window bounds restored to ($ORIG_BOUNDS)"
    else
      _skip "window set-bounds (Finder has no open window)" "open Finder window"
    fi
  fi
else
  _skip "system volume round-trip"  "--destructive"
  _skip "system dark-mode toggle"   "--destructive"
  _skip "system clipboard round-trip" "--destructive"
  _skip "system notify"             "--destructive"
  _skip "app launch/kill TextEdit"  "--destructive --tcc"
  _skip "window set-bounds Finder"  "--destructive --tcc"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SUMMARY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL=$((PASS + FAIL + SKIP))
echo ""
echo "────────────────────────────────────────────────────"
echo -e "${BOLD}Results: ${GREEN}${PASS} passed${RESET}  ${RED}${FAIL} failed${RESET}  ${YELLOW}${SKIP} skipped${RESET}  (${TOTAL} total)"
echo ""
echo "To run more tiers:"
echo "  bash test-subcommands.sh --tcc          # screen capture + AX bridge"
echo "  bash test-subcommands.sh --destructive  # volume, dark-mode, clipboard, app lifecycle"
echo "  bash test-subcommands.sh --all          # everything"
echo ""

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
