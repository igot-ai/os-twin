#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# build-frontend.sh — Unified frontend build function
#
# Provides: build_frontend(dir, label)
#
# Replaces the old build_nextjs() and build_dashboard_fe() with a single
# parameterized function that can build any frontend project.
#
# Requires: lib.sh, globals: SOURCE_DIR, SCRIPT_DIR
# ──────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
[[ -n "${_BUILD_FRONTEND_SH_LOADED:-}" ]] && return 0
_BUILD_FRONTEND_SH_LOADED=1

# ─── build_frontend ─────────────────────────────────────────────────────────
# Usage: build_frontend <subdir> <label>
#   subdir — relative path under the source repo (e.g. "dashboard/nextjs")
#   label  — human-readable label for log messages (e.g. "Next.js dashboard")

build_frontend() {
  local subdir="$1"
  local label="${2:-$subdir}"

  # Locate the frontend directory relative to the source repo
  local fe_dir=""
  for candidate in \
    "${SOURCE_DIR}/${subdir}" \
    "${SCRIPT_DIR}/../${subdir}" \
    "${SCRIPT_DIR}/${subdir}"; do
    if [[ -d "$candidate" ]] && [[ -f "$candidate/package.json" ]]; then
      fe_dir="$(cd "$candidate" && pwd)"
      break
    fi
  done

  if [[ -z "$fe_dir" ]]; then
    warn "$label not found — skipping build"
    info "Expected at ${subdir}/package.json"
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
    warn "No package manager (bun/pnpm/npm/yarn) found — skipping $label build"
    info "Install Node.js and a package manager to enable $label"
    return
  fi

  step "Building $label ($pm) at $fe_dir..."
  # shellcheck disable=SC2015
  (
    cd "$fe_dir" || exit

    run_pm() {
      if [[ "$pm" == "pnpm" ]] && [[ -n "${OSTWIN_PNPM_CMD:-}" ]]; then
        eval "${OSTWIN_PNPM_CMD} $*"
      else
        "$pm" "$@"
      fi
    }

    # Install deps if node_modules missing
    if [[ ! -d node_modules ]]; then
      step "Installing npm dependencies..."
      run_pm install --frozen-lockfile 2>/dev/null || run_pm install
    fi
    run_pm run build
  ) && ok "$label build complete" || warn "$label build failed"
}
