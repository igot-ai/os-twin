import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from connectors.notion import NotionConnector
from connectors.models import ExternalDocumentList

@pytest.fixture
def connector():
    return NotionConnector()

@pytest.fixture
def config():
    return {
        "accessToken": "test-token",
        "scope": "workspace",
        "maxPages": "10"
    }

@pytest.mark.asyncio
async def test_notion_list_documents_workspace(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "object": "page",
                "id": "page1",
                "url": "https://notion.so/page1",
                "last_edited_time": "2023-01-01T00:00:00.000Z",
                "properties": {
                    "Name": {"type": "title", "title": [{"plain_text": "Test Page"}]}
                }
            }
        ],
        "next_cursor": None,
        "has_more": False
    }

    with patch("connectors.client.ConnectorHttpClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        result = await connector.list_documents(config)
        
        assert isinstance(result, ExternalDocumentList)
        assert len(result.documents) == 1
        doc = result.documents[0]
        assert doc.external_id == "page1"
        assert doc.title == "Test Page"
        assert doc.content_deferred is True

@pytest.mark.asyncio
async def test_notion_get_document(connector, config):
    mock_page_response = MagicMock()
    mock_page_response.status_code = 200
    mock_page_response.json.return_value = {
        "id": "page1",
        "url": "https://notion.so/page1",
        "last_edited_time": "2023-01-01T00:00:00.000Z",
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": "Test Page"}]}
        },
        "archived": False
    }

    mock_blocks_response = MagicMock()
    mock_blocks_response.status_code = 200
    mock_blocks_response.json.return_value = {
        "results": [
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Hello world"}]}
            }
        ],
        "next_cursor": None,
        "has_more": False
    }

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [mock_page_response, mock_blocks_response]
        
        result = await connector.get_document("page1", config)
        
        assert result.external_id == "page1"
        assert result.title == "Test Page"
        assert result.content == "Hello world"
        assert result.content_deferred is False

@pytest.mark.asyncio
async def test_notion_validate_config_success(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}

    with patch("connectors.client.ConnectorHttpClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        await connector.validate_config(config)
