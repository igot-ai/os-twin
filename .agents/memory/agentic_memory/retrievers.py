"""Retriever backends for the Agentic Memory vector store.

Provides ChromaDB and Zvec retriever implementations with pluggable
embedding functions (SentenceTransformer local, Gemini API).

Memory-management design:
- Heavy ML imports (sentence_transformers, nltk, sklearn, litellm) are
  lazy-loaded on first use, not at module level (F11).
- Embedding functions cache the model and defer loading until first call (F1/F9).
- ZvecRetriever holds a single persistent collection handle; zvec handles concurrency internally.
- Embedding dimension is cached per model to avoid test-embedding calls (F9).
"""

from typing import List, Dict, Any, Optional, Union, Protocol, runtime_checkable
import os
import json
import logging
import threading

logger = logging.getLogger(__name__)

# --- Lazy imports ---------------------------------------------------------
# Per-backend lazy loading to avoid importing all ML libraries when only
# one backend is used.  Previously _ensure_retriever_imports() pulled in
# PyTorch (~800MB) even when the configured backend was Ollama.

_retriever_imports_done = False
_tokenizer_imports_done = False
_import_lock = threading.Lock()

# Sentinel — the *module-level* names stay None until lazy-loaded.
SentenceTransformer = None
BM25Okapi = None
word_tokenize = None
cosine_similarity = None
np = None
litellm = None


def _ensure_tokenizer_imports():
    """Import lightweight tokenizer + numpy (no PyTorch / ML models)."""
    global _tokenizer_imports_done, BM25Okapi, word_tokenize, cosine_similarity, np

    if _tokenizer_imports_done:
        return

    with _import_lock:
        if _tokenizer_imports_done:
            return

        from rank_bm25 import BM25Okapi as _BM
        from nltk.tokenize import word_tokenize as _wt
        from sklearn.metrics.pairwise import cosine_similarity as _cs
        import numpy as _np

        BM25Okapi = _BM
        word_tokenize = _wt
        cosine_similarity = _cs
        np = _np
        _tokenizer_imports_done = True


def _ensure_sentence_transformer_imports():
    """Import SentenceTransformer + litellm (heavy — loads PyTorch ~800MB)."""
    global _retriever_imports_done, SentenceTransformer, litellm

    if _retriever_imports_done:
        return

    _ensure_tokenizer_imports()

    with _import_lock:
        if _retriever_imports_done:
            return

        from sentence_transformers import SentenceTransformer as _ST
        import litellm as _lt

        SentenceTransformer = _ST
        litellm = _lt
        _retriever_imports_done = True


def _ensure_retriever_imports():
    """Legacy compat shim — loads ALL heavy ML libraries.

    Prefer the per-backend variants (_ensure_tokenizer_imports,
    _ensure_sentence_transformer_imports) when you know which
    backend is in use.
    """
    _ensure_sentence_transformer_imports()


@runtime_checkable
class EmbeddingFunction(Protocol):
    """Protocol for embedding functions (avoiding chromadb import)."""

    def __call__(self, input: List[str]) -> List[List[float]]: ...


Documents = List[str]
Embeddings = List[List[float]]


def simple_tokenize(text):
    _ensure_tokenizer_imports()
    return word_tokenize(text)


# --- Global embedding dimension -------------------------------------------
# All backends MUST produce vectors of this dimension to avoid conflicts
# when storing / querying a single vector collection.  Backends that natively
# support output-dimensionality (Vertex, Gemini) pass it explicitly; others
# (Ollama, SentenceTransformer) truncate after embedding.
EMBEDDING_DIMENSION: int = 768


# --- Embedding function singleton cache -----------------------------------
# Keyed by (backend, model_name) so each unique model is loaded exactly once
# when shared=True (default).

_embedding_cache: Dict[tuple, Any] = {}
_embedding_cache_lock = threading.Lock()

# Native model dimensions (before truncation) — avoids a test embedding call (F9).
# NOTE: at runtime every backend is normalised to EMBEDDING_DIMENSION.
_KNOWN_DIMENSIONS: Dict[str, int] = {
    "all-MiniLM-L6-v2": 384,
    "all-MiniLM-L12-v2": 384,
    "all-mpnet-base-v2": 768,
    "paraphrase-MiniLM-L6-v2": 384,
    "paraphrase-multilingual-MiniLM-L12-v2": 384,
    "gemini-embedding-001": 768,
    "gemini/gemini-embedding-001": 768,
    "text-embedding-004": 768,
    # Ollama embedding models (native dims — truncated to 768 at runtime)
    "leoipulsar/harrier-0.6b": 1024,
    "embeddinggemma": 768,
    "qwen3-embedding:0.6b": 896,
    # Vertex AI models
    "text-embedding-005": 768,
}


