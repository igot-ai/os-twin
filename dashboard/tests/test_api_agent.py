import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from dashboard.api import app

client = TestClient(app)

@pytest.mark.asyncio
@patch("dashboard.routes.agent.ask_agent", new_callable=AsyncMock)
@patch("dashboard.auth._API_KEY", "test-key")
async def test_api(mock_ask_agent):
    url = "/api/agent/ask"
    payload = {"question": "What is the status?", "platform": "generic"}
    headers = {"X-API-Key": "test-key"} 
    
    mock_ask_agent.return_value = "The status is green."
    
    response = client.post(url, json=payload, headers=headers)
    
    assert response.status_code == 200
    assert response.json() == {"answer": "The status is green."}
    mock_ask_agent.assert_called_once_with("What is the status?", platform="generic")

