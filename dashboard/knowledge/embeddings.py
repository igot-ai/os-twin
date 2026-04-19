"""sentence-transformers wrapper with lazy model load.

The actual model object is only constructed on first call to `embed`/`embed_one`,
so importing this module is essentially free.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from dashboard.knowledge.config import EMBEDDING_DIMENSION, EMBEDDING_MODEL

logger = logging.getLogger(__name__)


class KnowledgeEmbedder:
    """Wraps a sentence-transformers SentenceTransformer model.

    Instances share the underlying model via a class-level cache keyed on
    model_name, so spinning up many `KnowledgeEmbedder()`s is cheap.
    """

    # Class-level cache: {model_name: SentenceTransformer instance}
    _model_cache: dict[str, Any] = {}
    _cache_lock = threading.Lock()

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name: str = model_name or EMBEDDING_MODEL
        self._dimension: int | None = None  # populated on first use

    # -- Lazy loading ---------------------------------------------------

    def _load_model(self) -> Any:
        """Load (or fetch from cache) the sentence-transformers model."""
        with KnowledgeEmbedder._cache_lock:
            cached = KnowledgeEmbedder._model_cache.get(self.model_name)
            if cached is not None:
                return cached
        # Lazy import — this is the heavy bit.
        from sentence_transformers import SentenceTransformer  # noqa: WPS433

        logger.info("Loading embedding model: %s", self.model_name)
        model = SentenceTransformer(self.model_name)
        with KnowledgeEmbedder._cache_lock:
            KnowledgeEmbedder._model_cache[self.model_name] = model
        return model

    # -- Public API -----------------------------------------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns a list of float lists."""
        if not texts:
            return []
        model = self._load_model()
        # SentenceTransformer.encode returns numpy ndarray; convert to list[list[float]].
        vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return [v.tolist() for v in vectors]

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
        # Try config-default first to avoid forcing a model load.
        try:
            model = self._load_model()
            sentence_dim = model.get_sentence_embedding_dimension()
            self._dimension = int(sentence_dim) if sentence_dim else EMBEDDING_DIMENSION
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Could not determine embedder dimension dynamically: %s; using default %d",
                exc,
                EMBEDDING_DIMENSION,
            )
            self._dimension = EMBEDDING_DIMENSION
        return self._dimension
