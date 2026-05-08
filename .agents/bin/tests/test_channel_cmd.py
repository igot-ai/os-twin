import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add the directory containing channel_cmd.py to sys.path
_BIN_DIR = Path(__file__).resolve().parent.parent
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))

# Import the module after path is set
import channel_cmd

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.Client") as mock_client:
        client_instance = MagicMock()
        mock_client.return_value.__enter__.return_value = client_instance
        yield client_instance

def test_list_channels(mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"platform": "telegram", "status": "connected", "config": {"authorized_users": ["u1", "u2"], "pairing_code": "code1"}},
        {"platform": "discord", "status": "not_configured", "config": None},
        {"platform": "slack", "status": "disconnected", "config": {"pairing_code": "code2"}}
    ]
    mock_httpx_client.get.return_value = mock_response
    
    args = MagicMock()
    channel_cmd.list_channels(args)
    
    mock_httpx_client.get.assert_called_with("/api/channels")


# Tests for credential check logic

def test_connect_channel_with_existing_credentials_user_accepts(mock_httpx_client):
    """Test that when credentials exist and user accepts, we use them without prompting."""
    # Mock channel status with existing credentials
    mock_status_resp = MagicMock()
    mock_status_resp.json.return_value = {
        "platform": "telegram",
        "status": "disconnected",
        "config": {
            "platform": "telegram",
            "enabled": False,
            "credentials": {"token": "existing-token-123"},
            "settings": {},
            "authorized_users": [],
            "pairing_code": "old-code"
        }
    }
    
    # Mock connect
    mock_connect_resp = MagicMock()
    mock_connect_resp.json.return_value = {"status": "ok"}
    
    # Mock pairing
    mock_pairing_resp = MagicMock()
    mock_pairing_resp.json.return_value = {"pairing_code": "new-code"}
    
    mock_httpx_client.get.side_effect = [mock_status_resp, mock_pairing_resp]
    mock_httpx_client.post.return_value = mock_connect_resp
    
    args = MagicMock()
    args.platform = "telegram"
    
    with patch("builtins.input", return_value="y"):
        channel_cmd.connect_channel(args)
    
    # Should NOT call setup endpoint, should connect without new credentials
    mock_httpx_client.post.assert_called_with("/api/channels/telegram/connect", json={})


def test_connect_channel_with_existing_credentials_user_declines(mock_httpx_client):
    """Test that when credentials exist and user declines, we show full setup wizard."""
    # Mock channel status with existing credentials
    mock_status_resp = MagicMock()
    mock_status_resp.json.return_value = {
        "platform": "telegram",
        "status": "disconnected",
        "config": {
            "platform": "telegram",
            "enabled": False,
            "credentials": {"token": "existing-token-123"},
            "settings": {},
            "authorized_users": [],
            "pairing_code": "old-code"
        }
    }
    
    # Mock setup steps
    mock_setup_resp = MagicMock()
    mock_setup_resp.json.return_value = [{"title": "Step 1", "description": "Desc", "instructions": "Inst"}]
    
    # Mock connect
    mock_connect_resp = MagicMock()
    mock_connect_resp.json.return_value = {"status": "ok"}
    
    # Mock pairing
    mock_pairing_resp = MagicMock()
    mock_pairing_resp.json.return_value = {"pairing_code": "new-code"}
    
    mock_httpx_client.get.side_effect = [mock_status_resp, mock_setup_resp, mock_pairing_resp]
    mock_httpx_client.post.return_value = mock_connect_resp
    
    args = MagicMock()
    args.platform = "telegram"
    
    with patch("builtins.input", return_value="n"):
        with patch("channel_cmd.getpass.getpass", return_value="new-token"):
            channel_cmd.connect_channel(args)
    
    # Should call setup endpoint and connect with new credentials
    mock_httpx_client.get.assert_any_call("/api/channels/telegram/setup")
    mock_httpx_client.post.assert_called_with("/api/channels/telegram/connect", json={"credentials": {"token": "new-token"}})


def test_connect_channel_no_existing_credentials(mock_httpx_client):
    """Test that when no credentials exist, we show full setup wizard."""
    # Mock channel status without credentials
    mock_status_resp = MagicMock()
    mock_status_resp.json.return_value = {
        "platform": "telegram",
        "status": "not_configured",
        "config": None
    }
    
    # Mock setup steps
    mock_setup_resp = MagicMock()
    mock_setup_resp.json.return_value = [{"title": "Step 1", "description": "Desc", "instructions": "Inst"}]
    
    # Mock connect
    mock_connect_resp = MagicMock()
    mock_connect_resp.json.return_value = {"status": "ok"}
    
    # Mock pairing
    mock_pairing_resp = MagicMock()
    mock_pairing_resp.json.return_value = {"pairing_code": "new-code"}
    
    mock_httpx_client.get.side_effect = [mock_status_resp, mock_setup_resp, mock_pairing_resp]
    mock_httpx_client.post.return_value = mock_connect_resp
    
    args = MagicMock()
    args.platform = "telegram"
    
    with patch("channel_cmd.getpass.getpass", return_value="test-token"):
        channel_cmd.connect_channel(args)
    
    # Should call setup endpoint and connect with new credentials
    mock_httpx_client.get.assert_any_call("/api/channels/telegram/setup")
    mock_httpx_client.post.assert_called_with("/api/channels/telegram/connect", json={"credentials": {"token": "test-token"}})


