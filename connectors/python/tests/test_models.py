import pytest
from connectors.models import (
    ConnectorAuthConfig, 
    ExternalDocument, 
    ExternalDocumentList, 
    SyncResult, 
    ConnectorConfig,
    ConnectorConfigField
)
from pydantic import ValidationError, TypeAdapter

def test_auth_config_oauth():
    data = {
        "mode": "oauth",
        "provider": "google",
        "requiredScopes": ["email", "profile"]
    }
    adapter = TypeAdapter(ConnectorAuthConfig)
    config = adapter.validate_python(data)
    assert config.mode == "oauth"
    assert config.provider == "google"
    assert config.required_scopes == ["email", "profile"]

def test_auth_config_api_key():
    data = {
        "mode": "apiKey",
        "label": "My Key",
        "placeholder": "Enter key here"
    }
    adapter = TypeAdapter(ConnectorAuthConfig)
    config = adapter.validate_python(data)
    assert config.mode == "apiKey"
    assert config.label == "My Key"

def test_external_document_aliases():
    data = {
        "externalId": "123",
        "title": "Test Doc",
        "content": "some content",
        "mimeType": "text/plain",
        "sourceUrl": "http://example.com",
        "contentHash": "abc",
        "contentDeferred": True,
        "metadata": {"key": "value"}
    }
    doc = ExternalDocument(**data)
    assert doc.external_id == "123"
    assert doc.mime_type == "text/plain"
    assert doc.source_url == "http://example.com"
    assert doc.content_hash == "abc"
    assert doc.content_deferred is True

def test_sync_result():
    res = SyncResult(docsAdded=5, docsUpdated=2, docsDeleted=1, docsUnchanged=10, docsFailed=0)
    assert res.docs_added == 5
    assert res.docs_updated == 2
    assert res.docs_deleted == 1
    assert res.docs_unchanged == 10
    assert res.docs_failed == 0

def test_connector_config():
    data = {
        "id": "test_con",
        "name": "Test Connector",
        "description": "Desc",
        "version": "1.0.0",
        "icon": "test-icon",
        "authConfig": {"mode": "apiKey"},
        "configFields": [
            {
                "id": "field1",
                "title": "Field 1",
                "type": "short-input"
            }
        ]
    }
    config = ConnectorConfig(**data)
    assert config.id == "test_con"
    assert config.auth_config.mode == "apiKey"
    assert len(config.config_fields) == 1
    assert config.config_fields[0].type == "short-input"
