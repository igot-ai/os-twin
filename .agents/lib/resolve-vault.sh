#!/bin/bash
# `.agents/lib/resolve-vault.sh`
# Bash shim that expands `${vault:...}` references to environment variables before passing them to the agent process.

vault_resolve() {
    local ref="$1"
    local scope="${ref%/*}"
    local key="${ref#*/}"
    
    # Call the python one-liner CLI
    local value=$(python3 -m dashboard.scripts.vault_get "$scope" "$key")
    echo "$value"
}
