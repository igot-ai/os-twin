import sys
import os
from pathlib import Path

_dashboard_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dashboard_dir)

# Override WARROOMS_DIR for this test
WARROOMS_DIR_OVERRIDE = Path(_dashboard_dir) / ".war-rooms"

if _root not in sys.path:
    sys.path.insert(0, _root)
if _dashboard_dir not in sys.path:
    sys.path.insert(0, _dashboard_dir)

from dashboard.api_utils import read_room

def test_read_room_extended():
    room_dir = WARROOMS_DIR_OVERRIDE / "room-003"
    if not room_dir.exists():
        print(f"Room {room_dir} not found, skipping test.")
        return

    print(f"Reading room: {room_dir}")
    room_data = read_room(room_dir, include_metadata=True)
    
    print(f"Room ID: {room_data.get('room_id')}")
    print(f"Lifecycle keys: {list(room_data.get('lifecycle', {}).keys())}")
    print(f"Roles count: {len(room_data.get('roles', []))}")
    print(f"Artifacts count: {len(room_data.get('artifact_files', []))}")
    print(f"Audit tail count: {len(room_data.get('audit_tail', []))}")

    assert "lifecycle" in room_data
    assert "roles" in room_data
    assert "artifact_files" in room_data
    assert "audit_tail" in room_data
    
    # Check lifecycle content
    lifecycle = room_data["lifecycle"]
    assert "initial_state" in lifecycle
    assert "states" in lifecycle
    assert "engineering" in lifecycle["states"]
    
    # Check roles content
    roles = room_data["roles"]
    assert len(roles) > 0
    assert roles[0]["role"] == "e"
    
    print("SUCCESS: read_room returns expected extended metadata.")

if __name__ == "__main__":
    test_read_room_extended()
