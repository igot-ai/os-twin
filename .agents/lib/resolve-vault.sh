#!/bin/bash
# DEPRECATED: This Bash shim is superseded by Config.psm1 / Utils.psm1.
# It remains for backward compatibility but receives no new features.
# Use Get-OstwinConfig or Read-OstwinConfig from PowerShell instead.
#
# .agents/lib/resolve-vault.sh
# Bash shim that resolves ${vault:scope/key} references.
#
# Uses the vault module at .agents/mcp/vault.py (not dashboard.scripts which
# does not exist as a standalone importable package).
#
# Usage:
#   source .agents/lib/resolve-vault.sh
#   vault_resolve "providers/claude"    # prints the secret to stdout

set -euo pipefail

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

export -f vault_resolve 2>/dev/null || true
