from abc import ABC, abstractmethod
from typing import Optional, List

class BasePromptProvider(ABC):
    @abstractmethod
    def load(self, key: str, lang: str) -> Optional[str]:
        """Load a prompt template by key and language."""
        pass

    @abstractmethod
    def save(self, key: str, lang: str, template: str):
        """Save a prompt template."""
        pass

    @abstractmethod
    def exists(self, key: str, lang: str) -> bool:
        """Check if a prompt exists for a given key and language."""
        pass

    @abstractmethod
    def list_languages(self) -> List[str]:
        """List all available languages."""
        pass

    @abstractmethod
    def list_keys(self, lang: str) -> List[str]:
        """List all available keys for a given language."""
        pass
