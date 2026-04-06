import unittest
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the server module
import sys
import importlib.util
spec = importlib.util.spec_from_file_location("connector_server", os.path.join(os.getcwd(), ".agents/mcp/connector-server.py"))
connector_server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(connector_server)

class TestConnectorServer(unittest.TestCase):

    def setUp(self):
        self.test_config_path = Path("/tmp/test_channels.json")
        connector_server.CHANNELS_CONFIG_PATH = self.test_config_path
        if self.test_config_path.exists():
            self.test_config_path.unlink()

    def tearDown(self):
        if self.test_config_path.exists():
            self.test_config_path.unlink()

    def test_list_connectors_empty(self):
        result = json.loads(connector_server.list_connectors())
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["platform"], "telegram")
        self.assertEqual(result[0]["status"], "not_configured")

    def test_configure_connector(self):
        # Configure telegram
        resp = connector_server.configure_connector(
            "telegram", 
            enabled=True, 
            credentials={"token": "test_token"}
        )
        self.assertEqual(resp, "updated:telegram")
        
        # Verify in list
        result = json.loads(connector_server.list_connectors())
        tg = next(c for c in result if c["platform"] == "telegram")
        self.assertEqual(tg["config"]["enabled"], True)
        self.assertEqual(tg["config"]["credentials"]["token"], "test_token")

    def test_get_setup_instructions(self):
        resp = json.loads(connector_server.get_setup_instructions("telegram"))
        self.assertTrue(len(resp) > 0)
        self.assertEqual(resp[0]["title"], "Create a Bot")

    def test_get_connector_status(self):
        # Without config
        resp = json.loads(connector_server.get_connector_status("discord"))
        self.assertEqual(resp["status"], "not_configured")
        
        # With config but not enabled
        connector_server.configure_connector("discord", enabled=False, credentials={"token": "foo"})
        resp = json.loads(connector_server.get_connector_status("discord"))
        self.assertEqual(resp["status"], "disconnected")

    @patch("os.kill")
    def test_get_connector_status_connected(self, mock_kill):
        # Mock bot running
        mock_kill.return_value = None # PID exists
        
        # Seed the config
        connector_server.configure_connector("slack", enabled=True, credentials={"token": "xoxb-..."})
        
        # Re-mock exists for the actual call in get_connector_status_raw
        with patch.object(connector_server.Path, "exists") as m_exists:
            m_exists.return_value = True
            with patch.object(connector_server.Path, "read_text") as m_read:
                m_read.return_value = "12345"
                resp = json.loads(connector_server.get_connector_status("slack"))
                self.assertEqual(resp["status"], "connected")

if __name__ == "__main__":
    unittest.main()
