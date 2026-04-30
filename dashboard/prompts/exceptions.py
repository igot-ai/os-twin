class PromptError(Exception):
    """Base class for prompt-related errors."""
    pass

class PromptNotFoundError(PromptError):
    """Raised when a prompt key is not found."""
    def __init__(self, key: str, language: str = None):
        self.key = key
        self.language = language
        msg = f"Prompt key '{key}' not found"
        if language:
            msg += f" for language '{language}'"
        super().__init__(msg)

class PromptValidationError(PromptError):
    """Raised when prompt formatting fails."""
    pass

class ProviderError(PromptError):
    """Raised when a prompt provider encounters an error."""
    pass
