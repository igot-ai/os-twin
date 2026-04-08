#!/bin/bash
# .agents/lib/resolve-vault.sh
# Bash shim that resolves ${vault:scope/key} references.
#
# Usage:
#   source .agents/lib/resolve-vault.sh
#   vault_resolve "providers/claude"    # prints the secret to stdout

set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_PROJECT_ROOT="$(cd "$_SCRIPT_DIR/../.." && pwd)"

vault_resolve() {
    local ref="$1"
    local scope="${ref%/*}"
    local key="${ref#*/}"

    python3 -m dashboard.scripts.vault_get "$scope" "$key"
}

export -f vault_resolve 2>/dev/null || true
