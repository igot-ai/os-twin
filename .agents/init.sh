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

# Copy only the plan template (not any actual plans)
[[ -f "$SOURCE_AGENTS/plans/PLAN.template.md" ]] && cp "$SOURCE_AGENTS/plans/PLAN.template.md" "$TARGET_AGENTS/plans/PLAN.template.md"

# Copy dashboard from sibling directory (source repo layout: dashboard/ is sibling to .agents/)
if [[ -d "$SOURCE_AGENTS/../dashboard" ]] && [[ ! -d "$TARGET_AGENTS/dashboard" ]]; then
  echo "  → Copying dashboard from source repo..."
  cp -r "$SOURCE_AGENTS/../dashboard" "$TARGET_AGENTS/dashboard"
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
