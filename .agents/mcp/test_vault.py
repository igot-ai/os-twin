import unittest
import os
import json
import shutil
from pathlib import Path
from vault import EncryptedFileVault, MacOSKeychainVault, get_vault
from config_resolver import ConfigResolver

class TestVault(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("/tmp/ostwin_test_mcp")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.vault_path = self.test_dir / ".vault.enc"
        if self.vault_path.exists():
            self.vault_path.unlink()
        self.file_vault = EncryptedFileVault(self.vault_path)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_file_vault_crud(self):
        v = self.file_vault
        v.set("server1", "key1", "val1")
        self.assertEqual(v.get("server1", "key1"), "val1")
        
        v.set("server1", "key2", "val2")
        self.assertEqual(sorted(v.list_keys("server1")), ["key1", "key2"])
        
        v.delete("server1", "key1")
        self.assertEqual(v.get("server1", "key1"), None)
        self.assertEqual(v.list_keys("server1"), ["key2"])

    def test_resolver(self):
        v = self.file_vault
        v.set("stitch", "X-Goog-Api-Key", "secret-key")
        
        resolver = ConfigResolver()
        resolver.vault = v  # Inject test vault
        
        config = {
            "mcp": {
                "stitch": {
                    "type": "remote",
                    "url": "https://stitch.googleapis.com/mcp",
                    "headers": {
                        "X-Goog-Api-Key": "${vault:stitch/X-Goog-Api-Key}"
                    }
                }
            }
        }

        resolved = resolver.resolve_config(config)
        self.assertEqual(resolved["mcp"]["stitch"]["headers"]["X-Goog-Api-Key"], "secret-key")
        
        # Test extraction
        refs = resolver.extract_vault_refs(config)
        self.assertEqual(refs, [("stitch", "X-Goog-Api-Key")])
        
        # Test unresolved
        config_missing = {
            "key": "${vault:missing/key}"
        }
        self.assertEqual(resolver.has_unresolved_refs(config_missing), ["missing/key"])

if __name__ == "__main__":
    unittest.main()
