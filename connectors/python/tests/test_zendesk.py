import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from connectors.zendesk import ZendeskConnector
from connectors.models import ExternalDocumentList

@pytest.fixture
def connector():
    return ZendeskConnector()

@pytest.fixture
def config():
    return {
        "apiKey": "test-token",
        "subdomain": "test",
        "email": "agent@test.com",
        "contentType": "articles"
    }

@pytest.mark.asyncio
async def test_zendesk_list_documents_articles(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "articles": [
            {
                "id": 1,
                "title": "Test Article",
                "body": "<p>Hello world</p>",
                "html_url": "https://test.zendesk.com/hc/articles/1",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z"
            }
        ],
        "next_page": None
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
async def test_zendesk_list_documents_tickets(connector, config):
    config["contentType"] = "tickets"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = [
        {
            "tickets": [
                {
                    "id": 1,
                    "subject": "Test Ticket",
                    "description": "<p>Problem</p>",
                    "status": "open",
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T00:00:00Z",
                    "tags": ["urgent"]
                }
            ],
            "next_page": None
        },
        {
            "comments": [
                {
                    "id": 1,
                    "body": "Comment 1",
                    "author_id": 123,
                    "created_at": "2023-01-01T01:00:00Z",
                    "public": True
                }
            ],
            "next_page": None
        }
    ]

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await connector.list_documents(config)
        
        assert len(result.documents) == 1
        doc = result.documents[0]
        assert doc.external_id == "ticket-1"
        assert "Test Ticket" in doc.title
        assert "Problem" in doc.content
        assert "Comment 1" in doc.content
        assert doc.metadata["type"] == "ticket"

@pytest.mark.asyncio
async def test_zendesk_validate_config_failure(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        with pytest.raises(Exception) as exc:
            await connector.validate_config(config)
        assert "401" in str(exc.value)
