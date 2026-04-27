from typing import Optional, List, Dict
import threading
from .providers.base import BasePromptProvider
from .exceptions import PromptNotFoundError

class PromptRegistry:
    def __init__(self, provider: BasePromptProvider):
        self.provider = provider
        self._lock = threading.RLock()
        self._cache: Dict[str, Dict[str, str]] = {}  # lang -> {key: template}

    def _normalize_lang(self, lang: str) -> str:
        if not lang:
            return "en"
        
        lang = lang.strip().lower()
        
        if lang in {"en", "eng", "english", "england"}: # English variants
            return "en"
        if lang in {"vi", "vn", "vietnamese", "vietnam", "tiếng việt"}: # Vietnamese variants
            return "vi"
        if lang in {"zh", "cn", "chinese", "中文", "mandarin", "zhongwen"}: # Chinese variants
            return "zh"
        if lang in {"es", "esp", "spanish", "español", "castellano"}: # Spanish variants
            return "es"
            
        return lang

    def get_prompt(self, key: str, lang: str) -> str:
        normalized_lang = self._normalize_lang(lang)
        with self._lock:
            template = self._get_from_cache_or_provider(key, normalized_lang) # Try normalized language
            if template is not None:
                return template
            
            if normalized_lang != "en": # Fallback to "en" if not already "en"
                template = self._get_from_cache_or_provider(key, "en")
                if template is not None:
                    return template
            
            raise PromptNotFoundError(key, lang)

    def _get_from_cache_or_provider(self, key: str, lang: str) -> Optional[str]:
        if lang in self._cache and key in self._cache[lang]: # Check cache first
            return self._cache[lang][key]

        template = self.provider.load(key, lang) # Load from provider
        if template is not None:
            if lang not in self._cache: # Update cache
                self._cache[lang] = {}
            self._cache[lang][key] = template
            return template
        
        return None

    def get_template(self, key: str, lang: str) -> str:
        """Alias for get_prompt to be explicit about getting the raw template."""
        return self.get_prompt(key, lang)

    def set_prompt(self, key: str, lang: str, template: str):
        normalized_lang = self._normalize_lang(lang)
        with self._lock:
            self.provider.save(key, normalized_lang, template)
            if normalized_lang not in self._cache:
                self._cache[normalized_lang] = {}
            self._cache[normalized_lang][key] = template

    def register_namespace(self, namespace: str, prompts: Dict[str, Dict[str, str]]):
        """
        Register multiple prompts for a namespace.
        prompts structure: {key_name: {lang: template}}
        """
        with self._lock:
            for name, lang_map in prompts.items():
                full_key = f"{namespace}.{name}" if namespace else name
                for lang, template in lang_map.items():
                    self.set_prompt(full_key, lang, template)

    def list_keys(self, language: str) -> List[str]:
        normalized_lang = self._normalize_lang(language)
        return self.provider.list_keys(normalized_lang)

    def list_languages(self) -> List[str]:
        return self.provider.list_languages()
