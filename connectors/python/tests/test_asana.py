import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from connectors.asana import AsanaConnector
from connectors.models import ExternalDocumentList

@pytest.fixture
def connector():
    return AsanaConnector()

@pytest.fixture
def config():
    return {
        "accessToken": "test-token",
        "workspace": "ws123",
        "maxTasks": "10"
    }

@pytest.mark.asyncio
async def test_asana_list_documents(connector, config):
    mock_projects_response = MagicMock()
    mock_projects_response.status_code = 200
    mock_projects_response.json.return_value = {
        "data": [{"gid": "proj1", "name": "Test Project"}]
    }

    mock_tasks_response = MagicMock()
    mock_tasks_response.status_code = 200
    mock_tasks_response.json.return_value = {
        "data": [
            {
                "gid": "task1",
                "name": "Test Task",
                "completed": False,
                "permalink_url": "https://asana.com/task1"
            }
        ],
        "next_page": None
    }

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [mock_projects_response, mock_tasks_response]
        
        result = await connector.list_documents(config)
        
        assert isinstance(result, ExternalDocumentList)
        assert len(result.documents) == 1
        doc = result.documents[0]
        assert doc.external_id == "task1"
        assert doc.title == "Test Task"
        assert "Completed: No" in doc.content

@pytest.mark.asyncio
async def test_asana_validate_config_success(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {}}

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        await connector.validate_config(config)
