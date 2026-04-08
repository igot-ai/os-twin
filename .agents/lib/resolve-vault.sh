#!/bin/bash
# `.agents/lib/resolve-vault.sh`
# Bash shim that expands `${vault:...}` references to environment variables
# before passing them to the agent process.
#
# Uses the vault module at .agents/mcp/vault.py (not dashboard.scripts which
# does not exist as a standalone importable package).

# Resolve the agents directory relative to this script
_VAULT_AGENTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

vault_resolve() {
    local ref="$1"
    local scope="${ref%/*}"
    local key="${ref#*/}"
    
    # Use the vault CLI at .agents/mcp/vault.py
    local value
    value=$(python3 "$_VAULT_AGENTS_DIR/mcp/vault.py" get "$scope" "$key" 2>/dev/null)
    echo "$value"
}
