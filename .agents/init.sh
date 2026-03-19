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

# Create plans dir (excluded from rsync below)
mkdir -p "$TARGET_AGENTS/plans"

# Copy entire .agents content, excluding the plans folder
rsync -a --exclude='plans/' "$SOURCE_AGENTS/" "$TARGET_AGENTS/"

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

# Copy CLI entry point and Python scripts
for bin_file in ostwin chat.py cli.py; do
  [[ -f "$SOURCE_AGENTS/bin/$bin_file" ]] && cp "$SOURCE_AGENTS/bin/$bin_file" "$TARGET_AGENTS/bin/$bin_file"
done

# Copy config
cp "$SOURCE_AGENTS/config.json" "$TARGET_AGENTS/config.json"

# Copy plan template
[[ -f "$SOURCE_AGENTS/plans/PLAN.template.md" ]] && cp "$SOURCE_AGENTS/plans/PLAN.template.md" "$TARGET_AGENTS/plans/PLAN.template.md"

# Copy dashboard from sibling directory (source repo layout: dashboard/ is sibling to .agents/)
if [[ -d "$SOURCE_AGENTS/../dashboard" ]] && [[ ! -d "$TARGET_AGENTS/dashboard" ]]; then
  echo "  → Copying dashboard from source repo..."
  mkdir -p "$TARGET_AGENTS/dashboard"
  cp -r "$SOURCE_AGENTS/../dashboard/" "$TARGET_AGENTS/dashboard/"
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