def test_connect_channel_empty_credentials(mock_httpx_client):
    """Test that when credentials dict is empty, we show full setup wizard."""
    # Mock channel status with empty credentials
    mock_status_resp = MagicMock()
    mock_status_resp.json.return_value = {
        "platform": "telegram",
        "status": "needs_setup",
        "config": {
            "platform": "telegram",
            "enabled": False,
            "credentials": {},  # Empty credentials
            "settings": {},
            "authorized_users": [],
            "pairing_code": ""
        }
    }
    
    # Mock setup steps
    mock_setup_resp = MagicMock()
    mock_setup_resp.json.return_value = [{"title": "Step 1", "description": "Desc", "instructions": "Inst"}]
    
    # Mock connect
    mock_connect_resp = MagicMock()
    mock_connect_resp.json.return_value = {"status": "ok"}
    
    # Mock pairing
    mock_pairing_resp = MagicMock()
    mock_pairing_resp.json.return_value = {"pairing_code": "new-code"}
    
    mock_httpx_client.get.side_effect = [mock_status_resp, mock_setup_resp, mock_pairing_resp]
    mock_httpx_client.post.return_value = mock_connect_resp
    
    args = MagicMock()
    args.platform = "telegram"
    
    with patch("channel_cmd.getpass.getpass", return_value="test-token"):
        channel_cmd.connect_channel(args)
    
    # Should call setup endpoint and connect with new credentials
    mock_httpx_client.get.assert_any_call("/api/channels/telegram/setup")
    mock_httpx_client.post.assert_called_with("/api/channels/telegram/connect", json={"credentials": {"token": "test-token"}})


def test_connect_channel_discord_with_existing_credentials(mock_httpx_client):
    """Test Discord connector with existing credentials."""
    # Mock channel status with existing credentials
    mock_status_resp = MagicMock()
    mock_status_resp.json.return_value = {
        "platform": "discord",
        "status": "disconnected",
        "config": {
            "platform": "discord",
            "enabled": False,
            "credentials": {"token": "existing-discord-token", "client_id": "123456789"},
            "settings": {},
            "authorized_users": [],
            "pairing_code": "old-code"
        }
    }
    
    # Mock connect
    mock_connect_resp = MagicMock()
    mock_connect_resp.json.return_value = {"status": "ok"}
    
    # Mock pairing
    mock_pairing_resp = MagicMock()
    mock_pairing_resp.json.return_value = {"pairing_code": "new-code"}
    
    mock_httpx_client.get.side_effect = [mock_status_resp, mock_pairing_resp]
    mock_httpx_client.post.return_value = mock_connect_resp
    
    args = MagicMock()
    args.platform = "discord"
    
    with patch("builtins.input", return_value="y"):
        channel_cmd.connect_channel(args)
    
    # Should connect without new credentials
    mock_httpx_client.post.assert_called_with("/api/channels/discord/connect", json={})


def test_connect_channel_slack_with_existing_credentials(mock_httpx_client):
    """Test Slack connector with existing credentials."""
    # Mock channel status with existing credentials
    mock_status_resp = MagicMock()
    mock_status_resp.json.return_value = {
        "platform": "slack",
        "status": "disconnected",
        "config": {
            "platform": "slack",
            "enabled": False,
            "credentials": {"bot_token": "xoxb-existing", "app_token": "xapp-existing"},
            "settings": {},
            "authorized_users": [],
            "pairing_code": "old-code"
        }
    }
    
    # Mock connect
    mock_connect_resp = MagicMock()
    mock_connect_resp.json.return_value = {"status": "ok"}
    
    # Mock pairing
    mock_pairing_resp = MagicMock()
    mock_pairing_resp.json.return_value = {"pairing_code": "new-code"}
    
    mock_httpx_client.get.side_effect = [mock_status_resp, mock_pairing_resp]
    mock_httpx_client.post.return_value = mock_connect_resp
    
    args = MagicMock()
    args.platform = "slack"
    
    with patch("builtins.input", return_value="y"):
        channel_cmd.connect_channel(args)
    
    # Should connect without new credentials
    mock_httpx_client.post.assert_called_with("/api/channels/slack/connect", json={})

def test_disconnect_channel(mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ok"}
    mock_httpx_client.post.return_value = mock_response
    
    args = MagicMock()
    args.platform = "telegram"
    channel_cmd.disconnect_channel(args)
    
    mock_httpx_client.post.assert_called_with("/api/channels/telegram/disconnect")

def test_test_channel(mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "healthy", "message": "all good"}
    mock_httpx_client.post.return_value = mock_response
    
    args = MagicMock()
    args.platform = "discord"
    channel_cmd.test_channel(args)
    
    mock_httpx_client.post.assert_called_with("/api/channels/discord/test")

def test_pair_channel_show(mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"pairing_code": "current-code"}
    mock_httpx_client.get.return_value = mock_response
    
    args = MagicMock()
    args.platform = "slack"
    args.regenerate = False
    channel_cmd.pair_channel(args)
    
    mock_httpx_client.get.assert_called_with("/api/channels/slack/pairing")

def test_pair_channel_regenerate(mock_httpx_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {"pairing_code": "new-code"}
    mock_httpx_client.post.return_value = mock_response
    
    args = MagicMock()
    args.platform = "slack"
    args.regenerate = True
    channel_cmd.pair_channel(args)
    
    mock_httpx_client.post.assert_called_with("/api/channels/slack/pairing/regenerate")
