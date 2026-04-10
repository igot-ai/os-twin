#!/bin/bash
# DEPRECATED: This Bash shim is superseded by Config.psm1 / Utils.psm1.
# It remains for backward compatibility but receives no new features.
# Use Get-OstwinConfig or Read-OstwinConfig from PowerShell instead.
#
# `.agents/lib/read-config.sh`
# Bash shim for reading values from .agents/config.json with vault reference support.
# Usage: source this file, then call read_config() or read_secret()

set -euo pipefail

# Find the agents directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${AGENT_OS_CONFIG:-$AGENTS_DIR/config.json}"

# Source vault resolution if available
VAULT_RESOLVER="$AGENTS_DIR/lib/resolve-vault.sh"
if [[ -f "$VAULT_RESOLVER" ]]; then
    source "$VAULT_RESOLVER"
fi

# Read a value from config.json with optional default
# Usage: read_config <jq-path> [default-value]
# Example: read_config '.runtime.poll_interval_seconds' 5
read_config() {
    local jq_path="$1"
    local default_value="${2:-}"
    
    # Check if config file exists
    if [[ ! -f "$CONFIG_FILE" ]]; then
        if [[ -n "$default_value" ]]; then
            echo "$default_value"
            return 0
        else
            echo "Error: Config file not found at $CONFIG_FILE" >&2
            return 1
        fi
    fi
    
    # Try to read the value using jq
    local value
    value=$(jq -r "$jq_path" "$CONFIG_FILE" 2>/dev/null) || {
        if [[ -n "$default_value" ]]; then
            echo "$default_value"
            return 0
        else
            echo "Error: Failed to read $jq_path from config" >&2
            return 1
        fi
    }
    
    # Check if value is null or empty
    if [[ "$value" == "null" || -z "$value" ]]; then
        if [[ -n "$default_value" ]]; then
            echo "$default_value"
            return 0
        else
            return 0  # Return empty string
        fi
    fi
    
    echo "$value"
}

# Read a secret value, dereferencing vault references if present
# Usage: read_secret <jq-path> [default-value]
# Example: read_secret '.providers.claude.api_key' 'default-key'
read_secret() {
    local jq_path="$1"
    local default_value="${2:-}"
    
    # First read the config value
    local value
    value=$(read_config "$jq_path" "$default_value") || return $?
    
    # Check if it's a vault reference
    if [[ "$value" =~ ^\$\{vault:([^}]+)\}$ ]]; then
        local vault_ref="${BASH_REMATCH[1]}"
        
        # Check if vault_resolve function is available
        if declare -f vault_resolve &>/dev/null; then
            vault_resolve "$vault_ref"
        else
            echo "Error: Vault reference found but resolve-vault.sh not loaded" >&2
            return 1
        fi
    else
        # Not a vault reference, return as-is
        echo "$value"
    fi
}

# Check if a config key exists (returns 0 if exists, 1 if not)
# Usage: config_has <jq-path>
config_has() {
    local jq_path="$1"
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        return 1
    fi
    
    local value
    value=$(jq -r "$jq_path" "$CONFIG_FILE" 2>/dev/null) || return 1
    
    [[ "$value" != "null" ]]
}
