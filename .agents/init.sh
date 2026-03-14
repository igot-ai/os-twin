#!/usr/bin/env bash
# Agent OS — Project Scaffolding
#
# Initializes Agent OS in a target directory by copying the core structure.
#
# Usage: init.sh [target-directory]
#
# If no directory is specified, initializes in the current directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_AGENTS="$SCRIPT_DIR"

TARGET_DIR="${1:-.}"
TARGET_AGENTS="$TARGET_DIR/.agents"

if [[ -d "$TARGET_AGENTS" ]]; then
  echo "[WARN] .agents/ already exists in $TARGET_DIR"
  echo "  Use ostwin config to modify settings."
  exit 1
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║        Ostwin — Project Init          ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  Target: $TARGET_DIR"
echo ""

# Create directory structure
mkdir -p "$TARGET_AGENTS"/{channel,roles/{manager,engineer,qa},war-rooms,release,plans,tests,lib,bin,logs,mcp}
mkdir -p "$TARGET_AGENTS/roles/manager"
mkdir -p "$TARGET_AGENTS/roles/engineer"
mkdir -p "$TARGET_AGENTS/roles/qa"

# Copy core scripts (bash + install)
for script in run.sh stop.sh logs.sh config.sh dashboard.sh health.sh init.sh plan.sh install.sh uninstall.sh; do
  [[ -f "$SOURCE_AGENTS/$script" ]] && cp "$SOURCE_AGENTS/$script" "$TARGET_AGENTS/$script"
done

# Copy channel tools (bash + PowerShell)
for script in post.sh read.sh wait-for.sh Post-Message.ps1 Read-Messages.ps1 Wait-ForMessage.ps1; do
  [[ -f "$SOURCE_AGENTS/channel/$script" ]] && cp "$SOURCE_AGENTS/channel/$script" "$TARGET_AGENTS/channel/$script"
done

# Copy plan tools (bash + PowerShell)
mkdir -p "$TARGET_AGENTS/plan"
for script in New-Plan.ps1 Start-Plan.ps1 New-Plan.Tests.ps1 Start-Plan.Tests.ps1; do
  [[ -f "$SOURCE_AGENTS/plan/$script" ]] && cp "$SOURCE_AGENTS/plan/$script" "$TARGET_AGENTS/plan/$script"
done

# Copy role definitions and runners (bash + PowerShell)
mkdir -p "$TARGET_AGENTS/roles/_base"
for role in manager engineer qa architect; do
  mkdir -p "$TARGET_AGENTS/roles/$role"
  for file in ROLE.md run.sh loop.sh deepagents-cli.md role.json Start-*.ps1; do
    for src in "$SOURCE_AGENTS/roles/$role/"$file; do
      [[ -f "$src" ]] && cp "$src" "$TARGET_AGENTS/roles/$role/$(basename "$src")"
    done
  done
done
# Copy _base role engine
for file in "$SOURCE_AGENTS/roles/_base/"*.ps1; do
  [[ -f "$file" ]] && cp "$file" "$TARGET_AGENTS/roles/_base/$(basename "$file")"
done
# Copy role registry
[[ -f "$SOURCE_AGENTS/roles/registry.json" ]] && cp "$SOURCE_AGENTS/roles/registry.json" "$TARGET_AGENTS/roles/registry.json"

# Copy release tools
for script in draft.sh signoff.sh; do
  [[ -f "$SOURCE_AGENTS/release/$script" ]] && cp "$SOURCE_AGENTS/release/$script" "$TARGET_AGENTS/release/$script"
done
[[ -f "$SOURCE_AGENTS/release/RELEASE.template.md" ]] && cp "$SOURCE_AGENTS/release/RELEASE.template.md" "$TARGET_AGENTS/release/RELEASE.template.md"

# Copy libraries (bash + PowerShell modules)
for lib in utils.sh log.sh; do
  [[ -f "$SOURCE_AGENTS/lib/$lib" ]] && cp "$SOURCE_AGENTS/lib/$lib" "$TARGET_AGENTS/lib/$lib"
