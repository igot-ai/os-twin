import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from connectors.intercom import IntercomConnector
from connectors.models import ExternalDocumentList

@pytest.fixture
def connector():
    return IntercomConnector()

@pytest.fixture
def config():
    return {
        "apiKey": "test-token",
        "contentType": "articles",
        "articleState": "published",
        "maxItems": "10"
    }

@pytest.mark.asyncio
async def test_intercom_list_documents_articles(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "id": "1",
                "title": "Test Article",
                "body": "<p>Hello world</p>",
                "state": "published",
                "author_id": 123,
                "created_at": 1672531200,
                "updated_at": 1672531200
            }
        ],
        "pages": {"total_pages": 1}
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await connector.list_documents(config)
        
        assert isinstance(result, ExternalDocumentList)
        assert len(result.documents) == 1
        doc = result.documents[0]
        assert doc.external_id == "article-1"
        assert doc.title == "Test Article"
        assert "Hello world" in doc.content
        assert doc.metadata["type"] == "article"

@pytest.mark.asyncio
async def test_intercom_validate_config_success(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        await connector.validate_config(config)

@pytest.mark.asyncio
async def test_intercom_validate_config_failure(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        with pytest.raises(Exception) as exc:
            await connector.validate_config(config)
        assert "401" in str(exc.value)
