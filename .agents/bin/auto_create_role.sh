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

OSTWIN_HOME="${OSTWIN_HOME:-$HOME/.ostwin}"
AGENT_BIN="${OSTWIN_AGENT_CMD:-$OSTWIN_HOME/.agents/bin/agent}"

if [ ! -x "$AGENT_BIN" ]; then
  echo "Agent binary not found at: $AGENT_BIN"
  echo "Run the installer or set \$OSTWIN_AGENT_CMD."
  exit 1
fi

MCP_CONFIG="$AGENTS_DIR/mcp/config.json"

"$AGENT_BIN" -a manager -n "$MANAGER_PROMPT" --auto-approve --trust-project-mcp --shell-allow-list all --mcp-config "$MCP_CONFIG"
