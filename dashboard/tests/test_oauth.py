import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

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
def mock_env():
    with patch.dict(os.environ, {
        "GOOGLE_CLIENT_ID": "google-id",
        "GOOGLE_CLIENT_SECRET": "google-secret",
        "MICROSOFT_CLIENT_ID": "ms-id",
        "MICROSOFT_CLIENT_SECRET": "ms-secret",
    }):
        yield

def test_authorize_redirect(mock_env):
    response = client.get("/api/oauth/authorize/google", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    assert "accounts.google.com" in location
    assert "client_id=google-id" in location
    assert "response_type=code" in location

def test_callback_success(mock_env):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "expires_in": 3600
    }
    
    mock_vault = MagicMock()
    
    # We need to patch httpx.AsyncClient.post which is used inside callback
    # Since it's an async call in an async function, but TestClient handles it, 
    # we might need to patch the right place.
    
    with patch("httpx.AsyncClient.post", return_value=mock_response), \
         patch("dashboard.routes.oauth.get_vault", return_value=mock_vault):
        
        response = client.get("/api/oauth/callback/google?code=test-code&state=default")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Verify vault storage
        assert mock_vault.set.called
        calls = [call.args for call in mock_vault.set.call_args_list]
        assert ("oauth/google", "default/access_token", "test-access-token") in calls
        assert ("oauth/google", "default/refresh_token", "test-refresh-token") in calls

def test_refresh_token_success(mock_env):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new-access-token",
        "expires_in": 3600
    }
    
    mock_vault = MagicMock()
    mock_vault.get.return_value = "old-refresh-token"
    
    with patch("httpx.AsyncClient.post", return_value=mock_response), \
         patch("dashboard.routes.oauth.get_vault", return_value=mock_vault):
        
        response = client.post("/api/oauth/refresh/google")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Verify vault storage of new token
        assert mock_vault.set.called
        calls = [call.args for call in mock_vault.set.call_args_list]
        assert ("oauth/google", "default/access_token", "new-access-token") in calls

def test_status_unauthenticated(mock_env):
    mock_vault = MagicMock()
    mock_vault.get.return_value = None
    
    with patch("dashboard.routes.oauth.get_vault", return_value=mock_vault):
        response = client.get("/api/oauth/status/google")
        assert response.status_code == 200
        assert not response.json()["authenticated"]

def test_status_authenticated(mock_env):
    mock_vault = MagicMock()
    mock_vault.get.side_effect = lambda s, k: "some-value" if "access_token" in k else None
    
    with patch("dashboard.routes.oauth.get_vault", return_value=mock_vault):
        response = client.get("/api/oauth/status/google")
        assert response.status_code == 200
        assert response.json()["authenticated"]
