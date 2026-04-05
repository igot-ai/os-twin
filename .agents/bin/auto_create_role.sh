#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${1:-}" ]] || [[ -z "${2:-}" ]]; then
  echo "Usage: $0 <role_name> <agents_dir>"
  exit 1
fi

ROLE_NAME="$1"
AGENTS_DIR="$2"

echo "Creating missing role: $ROLE_NAME..."

MANAGER_PROMPT="We need a new agent role called '$ROLE_NAME'. Please use the create-role skill to scaffold it. You MUST also create the specific SKILLs this role needs (as .md files in $AGENTS_DIR/skills/), and you MUST create a custom PowerShell start script (Start-*.ps1) in its role directory to orchestrate its specific workflow. Ensure the role is registered in registry.json pointing to this new runner script. Explain your reasoning."

if command -v deepagents >/dev/null 2>&1; then
  DA_CMD="deepagents"
elif [ -x "$HOME/.local/share/uv/tools/deepagents-cli/bin/deepagents" ]; then
  DA_CMD="$HOME/.local/share/uv/tools/deepagents-cli/bin/deepagents"
elif [ -x "$HOME/.local/bin/deepagents" ]; then
  DA_CMD="$HOME/.local/bin/deepagents"
else
  echo "deepagents CLI not found."
  exit 1
fi

MCP_CONFIG="$AGENTS_DIR/mcp/config.json"
if [[ ! -f "$MCP_CONFIG" && -f "$AGENTS_DIR/mcp/mcp-config.json" ]]; then
  MCP_CONFIG="$AGENTS_DIR/mcp/mcp-config.json"
fi

"$DA_CMD" -a manager -n "$MANAGER_PROMPT" --auto-approve --trust-project-mcp --shell-allow-list all --mcp-config "$MCP_CONFIG"
