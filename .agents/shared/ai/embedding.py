"""Unified embedding — routes cloud vs local based on model prefix.

- ``"vertex_ai/..."`` or ``"gemini/..."`` → litellm → Vertex AI / AI Studio
- ``"local/..."`` → SentenceTransformer (on-device, ~5ms, free)
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional

from .config import get_config
from .errors import AIError

logger = logging.getLogger(__name__)

# Thread-safe cache for local SentenceTransformer models (one per model name)
_local_models: dict = {}
_local_lock = threading.Lock()


def _get_local_model(model_name: str):
    """Lazy-load and cache a SentenceTransformer model."""
    if model_name in _local_models:
        return _local_models[model_name]

    with _local_lock:
        # Double-check after acquiring lock
        if model_name in _local_models:
            return _local_models[model_name]

        from sentence_transformers import SentenceTransformer

        logger.info("Loading local embedding model: %s", model_name)
        _local_models[model_name] = SentenceTransformer(model_name)
        return _local_models[model_name]


def embed(
    texts: List[str],
    *,
    model: Optional[str] = None,
) -> List[List[float]]:
    """Convert texts to embedding vectors.

    Args:
        texts: List of strings to embed.
        model: Model identifier.  Routing:
            - ``"local/<name>"`` → SentenceTransformer (on-device)
            - ``"vertex_ai/<name>"`` → Vertex AI Embedding API
            - ``"gemini/<name>"`` → AI Studio Embedding API
            - ``None`` → config default (cloud embedding model)

    Returns:
        List of float lists, one per input text.
    """
    if not texts:
        return []

    cfg = get_config()
    model = model or cfg.full_cloud_embedding_model()

    if model.startswith("local/"):
        return _embed_local(texts, model[len("local/") :])
    else:
        return _embed_cloud(texts, model)


def _embed_local(texts: List[str], model_name: str) -> List[List[float]]:
    """Embed using a local SentenceTransformer model."""
    from .monitor import record_embedding
    import time as _time

    model_ref = f"local/{model_name}"
    t0 = _time.time()
    try:
        st_model = _get_local_model(model_name)
        vectors = st_model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        latency = (_time.time() - t0) * 1000
        record_embedding(model_ref, len(texts), latency)
        return vectors.tolist()
    except Exception as exc:
        latency = (_time.time() - t0) * 1000
        record_embedding(model_ref, len(texts), latency, success=False, error=str(exc))
        raise AIError(f"Local embedding failed ({model_name}): {exc}") from exc


def _embed_cloud(texts: List[str], model: str) -> List[List[float]]:
    """Embed using litellm (Vertex AI or AI Studio)."""
    from .monitor import record_embedding
    import time as _time
    import litellm

    t0 = _time.time()
    try:
        response = litellm.embedding(model=model, input=texts)
        latency = (_time.time() - t0) * 1000
        record_embedding(model, len(texts), latency)
        return [item["embedding"] for item in response.data]
    except Exception as exc:
        latency = (_time.time() - t0) * 1000
        record_embedding(model, len(texts), latency, success=False, error=str(exc))
        raise AIError(f"Cloud embedding failed ({model}): {exc}") from exc
