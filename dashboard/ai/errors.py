"""Error hierarchy for the unified AI gateway."""


class AIError(Exception):
    """Base error for all AI gateway errors."""


class AIAuthError(AIError):
    """Authentication failed. Check API keys or ADC setup.

    For Vertex AI: run ``gcloud auth application-default login``
    For AI Studio: set ``GOOGLE_API_KEY``
    """


class AITimeoutError(AIError):
    """Request timed out."""


class AIQuotaError(AIError):
    """Rate limit or quota exceeded."""
