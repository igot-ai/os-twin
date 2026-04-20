import os
import sys

# SET ENV VAR BEFORE IMPORTS
os.environ["OSTWIN_API_KEY"] = "test-key"

from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Ensure dashboard is importable
sys.path.insert(0, os.getcwd())

def test_paths():
    from dashboard.api import app
    from dashboard.routes.knowledge import _get_service
    
    mock_service = MagicMock()
    headers = {"Authorization": "Bearer test-key"}
    
    patterns = [
        "../etc/passwd",
        "/etc/passwd",
        "/sys/class",
        "/proc/self",
        "/dev/null",
        "relative/path",
        "",
        " ",
        "/Users/paulaan/PycharmProjects/agent-os/dashboard/../../../../etc/passwd",
    ]
    
    with patch("dashboard.routes.knowledge._get_service", return_value=mock_service):
        with TestClient(app) as client:
            for p in patterns:
                response = client.post(
                    "/api/knowledge/namespaces/test-ns/import",
                    headers=headers,
                    json={"folder_path": p}
                )
                print(f"Path: '{p}' -> Status: {response.status_code}, Code: {response.json().get('detail', {}).get('code')}")

if __name__ == "__main__":
    test_paths()
