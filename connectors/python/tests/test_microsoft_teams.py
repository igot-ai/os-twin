import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from connectors.microsoft_teams import MicrosoftTeamsConnector
from connectors.models import ExternalDocumentList

@pytest.fixture
def connector():
    return MicrosoftTeamsConnector()

@pytest.fixture
def config():
    return {
        "accessToken": "test-token",
        "teamId": "team123",
        "channel": "General",
        "maxMessages": "10"
    }

@pytest.mark.asyncio
async def test_teams_list_documents(connector, config):
    mock_channels_response = MagicMock()
    mock_channels_response.status_code = 200
    mock_channels_response.json.return_value = {
        "value": [{"id": "chan123", "displayName": "General"}]
    }

    mock_messages_response = MagicMock()
    mock_messages_response.status_code = 200
    mock_messages_response.json.return_value = {
        "value": [
            {
                "id": "msg1",
                "messageType": "message",
                "createdDateTime": "2023-01-01T00:00:00Z",
                "from": {"user": {"displayName": "User A"}},
                "body": {"contentType": "text", "content": "Hello world"}
            }
        ]
    }

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [mock_channels_response, mock_messages_response]
        
        result = await connector.list_documents(config)
        
        assert isinstance(result, ExternalDocumentList)
        assert len(result.documents) == 1
        doc = result.documents[0]
        assert doc.external_id == "chan123"
        assert doc.title == "General"
        assert "User A: Hello world" in doc.content

@pytest.mark.asyncio
async def test_teams_validate_config_success(connector, config):
    mock_channels_response = MagicMock()
    mock_channels_response.status_code = 200
    mock_channels_response.json.return_value = {
        "value": [{"id": "chan123", "displayName": "General"}]
    }

    mock_messages_response = MagicMock()
    mock_messages_response.status_code = 200
    mock_messages_response.json.return_value = {"value": []}

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [mock_channels_response, mock_messages_response]
        await connector.validate_config(config)
