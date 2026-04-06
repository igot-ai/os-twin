import pytest
from connectors.registry import ConnectorRegistry
from connectors.base import BaseConnector
from connectors.models import ConnectorConfig, ExternalDocument, ExternalDocumentList
from typing import Dict, Any, Optional

class MockConnector(BaseConnector):
    @property
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(
            id="mock",
            name="Mock",
            description="Mock connector",
            version="1.0.0",
            icon="mock-icon",
            authConfig={"mode": "apiKey"},
            configFields=[]
        )

    async def list_documents(self, config: Dict[str, Any], cursor: Optional[str] = None) -> ExternalDocumentList:
        return ExternalDocumentList(documents=[], hasMore=False)

    async def get_document(self, external_id: str, config: Dict[str, Any]) -> ExternalDocument:
        return ExternalDocument(
            externalId="1", title="1", content="1", mimeType="1", contentHash="1"
        )

    async def validate_config(self, config: Dict[str, Any]) -> None:
        pass

def test_registry_registration():
    reg = ConnectorRegistry()
    reg.register(MockConnector)
    
    assert reg.get_class("mock") == MockConnector
    assert isinstance(reg.get_instance("mock"), MockConnector)
    assert reg.get_instance("mock") is reg.get_instance("mock")  # Singleton behavior
    assert "mock" in reg.list_connectors()

def test_registry_not_found():
    reg = ConnectorRegistry()
    with pytest.raises(KeyError):
        reg.get_class("unknown")
    with pytest.raises(KeyError):
        reg.get_instance("unknown")
