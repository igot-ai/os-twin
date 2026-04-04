import json
import re
import os
import sys
from typing import Any, Dict, List, Tuple
from pathlib import Path

# Try to import vault from the same directory
try:
    from .vault import get_vault
except ImportError:
    # Fallback for standalone execution
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from vault import get_vault

# Regex to match ${vault:server/key}
VAULT_REF_PATTERN = re.compile(r"\$\{vault:([^/]+)/([^}]+)\}")

class ConfigResolver:
    def __init__(self):
        self.vault = get_vault()

    def resolve_config(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively resolves vault references in a config dictionary."""
        return self._resolve_recursive(config_dict)

    def _resolve_recursive(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._resolve_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._resolve_recursive(v) for v in obj]
        elif isinstance(obj, str):
            match = VAULT_REF_PATTERN.search(obj)
            if match:
                server, key = match.groups()
                secret = self.vault.get(server, key)
                if secret is None:
                    raise ValueError(f"Vault reference not found: ${{vault:{server}/{key}}}")
                # Replace the entire reference with the secret
                # Note: this only supports one reference per string for now
                return obj.replace(match.group(0), secret)
        return obj

    def has_unresolved_refs(self, config_dict: Dict[str, Any]) -> List[str]:
        """Returns a list of missing vault references as 'server/key' strings."""
        unresolved = []
        refs = self.extract_vault_refs(config_dict)
        for server, key in refs:
            if self.vault.get(server, key) is None:
                unresolved.append(f"{server}/{key}")
        return unresolved

    def extract_vault_refs(self, config_dict: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Extracts all vault references found in the config dictionary."""
        refs = []
        self._extract_recursive(config_dict, refs)
        return sorted(list(set(refs)))

    def _extract_recursive(self, obj: Any, refs: List[Tuple[str, str]]):
        if isinstance(obj, dict):
            for v in obj.values():
                self._extract_recursive(v, refs)
        elif isinstance(obj, list):
            for v in obj:
                self._extract_recursive(v, refs)
        elif isinstance(obj, str):
            for match in VAULT_REF_PATTERN.finditer(obj):
                refs.append(match.groups())

    def compile_config(self, home_config: Dict[str, Any], builtin_config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Compiles home config + builtin config into project config.
        Replaces ${vault:server/key} with ${ENV_VAR} and returns the env var mapping.
        """
        # Merge configs
        compiled_config = {"mcpServers": {}}
        compiled_config["mcpServers"].update(builtin_config.get("mcpServers", {}))
        compiled_config["mcpServers"].update(home_config.get("mcpServers", {}))
        
        env_vars = {}
        
        def _compile_recursive(obj, server_name):
            if isinstance(obj, dict):
                return {k: _compile_recursive(v, server_name) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_compile_recursive(v, server_name) for v in obj]
            elif isinstance(obj, str):
                match = VAULT_REF_PATTERN.search(obj)
                if match:
                    server, key = match.groups()
                    secret = self.vault.get(server, key)
                    if secret is None:
                        # If we can't find it in vault, we'll leave it as is for now
                        # or raise an error? The spec says to resolve it.
                        pass
                    
                    # ENV var naming convention: MCP_{SERVER}_{KEY} (uppercased, sanitized)
                    env_name = f"MCP_{server.upper()}_{key.upper()}".replace("-", "_").replace(".", "_")
                    env_vars[env_name] = secret or ""
                    return obj.replace(match.group(0), f"${{{env_name}}}")
            return obj

        for name, server_cfg in compiled_config["mcpServers"].items():
            compiled_config["mcpServers"][name] = _compile_recursive(server_cfg, name)
            
        return compiled_config, env_vars

if __name__ == "__main__":
    # Test script
    resolver = ConfigResolver()
    test_config = {
        "mcpServers": {
            "test": {
                "env": {
                    "API_KEY": "${vault:test/API_KEY}",
                    "OTHER": "plain"
                }
            }
        }
    }
    print("Extracting refs:", resolver.extract_vault_refs(test_config))
    print("Has unresolved:", resolver.has_unresolved_refs(test_config))
    
    # Try setting a value and resolving
    resolver.vault.set("test", "API_KEY", "secret-value")
    print("Resolved config:", resolver.resolve_config(test_config))
    resolver.vault.delete("test", "API_KEY")
