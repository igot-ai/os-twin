import unittest
import json
import os
import subprocess

class TestSubcommandManifest(unittest.TestCase):
    def setUp(self):
        self.schema_path = "/Users/paulaan/PycharmProjects/agent-os/.agents/schemas/subcommands-schema.json"
        self.validate_script = "/Users/paulaan/PycharmProjects/agent-os/.agents/bin/validate-subcommands.sh"
        self.reporter_manifest = "/Users/paulaan/PycharmProjects/agent-os/.agents/roles/reporter/subcommands.json"
        self.manager_manifest = "/Users/paulaan/PycharmProjects/agent-os/.agents/roles/manager/subcommands.json"
        self.template_manifest = "/Users/paulaan/PycharmProjects/agent-os/.agents/roles/_base/subcommands.json.template"

    def test_schema_exists(self):
        self.assertTrue(os.path.exists(self.schema_path))

    def test_validate_script_exists(self):
        self.assertTrue(os.path.exists(self.validate_script))

    def test_validate_reporter(self):
        result = subprocess.run(["bash", self.validate_script, self.reporter_manifest], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"Reporter manifest validation failed: {result.stderr}")

    def test_validate_manager(self):
        result = subprocess.run(["bash", self.validate_script, self.manager_manifest], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"Manager manifest validation failed: {result.stderr}")

    def test_validate_template(self):
        # We need to replace placeholder for it to be valid if role name has constraints, 
        # but currently schema says role is just a string.
        # Actually, schema doesn't have a regex for role.
        result = subprocess.run(["bash", self.validate_script, self.template_manifest], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"Template manifest validation failed: {result.stderr}")

    def test_invalid_manifest(self):
        invalid_manifest = "/tmp/invalid_subcommands.json"
        with open(invalid_manifest, "w") as f:
            json.dump({"role": "test", "language": "invalid_lang", "subcommands": []}, f)
        
        result = subprocess.run(["bash", self.validate_script, invalid_manifest], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is not one of ['python', 'powershell', 'bash', 'node']", result.stderr)
        os.remove(invalid_manifest)

if __name__ == "__main__":
    unittest.main()
