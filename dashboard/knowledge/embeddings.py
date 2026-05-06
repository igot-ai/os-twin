"""Multi-provider embedding wrapper with lazy model load.

Supports two provider backends:

- ``"sentence-transformer"`` (default) — local HuggingFace models via
  `sentence-transformers`. The actual model is only loaded on first call.
- ``"gemini"`` — Google Generative AI embeddings via ``google.genai``.
- ``"ollama"`` — Local Ollama embedding server via the native ``ollama`` SDK.
- ``"vertex"`` — Google Vertex AI embeddings via ``google.genai`` with
  ``EmbedContentConfig`` for task-type hinting.

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
        The embedding model name. For ``sentence-transformer`` this is a
        HuggingFace model ID. For ``gemini`` this is a Google model ID
        (e.g. ``text-embedding-004``).
    provider:
        Embedding backend: ``"sentence-transformer"`` (default) or ``"gemini"``.
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

        self.model_name: str = model_name or "BAAI/bge-base-en-v1.5"
        self.provider: str = (provider or "sentence-transformer").lower()
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

        if self.provider in ("sentence-transformer", "huggingface"):
            model = self._load_sentence_transformer()
        elif self.provider == "gemini":
            model = self._load_gemini_client()
        elif self.provider == "ollama":
            model = self._load_ollama_marker()
        elif self.provider == "vertex":
            model = self._load_vertex_client()
        else:
            # Fallback: treat as sentence-transformer
            logger.warning(
                "Unknown embedding provider %r; falling back to sentence-transformer",
                self.provider,
            )
            model = self._load_sentence_transformer()

        with KnowledgeEmbedder._cache_lock:
            KnowledgeEmbedder._model_cache[cache_key] = model
        return model

    def _load_sentence_transformer(self) -> Any:
        """Load a local sentence-transformers model."""
        from sentence_transformers import SentenceTransformer  # noqa: WPS433

        logger.info("Loading embedding model (sentence-transformer): %s", self.model_name)
        return SentenceTransformer(self.model_name)

    def _load_gemini_client(self) -> Any:
        """Create a Google GenAI client for Gemini embeddings."""
        from google import genai  # noqa: WPS433

        api_key = self._resolve_api_key("gemini")
        logger.info("Creating Gemini embedding client: model=%s", self.model_name)
        return genai.Client(api_key=api_key)

    def _resolve_api_key(self, provider: str) -> Optional[str]:
        """Resolve API key for the embedding provider."""
        from dashboard.llm_client import PROVIDER_API_KEYS  # noqa: WPS433

        # Standard env var
        env_name = PROVIDER_API_KEYS.get(provider) or PROVIDER_API_KEYS.get("google")
        if env_name:
            val = os.environ.get(env_name)
            if val:
                return val

        # master_agent vault fallback
        try:
            from dashboard.master_agent import get_api_key  # noqa: WPS433
            key = get_api_key(provider)
            if key:
                return key
        except Exception as exc:  # noqa: BLE001
            logger.debug("master_agent.get_api_key(%s) failed: %s", provider, exc)

        return None

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

        if self.provider in ("sentence-transformer", "huggingface"):
            raw_embeddings = self._embed_local(texts)
        elif self.provider == "gemini":
            raw_embeddings = self._embed_gemini(texts)
        elif self.provider == "ollama":
            raw_embeddings = self._embed_ollama(texts)
        elif self.provider == "vertex":
            raw_embeddings = self._embed_vertex(texts)
        else:
            raw_embeddings = self._embed_local(texts)
            
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

    # -- sentence-transformer backend -----------------------------------

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """Embed using local sentence-transformers model."""
        model = self._load_model()
        vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return [v.tolist() for v in vectors]

    def _dimension_local(self) -> int:
        """Always returns the global EMBEDDING_DIMENSION (768)."""
        return EMBEDDING_DIMENSION

    # -- Gemini backend -------------------------------------------------

    def _embed_gemini(self, texts: list[str]) -> list[list[float]]:
        """Embed using Google Gemini embedding API."""
        client = self._load_model()

        def _sync_embed():
            """Run Gemini embedding (sync API)."""
            result = client.models.embed_content(
                model=self.model_name,
                contents=texts,
            )
            # result.embeddings is a list of EmbedContentResponse.Embedding
            return [list(e.values) for e in result.embeddings]

        try:
            return _sync_embed()
        except Exception as exc:  # noqa: BLE001
            logger.error("Gemini embedding failed: %s", exc)
            return [[] for _ in texts]

    def _dimension_gemini(self) -> int:
        """Always returns the global EMBEDDING_DIMENSION (768)."""
        return EMBEDDING_DIMENSION

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

    # -- Vertex AI backend -----------------------------------------------

    def _load_vertex_client(self) -> Any:
        """Create a Google GenAI client for Vertex AI embeddings."""
        from google import genai  # noqa: WPS433

        api_key = self._resolve_api_key("google")
        logger.info("Creating Vertex AI embedding client: model=%s", self.model_name)
        return genai.Client(api_key=api_key) if api_key else genai.Client()

    def _embed_vertex(self, texts: list[str]) -> list[list[float]]:
        """Embed using Google Vertex AI via google.genai."""
        from google.genai.types import EmbedContentConfig  # noqa: WPS433

        client = self._load_model()

        def _sync_embed():
            """Run Vertex AI embedding (sync API)."""
            result = client.models.embed_content(
                model=self.model_name,
                contents=texts,
                config=EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                ),
            )
            return [list(e.values) for e in result.embeddings]

        try:
            return _sync_embed()
        except Exception as exc:  # noqa: BLE001
            logger.error("Vertex AI embedding failed: %s", exc)
            return [[] for _ in texts]

    def _dimension_vertex(self) -> int:
        """Always returns the global EMBEDDING_DIMENSION (768)."""
        return EMBEDDING_DIMENSION
