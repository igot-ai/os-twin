import asyncio
import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the current directory to sys.path to ensure notify can be imported
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import notify

class TestTelegramBot(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config_path = Path("notify_config.json")
        if self.config_path.exists():
            self.config_path.unlink()

    async def asyncTearDown(self):
        if self.config_path.exists():
            self.config_path.unlink()

    def test_save_and_get_config(self):
        notify.save_config("test_token", "test_chat_id")
        config = notify.get_config()
        self.assertEqual(config["bot_token"], "test_token")
        self.assertEqual(config["chat_id"], "test_chat_id")

    @patch("httpx.AsyncClient.post")
    async def test_send_message_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        notify.save_config("test_token", "test_chat_id")
        success = await notify.send_message("test message")
        
        self.assertTrue(success)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["text"], "test message")
        self.assertEqual(kwargs["json"]["chat_id"], "test_chat_id")
        self.assertIn("test_token", args[0])

    @patch("httpx.AsyncClient.post")
    async def test_send_message_failure(self, mock_post):
        mock_post.side_effect = Exception("API error")
        
        notify.save_config("test_token", "test_chat_id")
        success = await notify.send_message("test message")
        
        self.assertFalse(success)

    async def test_send_message_no_config(self):
        success = await notify.send_message("test message")
        self.assertFalse(success)

if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

