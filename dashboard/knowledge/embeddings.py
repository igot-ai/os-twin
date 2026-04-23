"""Knowledge embedding via shared.ai gateway.

Routes to local SentenceTransformer via shared.ai.get_embedding().
Model lazy-loading and caching handled by the gateway.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dashboard.knowledge.config import EMBEDDING_DIMENSION, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Ensure shared.ai is importable
_agents_dir = str(Path(__file__).resolve().parent.parent.parent / ".agents")
if _agents_dir not in sys.path:
    sys.path.insert(0, _agents_dir)


class KnowledgeEmbedder:
    """Routes embedding calls through shared.ai.

    Uses ``local/<model_name>`` prefix so the gateway runs
    SentenceTransformer on-device (fast, free, offline).
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name: str = model_name or EMBEDDING_MODEL
        self._model_ref = f"local/{self.model_name}"
        self._dimension: int | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns a list of float lists."""
        if not texts:
            return []
        from shared.ai import get_embedding

        return get_embedding(texts, model=self._model_ref)

    def embed_one(self, text: str) -> list[float]:
        """Embed a single text. Returns a list of floats."""
        if text is None:
            return []
        result = self.embed([text])
        return result[0] if result else []

    def dimension(self) -> int:
        """Return the embedding dimension (cached after first call)."""
        if self._dimension is not None:
            return self._dimension
        try:
            test_vec = self.embed(["test"])
            self._dimension = len(test_vec[0]) if test_vec else EMBEDDING_DIMENSION
        except Exception as exc:
            logger.warning(
                "Could not determine embedder dimension: %s; using default %d",
                exc,
                EMBEDDING_DIMENSION,
            )
            self._dimension = EMBEDDING_DIMENSION
        return self._dimension
