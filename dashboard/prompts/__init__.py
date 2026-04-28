from .service import PromptService
from .providers.file_provider import FilePromptProvider
from .providers.memory_provider import MemoryPromptProvider
import os

# Initialize a default service instance
_default_locales_path = os.path.join(os.path.dirname(__file__), "locales")
default_provider = FilePromptProvider(_default_locales_path)
prompt_service = PromptService(default_provider)

__all__ = ["PromptService", "prompt_service"]
