import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from connectors.obsidian import ObsidianConnector
from connectors.models import ExternalDocumentList

@pytest.fixture
def connector():
    return ObsidianConnector()

@pytest.fixture
def config():
    return {
        "apiKey": "test-token",
        "vaultUrl": "https://127.0.0.1:27124",
        "folderPath": "Notes"
    }

@pytest.mark.asyncio
async def test_obsidian_list_documents(connector, config):
    # Mock list_directory for root and sub-folder
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "files": ["note1.md", "note2.md"]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await connector.list_documents(config)
        
        assert isinstance(result, ExternalDocumentList)
        assert len(result.documents) == 2
        doc = result.documents[0]
        assert doc.external_id == "Notes/note1.md"
        assert doc.title == "note1"
        assert doc.content_deferred is True

@pytest.mark.asyncio
async def test_obsidian_get_document(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": "# Test Note\nHello world",
        "tags": ["tag1", "tag2"],
        "frontmatter": {"author": "Tester"},
        "stat": {
            "ctime": 1672531200000,
            "mtime": 1672531200000,
            "size": 100
        }
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await connector.get_document("Notes/note1.md", config)
        
        assert result.external_id == "Notes/note1.md"
        assert "# Test Note" in result.content
        assert result.metadata["tags"] == ["tag1", "tag2"]
        assert result.metadata["frontmatter"]["author"] == "Tester"

@pytest.mark.asyncio
async def test_obsidian_validate_config_failure(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        with pytest.raises(ValueError) as exc:
            await connector.validate_config(config)
        assert "Invalid API key" in str(exc.value)
