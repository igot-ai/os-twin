from typing import List, Dict, Any, Optional, Union, Protocol, runtime_checkable
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import nltk
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pickle
from nltk.tokenize import word_tokenize
import os
import json
import litellm


@runtime_checkable
class EmbeddingFunction(Protocol):
    """Protocol for embedding functions (avoiding chromadb import)."""

    def __call__(self, input: List[str]) -> List[List[float]]: ...


Documents = List[str]
Embeddings = List[List[float]]


def simple_tokenize(text):
    return word_tokenize(text)


class GeminiEmbeddingFunction(EmbeddingFunction):
    """ChromaDB embedding function using Gemini embedding models via litellm."""

    def __init__(self, model_name: str = "gemini-embedding-001"):
        self.model_name = (
            f"gemini/{model_name}"
            if not model_name.startswith("gemini/")
            else model_name
        )

    def __call__(self, input: Documents) -> Embeddings:
        response = litellm.embedding(model=self.model_name, input=input)
        return [item["embedding"] for item in response.data]


class SentenceTransformerEmbeddingFunction:
    """SentenceTransformer embedding function (avoids chromadb import)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def __call__(self, input: Documents) -> Embeddings:
        return self.model.encode(input).tolist()


def _create_embedding_function(embedding_backend: str, model_name: str):
    """Create an embedding function based on the backend type."""
    if embedding_backend == "gemini":
        return GeminiEmbeddingFunction(model_name=model_name)
    else:
        return SentenceTransformerEmbeddingFunction(model_name=model_name)


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

    Uses short-lived collection handles instead of holding a persistent
    read-write lock.  This allows multiple MCP server processes to share
    the same ``vectordb/`` directory:

    - **Read operations** (search, fetch, has_document) open a read-only
      handle, execute, then release it immediately.
    - **Write operations** (add_document, delete_document, clear) open a
      read-write handle with retry, execute, then release it immediately.

    The lock is only held for the duration of a single operation, not the
    entire process lifetime.
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

        self.embedding_function = _create_embedding_function(
            embedding_backend, model_name
        )
        self.persist_dir = persist_dir

        # Determine embedding dimension by encoding a test string
        test_embedding = self.embedding_function(["test"])
        self._dimension = len(test_embedding[0])

        collection_path = (
            os.path.join(persist_dir, collection_name)
            if persist_dir
            else os.path.join("/tmp/zvec", collection_name)
        )
        # Resolve to absolute path so later opens work regardless of CWD
        self._collection_path = os.path.abspath(collection_path)
        self._collection_name = collection_name

        # Ensure the collection exists (one-time setup).
        if not os.path.exists(collection_path):
            os.makedirs(os.path.dirname(collection_path), exist_ok=True)
            col = _zvec.create_and_open(
                path=collection_path,
                schema=self._build_schema(_zvec, collection_name),
            )
            del col
            self._gc()

    # --- Handle management -------------------------------------------

    @staticmethod
    def _gc():
        """Force garbage collection to release zvec file locks."""
        import gc

        gc.collect()

    def _open_ro(self):
        """Open a read-only handle (no exclusive lock)."""
        return self._zvec.open(
            path=self._collection_path,
            option=self._zvec.CollectionOption(read_only=True),
        )

    def _open_rw(self):
        """Open a read-write handle with retry on lock contention."""
        import time

        last_err = None
        for _attempt in range(30):  # ~30s total wait
            try:
                return self._zvec.open(path=self._collection_path)
            except RuntimeError as e:
                last_err = e
                if "lock" not in str(e).lower():
                    raise
                time.sleep(1.0)
        raise (
            last_err
            if last_err
            else RuntimeError(
                f"Failed to lock zvec collection: {self._collection_path}"
            )
        )

    def _build_schema(self, _zvec, collection_name: str):
        """Build a Zvec collection schema for memory storage."""
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
                    dimension=self._dimension,
                    index_param=_zvec.HnswIndexParam(
                        metric_type=_zvec.MetricType.COSINE
                    ),
                ),
            ],
        )

    # --- Write operations (read-write lock) --------------------------

    def clear(self):
        """Delete all documents and recreate the collection."""
        col = self._open_rw()
        col.destroy()
        del col
        self._gc()
        col = self._zvec.create_and_open(
            path=self._collection_path,
            schema=self._build_schema(self._zvec, self._collection_name),
        )
        del col
        self._gc()

    def add_document(self, document: str, metadata: Dict, doc_id: str) -> None:
        """Add a document to Zvec with enhanced embedding using metadata."""
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
        col = self._open_rw()
        col.insert(doc)
        del col
        self._gc()

    def delete_document(self, doc_id: str):
        """Delete a document from Zvec."""
        col = self._open_rw()
        col.delete(ids=doc_id)
        del col
        self._gc()

    # --- Read operations (read-only, no exclusive lock) ---------------

    def has_document(self, doc_id: str) -> bool:
        """Check if a document exists in the Zvec collection."""
        col = self._open_ro()
        result = col.fetch(doc_id)
        del col
        self._gc()
        return bool(result)

    def existing_ids(self, doc_ids: List[str]) -> set:
        """Return the subset of *doc_ids* that exist in the collection."""
        if not doc_ids:
            return set()
        col = self._open_ro()
        result = col.fetch(doc_ids)
        del col
        self._gc()
        return set(result.keys())

    def get_stored_hashes(self, doc_ids: List[str]) -> Dict[str, Optional[str]]:
        """Return {doc_id: content_hash} for each ID. Missing IDs omitted."""
        if not doc_ids:
            return {}
        col = self._open_ro()
        fetched = col.fetch(doc_ids)
        del col
        self._gc()
        out: Dict[str, Optional[str]] = {}
        for did, doc in fetched.items():
            meta = json.loads(doc.fields.get("metadata_json", "{}"))
            out[did] = meta.get("content_hash")
        return out

    def search(self, query: str, k: int = 5) -> dict:
        """Search for similar documents. Returns ChromaDB-compatible result format."""
        empty_result: dict = {"ids": [[]], "metadatas": [[]], "distances": [[]]}
        embeddings = self.embedding_function([query])
        if not embeddings:
            return empty_result

        col = self._open_ro()
        results = col.query(
            vectors=self._zvec.VectorQuery(
                field_name="embedding", vector=embeddings[0]
            ),
            topk=k,
        )
        del col
        self._gc()

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