done
for lib in "$SOURCE_AGENTS/lib/"*.psm1; do
  [[ -f "$lib" ]] && cp "$lib" "$TARGET_AGENTS/lib/$(basename "$lib")"
done

# Copy CLI entry point
[[ -f "$SOURCE_AGENTS/bin/ostwin" ]] && cp "$SOURCE_AGENTS/bin/ostwin" "$TARGET_AGENTS/bin/ostwin"

# Copy config
cp "$SOURCE_AGENTS/config.json" "$TARGET_AGENTS/config.json"

# Copy plan template
[[ -f "$SOURCE_AGENTS/plans/PLAN.template.md" ]] && cp "$SOURCE_AGENTS/plans/PLAN.template.md" "$TARGET_AGENTS/plans/PLAN.template.md"

# Copy war-room lifecycle scripts (bash + PowerShell)
for script in create.sh status.sh teardown.sh New-WarRoom.ps1 Get-WarRoomStatus.ps1 Remove-WarRoom.ps1; do
  [[ -f "$SOURCE_AGENTS/war-rooms/$script" ]] && cp "$SOURCE_AGENTS/war-rooms/$script" "$TARGET_AGENTS/war-rooms/$script"
done

# Copy tests
for test_file in "$SOURCE_AGENTS"/tests/*.sh; do
  [[ -f "$test_file" ]] && cp "$test_file" "$TARGET_AGENTS/tests/$(basename "$test_file")"
done

# Copy MCP servers
for mcp_file in "$SOURCE_AGENTS"/mcp/*.py; do
  [[ -f "$mcp_file" ]] && cp "$mcp_file" "$TARGET_AGENTS/mcp/$(basename "$mcp_file")"
done
[[ -f "$SOURCE_AGENTS/mcp/requirements.txt" ]] && cp "$SOURCE_AGENTS/mcp/requirements.txt" "$TARGET_AGENTS/mcp/requirements.txt"

# Copy dashboard (web UI + API)
if [[ -d "$SOURCE_AGENTS/../dashboard" ]]; then
  # Source repo layout: dashboard/ is sibling to .agents/
  echo "  → Copying dashboard from source repo..."
  cp -r "$SOURCE_AGENTS/../dashboard" "$TARGET_AGENTS/dashboard"
elif [[ -d "$SOURCE_AGENTS/dashboard" ]]; then
  # Installed layout: dashboard/ is inside .agents/
  echo "  → Copying dashboard from installed location..."
  cp -r "$SOURCE_AGENTS/dashboard" "$TARGET_AGENTS/dashboard"
fi

# Make all scripts executable
find "$TARGET_AGENTS" -name "*.sh" -exec chmod +x {} \;
chmod +x "$TARGET_AGENTS/bin/ostwin" 2>/dev/null || true

# Add .war-rooms to .gitignore (project-scoped runtime data)
if [[ -f "$TARGET_DIR/.gitignore" ]]; then
  if ! grep -q "^\.war-rooms" "$TARGET_DIR/.gitignore" 2>/dev/null; then
    echo ".war-rooms/" >> "$TARGET_DIR/.gitignore"
  fi
else
  echo ".war-rooms/" > "$TARGET_DIR/.gitignore"
fi

echo "  [OK] Ostwin initialized in $TARGET_DIR/.agents/"
echo ""
echo "  War-rooms will be created at: $TARGET_DIR/.war-rooms/ (project-scoped)"
echo ""
echo "  Next steps:"
echo "    1. Edit your plan:  cp .agents/plans/PLAN.template.md .agents/plans/my-plan.md"
echo "    2. Configure:       .agents/bin/ostwin config"
echo "    3. Run:             .agents/bin/ostwin run .agents/plans/my-plan.md"
echo ""
echo "  Or add to PATH:       export PATH=\"$TARGET_AGENTS/bin:\$PATH\""
echo ""
