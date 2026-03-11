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
  echo "  Use agent-os config to modify settings."
  exit 1
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║       Agent OS — Project Init        ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  Target: $TARGET_DIR"
echo ""

# Create directory structure
mkdir -p "$TARGET_AGENTS"/{channel,roles/{manager,engineer,qa},war-rooms,release,plans,tests,lib,bin,logs,mcp}
mkdir -p "$TARGET_AGENTS/roles/manager"
mkdir -p "$TARGET_AGENTS/roles/engineer"
mkdir -p "$TARGET_AGENTS/roles/qa"

# Copy core scripts
for script in run.sh stop.sh logs.sh config.sh demo.sh health.sh init.sh; do
  [[ -f "$SOURCE_AGENTS/$script" ]] && cp "$SOURCE_AGENTS/$script" "$TARGET_AGENTS/$script"
done

# Copy channel tools
for script in post.sh read.sh wait-for.sh; do
  [[ -f "$SOURCE_AGENTS/channel/$script" ]] && cp "$SOURCE_AGENTS/channel/$script" "$TARGET_AGENTS/channel/$script"
done

# Copy role definitions and runners
for role in manager engineer qa; do
  for file in ROLE.md run.sh loop.sh; do
    src="$SOURCE_AGENTS/roles/$role/$file"
    [[ -f "$src" ]] && cp "$src" "$TARGET_AGENTS/roles/$role/$file"
  done
done

# Copy release tools
for script in draft.sh signoff.sh; do
  [[ -f "$SOURCE_AGENTS/release/$script" ]] && cp "$SOURCE_AGENTS/release/$script" "$TARGET_AGENTS/release/$script"
done
[[ -f "$SOURCE_AGENTS/release/RELEASE.template.md" ]] && cp "$SOURCE_AGENTS/release/RELEASE.template.md" "$TARGET_AGENTS/release/RELEASE.template.md"

# Copy libraries
for lib in utils.sh log.sh; do
  [[ -f "$SOURCE_AGENTS/lib/$lib" ]] && cp "$SOURCE_AGENTS/lib/$lib" "$TARGET_AGENTS/lib/$lib"
done

# Copy CLI entry point
[[ -f "$SOURCE_AGENTS/bin/agent-os" ]] && cp "$SOURCE_AGENTS/bin/agent-os" "$TARGET_AGENTS/bin/agent-os"

# Copy config
cp "$SOURCE_AGENTS/config.json" "$TARGET_AGENTS/config.json"

# Copy plan template
[[ -f "$SOURCE_AGENTS/plans/PLAN.template.md" ]] && cp "$SOURCE_AGENTS/plans/PLAN.template.md" "$TARGET_AGENTS/plans/PLAN.template.md"

# Copy war-room lifecycle scripts
for script in create.sh status.sh teardown.sh; do
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

# Make all scripts executable
find "$TARGET_AGENTS" -name "*.sh" -exec chmod +x {} \;
chmod +x "$TARGET_AGENTS/bin/agent-os" 2>/dev/null || true

echo "  [OK] Agent OS initialized in $TARGET_DIR/.agents/"
echo ""
echo "  Next steps:"
echo "    1. Edit your plan:  cp .agents/plans/PLAN.template.md .agents/plans/my-plan.md"
echo "    2. Configure:       .agents/bin/agent-os config"
echo "    3. Run:             .agents/bin/agent-os run .agents/plans/my-plan.md"
echo ""
echo "  Or add to PATH:       export PATH=\"$TARGET_AGENTS/bin:\$PATH\""
echo ""
