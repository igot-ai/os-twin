import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from connectors.outlook import OutlookConnector
from connectors.models import ExternalDocumentList

@pytest.fixture
def connector():
    return OutlookConnector()

@pytest.fixture
def config():
    return {
        "accessToken": "test-token",
        "folder": "inbox",
        "maxConversations": "10"
    }

@pytest.mark.asyncio
async def test_outlook_list_documents(connector, config):
    mock_messages_response = MagicMock()
    mock_messages_response.status_code = 200
    mock_messages_response.json.return_value = {
        "value": [
            {
                "id": "msg1",
                "conversationId": "conv1",
                "subject": "Test Email",
                "from": {"emailAddress": {"name": "Sender", "address": "sender@test.com"}},
                "receivedDateTime": "2023-01-01T00:00:00Z",
                "body": {"contentType": "text", "content": "Hello world"},
                "webLink": "https://outlook.com/msg1"
            }
        ]
    }

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_messages_response
        
        result = await connector.list_documents(config)
        
        assert isinstance(result, ExternalDocumentList)
        assert len(result.documents) == 1
        doc = result.documents[0]
        assert doc.external_id == "conv1"
        assert doc.title == "Test Email"
        assert "Hello world" in doc.content

@pytest.mark.asyncio
async def test_outlook_validate_config_success(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"value": []}

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        await connector.validate_config(config)
