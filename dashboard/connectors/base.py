from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from .models import ExternalDocument, ExternalDocumentList, ConnectorConfig

class BaseConnector(ABC):
    """
    Abstract base class for all connectors.
    """

    @property
    @abstractmethod
    def config(self) -> ConnectorConfig:
        """
        Returns the static configuration for this connector.
        """
        pass

    @abstractmethod
    async def list_documents(
        self, 
        config: Dict[str, Any], 
        cursor: Optional[str] = None
    ) -> ExternalDocumentList:
        """
        Lists documents from the external source.
        Returns a paginated list of ExternalDocument.
        """
        pass

    @abstractmethod
    async def get_document(
        self, 
        external_id: str, 
        config: Dict[str, Any]
    ) -> ExternalDocument:
        """
        Fetches the full content of a specific document.
        Called when content_deferred is True in the list results.
        """
        pass

    @abstractmethod
    async def validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validates the user-provided configuration.
        Should raise an exception (or return a structured error) if invalid.
        """
        pass
