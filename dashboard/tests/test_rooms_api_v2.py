import json
import pytest
from pathlib import Path
from dashboard.api_utils import read_channel

def test_read_channel_comprehensive_filtering(tmp_path):
    room_dir = tmp_path / "room-test"
    room_dir.mkdir()
    channel_file = room_dir / "channel.jsonl"
    
    messages = [
        {"id": "1", "ts": "2026-03-21T10:00:00Z", "from": "manager", "to": "engineer", "type": "task", "ref": "EPIC-001", "body": "Initial task"},
        {"id": "2", "ts": "2026-03-21T10:05:00Z", "from": "engineer", "to": "manager", "type": "done", "ref": "EPIC-001", "body": "Finished task 1"},
        {"id": "3", "ts": "2026-03-21T10:10:00Z", "from": "manager", "to": "qa", "type": "review", "ref": "EPIC-001", "body": "Please review"},
        {"id": "4", "ts": "2026-03-21T10:15:00Z", "from": "qa", "to": "manager", "type": "fail", "ref": "EPIC-001", "body": "Found a bug"},
        {"id": "5", "ts": "2026-03-21T10:20:00Z", "from": "engineer", "to": "qa", "type": "done", "ref": "TASK-123", "body": "Fix for bug"},
    ]
    
    with open(channel_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
            
    # Filter by from_role
    assert len(read_channel(room_dir, from_role="engineer")) == 2
    # Filter by to_role
    assert len(read_channel(room_dir, to_role="qa")) == 2
    # Filter by msg_type
    assert len(read_channel(room_dir, msg_type="done")) == 2
    # Filter by ref
    assert len(read_channel(room_dir, ref="TASK-123")) == 1
    # Filter by query
    assert len(read_channel(room_dir, query="bug")) == 2
    # Combined filters
    assert len(read_channel(room_dir, from_role="engineer", msg_type="done")) == 2
    assert len(read_channel(room_dir, from_role="engineer", ref="TASK-123")) == 1
    # Limit
    assert len(read_channel(room_dir, limit=3)) == 3
    assert read_channel(room_dir, limit=1)[0]["id"] == "5"
    print("SUCCESS: read_channel filtering tests passed.")

def test_analyze_logic(tmp_path):
    # We can test the logic inside analyze_messages if we refactor it or just test it here manually
    # For now, let's just verify read_channel which is the core of it
    pass

if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_read_channel_comprehensive_filtering(Path(tmp_dir))

def test_read_channel_no_file(tmp_path):
    assert read_channel(tmp_path / "non-existent") == []
