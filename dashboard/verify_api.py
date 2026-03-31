
from fastapi.testclient import TestClient
from api import app
import notify
import json
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

client = TestClient(app)

class TestApiTelegram(unittest.TestCase):
    def setUp(self):
        self.config_path = Path("notify_config.json")
        if self.config_path.exists():
            self.config_path.unlink()

    def tearDown(self):
        if self.config_path.exists():
            self.config_path.unlink()

    def test_get_config_empty(self):
        response = client.get("/api/telegram/config")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bot_token"], "")

    def test_post_config(self):
        payload = {"bot_token": "token123", "chat_id": "chat456"}
        response = client.post("/api/telegram/config", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success"})
        
        # Verify it was saved
        response = client.get("/api/telegram/config")
        self.assertEqual(response.json()["bot_token"], "token123")

    @patch("notify.send_message")
    def test_test_connection_success(self, mock_send):
        # We need to use a mock that returns a coroutine for async functions if they are awaited
        # But here we are mocking at the notify module level which api.py imports
        async def mock_async_send(*args, **kwargs):
            return True
        mock_send.side_effect = mock_async_send
        
        response = client.post("/api/telegram/test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success"})

    @patch("notify.send_message")
    def test_test_connection_failure(self, mock_send):
        async def mock_async_send(*args, **kwargs):
            return False
        mock_send.side_effect = mock_async_send
        
        response = client.post("/api/telegram/test")
        self.assertEqual(response.status_code, 500)
        self.assertIn("detail", response.json())

if __name__ == "__main__":
    unittest.main()
