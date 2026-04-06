import os
import sys
import json
import uuid
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, "/Users/paulaan/PycharmProjects/agent-os")

from dashboard.api import app
from dashboard.auth import get_current_user

client = TestClient(app)

# Mock the get_current_user dependency
def mock_get_current_user():
    return {"user_id": "test-user"}

app.dependency_overrides[get_current_user] = mock_get_current_user

@pytest.fixture
def mock_connector_data(tmp_path):
    # Set up a fake connectors.json in the isolated environment
    config_file = tmp_path / "connectors.json"
    os.environ["OSTWIN_CONNECTORS_CONFIG"] = str(config_file)
    
    initial_configs = [
        {
            "id": "inst-001",
            "connector_id": "mock",
            "name": "My Mock Instance",
            "enabled": True,
            "config": {"apiKey": "${vault:connector/inst-001/apiKey}", "settings": "value"}
        }
    ]
    config_file.write_text(json.dumps(initial_configs))
    yield config_file
    # Cleanup env var after test
    if "OSTWIN_CONNECTORS_CONFIG" in os.environ:
        del os.environ["OSTWIN_CONNECTORS_CONFIG"]

@pytest.fixture
def mock_registry():
    from dashboard.connectors.models import ConnectorConfig, ApiKeyAuthConfig, ConnectorConfigField
    from dashboard.connectors.base import BaseConnector
    
    class MockConnector(BaseConnector):
        @property
        def config(self) -> ConnectorConfig:
            return ConnectorConfig(
                id="mock",
                name="Mock",
                description="Mock connector",
                version="1.0.0",
                icon="mock-icon",
                authConfig=ApiKeyAuthConfig(mode="apiKey"),
                configFields=[
                    ConnectorConfigField(id="settings", title="Settings", type="short-input")
                ]
            )

        async def list_documents(self, config, cursor=None):
            from dashboard.connectors.models import ExternalDocumentList, ExternalDocument
            return ExternalDocumentList(
                documents=[ExternalDocument(externalId="1", title="Doc 1", content="Content", mimeType="text/plain", contentHash="abc")],
                hasMore=False
            )

        async def get_document(self, external_id, config):
            from dashboard.connectors.models import ExternalDocument
            return ExternalDocument(externalId=external_id, title=f"Doc {external_id}", content="Full content", mimeType="text/plain", contentHash="abc")

        async def validate_config(self, config):
            if config.get("apiKey") == "invalid":
                raise Exception("Invalid API Key")
            return None

    mock_reg = MagicMock()
    mock_reg.list_connectors.return_value = {"mock": MockConnector}
    mock_reg.get_instance.return_value = MockConnector()
    return mock_reg

@patch("dashboard.routes.connectors.registry")
def test_list_registry(mock_reg_internal, mock_registry):
    # We patch the 'registry' instance imported by connectors.py
    # Patch the registry imported by connectors route (from dashboard.connectors.registry)
    # So we need to patch it where it's used.
    with patch("dashboard.routes.connectors.registry", mock_registry):
        response = client.get("/api/connectors/registry")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "mock"

def test_list_instances(mock_connector_data):
    response = client.get("/api/connectors/instances")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "inst-001"
    # Vault references are not masked by _mask_sensitive_config as they start with ${
    assert data[0]["config"]["apiKey"] == "${vault:connector/inst-001/apiKey}"

@patch("dashboard.routes.connectors.registry")
@patch("dashboard.routes.connectors.get_vault")
def test_create_instance(mock_vault_getter, mock_reg_internal, mock_registry, mock_connector_data):
    mock_vault = MagicMock()
    mock_vault_getter.return_value = mock_vault
    
    with patch("dashboard.routes.connectors.registry", mock_registry):
        payload = {
            "connector_id": "mock",
            "name": "New Instance",
            "config": {"apiKey": "secret-token", "settings": "foo"},
            "store_in_vault": True
        }
        response = client.post("/api/connectors/instances", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Instance"
        # Since it's stored in vault, config[apiKey] will be a vault ref, which is not masked by _mask_sensitive_config
        assert data["config"]["apiKey"].startswith("${vault:connector/")
        
        # Check vault call
        mock_vault.set.assert_called()
        # Check config file
        with open(mock_connector_data, "r") as f:
            configs = json.load(f)
            assert len(configs) == 2
            assert configs[1]["config"]["apiKey"].startswith("${vault:")

def test_get_instance(mock_connector_data):
    response = client.get("/api/connectors/instances/inst-001")
    assert response.status_code == 200
    assert response.json()["id"] == "inst-001"

@patch("dashboard.routes.connectors.get_vault")
def test_delete_instance(mock_vault_getter, mock_connector_data):
    mock_vault = MagicMock()
    mock_vault_getter.return_value = mock_vault
    mock_vault.list_keys.return_value = ["apiKey"]
    
    response = client.delete("/api/connectors/instances/inst-001")
    assert response.status_code == 200
    
    with open(mock_connector_data, "r") as f:
        configs = json.load(f)
        assert len(configs) == 0
    
    # Check vault cleanup
    mock_vault.delete.assert_called_with("connector/inst-001", "apiKey")

@patch("dashboard.routes.connectors.registry")
@patch("dashboard.routes.connectors.ConfigResolver")
def test_validate_instance(mock_resolver_class, mock_reg_internal, mock_registry, mock_connector_data):
    mock_resolver = MagicMock()
    mock_resolver_class.return_value = mock_resolver
    mock_resolver.resolve.return_value = {"apiKey": "valid"}
    
    with patch("dashboard.routes.connectors.registry", mock_registry):
        response = client.post("/api/connectors/instances/inst-001/validate")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

@patch("dashboard.routes.connectors.registry")
@patch("dashboard.routes.connectors.ConfigResolver")
def test_list_documents(mock_resolver_class, mock_reg_internal, mock_registry, mock_connector_data):
    mock_resolver = MagicMock()
    mock_resolver_class.return_value = mock_resolver
    mock_resolver.resolve.return_value = {"apiKey": "valid"}
    
    with patch("dashboard.routes.connectors.registry", mock_registry):
        response = client.get("/api/connectors/instances/inst-001/documents")
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert len(data["documents"]) == 1
        assert data["documents"][0]["title"] == "Doc 1"
