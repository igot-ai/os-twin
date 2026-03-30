import json
import os
import unittest
import sys
from pathlib import Path

# Add mcp dir to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "mcp"))
from config_resolver import ConfigResolver

class MockVault:
    def get(self, server, key):
        if server == "test" and key == "API_KEY":
            return "secret-value"
        return None
    def list_keys(self, server):
        return []

class TestMCPCompile(unittest.TestCase):
    def test_compile_config(self):
        resolver = ConfigResolver()
        resolver.vault = MockVault()
        
        home_config = {
            "mcpServers": {
                "test": {
                    "env": {
                        "API_KEY": "${vault:test/API_KEY}"
                    }
                }
            }
        }
        builtin_config = {
            "mcpServers": {
                "builtin": {
                    "command": "python"
                }
            }
        }
        
        compiled, env_vars = resolver.compile_config(home_config, builtin_config)
        
        self.assertIn("test", compiled["mcpServers"])
        self.assertIn("builtin", compiled["mcpServers"])
        self.assertEqual(compiled["mcpServers"]["test"]["env"]["API_KEY"], "${MCP_TEST_API_KEY}")
        self.assertEqual(env_vars["MCP_TEST_API_KEY"], "secret-value")

if __name__ == "__main__":
    unittest.main()
