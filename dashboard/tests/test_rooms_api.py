import json
from dashboard.api_utils import read_channel


def test_read_channel_filtering(tmp_path):
    # Setup mock channel.jsonl
    room_dir = tmp_path / "room-test"
    room_dir.mkdir()
    channel_file = room_dir / "channel.jsonl"
    
    messages = [
        {"v": 1, "id": "1", "ts": "2026-03-21T10:00:00Z", "from": "manager", "to": "e", "type": "task", "ref": "EPIC-001", "body": "Start task 1"},
        {"v": 1, "id": "2", "ts": "2026-03-21T10:05:00Z", "from": "e", "to": "manager", "type": "done", "ref": "EPIC-001", "body": "Finished task 1 successfully"},
        {"v": 1, "id": "3", "ts": "2026-03-21T10:10:00Z", "from": "manager", "to": "qa", "type": "review", "ref": "EPIC-001", "body": "Please review"},
        {"v": 1, "id": "4", "ts": "2026-03-21T10:15:00Z", "from": "qa", "to": "manager", "type": "fail", "ref": "EPIC-001", "body": "Found a bug in task 1"},
    ]
    
    with open(channel_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
            
    # Test all messages
    assert len(read_channel(room_dir)) == 4
    
    # Test filter by from_role
    assert len(read_channel(room_dir, from_role="manager")) == 2
    assert len(read_channel(room_dir, from_role="qa")) == 1
    
    # Test filter by type
    assert len(read_channel(room_dir, msg_type="done")) == 1
    assert read_channel(room_dir, msg_type="done")[0]["id"] == "2"
    
    # Test filter by query
    assert len(read_channel(room_dir, query="bug")) == 1
    assert read_channel(room_dir, query="bug")[0]["id"] == "4"
    assert len(read_channel(room_dir, query="task")) == 3
    
    # Test limit
    assert len(read_channel(room_dir, limit=2)) == 2
    assert read_channel(room_dir, limit=2)[0]["id"] == "3"
    assert read_channel(room_dir, limit=2)[1]["id"] == "4"


def test_read_channel_empty(tmp_path):
    room_dir = tmp_path / "room-empty"
    room_dir.mkdir()
    assert read_channel(room_dir) == []
