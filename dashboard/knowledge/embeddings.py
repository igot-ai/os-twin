"""Multi-provider embedding wrapper with lazy model load.

Supports provider backends:

- ``"ollama"`` — Local Ollama embedding server via the native ``ollama`` SDK.
- ``"openai-compatible"`` — Any OpenAI-compatible embedding API.
- ``"gemini"`` — Google Gemini embedding via litellm.

The provider is controlled by ``OSTWIN_KNOWLEDGE_EMBED_PROVIDER`` env var
or ``MasterSettings.knowledge.embedding_backend`` (via ``KnowledgeService``).

Importing this module is essentially free — no heavy deps at module load.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Any, Optional

from dashboard.knowledge.config import EMBEDDING_DIMENSION, EMBEDDING_MODEL, EMBEDDING_PROVIDER

logger = logging.getLogger(__name__)


class KnowledgeEmbedder:
    """Multi-provider embedding helper.

    Instances share the underlying model via a class-level cache keyed on
    (provider, model_name), so spinning up many `KnowledgeEmbedder()`s is cheap.

    Parameters
    ----------
    model_name:
        The embedding model name. For ``ollama`` this is the Ollama model ID.
        For ``openai-compatible`` this is the model ID expected by your server.
    provider:
        Embedding backend: ``"ollama"`` (default) or ``openai-compatible``.
    """

    # Class-level cache: {(provider, model_name): model/client instance}
    _model_cache: dict[str, Any] = {}
    _cache_lock = threading.Lock()

    def __init__(
        self,
        model_name: str | None = None,
        provider: str | None = None,
        compatible_url: str | None = None,
        compatible_key: str | None = None,
    ) -> None:
        self.model_name: str = model_name or EMBEDDING_MODEL
        self.provider: str = (provider or EMBEDDING_PROVIDER or "ollama").lower()
        # Only add hf.co/ prefix for ollama provider with slash in model name
        if self.provider == "ollama" and "/" in self.model_name and not self.model_name.startswith("hf.co/"):
            self.model_name = f"hf.co/{self.model_name}"
        self.compatible_url: str = compatible_url or ""
        self.compatible_key: str = compatible_key or ""
        self._dimension: int | None = None  # populated on first use

    # -- Lazy loading ---------------------------------------------------

    def _load_model(self) -> Any:
        """Load (or fetch from cache) the embedding model/client."""
        cache_key = f"{self.provider}:{self.model_name}"
        with KnowledgeEmbedder._cache_lock:
            cached = KnowledgeEmbedder._model_cache.get(cache_key)
            if cached is not None:
                return cached

        if self.provider == "ollama":
            model = self._load_ollama_marker()
        elif self.provider == "openai-compatible":
            model = self._load_openai_compatible_marker()
        elif self.provider == "gemini":
            model = self._load_gemini_marker()
        else:
            # Fallback: treat as ollama
            logger.warning(
                "Unknown embedding provider %r; falling back to ollama",
                self.provider,
            )
            model = self._load_ollama_marker()

        with KnowledgeEmbedder._cache_lock:
            KnowledgeEmbedder._model_cache[cache_key] = model
        return model

    def _load_sentence_transformer(self) -> Any:
        """Load a local sentence-transformers model."""
        from sentence_transformers import SentenceTransformer  # noqa: WPS433

        logger.info("Loading embedding model (sentence-transformer): %s", self.model_name)
        return SentenceTransformer(self.model_name)

    # -- Public API -----------------------------------------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns a list of float lists."""
        if not texts:
            return []

        if self.provider == "ollama":
            return self._embed_ollama(texts)
        elif self.provider == "openai-compatible":
            return self._embed_openai_compatible(texts)
        elif self.provider == "gemini":
            return self._embed_gemini(texts)
        else:
            return self._embed_ollama(texts)

    def embed_one(self, text: str) -> list[float]:
        """Embed a single text. Returns a list of floats."""
        if text is None:
            return []
        result = self.embed([text])
        return result[0] if result else []

    def dimension(self) -> int:
        """Return the embedding dimension (cached after first load)."""
        if self._dimension is not None:
            return self._dimension

        if self.provider == "ollama":
            self._dimension = self._dimension_ollama()
        elif self.provider == "openai-compatible":
            self._dimension = self._dimension_openai_compatible()
        elif self.provider == "gemini":
            self._dimension = self._dimension_gemini()
        else:
            self._dimension = self._dimension_ollama()

        return self._dimension

    # -- Ollama backend --------------------------------------------------

    def _load_ollama_marker(self) -> Any:
        """Return a sentinel; ollama SDK is called directly per-embed."""
        logger.info("Ollama embedding provider: model=%s", self.model_name)
        return True  # marker — ollama.embed() is stateless

    def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        """Embed using Ollama /api/embed endpoint directly."""
        import httpx as _httpx

        model_ref = self.model_name
        if not model_ref.startswith("hf.co/"):
            model_ref = f"hf.co/{model_ref}"
        if ":latest" not in model_ref:
            model_ref = f"{model_ref}:latest"

        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

        try:
            resp = _httpx.post(
                f"{ollama_url}/api/embed",
                json={"model": model_ref, "input": texts},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("embeddings", [[] for _ in texts])
        except Exception as exc:
            logger.error("Ollama embedding failed: %s", exc)
            return [[] for _ in texts]

    def _dimension_ollama(self) -> int:
        """Determine embedding dimension from Ollama by probing."""
        # Check known dimensions first
        _known = {
            "leoipulsar/harrier-0.6b": 1024,
            "embeddinggemma": 768,
            "qwen3-embedding:0.6b": 896,
        }
        dim = _known.get(self.model_name)
        if dim is not None:
            return dim
        try:
            result = self.embed_one("dimension probe")
            if result:
                dim = len(result)
                logger.info("Ollama embedding dimension detected: %d", dim)
                return dim
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not probe Ollama dimension: %s", exc)
        return EMBEDDING_DIMENSION

    # -- OpenAI-Compatible backend -----------------------------------------

    def _load_openai_compatible_marker(self) -> Any:
        """Return a sentinel; OpenAI-compatible API is called directly per-embed."""
        logger.info("OpenAI-compatible embedding provider: model=%s", self.model_name)
        return True  # marker — stateless HTTP calls

    def _embed_openai_compatible(self, texts: list[str]) -> list[list[float]]:
        """Embed using an OpenAI-compatible embedding API."""
        import httpx

        base_url = self.compatible_url or os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:8000")
        api_key = self.compatible_key or os.environ.get("OPENAI_COMPATIBLE_API_KEY", "")

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{base_url}/v1/embeddings",
                    headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
                    json={"model": self.model_name, "input": texts},
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()
                return [item["embedding"] for item in data["data"]]
        except Exception as exc:
            logger.error("OpenAI-compatible embedding failed: %s", exc)
            return [[] for _ in texts]

    def _dimension_openai_compatible(self) -> int:
        """Determine embedding dimension from OpenAI-compatible API by probing."""
        try:
            result = self.embed_one("dimension probe")
            if result:
                dim = len(result)
                logger.info("OpenAI-compatible embedding dimension detected: %d", dim)
                return dim
        except Exception as exc:
            logger.warning("Could not probe OpenAI-compatible dimension: %s", exc)
        return EMBEDDING_DIMENSION

    # -- Gemini backend --------------------------------------------------

    def _gemini_model_ref(self) -> str:
        """Return the litellm-compatible model name for Gemini."""
        name = self.model_name
        if name.startswith("gemini/"):
            return name
        if name.startswith("hf.co/"):
            name = name[len("hf.co/"):]
        return f"gemini/{name}"

    def _load_gemini_marker(self) -> Any:
        """Return a sentinel; litellm is called directly per-embed."""
        logger.info("Gemini embedding provider: model=%s", self.model_name)
        return True

    def _embed_gemini(self, texts: list[str]) -> list[list[float]]:
        """Embed using Gemini via litellm.embedding."""
        try:
            import litellm  # noqa: WPS433
        except ImportError as exc:
            logger.error("litellm not installed; cannot use gemini embeddings: %s", exc)
            return [[] for _ in texts]

        try:
            response = litellm.embedding(
                model=self._gemini_model_ref(),
                input=texts,
                dimensions=EMBEDDING_DIMENSION,
            )
            return [item["embedding"] for item in response.data]
        except Exception as exc:
            logger.error("Gemini embedding failed: %s", exc)
            return [[] for _ in texts]

    def _dimension_gemini(self) -> int:
        """Gemini embeddings are produced at EMBEDDING_DIMENSION via litellm."""
        return EMBEDDING_DIMENSION
