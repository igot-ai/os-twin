import os
import yaml
from typing import Dict, Optional, List, Any
from .base import BasePromptProvider
from ..exceptions import ProviderError

class FilePromptProvider(BasePromptProvider):
    def __init__(self, locales_path: str):
        self.locales_path = locales_path
        self._cache: Dict[str, Dict[str, Any]] = {}  # language -> nested dict

    def _get_lang_file(self, lang: str) -> str:
        return os.path.join(self.locales_path, f"{lang}.yaml")

    def _load_file(self, lang: str) -> Dict[str, Any]:
        if lang in self._cache:
            return self._cache[lang]

        file_path = self._get_lang_file(lang)
        if not os.path.exists(file_path):
            return {}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                self._cache[lang] = data
                return data
        except Exception as e:
            raise ProviderError(f"Failed to load language file {file_path}: {e}")

    def _get_nested(self, data: Dict[str, Any], key: str) -> Optional[str]:
        parts = key.split(".")
        current = data
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        
        return current if isinstance(current, str) else None

    def load(self, key: str, lang: str) -> Optional[str]:
        data = self._load_file(lang)
        return self._get_nested(data, key)

    def save(self, key: str, lang: str, template: str):
        # For now, we only support memory updates for saving. 
        # Persistence to file can be added later if needed.
        data = self._load_file(lang)
        parts = key.split(".")
        current = data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = template
        self._cache[lang] = data

    def exists(self, key: str, lang: str) -> bool:
        return self.load(key, lang) is not None

    def list_languages(self) -> List[str]:
        if not os.path.exists(self.locales_path):
            return []
        return [f.split(".")[0] for f in os.listdir(self.locales_path) if f.endswith(".yaml")]

    def list_keys(self, lang: str) -> List[str]:
        data = self._load_file(lang)
        keys = []

        def _walk(d, prefix=""):
            for k, v in d.items():
                full_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    _walk(v, full_key)
                else:
                    keys.append(full_key)

        _walk(data)
        return keys
