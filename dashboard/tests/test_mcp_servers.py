import sys
import asyncio
from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, "/Users/paulaan/PycharmProjects/agent-os")

from dashboard.api import app
from dashboard.auth import get_current_user

client = TestClient(app)

# Mock the get_current_user dependency
def mock_get_current_user():
    return {"user_id": "test-user"}

app.dependency_overrides[get_current_user] = mock_get_current_user

@pytest.fixture
def mock_mcp_configs(tmp_path):
    builtin_file = tmp_path / "builtin.json"
    home_file = tmp_path / "home.json"
    
    builtin_data = {
        "mcpServers": {
            "builtin-server": {
                "command": "python",
                "args": ["-m", "server"]
            }
        }
    }
    
    home_data = {
        "mcpServers": {
            "home-server": {
                "httpUrl": "http://localhost:8080"
            }
        }
    }
    
    builtin_file.write_text(json.dumps(builtin_data))
    home_file.write_text(json.dumps(home_data))
    
    return builtin_file, home_file

def test_list_mcp_servers():
    with patch("dashboard.routes.mcp.BUILTIN_CONFIG_FILE") as mock_builtin, \
         patch("dashboard.routes.mcp.HOME_CONFIG_FILE") as mock_home, \
         patch("dashboard.routes.mcp.ConfigResolver") as mock_resolver, \
         patch("dashboard.routes.mcp._read_json") as mock_read:
        
        mock_read.side_effect = [
            {"mcpServers": {"builtin": {"command": "ls"}}},
            {"mcpServers": {"home": {"httpUrl": "http://test"}}}
        ]
        
        response = client.get("/api/mcp/servers")
        assert response.status_code == 200
        data = response.json()
        assert "servers" in data
        assert len(data["servers"]) == 2
        names = [s["name"] for s in data["servers"]]
        assert "builtin" in names
        assert "home" in names

def test_add_mcp_server():
    with patch("dashboard.routes.mcp.HOME_CONFIG_FILE") as mock_home_path, \
         patch("dashboard.routes.mcp._read_json", return_value={"mcpServers": {}}):
        
        mock_home_path.parent.mkdir = MagicMock()
        mock_home_path.write_text = MagicMock()
        
        payload = {
            "name": "new-server",
            "type": "stdio",
            "command": "node",
            "args": ["index.js"]
        }
        response = client.post("/api/mcp/servers", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Verify write_text was called with correct data
        assert mock_home_path.write_text.called
        written_data = json.loads(mock_home_path.write_text.call_args[0][0])
        assert "new-server" in written_data["mcpServers"]
        assert written_data["mcpServers"]["new-server"]["command"] == "node"

@pytest.mark.asyncio
async def test_test_mcp_server_success():
    mock_session = MagicMock()
    async def mock_init():
        return MagicMock(serverInfo=MagicMock(name="test", version="1.0"))
    mock_session.initialize = mock_init
    
    async def mock_list_tools():
        return MagicMock(tools=[MagicMock(name="tool1", description="desc1")])
    mock_session.list_tools = mock_list_tools
    
    mock_stdio = MagicMock()
    mock_stdio.__aenter__.return_value = (MagicMock(), MagicMock())
    
    mock_client_session = MagicMock()
    mock_client_session.__aenter__.return_value = mock_session

    with patch("dashboard.routes.mcp._read_json", return_value={"mcpServers": {"test": {"command": "ls"}}}), \
         patch("shutil.which", return_value="/bin/ls"), \
         patch("dashboard.routes.mcp.stdio_client", return_value=mock_stdio), \
         patch("dashboard.routes.mcp.ClientSession", return_value=mock_client_session):
        
        response = client.post("/api/mcp/servers/test/test")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert "Connected" in response.json()["message"]

def test_set_server_credential():
    mock_vault = MagicMock()
    with patch("dashboard.routes.mcp.get_vault", return_value=mock_vault):
        payload = {"value": "secret"}
        response = client.put("/api/mcp/servers/test-server/credentials/vault-serv/key1", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_vault.set.assert_called_with("vault-serv", "key1", "secret")

        # Test simplified path (matching spec)
        response = client.put("/api/mcp/servers/test-server/credentials/key2", json=payload)
        assert response.status_code == 200
        mock_vault.set.assert_called_with("test-server", "key2", "secret")

def test_delete_server_credential():
    mock_vault = MagicMock()
    with patch("dashboard.routes.mcp.get_vault", return_value=mock_vault):
        response = client.delete("/api/mcp/servers/test-server/credentials/vault-serv/key1")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_vault.delete.assert_called_with("vault-serv", "key1")

        # Test simplified path
        response = client.delete("/api/mcp/servers/test-server/credentials/key2")
        assert response.status_code == 200
        mock_vault.delete.assert_called_with("test-server", "key2")

@pytest.mark.asyncio
async def test_test_mcp_server_http():
    mock_session = MagicMock()
    async def mock_init(): return MagicMock(serverInfo=MagicMock(name="test", version="1.0"))
    mock_session.initialize = mock_init
    
    async def mock_list_tools(): return MagicMock(tools=[MagicMock(name="tool1", description="desc1")])
    mock_session.list_tools = mock_list_tools
    
    mock_sse = MagicMock()
    mock_sse.__aenter__.return_value = (MagicMock(), MagicMock())
    
    mock_client_session = MagicMock()
    mock_client_session.__aenter__.return_value = mock_session

    with patch("dashboard.routes.mcp._read_json", return_value={"mcpServers": {"test": {"httpUrl": "http://test"}}}), \
         patch("dashboard.routes.mcp.sse_client", return_value=mock_sse), \
         patch("dashboard.routes.mcp.ClientSession", return_value=mock_client_session):
        
        response = client.post("/api/mcp/servers/test/test")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert "Connected" in response.json()["message"]

def test_remove_mcp_server():
    with patch("dashboard.routes.mcp.HOME_CONFIG_FILE") as mock_home_path, \
         patch("dashboard.routes.mcp._read_json", return_value={"mcpServers": {"test": {}}}):
        
        mock_home_path.write_text = MagicMock()
        response = client.delete("/api/mcp/servers/test")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        written_data = json.loads(mock_home_path.write_text.call_args[0][0])
        assert "test" not in written_data["mcpServers"]

def test_list_credentials():
    mock_resolver_inst = MagicMock()
    mock_resolver_inst.extract_vault_refs.return_value = [("serv", "key1"), ("serv", "key2")]
    
    with patch("dashboard.routes.mcp._read_json", return_value={"mcpServers": {"test": {"command": "ls"}}}), \
         patch("dashboard.routes.mcp.ConfigResolver", return_value=mock_resolver_inst), \
         patch("dashboard.routes.mcp.BUILTIN_CONFIG_FILE", Path("/tmp/builtin.json")), \
         patch("dashboard.routes.mcp.HOME_CONFIG_FILE", Path("/tmp/home.json")):
        
        response = client.get("/api/mcp/servers/test/credentials")
        assert response.status_code == 200
        data = response.json()
        assert "credentials" in data
        assert len(data["credentials"]) == 2
        assert data["credentials"][0]["key"] == "key1"
