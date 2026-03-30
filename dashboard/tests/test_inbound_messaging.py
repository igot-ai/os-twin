import json
import pytest
import asyncio
from fastapi.testclient import TestClient
from pathlib import Path
from dashboard.api import app
from dashboard.api_utils import WARROOMS_DIR, post_message_to_room, read_channel, save_thread_mapping

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
    
    return {"rooms_dir": rooms_dir, "room_001": room_dir, "tmp_path": tmp_path}

def test_dashboard_post_message(mock_env):
    # Mock authentication
    from dashboard.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"username": "testuser"}
    
    response = client.post(
        "/api/rooms/room-001/message",
        json={"body": "Hello from dashboard", "from": "user123"}
    )
    app.dependency_overrides = {}
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    messages = read_channel(mock_env["room_001"])
    assert len(messages) == 1
    assert messages[0]["body"] == "Hello from dashboard"
    assert messages[0]["from"] == "user123"
    assert messages[0]["type"] == "human-directive"

def test_telegram_webhook(mock_env):
    payload = {
        "update_id": 1,
        "message": {
            "text": "/room room-001 hello from telegram",
            "from": {"username": "tguser"}
        }
    }
    # Mock adapter config
    from dashboard.chat_adapters.registry import registry
    registry.update_config("telegram", {"bot_token": "abc", "chat_id": "123"})
    
    response = client.post("/api/chat-adapters/telegram/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    messages = read_channel(mock_env["room_001"])
    assert len(messages) == 1
    assert messages[0]["body"] == "hello from telegram"
    assert messages[0]["from"] == "telegram:tguser"

def test_discord_webhook(mock_env):
    payload = {
        "type": 2,
        "data": {
            "name": "ostwin",
            "options": [
                {"name": "room", "value": "room-001"},
                {"name": "message", "value": "hello from discord"}
            ]
        },
        "member": {"user": {"username": "dcuser"}}
    }
    from dashboard.chat_adapters.registry import registry
    registry.update_config("discord", {"webhook_url": "http://example.com"})

    response = client.post("/api/chat-adapters/discord/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    messages = read_channel(mock_env["room_001"])
    assert len(messages) == 1
    assert messages[0]["body"] == "hello from discord"
    assert messages[0]["from"] == "discord:dcuser"

def test_slack_webhook_mention(mock_env):
    payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "text": "<@U123> room-001 hello from slack",
            "user": "sluser"
        }
    }
    from dashboard.chat_adapters.registry import registry
    registry.update_config("slack", {"webhook_url": "http://example.com"})

    response = client.post("/api/chat-adapters/slack/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    messages = read_channel(mock_env["room_001"])
    assert len(messages) == 1
    assert messages[0]["body"] == "hello from slack"
    assert messages[0]["from"] == "slack:sluser"

def test_slack_webhook_thread(mock_env):
    # Save thread mapping
    save_thread_mapping("slack", "123.456", "room-001")
    
    payload = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "text": "replying to thread",
            "thread_ts": "123.456",
            "user": "sluser"
        }
    }
    response = client.post("/api/chat-adapters/slack/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    messages = read_channel(mock_env["room_001"])
    assert len(messages) == 1
    assert messages[0]["body"] == "replying to thread"
    assert messages[0]["from"] == "slack:sluser"
