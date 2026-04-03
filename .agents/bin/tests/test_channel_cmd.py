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

def test_connect_channel_telegram(mock_httpx_client):
    # Mock setup steps
    mock_setup_resp = MagicMock()
    mock_setup_resp.json.return_value = [{"title": "Step 1", "description": "Desc", "instructions": "Inst"}]
    
    # Mock connect
    mock_connect_resp = MagicMock()
    mock_connect_resp.json.return_value = {"status": "ok"}
    
    # Mock pairing
    mock_pairing_resp = MagicMock()
    mock_pairing_resp.json.return_value = {"pairing_code": "new-code"}
    
    mock_httpx_client.get.side_effect = [mock_setup_resp, mock_pairing_resp]
    mock_httpx_client.post.return_value = mock_connect_resp
    
    args = MagicMock()
    args.platform = "telegram"
    
    with patch("channel_cmd.getpass.getpass", return_value="test-token"):
        channel_cmd.connect_channel(args)
    
    mock_httpx_client.get.assert_any_call("/api/channels/telegram/setup")
    mock_httpx_client.post.assert_called_with("/api/channels/telegram/connect", json={"credentials": {"token": "test-token"}})

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
