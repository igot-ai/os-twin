import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from connectors.airtable import AirtableConnector
from connectors.models import ExternalDocumentList

@pytest.fixture
def connector():
    return AirtableConnector()

@pytest.fixture
def config():
    return {
        "accessToken": "test-token",
        "baseId": "appTestBase",
        "tableIdOrName": "Test Table",
        "maxRecords": "10"
    }

@pytest.mark.asyncio
async def test_airtable_list_documents(connector, config):
    mock_response_schema = MagicMock()
    mock_response_schema.status_code = 200
    mock_response_schema.json.return_value = {
        "tables": [
            {
                "id": "tblTest",
                "name": "Test Table",
                "fields": [{"id": "fld1", "name": "Name", "type": "singleLineText"}]
            }
        ]
    }

    mock_response_records = MagicMock()
    mock_response_records.status_code = 200
    mock_response_records.json.return_value = {
        "records": [
            {
                "id": "rec1",
                "fields": {"Name": "Test Record"},
                "createdTime": "2023-01-01T00:00:00.000Z"
            }
        ]
    }

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [mock_response_schema, mock_response_records]
        
        result = await connector.list_documents(config)
        
        assert isinstance(result, ExternalDocumentList)
        assert len(result.documents) == 1
        doc = result.documents[0]
        assert doc.external_id == "rec1"
        assert doc.title == "Test Record"
        assert "Name: Test Record" in doc.content

@pytest.mark.asyncio
async def test_airtable_validate_config_success(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"records": []}

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        await connector.validate_config(config)

@pytest.mark.asyncio
async def test_airtable_validate_config_failure(connector, config):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Table not found"

    with patch("connectors.client.ConnectorHttpClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        with pytest.raises(ValueError) as exc:
            await connector.validate_config(config)
        assert "not found" in str(exc.value)
