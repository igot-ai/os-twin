from typing import Optional, List
from .base import BasePromptProvider

class DatabasePromptProvider(BasePromptProvider):
    """Stub for future database-backed prompt storage."""
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string

    def load(self, key: str, lang: str) -> Optional[str]:
        return None

    def save(self, key: str, lang: str, template: str):
        pass

    def exists(self, key: str, lang: str) -> bool:
        return False

    def list_languages(self) -> List[str]:
        return []

    def list_keys(self, lang: str) -> List[str]:
        return []
