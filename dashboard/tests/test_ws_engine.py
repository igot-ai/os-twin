import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

import api
from api import app, poll_war_rooms, broadcaster, WARROOMS_DIR, AGENTS_DIR

client = TestClient(app)

@pytest.fixture
def mock_dirs(tmp_path):
    orig_warrooms = api.WARROOMS_DIR
    orig_agents = api.AGENTS_DIR
    
    api.WARROOMS_DIR = tmp_path / ".war-rooms"
    api.WARROOMS_DIR.mkdir()
    
    api.AGENTS_DIR = tmp_path / ".agents"
    api.AGENTS_DIR.mkdir()
    plans_dir = api.AGENTS_DIR / "plans"
    plans_dir.mkdir()
    
    yield
    
    api.WARROOMS_DIR = orig_warrooms
    api.AGENTS_DIR = orig_agents

@pytest.mark.asyncio
async def test_initial_messages_broadcast_on_room_creation(mock_dirs):
    """TASK-001: Ensure existing messages are broadcast when a new room is discovered."""
    with patch.object(broadcaster, "broadcast", new_callable=AsyncMock) as mock_broadcast:
        # Start the background task
        task = asyncio.create_task(poll_war_rooms())
        await asyncio.sleep(0.5) # Let last_snapshot initialize
        
        # Create a new room with a message
        room_dir = api.WARROOMS_DIR / "room-test1"
        room_dir.mkdir()
        channel_file = room_dir / "channel.jsonl"
        channel_file.write_text(json.dumps({"type": "task", "body": "first message"}) + "\n")
        
        await asyncio.sleep(1.5) # Let poller detect it
        task.cancel()
        
        # Verify room_updated with new_messages was called
        found = False
        for call in mock_broadcast.mock_calls:
            args, _ = call[1], call[2]
            event_type = args[0]
            data = args[1]
            if event_type == "room_updated" and data["room"]["room_id"] == "room-test1":
                if "new_messages" in data and len(data["new_messages"]) == 1:
                    found = True
        
        assert found, "Initial messages were not broadcast on room creation"

@pytest.mark.asyncio
async def test_plan_queue_updates_broadcast(mock_dirs):
    """TASK-002: Ensure plan updates trigger broadcast."""
    with patch.object(broadcaster, "broadcast", new_callable=AsyncMock) as mock_broadcast:
        # Start the background task
        task = asyncio.create_task(poll_war_rooms())
        await asyncio.sleep(0.5)
        
        # Create a new plan
        plan_file = api.AGENTS_DIR / "plans" / "agent-os-plan-test.md"
        plan_file.write_text("# Plan: Test")
        
        await asyncio.sleep(1.5)
        task.cancel()
        
        # Verify plans_updated was called
        found = False
        for call in mock_broadcast.mock_calls:
            args, _ = call[1], call[2]
            if args[0] == "plans_updated":
                found = True
                
        assert found, "Plan queue update did not trigger broadcast"

def test_websocket_endpoint():
    """TASK-003: Ensure WebSocket endpoint correctly accepts connections."""
    with client.websocket_connect("/api/ws") as websocket:
        # Should receive initial connected event
        data = websocket.receive_json()
        assert data["event"] == "connected"
        
        # Should reply to ping
        websocket.send_text(json.dumps({"type": "ping"}))
        response = websocket.receive_json()
        assert response["type"] == "pong"
        assert "ts" in response
        
        # Should handle invalid JSON without disconnecting
        websocket.send_text("invalid json")
        
        # Ensure still connected by sending another ping
        websocket.send_text(json.dumps({"type": "ping"}))
        response = websocket.receive_json()
        assert response["type"] == "pong"