def _truncate_to_dim(embeddings: Embeddings, dim: int = EMBEDDING_DIMENSION) -> Embeddings:
    """Truncate (or zero-pad) each embedding vector to exactly *dim* floats.

    Truncation of MRL (Matryoshka Representation Learning) models is
    dimension-preserving: the first *dim* components retain full semantic
    quality.  Zero-padding is a lossy fallback for models whose native
    dimension is smaller than the target.
    """
    out: Embeddings = []
    for vec in embeddings:
        if len(vec) >= dim:
            out.append(vec[:dim])
        else:
            out.append(vec + [0.0] * (dim - len(vec)))
    return out


class GeminiEmbeddingFunction(EmbeddingFunction):
    """Gemini embedding function via litellm.

    Always produces ``EMBEDDING_DIMENSION``-wide vectors by passing
    ``dimensions=EMBEDDING_DIMENSION`` to litellm and truncating as a
    safety net.
    """

    def __init__(self, model_name: str = "gemini-embedding-001"):
        self.model_name = (
            f"gemini/{model_name}"
            if not model_name.startswith("gemini/")
            else model_name
        )

    def __call__(self, input: Documents) -> Embeddings:
        _ensure_retriever_imports()
        response = litellm.embedding(
            model=self.model_name,
            input=input,
            dimensions=EMBEDDING_DIMENSION,
        )
        result = [item["embedding"] for item in response.data]
        return _truncate_to_dim(result)

    @property
    def dimension(self) -> int:
        """Always returns the global EMBEDDING_DIMENSION (768)."""
        return EMBEDDING_DIMENSION


