import json
import pytest
import asyncio
import hmac
import hashlib
import time
from fastapi.testclient import TestClient
from pathlib import Path
from dashboard.api import app
from dashboard.api_utils import WARROOMS_DIR, post_message_to_room, read_channel, save_thread_mapping, get_last_active_room, save_last_active_room
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

client = TestClient(app)

@pytest.fixture
def mock_env(tmp_path, monkeypatch):
    # Setup mock directories
    rooms_dir = tmp_path / "warrooms"
    rooms_dir.mkdir()
    data_dir = tmp_path / ".data"
    data_dir.mkdir()
    
    room_dir = rooms_dir / "room-001"
    room_dir.mkdir()
    (room_dir / "status").write_text("pending")
    (room_dir / "channel.jsonl").touch()
    
    # Patch all the places where WARROOMS_DIR or PROJECT_ROOT are used
    monkeypatch.setattr("dashboard.api_utils.WARROOMS_DIR", rooms_dir)
    monkeypatch.setattr("dashboard.api_utils.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("dashboard.routes.rooms.WARROOMS_DIR", rooms_dir)
    monkeypatch.setattr("dashboard.routes.chat_adapters.find_room_dir", lambda r: rooms_dir / r if (rooms_dir / r).exists() else None)
    
    # Reset registry configs
    from dashboard.chat_adapters.registry import registry
    registry.configs = {}
    
    return {"rooms_dir": rooms_dir, "room_001": room_dir, "tmp_path": tmp_path}

def test_telegram_security_verification(mock_env):
    from dashboard.chat_adapters.registry import registry
    registry.update_config("telegram", {"bot_token": "abc", "chat_id": "123", "secret_token": "secret123"})
    
    payload = {
        "message": {
            "text": "/room room-001 hello",
            "from": {"username": "tguser"}
        }
    }
    
    # 1. Fail without token
    response = client.post("/api/chat-adapters/telegram/webhook", json=payload)
    assert response.json()["status"] == "ignored"
    
    # 2. Fail with wrong token
    headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong"}
    response = client.post("/api/chat-adapters/telegram/webhook", json=payload, headers=headers)
    assert response.json()["status"] == "ignored"
    
    # 3. Success with correct token
    headers = {"X-Telegram-Bot-Api-Secret-Token": "secret123"}
    response = client.post("/api/chat-adapters/telegram/webhook", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_slack_security_verification(mock_env):
    from dashboard.chat_adapters.registry import registry
    secret = "slack_secret_123"
    registry.update_config("slack", {"webhook_url": "http://example.com", "signing_secret": secret})
    
    payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "text": "room-001 hello",
            "user": "sluser"
        }
    }
    body = json.dumps(payload)
    timestamp = str(int(time.time()))
    
    # 1. Fail without signature
    response = client.post("/api/chat-adapters/slack/webhook", content=body)
    assert response.json()["status"] == "ignored"
    
    # 2. Success with correct signature
    sig_basestring = f"v0:{timestamp}:{body}"
    signature = "v0=" + hmac.new(secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()
    headers = {
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature,
        "Content-Type": "application/json"
    }
    response = client.post("/api/chat-adapters/slack/webhook", content=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_discord_security_verification(mock_env):
    from dashboard.chat_adapters.registry import registry
    private_key = Ed25519PrivateKey.generate()
    public_key_hex = private_key.public_key().public_bytes_raw().hex()
    registry.update_config("discord", {"webhook_url": "http://example.com", "public_key": public_key_hex})
    
    # Test Ping (type 1)
    ping_payload = {"type": 1}
    ping_body = json.dumps(ping_payload)
    timestamp = str(int(time.time()))
    signature = private_key.sign(timestamp.encode() + ping_body.encode()).hex()
    headers = {
        "X-Signature-Ed25519": signature,
        "X-Signature-Timestamp": timestamp,
        "Content-Type": "application/json"
    }
    response = client.post("/api/chat-adapters/discord/webhook", content=ping_body, headers=headers)
    assert response.status_code == 200
    assert response.json()["type"] == 1

    # Test Command (type 2)
    cmd_payload = {
        "type": 2,
        "data": {
            "name": "ostwin",
            "options": [
                {"name": "room", "value": "room-001"},
                {"name": "message", "value": "hello discord"}
            ]
        },
        "member": {"user": {"username": "dcuser"}}
    }
    cmd_body = json.dumps(cmd_payload)
    signature = private_key.sign(timestamp.encode() + cmd_body.encode()).hex()
    headers["X-Signature-Ed25519"] = signature
    response = client.post("/api/chat-adapters/discord/webhook", content=cmd_body, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_telegram_last_active_fallback(mock_env):
    from dashboard.chat_adapters.registry import registry
    registry.update_config("telegram", {"bot_token": "abc", "chat_id": "123"})
    
    # 1. Set last active room
    save_last_active_room("telegram:12345", "room-001")
    
    # 2. Post message without /room command
    payload = {
        "message": {
            "text": "just a message",
            "from": {"username": "tguser"},
            "chat": {"id": 12345}
        }
    }
    response = client.post("/api/chat-adapters/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["room_id"] == "room-001"
    
    messages = read_channel(mock_env["room_001"])
    assert messages[0]["body"] == "just a message"

def test_telegram_thread_resolution(mock_env):
    from dashboard.chat_adapters.registry import registry
    registry.update_config("telegram", {"bot_token": "abc", "chat_id": "123"})
    
    # 1. Save thread mapping
    save_thread_mapping("telegram", "999", "room-001")
    
    # 2. Reply to message 999
    payload = {
        "message": {
            "text": "threaded reply",
            "from": {"username": "tguser"},
            "reply_to_message": {"message_id": 999}
        }
    }
    response = client.post("/api/chat-adapters/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["room_id"] == "room-001"

def test_telegram_relaxed_regex(mock_env):
    from dashboard.chat_adapters.registry import registry
    registry.update_config("telegram", {"bot_token": "abc", "chat_id": "123"})
    
    # Test /room room-001 (no content)
    payload = {"message": {"text": "/room room-001", "from": {"username": "u"}}}
    response = client.post("/api/chat-adapters/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["room_id"] == "room-001"
    
    # Test /room room-001 content
    payload = {"message": {"text": "/room room-001 some content", "from": {"username": "u"}}}
    response = client.post("/api/chat-adapters/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["room_id"] == "room-001"
