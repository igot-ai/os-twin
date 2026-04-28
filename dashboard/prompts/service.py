from typing import Optional, List, Dict, Any
from .registry import PromptRegistry
from .formatter import PromptFormatter
from .providers.base import BasePromptProvider
from .exceptions import PromptNotFoundError

class PromptService:
    def __init__(self, provider: BasePromptProvider, default_language: str = "en"):
        self.registry = PromptRegistry(provider)
        self.formatter = PromptFormatter()
        self.default_language = default_language

    def get(self, key: str, lang: Optional[str] = None, **kwargs) -> str:
        """
        Fetch a prompt template and format it with arguments.
        Falls back to default_language if not found in requested language.
        """
        template = self.get_template(key, lang)
        return self.formatter.format(template, **kwargs)

    def get_template(self, key: str, lang: Optional[str] = None) -> str:
        """
        Fetch the raw prompt template.
        Falls back to default_language if not found in requested language.
        """
        requested_lang = lang or self.default_language
        try:
            return self.registry.get_template(key, requested_lang)
        except PromptNotFoundError:
            if requested_lang != self.default_language:
                # Fallback to default language
                try:
                    return self.registry.get_template(key, self.default_language)
                except PromptNotFoundError:
                    raise PromptNotFoundError(key)
            else:
                raise

    def register(self, key: str, templates: Dict[str, str]):
        """Register a new prompt with multiple language templates."""
        for lang, template in templates.items():
            self.registry.set_prompt(key, lang, template)

    def set_default_language(self, language: str):
        self.default_language = language

    def list_keys(self, language: Optional[str] = None) -> List[str]:
        return self.registry.list_keys(language or self.default_language)

    def supports_language(self, language: str) -> bool:
        return language in self.registry.list_languages()
