from typing import List, Dict, Optional
import os
import json
import logging
import litellm

logger = logging.getLogger(__name__)


class GeminiEmbeddingFunction:
    """Embedding function using Gemini embedding models via litellm."""

    def __init__(self, model_name: str = "gemini-embedding-001"):
        self.model_name = f"gemini/{model_name}" if not model_name.startswith("gemini/") else model_name
        self._dimension: Optional[int] = None

    def __call__(self, input: List[str]) -> List[List[float]]:
        response = litellm.embedding(model=self.model_name, input=input)
        embeddings = [item["embedding"] for item in response.data]
        if self._dimension is None and embeddings:
            self._dimension = len(embeddings[0])
        return embeddings

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            # Lazy init: encode a test string to get dimension
            test = self(["test"])
            self._dimension = len(test[0]) if test else 768
        return self._dimension


class SentenceTransformerEmbedding:
    """Embedding function using SentenceTransformer models with lazy loading."""

    def __init__(self, model_name: str = "microsoft/harrier-oss-v1-270m"):
        self._model_name = model_name
        self._model = None
        self._dimension: Optional[int] = None

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self._model_name}")
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def __call__(self, input: List[str]) -> List[List[float]]:
        model = self._ensure_model()
        embeddings = model.encode(input)
        result = embeddings.tolist()
        if self._dimension is None and result:
            self._dimension = len(result[0])
        return result

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            # Lazy init: encode a test string to get dimension
            test = self(["test"])
            self._dimension = len(test[0]) if test else 384
        return self._dimension


def _create_embedding_function(embedding_backend: str, model_name: str):
    """Create an embedding function based on the backend type."""
    if embedding_backend == "gemini":
        return GeminiEmbeddingFunction(model_name=model_name)
    else:
        return SentenceTransformerEmbedding(model_name=model_name)


class ZvecRetriever:
    """Vector database retrieval using Zvec with lazy embedding initialization."""

    def __init__(self, collection_name: str = "memories", model_name: str = "microsoft/harrier-oss-v1-270m",
                 persist_dir: str = None, embedding_backend: str = "sentence-transformer"):
        """Initialize Zvec retriever.

        Args:
            collection_name: Name of the Zvec collection
            model_name: Name of the embedding model
            persist_dir: Directory for persistent storage. If None, falls back to /tmp/zvec.
            embedding_backend: "sentence-transformer" or "gemini"
        """
        import zvec as _zvec
        self._zvec = _zvec

        self._model_name = model_name
        self._embedding_backend = embedding_backend
        self._embedding_function: Optional[object] = None
        self.persist_dir = persist_dir
        self._dimension: Optional[int] = None

        collection_path = os.path.join(persist_dir, collection_name) if persist_dir else os.path.join("/tmp/zvec", collection_name)
        self._collection_path = collection_path

        if os.path.exists(collection_path):
            self.collection = _zvec.open(path=collection_path)
            # Try to infer dimension from existing collection
            try:
                # Query with empty result to get schema info
                sample = self.collection.query(
                    vectors=_zvec.VectorQuery(field_name="embedding", vector=[0.0] * 384),  # placeholder
                    topk=1,
                )
                # If we got here, collection exists but we need proper dimension
                # We'll get it lazily when embedding function is created
            except Exception:
                pass
        else:
            # Defer collection creation until we know the dimension
            self.collection = None

    @property
    def embedding_function(self):
        if self._embedding_function is None:
            self._embedding_function = _create_embedding_function(self._embedding_backend, self._model_name)
        return self._embedding_function

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._dimension = self.embedding_function.dimension
        return self._dimension

    def _ensure_collection(self):
        if self.collection is None:
            os.makedirs(os.path.dirname(self._collection_path), exist_ok=True)
            schema = self._zvec.CollectionSchema(
                name="memories",
                fields=[
                    self._zvec.FieldSchema(name="metadata_json", data_type=self._zvec.DataType.STRING),
                ],
                vectors=[
                    self._zvec.VectorSchema(
                        name="embedding",
                        data_type=self._zvec.DataType.VECTOR_FP32,
                        dimension=self.dimension,
                        index_param=self._zvec.HnswIndexParam(metric_type=self._zvec.MetricType.COSINE),
                    ),
                ],
            )
            self.collection = self._zvec.create_and_open(path=self._collection_path, schema=schema)

    def clear(self):
        if self.collection is not None:
            self.collection.destroy()
        self._ensure_collection()

    def add_document(self, document: str, metadata: dict, doc_id: str):
        self._ensure_collection()
        
        summary = metadata.get('summary')
        enhanced_document = summary if summary else document

        if 'context' in metadata and metadata['context'] != "General":
            enhanced_document += f" context: {metadata['context']}"
        if 'keywords' in metadata and metadata['keywords']:
            keywords = metadata['keywords'] if isinstance(metadata['keywords'], list) else json.loads(metadata['keywords'])
            if keywords:
                enhanced_document += f" keywords: {', '.join(keywords)}"
        if 'tags' in metadata and metadata['tags']:
            tags = metadata['tags'] if isinstance(metadata['tags'], list) else json.loads(metadata['tags'])
            if tags:
                enhanced_document += f" tags: {', '.join(tags)}"

        embedding = self.embedding_function([enhanced_document])[0]

        processed_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, (list, dict)):
                processed_metadata[key] = value
            elif value is None:
                processed_metadata[key] = None
            else:
                processed_metadata[key] = str(value)

        doc = self._zvec.Doc(
            id=doc_id,
            vectors={"embedding": embedding},
            fields={"metadata_json": json.dumps(processed_metadata, ensure_ascii=False)},
        )
        self.collection.insert(doc)

    def delete_document(self, doc_id: str):
        if self.collection is not None:
            self.collection.delete(ids=doc_id)

    def search(self, query: str, k: int = 5):
        if self.collection is None:
            return {'ids': [[]], 'metadatas': [[]], 'distances': [[]]}
        
        embedding = self.embedding_function([query])[0]

        results = self.collection.query(
            vectors=self._zvec.VectorQuery(field_name="embedding", vector=embedding),
            topk=k,
        )

        ids = []
        metadatas = []
        distances = []

        for doc in results:
            ids.append(doc.id)
            distances.append(doc.score)
            meta_str = doc.fields.get("metadata_json", "{}")
            meta = json.loads(meta_str) if isinstance(meta_str, str) else {}
            for key, value in meta.items():
                if isinstance(value, str):
                    try:
                        if value.startswith('[') or value.startswith('{'):
                            meta[key] = json.loads(value)
                    except (json.JSONDecodeError, ValueError):
                        pass
            metadatas.append(meta)

        return {
            'ids': [ids],
            'metadatas': [metadatas],
            'distances': [distances],
        }

    def count(self) -> int:
        if self.collection is None:
            return 0
        try:
            # Zvec doesn't have a direct count, so we query with high topk
            results = self.collection.query(
                vectors=self._zvec.VectorQuery(field_name="embedding", vector=[0.0] * self.dimension),
                topk=10000,
            )
            return len(list(results))
        except Exception:
            return 0