class SentenceTransformerEmbedding(EmbeddingFunction):
    """SentenceTransformer embedding function with true lazy model loading.

    Output is always truncated/padded to ``EMBEDDING_DIMENSION`` (768).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None

    def _ensure_model(self):
        """Import and load the SentenceTransformer model on first use."""
        if self._model is not None:
            return self._model
        _ensure_retriever_imports()
        from sentence_transformers import SentenceTransformer as _ST
        self._model = _ST(self._model_name)
        return self._model

    def __call__(self, input: Documents) -> Embeddings:
        model = self._ensure_model()
        result = model.encode(input).tolist()
        return _truncate_to_dim(result)

    @property
    def dimension(self) -> int:
        """Always returns the global EMBEDDING_DIMENSION (768)."""
        return EMBEDDING_DIMENSION

    def close(self):
        """Release the underlying model to free GPU/CPU memory."""
        if self._model is not None:
            del self._model
            self._model = None


# Backward-compatible alias
SentenceTransformerEmbeddingFunction = SentenceTransformerEmbedding


# Semaphore to limit concurrent Ollama embedding requests and prevent
# thermal stress from sustained GPU/CPU load during parallel plan execution.
_ollama_embed_semaphore = threading.Semaphore(2)


class OllamaEmbeddingFunction(EmbeddingFunction):
    """Ollama embedding function via the native ``ollama`` Python SDK.

    Output is always truncated to ``EMBEDDING_DIMENSION`` (768) to ensure
    consistency across all backends.  No litellm dependency.

    Concurrent calls are gated by a module-level semaphore to prevent
    thermal stress on machines with limited cooling (e.g. MacBooks).
    """

    def __init__(
        self,
        model_name: str = "leoipulsar/harrier-0.6b",
        base_url: Optional[str] = None,
    ):
        self._model_name = model_name
        self._base_url = base_url  # None → ollama default (localhost:11434)

    def __call__(self, input: Documents) -> Embeddings:
        import ollama as _ollama  # noqa: WPS433 — lazy import

        kwargs: Dict[str, Any] = {"model": self._model_name, "input": input}
        with _ollama_embed_semaphore:
            if self._base_url:
                client = _ollama.Client(host=self._base_url)
                response = client.embed(**kwargs)
            else:
                response = _ollama.embed(**kwargs)

        result = response["embeddings"]
        return _truncate_to_dim(result)

    @property
    def dimension(self) -> int:
        """Always returns the global EMBEDDING_DIMENSION (768)."""
        return EMBEDDING_DIMENSION


class VertexEmbeddingFunction(EmbeddingFunction):
    """Google Vertex AI embedding function via ``google.genai``.

    Always requests ``output_dimensionality=EMBEDDING_DIMENSION`` (768)
    from the API, and truncates as a safety net.  No litellm dependency.
    """

    def __init__(
        self,
        model_name: str = "gemini-embedding-001",
        task_type: str = "RETRIEVAL_DOCUMENT",
    ):
        self._model_name = model_name
        self._task_type = task_type
        self._client = None

    def _ensure_client(self):
        """Lazy-create the google.genai Client."""
        if self._client is not None:
            return self._client
        from google import genai  # noqa: WPS433
        api_key = os.getenv("GOOGLE_API_KEY")
        self._client = genai.Client(api_key=api_key) if api_key else genai.Client()
        return self._client

    def __call__(self, input: Documents) -> Embeddings:
        from google.genai.types import EmbedContentConfig  # noqa: WPS433

        client = self._ensure_client()
        response = client.models.embed_content(
            model=self._model_name,
            contents=input,
            config=EmbedContentConfig(
                task_type=self._task_type,
                output_dimensionality=EMBEDDING_DIMENSION,
            ),
        )

        result = [list(e.values) for e in response.embeddings]
        return _truncate_to_dim(result)

    @property
    def dimension(self) -> int:
        """Always returns the global EMBEDDING_DIMENSION (768)."""
        return EMBEDDING_DIMENSION


def _create_embedding_function(
    embedding_backend: str,
    model_name: str,
    *,
    shared: bool = True,
):
    """Create or retrieve a cached embedding function.

    Args:
        embedding_backend: "sentence-transformer" or "gemini"
        model_name: Model identifier
        shared: If True (default), return a singleton instance cached by
            (backend, model_name).  Set False to get a private instance.

    Returns:
        An embedding function callable.
    """
    # Normalise backend aliases
    if embedding_backend in ("sentence-transformer", "huggingface"):
        embedding_backend = "sentence-transformer"

    cache_key = (embedding_backend, model_name)

    if shared:
        with _embedding_cache_lock:
            cached = _embedding_cache.get(cache_key)
            if cached is not None:
                return cached

    if embedding_backend == "gemini":
        fn = GeminiEmbeddingFunction(model_name=model_name)
    elif embedding_backend == "ollama":
        fn = OllamaEmbeddingFunction(model_name=model_name)
    elif embedding_backend == "vertex":
        fn = VertexEmbeddingFunction(model_name=model_name)
    else:
        fn = SentenceTransformerEmbedding(model_name=model_name)

    if shared:
        with _embedding_cache_lock:
            # Double-check: another thread may have created it
            existing = _embedding_cache.get(cache_key)
            if existing is not None:
                if hasattr(fn, "close"):
                    fn.close()
                return existing
            _embedding_cache[cache_key] = fn

    return fn


def _parse_json_field(metadata: Dict, field: str) -> list:
    """Parse a metadata field that may be a list or JSON string, returning a list."""
    value = metadata.get(field)
    if not value:
        return []
    if isinstance(value, list):
        return value
    return json.loads(value)


def _build_enhanced_document(document: str, metadata: Dict) -> str:
    """Build an enhanced document string by appending context, keywords, and tags."""
    summary = metadata.get("summary")
    enhanced = summary if summary else document

    if "context" in metadata and metadata["context"] != "General":
        enhanced += f" context: {metadata['context']}"

    keywords = _parse_json_field(metadata, "keywords")
    if keywords:
        enhanced += f" keywords: {', '.join(str(k) for k in keywords)}"

    tags = _parse_json_field(metadata, "tags")
    if tags:
        enhanced += f" tags: {', '.join(str(t) for t in tags)}"

    return enhanced


def _serialize_metadata(metadata: Dict) -> Dict[str, str]:
    """Convert metadata values to ChromaDB-compatible string format."""
    processed = {}
    for key, value in metadata.items():
        if isinstance(value, (list, dict)):
            processed[key] = json.dumps(value)
        else:
            processed[key] = str(value)
    return processed


def _deserialize_json_value(value: str) -> Any:
    """Try to parse a string as JSON list/dict, or as a number."""
    try:
        if value.startswith("[") or value.startswith("{"):
            return json.loads(value)
    except ValueError:
        pass
    return value


class ChromaRetriever:
    """Vector database retrieval using ChromaDB (lazy import)."""

    def __init__(
        self,
        collection_name: str = "memories",
        model_name: str = "all-MiniLM-L6-v2",
        persist_dir: str = None,
        embedding_backend: str = "sentence-transformer",
    ):
        """Initialize ChromaDB retriever.

        Args:
            collection_name: Name of the ChromaDB collection
            model_name: Name of the embedding model
            persist_dir: Directory for persistent storage. If None, uses in-memory mode.
            embedding_backend: "sentence-transformer" or "gemini"
        """
        import chromadb
        from chromadb.config import Settings

        if persist_dir:
            self.client = chromadb.PersistentClient(path=persist_dir)
        else:
            self.client = chromadb.Client(Settings(allow_reset=True))
        self.persist_dir = persist_dir

        self.embedding_function = _create_embedding_function(
            embedding_backend, model_name
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name, embedding_function=self.embedding_function
        )

    def close(self):
        """Release resources held by this retriever.

        Note: the embedding function is shared (singleton) and is NOT
        closed here — it may be in use by other retrievers.
        """
        self.collection = None
        self.client = None

    def add_document(self, document: str, metadata: Dict, doc_id: str):
        """Add a document to ChromaDB with enhanced embedding using metadata.

        Args:
            document: Text content to add
            metadata: Dictionary of metadata including keywords, tags, context
            doc_id: Unique identifier for the document
        """
        enhanced_document = _build_enhanced_document(document, metadata)
        processed_metadata = _serialize_metadata(metadata)
        processed_metadata["enhanced_content"] = enhanced_document

        self.collection.add(
            documents=[enhanced_document], metadatas=[processed_metadata], ids=[doc_id]
        )

    def clear(self):
        """Delete all documents and recreate the collection."""
        self.client.delete_collection("memories")
        self.collection = self.client.get_or_create_collection(
            name="memories", embedding_function=self.embedding_function
        )

    def has_document(self, doc_id: str) -> bool:
        """Check if a document exists in ChromaDB."""
        results = self.collection.get(ids=[doc_id])
        return bool(results and results.get("ids"))

    def existing_ids(self, doc_ids: List[str]) -> set:
        """Return the subset of *doc_ids* that exist in the collection."""
        if not doc_ids:
            return set()
        results = self.collection.get(ids=doc_ids)
        return set(results.get("ids", []))

    def get_stored_hashes(self, doc_ids: List[str]) -> Dict[str, Optional[str]]:
        """Return {doc_id: content_hash} for each ID. Missing IDs omitted."""
        if not doc_ids:
            return {}
        results = self.collection.get(ids=doc_ids, include=["metadatas"])
        out: Dict[str, Optional[str]] = {}
        for i, did in enumerate(results.get("ids", [])):
            meta = (
                (results.get("metadatas") or [])[i] if results.get("metadatas") else {}
            )
            out[did] = (meta or {}).get("content_hash")
        return out

    def delete_document(self, doc_id: str):
        """Delete a document from ChromaDB.

        Args:
            doc_id: ID of document to delete
        """
        self.collection.delete(ids=[doc_id])

    @staticmethod
    def _deserialize_metadata_value(value):
        """Attempt to deserialize a single metadata value from its string representation.

        Converts JSON strings back to lists/dicts and numeric strings back to
        int/float.  Returns the original value unchanged on failure.
        """
        if not isinstance(value, str):
            return value
        parsed = _deserialize_json_value(value)
        if parsed is not value:
            return parsed
        if value.replace(".", "", 1).isdigit():
            return float(value) if "." in value else int(value)
        return value

    @staticmethod
    def _deserialize_metadata_dict(metadata: dict) -> None:
        """Deserialize all values in a single metadata dict in-place."""
        for key, value in metadata.items():
            metadata[key] = ChromaRetriever._deserialize_metadata_value(value)

    def search(self, query: str, k: int = 5):
        """Search for similar documents.

        Args:
            query: Query text
            k: Number of results to return

        Returns:
            Dict with documents, metadatas, ids, and distances
        """
        results = self.collection.query(query_texts=[query], n_results=k)

        # Convert string metadata back to original types
        if results.get("metadatas"):
            for query_metadatas in results["metadatas"]:
                if not isinstance(query_metadatas, list):
                    continue
                for metadata in query_metadatas:
                    if isinstance(metadata, dict):
                        self._deserialize_metadata_dict(metadata)

        return results


class ZvecRetriever:
    """Vector database retrieval using Zvec.

    Uses deferred collection initialization (``self.collection`` is ``None``
    until the first write or until ``_ensure_collection()`` is called).  This
    allows the retriever to be created cheaply even when the underlying
    zvec path doesn't exist yet.

    Zvec handles its own concurrency: reads, writes, and ``optimize()`` are
    all thread-safe and can run concurrently without external locking or GC.
    We hold a single persistent collection handle for the lifetime of the
    retriever.

    The public ``embedding_function`` attribute is a *property* that
    lazy-creates the embedding function on first access and caches it.
    """

    def __init__(
        self,
        collection_name: str = "memories",
        model_name: str = "all-MiniLM-L6-v2",
        persist_dir: str = None,
        embedding_backend: str = "sentence-transformer",
    ):
        import zvec as _zvec

        self._zvec = _zvec
        self._model_name = model_name
        self._embedding_backend = embedding_backend
        self._embedding_function: Optional[Any] = None

        self.persist_dir = persist_dir
        self._dimension: Optional[int] = None

        collection_path = (
            os.path.join(persist_dir, collection_name)
            if persist_dir
            else os.path.join("/tmp/zvec", collection_name)
        )
        # Resolve to absolute path so later opens work regardless of CWD
        self._collection_path = os.path.abspath(collection_path)
        self._collection_name = collection_name

        # Deferred initialization: collection is None until first use.
        self.collection = None

        # If the collection already exists on disk, open a persistent handle.
        if os.path.exists(collection_path):
            try:
                self.collection = _zvec.open(path=self._collection_path)
            except Exception:
                self.collection = None

    # --- Embedding property (lazy, cached) --------------------------------

    @property
    def embedding_function(self):
        """Lazily create and cache the embedding function (F1 singleton)."""
        if self._embedding_function is None:
            self._embedding_function = _create_embedding_function(
                self._embedding_backend, self._model_name
            )
        return self._embedding_function

    @embedding_function.setter
    def embedding_function(self, value):
        """Allow external override (used by tests)."""
        self._embedding_function = value

    # --- Dimension detection ------------------------------------------

    def _get_dimension(self) -> int:
        """Get embedding dimension, using cache of known models (F9)."""
        if self._dimension is not None:
            return self._dimension

        # Check known dimensions first
        dim = _KNOWN_DIMENSIONS.get(self._model_name)
        if dim is not None:
            self._dimension = dim
            return dim

        # Check embedding function's own dimension tracking
        ef = self.embedding_function
        if hasattr(ef, "dimension"):
            try:
                self._dimension = ef.dimension
                return self._dimension
            except Exception:
                pass

        # Fallback: test embed
        logger.info("Unknown dimension for '%s', computing via test embed", self._model_name)
        test_embedding = ef(["dimension probe"])
        self._dimension = len(test_embedding[0]) if test_embedding else 384
        _KNOWN_DIMENSIONS[self._model_name] = self._dimension
        return self._dimension

    # --- Collection management ----------------------------------------

    def _ensure_collection(self):
        """Create or open the zvec collection if not already open."""
        if self.collection is not None:
            return self.collection

        dim = self._get_dimension()

        if not os.path.exists(self._collection_path):
            os.makedirs(os.path.dirname(self._collection_path), exist_ok=True)
            self.collection = self._zvec.create_and_open(
                path=self._collection_path,
                schema=self._build_schema(self._zvec, self._collection_name, dim),
            )
        else:
            self.collection = self._zvec.open(path=self._collection_path)

        return self.collection

    def _build_schema(self, _zvec, collection_name: str, dimension: int = None):
        """Build a Zvec collection schema for memory storage."""
        dim = dimension or self._get_dimension()
        return _zvec.CollectionSchema(
            name=collection_name,
            fields=[
                _zvec.FieldSchema(
                    name="metadata_json", data_type=_zvec.DataType.STRING
                ),
            ],
            vectors=[
                _zvec.VectorSchema(
                    name="embedding",
                    data_type=_zvec.DataType.VECTOR_FP32,
                    dimension=dim,
                    index_param=_zvec.HnswIndexParam(
                        metric_type=_zvec.MetricType.COSINE
                    ),
                ),
            ],
        )

    def close(self):
        """Release the collection handle and embedding function reference.

        Note: the embedding function is shared (singleton) and is NOT
        closed here — it may be in use by other retrievers.
        """
        self.collection = None
        self._embedding_function = None

    def count(self) -> int:
        """Return the number of documents in the collection."""
        if self.collection is None:
            return 0
        try:
            return self.collection.count()
        except Exception:
            return 0

    # --- Write operations (read-write lock) --------------------------

    def clear(self):
        """Delete all documents and recreate the collection."""
        if self.collection is not None:
            self.collection.destroy()
            self.collection = None

        dim = self._get_dimension()
        os.makedirs(os.path.dirname(self._collection_path), exist_ok=True)
        self.collection = self._zvec.create_and_open(
            path=self._collection_path,
            schema=self._build_schema(self._zvec, self._collection_name, dim),
        )

    def add_document(self, document: str, metadata: Dict, doc_id: str) -> None:
        """Add a document to Zvec with enhanced embedding using metadata."""
        self._ensure_collection()

        enhanced_document = _build_enhanced_document(document, metadata)
        embedding = self.embedding_function([enhanced_document])[0]

        processed_metadata = self._prepare_zvec_metadata(metadata)
        doc = self._zvec.Doc(
            id=doc_id,
            vectors={"embedding": embedding},
            fields={
                "metadata_json": json.dumps(processed_metadata, ensure_ascii=False)
            },
        )

        self.collection.insert(doc)
        self.collection.optimize()

    def delete_document(self, doc_id: str):
        """Delete a document from Zvec."""
        if self.collection is None:
            return
        self.collection.delete(ids=doc_id)
        self.collection.optimize()

    # --- Read operations (read-only, no exclusive lock) ---------------

    def has_document(self, doc_id: str) -> bool:
        """Check if a document exists in the Zvec collection."""
        if self.collection is None:
            return False
        result = self.collection.fetch(doc_id)
        return bool(result)

    def existing_ids(self, doc_ids: List[str]) -> set:
        """Return the subset of *doc_ids* that exist in the collection."""
        if not doc_ids or self.collection is None:
            return set()
        result = self.collection.fetch(doc_ids)
        return set(result.keys())

    def get_stored_hashes(self, doc_ids: List[str]) -> Dict[str, Optional[str]]:
        """Return {doc_id: content_hash} for each ID. Missing IDs omitted."""
        if not doc_ids or self.collection is None:
            return {}
        fetched = self.collection.fetch(doc_ids)
        out: Dict[str, Optional[str]] = {}
        for did, doc in fetched.items():
            meta = json.loads(doc.fields.get("metadata_json", "{}"))
            out[did] = meta.get("content_hash")
        return out

    def search(self, query: str, k: int = 5) -> dict:
        """Search for similar documents. Returns ChromaDB-compatible result format."""
        empty_result: dict = {"ids": [[]], "metadatas": [[]], "distances": [[]]}

        if self.collection is None:
            return empty_result

        embeddings = self.embedding_function([query])
        if not embeddings:
            return empty_result

        results = self.collection.query(
            vectors=self._zvec.VectorQuery(
                field_name="embedding", vector=embeddings[0]
            ),
            topk=k,
        )

        if not results:
            return empty_result

        ids = []
        metadatas = []
        distances = []

        for doc in results:
            ids.append(doc.id)
            distances.append(doc.score)
            metadatas.append(self._parse_doc_metadata(doc))

        return {
            "ids": [ids],
            "metadatas": [metadatas],
            "distances": [distances],
        }

    # --- Helpers ------------------------------------------------------

    @staticmethod
    def _prepare_zvec_metadata(metadata: Dict) -> Dict:
        """Convert metadata values for Zvec JSON storage."""
        processed = {}
        for key, value in metadata.items():
            if isinstance(value, (list, dict)):
                processed[key] = value
            elif value is None:
                processed[key] = None
            else:
                processed[key] = str(value)
        return processed

    @staticmethod
    def _parse_doc_metadata(doc) -> dict:
        """Deserialize metadata from a Zvec doc's fields."""
        meta_str = doc.fields.get("metadata_json", "{}")
        meta = json.loads(meta_str) if isinstance(meta_str, str) else {}
        for key, value in meta.items():
            if isinstance(value, str):
                meta[key] = _deserialize_json_value(value)
        return meta
