from typing import Dict, Type, Optional
from .base import BaseConnector

class ConnectorRegistry:
    """
    Registry for managing connector classes and their instances.
    """

    def __init__(self):
        self._registry: Dict[str, Type[BaseConnector]] = {}
        self._instances: Dict[str, BaseConnector] = {}

    def register(self, connector_class: Type[BaseConnector]) -> Type[BaseConnector]:
        """
        Registers a connector class.
        Usage: 
            @registry.register
            class MyConnector(BaseConnector): ...
        """
        # Create a temporary instance to access the config ID
        # (or assume the config is a class attribute)
        # Let's assume it's a class attribute for easier registration
        # But BaseConnector defines it as an abstract property.
        # We'll just instantiate it once to check or require it to be defined on the class.
        
        # Instantiate once to check ID (alternative: class-level config)
        # Since it's an ABC, we can't instantiate it directly.
        # Let's just trust the developer to provide a class that can be registered.
        # We will extract the ID by instantiating it.
        instance = connector_class()
        connector_id = instance.config.id
        self._registry[connector_id] = connector_class
        return connector_class

    def get_class(self, connector_id: str) -> Type[BaseConnector]:
        """
        Retrieves a connector class by ID.
        """
        if connector_id not in self._registry:
            raise KeyError(f"Connector '{connector_id}' is not registered.")
        return self._registry[connector_id]

    def get_instance(self, connector_id: str) -> BaseConnector:
        """
        Retrieves or creates a singleton instance of a connector.
        """
        if connector_id not in self._instances:
            connector_class = self.get_class(connector_id)
            self._instances[connector_id] = connector_class()
        return self._instances[connector_id]

    def list_connectors(self) -> Dict[str, Type[BaseConnector]]:
        """
        Returns all registered connector classes.
        """
        return self._registry.copy()

# Global registry instance
registry = ConnectorRegistry()
