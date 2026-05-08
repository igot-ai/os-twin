from typing import Dict, Optional, List
from .base import BasePromptProvider

class MemoryPromptProvider(BasePromptProvider):
    def __init__(self):
        # Structure: {language: {key: template}}
        self._prompts: Dict[str, Dict[str, str]] = {}

    def load(self, key: str, lang: str) -> Optional[str]:
        return self._prompts.get(lang, {}).get(key)

    def save(self, key: str, lang: str, template: str):
        if lang not in self._prompts:
            self._prompts[lang] = {}
        self._prompts[lang][key] = template

    def exists(self, key: str, lang: str) -> bool:
        return key in self._prompts.get(lang, {})

    def list_languages(self) -> List[str]:
        return list(self._prompts.keys())

    def list_keys(self, lang: str) -> List[str]:
        return list(self._prompts.get(lang, {}).keys())
