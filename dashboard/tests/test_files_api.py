import json
import pytest
from fastapi.testclient import TestClient
from dashboard.api import app
from dashboard.auth import get_current_user

# Mock authentication
async def mock_get_current_user():
    return {"user_id": "test_user"}

app.dependency_overrides[get_current_user] = mock_get_current_user

@pytest.fixture
def test_workspace(tmp_path):
    # Create a dummy working directory
    working_dir = tmp_path / "workspace"
    working_dir.mkdir()
    
    # Create some files and dirs
    (working_dir / "src").mkdir()
    (working_dir / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    (working_dir / "README.md").write_text("# Project", encoding="utf-8")
    (working_dir / "data.bin").write_bytes(b"\x80\x81\x82")
    
    # Create a plan meta file
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    plan_id = "test-plan"
    meta = {
        "plan_id": plan_id,
        "working_dir": str(working_dir)
    }
    (plans_dir / f"{plan_id}.meta.json").write_text(json.dumps(meta))
    
    return {
        "working_dir": working_dir,
        "plans_dir": plans_dir,
        "plan_id": plan_id
    }

def test_list_files(test_workspace, monkeypatch):
    monkeypatch.setattr("dashboard.routes.files.PLANS_DIR", test_workspace["plans_dir"])
    client = TestClient(app)
    
    response = client.get(f"/api/plans/{test_workspace['plan_id']}/files")
    assert response.status_code == 200
    data = response.json()
    assert data["path"] == ""
    assert len(data["entries"]) == 3
    
    names = [e["name"] for e in data["entries"]]
    assert "src" in names
    assert "README.md" in names
    assert "data.bin" in names
    
    # Check sorting (dirs first)
    assert data["entries"][0]["name"] == "src"

def test_list_files_subdir(test_workspace, monkeypatch):
    monkeypatch.setattr("dashboard.routes.files.PLANS_DIR", test_workspace["plans_dir"])
    client = TestClient(app)
    
    response = client.get(f"/api/plans/{test_workspace['plan_id']}/files?path=src")
    assert response.status_code == 200
    data = response.json()
    assert data["path"] == "src"
    assert len(data["entries"]) == 1
    assert data["entries"][0]["name"] == "main.py"

def test_get_content_text(test_workspace, monkeypatch):
    monkeypatch.setattr("dashboard.routes.files.PLANS_DIR", test_workspace["plans_dir"])
    client = TestClient(app)
    
    response = client.get(f"/api/plans/{test_workspace['plan_id']}/files/content?path=README.md")
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "# Project"
    assert data["encoding"] == "utf-8"
    assert data["truncated"] is False

def test_get_content_binary(test_workspace, monkeypatch):
    monkeypatch.setattr("dashboard.routes.files.PLANS_DIR", test_workspace["plans_dir"])
    client = TestClient(app)
    
    response = client.get(f"/api/plans/{test_workspace['plan_id']}/files/content?path=data.bin")
    assert response.status_code == 200
    data = response.json()
    import base64
    assert data["content"] == base64.b64encode(b"\x80\x81\x82").decode("utf-8")
    assert data["encoding"] == "base64"

def test_get_content_limit(test_workspace, monkeypatch):
    monkeypatch.setattr("dashboard.routes.files.PLANS_DIR", test_workspace["plans_dir"])
    client = TestClient(app)
    
    large_file = test_workspace["working_dir"] / "large.txt"
    large_file.write_text("A" * (2 * 1024 * 1024 + 1))
    
    response = client.get(f"/api/plans/{test_workspace['plan_id']}/files/content?path=large.txt")
    assert response.status_code == 200
    data = response.json()
    assert data["content"] is None
    assert data["truncated"] is True

def test_get_tree(test_workspace, monkeypatch):
    monkeypatch.setattr("dashboard.routes.files.PLANS_DIR", test_workspace["plans_dir"])
    client = TestClient(app)
    
    response = client.get(f"/api/plans/{test_workspace['plan_id']}/files/tree")
    assert response.status_code == 200
    data = response.json()
    assert "tree" in data
    assert len(data["tree"]) > 0
    
    # Find 'src' in tree
    src_node = next((n for n in data["tree"] if n["name"] == "src"), None)
    assert src_node is not None
    assert "children" in src_node
    assert src_node["children"][0]["name"] == "main.py"

def test_path_traversal(test_workspace, monkeypatch):
    monkeypatch.setattr("dashboard.routes.files.PLANS_DIR", test_workspace["plans_dir"])
    client = TestClient(app)
    
    response = client.get(f"/api/plans/{test_workspace['plan_id']}/files?path=../../")
    assert response.status_code == 403
    assert "traversal" in response.json()["detail"].lower()

def test_git_changes_repo(test_workspace, monkeypatch):
    monkeypatch.setattr("dashboard.routes.files.PLANS_DIR", test_workspace["plans_dir"])
    client = TestClient(app)
    
    # Init git
    import subprocess
    subprocess.run(["git", "init"], cwd=str(test_workspace["working_dir"]), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(test_workspace["working_dir"]), check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(test_workspace["working_dir"]), check=True)
    subprocess.run(["git", "add", "."], cwd=str(test_workspace["working_dir"]), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(test_workspace["working_dir"]), check=True)
    
    # Make a change
    (test_workspace["working_dir"] / "new.txt").write_text("new file")
    
    response = client.get(f"/api/plans/{test_workspace['plan_id']}/files/changes")
    assert response.status_code == 200
    data = response.json()
    assert data["git_enabled"] is True
    assert len(data["status"]) > 0
    assert "new.txt" in data["status"][0]
    assert len(data["recent_commits"]) == 1
    assert data["recent_commits"][0]["subject"] == "Initial commit"
