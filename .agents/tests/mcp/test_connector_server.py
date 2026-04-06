import json
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys
import importlib.util

# Add the directory containing connector-server.py to sys.path
test_dir = os.path.dirname(os.path.abspath(__file__))
mcp_dir = os.path.abspath(os.path.join(test_dir, "../../mcp"))
sys.path.append(mcp_dir)

# Import the module with hyphen in name
module_name = "connector_server"
spec = importlib.util.spec_from_file_location(module_name, os.path.join(mcp_dir, "connector-server.py"))
connector_server = importlib.util.module_from_spec(spec)
sys.modules[module_name] = connector_server
spec.loader.exec_module(connector_server)

# Import tools from the loaded module
list_connectors = connector_server.list_connectors
configure_connector = connector_server.configure_connector
get_setup_instructions = connector_server.get_setup_instructions
get_connector_status = connector_server.get_connector_status
PLATFORMS = connector_server.PLATFORMS

class TestConnectorServer(unittest.TestCase):
    def setUp(self):
        self.test_config = [
            {
                "platform": "telegram",
                "enabled": True,
                "credentials": {"token": "test-token"},
                "settings": {}
            }
        ]

    @patch("connector_server.read_channels_config")
    @patch("connector_server.get_connector_status_raw")
    def test_list_connectors(self, mock_status, mock_read):
        mock_read.return_value = self.test_config
        mock_status.return_value = "connected"
        
        result_json = list_connectors()
        result = json.loads(result_json)
        
        self.assertEqual(len(result), 3) # telegram, discord, slack
        telegram = next(p for p in result if p["platform"] == "telegram")
        self.assertEqual(telegram["status"], "connected")
        self.assertEqual(telegram["config"]["credentials"]["token"], "test-token")

    @patch("connector_server.read_channels_config")
    @patch("connector_server.save_channels_config")
    def test_configure_connector_new(self, mock_save, mock_read):
        mock_read.return_value = []
        
        result = configure_connector(
            platform="discord",
            enabled=True,
            credentials={"token": "disc-token"},
            settings={"guild_id": "123"}
        )
        
        self.assertEqual(result, "updated:discord")
        mock_save.assert_called_once()
        saved_configs = mock_save.call_args[0][0]
        discord_config = next(c for c in saved_configs if c["platform"] == "discord")
        self.assertTrue(discord_config["enabled"])
        self.assertEqual(discord_config["credentials"]["token"], "disc-token")
        self.assertEqual(discord_config["settings"]["guild_id"], "123")

    @patch("connector_server.read_channels_config")
    @patch("connector_server.save_channels_config")
    def test_configure_connector_update(self, mock_save, mock_read):
        mock_read.return_value = [
            {"platform": "telegram", "enabled": False, "credentials": {}, "settings": {}}
        ]
        
        result = configure_connector(
            platform="telegram",
            enabled=True,
            credentials={"token": "new-token"}
        )
        
        self.assertEqual(result, "updated:telegram")
        saved_configs = mock_save.call_args[0][0]
        telegram_config = next(c for c in saved_configs if c["platform"] == "telegram")
        self.assertTrue(telegram_config["enabled"])
        self.assertEqual(telegram_config["credentials"]["token"], "new-token")

    def test_get_setup_instructions(self):
        result_json = get_setup_instructions("slack")
        result = json.loads(result_json)
        
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0]["title"], "Create Slack App")

    @patch("connector_server.read_channels_config")
    @patch("connector_server.get_connector_status_raw")
    def test_get_connector_status(self, mock_status, mock_read):
        mock_read.return_value = self.test_config
        mock_status.return_value = "connected"
        
        result_json = get_connector_status("telegram")
        result = json.loads(result_json)
        
        self.assertEqual(result["platform"], "telegram")
        self.assertEqual(result["status"], "connected")

    def test_invalid_platform(self):
        result = configure_connector(platform="invalid")
        self.assertTrue(result.startswith("error:"))

    @patch("connector_server.AGENT_OS_ROOT", "/tmp")
    def test_get_connector_status_raw(self):
        from connector_server import get_connector_status_raw
        
        # Test needs_setup
        self.assertEqual(get_connector_status_raw("telegram", {"enabled": False, "credentials": {}}), "needs_setup")
        
        # Test disconnected (enabled but no pid)
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False
            self.assertEqual(get_connector_status_raw("telegram", {"enabled": True, "credentials": {"token": "x"}}), "disconnected")
        
        # Test connected (enabled and pid exists)
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("pathlib.Path.read_text") as mock_read:
                mock_read.return_value = "12345"
                with patch("os.kill") as mock_kill:
                    mock_kill.return_value = None
                    self.assertEqual(get_connector_status_raw("telegram", {"enabled": True, "credentials": {"token": "x"}}), "connected")

if __name__ == "__main__":
    unittest.main()
