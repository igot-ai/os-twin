"""Multi-provider embedding wrapper with lazy model load.

Supports provider backends:

- ``"ollama"`` — Local Ollama embedding server via the native ``ollama`` SDK.
- ``"openai-compatible"`` — Any OpenAI-compatible embedding API.

The provider is controlled by ``OSTWIN_KNOWLEDGE_EMBED_PROVIDER`` env var
or ``MasterSettings.knowledge.embedding_backend`` (via ``KnowledgeService``).

Importing this module is essentially free — no heavy deps at module load.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

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
    
    # Semaphore to limit concurrent Ollama embedding requests and prevent
    # thermal stress from sustained GPU/CPU load during parallel plan execution.
    _ollama_embed_semaphore = threading.Semaphore(2)

    def __init__(
        self,
        model_name: str | None = None,
        provider: str | None = None,
    ) -> None:
        # Load from MasterSettings if not explicitly provided
        from dashboard.lib.settings.resolver import get_settings_resolver

        resolver = get_settings_resolver()
        master = resolver.get_master_settings()
        knowledge_cfg = master.knowledge if master.knowledge else None

        if provider is None:
            provider = (
                knowledge_cfg.knowledge_embedding_backend
                if knowledge_cfg and knowledge_cfg.knowledge_embedding_backend
                else EMBEDDING_PROVIDER
            )
            
        if model_name is None:
            model_name = (
                knowledge_cfg.knowledge_embedding_model
                if knowledge_cfg and knowledge_cfg.knowledge_embedding_model
                else EMBEDDING_MODEL
            )
            
        dimension = (
            knowledge_cfg.knowledge_embedding_dimension
            if knowledge_cfg and getattr(knowledge_cfg, "knowledge_embedding_dimension", None)
            else EMBEDDING_DIMENSION
        )
        
        self.openai_compatible_url = (
            knowledge_cfg.knowledge_embedding_compatible_url
            if knowledge_cfg and getattr(knowledge_cfg, "knowledge_embedding_compatible_url", "")
            else ""
        )
        
        self.openai_compatible_key = (
            knowledge_cfg.knowledge_embedding_compatible_key
            if knowledge_cfg and getattr(knowledge_cfg, "knowledge_embedding_compatible_key", "")
            else ""
        )

        self.model_name: str = model_name or EMBEDDING_MODEL
        self.provider: str = (provider or EMBEDDING_PROVIDER or "ollama").lower()
        if self.provider == "ollama" and "/" in self.model_name and not self.model_name.startswith("hf.co/"):
            self.model_name = f"hf.co/{self.model_name}"
            
        self._target_dimension: int = int(dimension)
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

    # -- Public API -----------------------------------------------------

    def _truncate_to_dim(self, embeddings: list[list[float]], dim: int = EMBEDDING_DIMENSION) -> list[list[float]]:
        """Truncate (or zero-pad) each embedding vector to exactly *dim* floats.
        
        Truncation of MRL (Matryoshka Representation Learning) models is
        dimension-preserving. Zero-padding is a lossy fallback for models whose
        native dimension is smaller than the target.
        """
        out: list[list[float]] = []
        for vec in embeddings:
            if len(vec) >= dim:
                out.append(vec[:dim])
            else:
                out.append(vec + [0.0] * (dim - len(vec)))
        return out

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns a list of float lists (normalized to dimension)."""
        if not texts:
            return []

        if self.provider == "ollama":
            raw_embeddings = self._embed_ollama(texts)
        elif self.provider == "openai-compatible":
            raw_embeddings = self._embed_openai_compatible(texts)
        else:
            raw_embeddings = self._embed_ollama(texts)
            
        return self._truncate_to_dim(raw_embeddings, self.dimension())

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

        # Always return the explicitly configured target dimension
        self._dimension = self._target_dimension

        return self._dimension

    # -- Ollama backend --------------------------------------------------

    def _load_ollama_marker(self) -> Any:
        """Return a sentinel; ollama SDK is called directly per-embed."""
        logger.info("Ollama embedding provider: model=%s", self.model_name)
        return True  # marker — ollama.embed() is stateless

    def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        """Embed using the native Ollama SDK."""
        import ollama as _ollama  # noqa: WPS433

        try:
            with self._ollama_embed_semaphore:
                response = _ollama.embed(model=self.model_name, input=texts)
            return response["embeddings"]
        except Exception as exc:  # noqa: BLE001
            logger.error("Ollama embedding failed: %s", exc)
            return [[] for _ in texts]

    def _dimension_ollama(self) -> int:
        """Always returns the global EMBEDDING_DIMENSION (768)."""
        return EMBEDDING_DIMENSION

    # -- OpenAI-Compatible backend -----------------------------------------

    def _load_openai_compatible_marker(self) -> Any:
        """Return a sentinel; OpenAI-compatible API is called directly per-embed."""
        logger.info("OpenAI-compatible embedding provider: model=%s", self.model_name)
        return True  # marker — stateless HTTP calls

    def _embed_openai_compatible(self, texts: list[str]) -> list[list[float]]:
        """Embed using an OpenAI-compatible embedding API."""
        import os as _os
        import httpx

        base_url = self.openai_compatible_url or _os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:8000")
        api_key = self.openai_compatible_key or _os.environ.get("OPENAI_COMPATIBLE_API_KEY", "")

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
        """Always returns the global EMBEDDING_DIMENSION (768)."""
        return EMBEDDING_DIMENSION
