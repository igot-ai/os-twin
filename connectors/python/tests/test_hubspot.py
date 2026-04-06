import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from connectors.hubspot import HubSpotConnector
from connectors.models import ExternalDocumentList

@pytest.fixture
def connector():
    return HubSpotConnector()

@pytest.fixture
def config():
    return {
        "accessToken": "test-token",
        "objectType": "contacts",
        "maxRecords": "10"
    }

@pytest.mark.asyncio
async def test_hubspot_list_documents(connector, config):
    mock_portal_response = MagicMock()
    mock_portal_response.status_code = 200
    mock_portal_response.json.return_value = {"portalId": "12345"}

    mock_search_response = MagicMock()
    mock_search_response.status_code = 200
    mock_search_response.json.return_value = {
        "results": [
            {
                "id": "cont1",
                "properties": {
                    "firstname": "John",
                    "lastname": "Doe",
                    "email": "john@example.com"
                }
            }
        ],
        "paging": {}
    }

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get, \
         patch("connectors.client.ConnectorHttpClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = mock_portal_response
        mock_post.return_value = mock_search_response
        
        result = await connector.list_documents(config)
        
        assert isinstance(result, ExternalDocumentList)
        assert len(result.documents) == 1
        doc = result.documents[0]
        assert doc.external_id == "cont1"
        assert doc.title == "John Doe"
        assert "Email: john@example.com" in doc.content
        assert "12345" in doc.source_url

@pytest.mark.asyncio
async def test_hubspot_validate_config_success(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        await connector.validate_config(config)
