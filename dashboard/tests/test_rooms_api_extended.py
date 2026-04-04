
from fastapi.testclient import TestClient
import os
import sys
from pathlib import Path

# Setup paths
_dashboard_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dashboard_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)
if _dashboard_dir not in sys.path:
    sys.path.insert(0, _dashboard_dir)

from dashboard.api import app

client = TestClient(app)

def test_get_room_state_extended():
    response = client.get("/api/rooms/room-003/state")
    if response.status_code != 200:
        from dashboard.api_utils import WARROOMS_DIR
        print(f"DEBUG: WARROOMS_DIR = {WARROOMS_DIR}")
        print(f"DEBUG: Does room-003 exist in it? {(WARROOMS_DIR / 'room-003').exists()}")
        print(f"DEBUG: Response body: {response.text}")
    assert response.status_code == 200
    data = response.json()
    
    assert data["room_id"] == "room-003"
    assert "lifecycle" in data
    assert "roles" in data
    assert "artifact_files" in data
    assert "audit_tail" in data
    
    # Check if we got the expected metadata
    # The initial_state depends on what's in lifecycle.json for room-003
    assert "initial_state" in data["lifecycle"]
    assert "states" in data["lifecycle"]
    assert len(data["roles"]) > 0
    assert data["roles"][0]["role"] == "engineer"
    
    print("SUCCESS: API endpoint /api/rooms/room-003/state returns full metadata.")

if __name__ == "__main__":
    test_get_room_state_extended()
