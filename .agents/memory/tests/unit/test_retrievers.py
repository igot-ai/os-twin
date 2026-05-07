"""Unit tests for agentic_memory.retrievers module.

All external dependencies (litellm, zvec, sentence_transformers) are mocked
to ensure pure unit testing without network/disk I/O.
"""
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Pre-import mocks: zvec is not installed in CI,
# so we inject lightweight stubs into sys.modules BEFORE importing the SUT.
# ---------------------------------------------------------------------------
_mock_zvec = MagicMock()
_mock_zvec.DataType = MagicMock()
_mock_zvec.DataType.STRING = "STRING"
_mock_zvec.DataType.VECTOR_FP32 = "VECTOR_FP32"
_mock_zvec.MetricType = MagicMock()
_mock_zvec.MetricType.COSINE = "COSINE"
sys.modules.setdefault("zvec", _mock_zvec)

# Ensure the lazy-import globals are populated for tests
import agentic_memory.retrievers as _retrievers_mod
_retrievers_mod._tokenizer_imports_done = True
_retrievers_mod.word_tokenize = MagicMock()
_retrievers_mod.cosine_similarity = MagicMock()
_retrievers_mod.np = MagicMock()

from agentic_memory.retrievers import (
    EMBEDDING_DIMENSION,
    OllamaEmbeddingFunction,
    OpenAICompatibleEmbeddingFunction,
    ZvecRetriever,
    _create_embedding_function,
    _embedding_cache,
    _embedding_cache_lock,
    _truncate_to_dim,
)


# =========================================================================
# _create_embedding_function factory
# =========================================================================
class TestCreateEmbeddingFunction(unittest.TestCase):
    """Tests for the factory function that dispatches by backend name."""

    def setUp(self):
        # Clear singleton cache before each factory test
        with _embedding_cache_lock:
            _embedding_cache.clear()

    def test_ollama_backend_creates_ollama_function(self):
        fn = _create_embedding_function("ollama", "leoipulsar/harrier-0.6b", shared=False)
        self.assertIsInstance(fn, OllamaEmbeddingFunction)
        self.assertEqual(fn._model_name, "leoipulsar/harrier-0.6b")

    def test_openai_compatible_backend_creates_oai_function(self):
        fn = _create_embedding_function("openai-compatible", "test-model", shared=False)
        self.assertIsInstance(fn, OpenAICompatibleEmbeddingFunction)
        self.assertEqual(fn._model_name, "test-model")

    def test_unknown_backend_raises_value_error(self):
        with self.assertRaises(ValueError):
            _create_embedding_function("unknown-backend", "model", shared=False)


# =========================================================================
# OllamaEmbeddingFunction
# =========================================================================
class TestOllamaEmbeddingFunction(unittest.TestCase):
    """Tests for the Ollama embedding wrapper using native SDK."""

    def test_init_stores_model_name(self):
        fn = OllamaEmbeddingFunction(model_name="embeddinggemma")
        self.assertEqual(fn._model_name, "embeddinggemma")

    def test_init_default_model(self):
        fn = OllamaEmbeddingFunction()
        self.assertEqual(fn._model_name, "leoipulsar/harrier-0.6b")

    @patch.dict("sys.modules", {"ollama": MagicMock(), "httpx": MagicMock()})
    def test_call_truncates_to_768(self):
        """__call__ should truncate 1024-dim Ollama output to 768."""
        import sys
        mock_ollama = sys.modules["ollama"]
        mock_ollama.embed.return_value = {
            "embeddings": [[0.1] * 1024]
        }

        fn = OllamaEmbeddingFunction(model_name="leoipulsar/harrier-0.6b")
        result = fn(["hello"])

        self.assertEqual(len(result[0]), 768)

    @patch.dict("sys.modules", {"ollama": MagicMock(), "httpx": MagicMock()})
    def test_call_pads_short_vectors(self):
        """__call__ should pad <768-dim Ollama output to 768."""
        import sys
        mock_ollama = sys.modules["ollama"]
        mock_ollama.embed.return_value = {
            "embeddings": [[0.5] * 256]
        }

        fn = OllamaEmbeddingFunction(model_name="small-model")
        result = fn(["hello"])

        self.assertEqual(len(result[0]), 768)
        self.assertEqual(result[0][255], 0.5)
        self.assertEqual(result[0][256], 0.0)  # zero-padded

    def test_dimension_always_returns_768(self):
        """dimension always returns EMBEDDING_DIMENSION regardless of model."""
        fn = OllamaEmbeddingFunction(model_name="leoipulsar/harrier-0.6b")
        self.assertEqual(fn.dimension, 768)


# =========================================================================
# OpenAICompatibleEmbeddingFunction
# =========================================================================
class TestOpenAICompatibleEmbeddingFunction(unittest.TestCase):
    """Tests for the OpenAI-compatible embedding wrapper."""

    def test_init_stores_params(self):
        fn = OpenAICompatibleEmbeddingFunction(
            model_name="test-model",
            base_url="http://test:8000",
            api_key="sk-test"
        )
        self.assertEqual(fn._model_name, "test-model")
        self.assertEqual(fn._base_url, "http://test:8000")
        self.assertEqual(fn._api_key, "sk-test")

    @patch("httpx.Client")
    def test_call_delegates_to_httpx(self, mock_client_class):
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 768}]
        }
        mock_client.post.return_value = mock_response

        fn = OpenAICompatibleEmbeddingFunction(model_name="test-model")
        result = fn(["hello"])

        self.assertEqual(len(result[0]), 768)
        mock_client.post.assert_called()


# =========================================================================
# _truncate_to_dim helper
# =========================================================================
class TestTruncateToDim(unittest.TestCase):
    """Tests for the _truncate_to_dim utility."""

    def test_truncates_long_vectors(self):
        result = _truncate_to_dim([[0.1] * 1024])
        self.assertEqual(len(result[0]), 768)

    def test_pads_short_vectors(self):
        result = _truncate_to_dim([[1.0, 2.0, 3.0]])
        self.assertEqual(len(result[0]), 768)
        self.assertEqual(result[0][:3], [1.0, 2.0, 3.0])
        self.assertTrue(all(v == 0.0 for v in result[0][3:]))


# =========================================================================
# ZvecRetriever
# =========================================================================
class TestZvecRetriever(unittest.TestCase):
    """Tests for the Zvec-backed vector retriever."""

    def _make_retriever(self, persist_dir="/tmp/test_zvec_dir", collection_name="test_col",
                        path_exists=False):
        """Helper to create a ZvecRetriever with mocked zvec and os.path.exists."""
        with patch("os.path.exists", return_value=path_exists), \
             patch("os.path.join", side_effect=lambda *parts: "/".join(parts)):
            retriever = ZvecRetriever(
                collection_name=collection_name,
                model_name="test-model",
                persist_dir=persist_dir,
                embedding_backend="ollama",
            )
        return retriever

    def test_init_with_nonexistent_path_sets_collection_none(self):
        """When the collection path does not exist, collection is deferred (None)."""
        retriever = self._make_retriever(path_exists=False)
        self.assertIsNone(retriever.collection)

    def test_search_with_no_collection_returns_empty_structure(self):
        """search() on uninitialized collection returns empty wrapper dicts."""
        retriever = self._make_retriever(path_exists=False)
        result = retriever.search("any query")
        self.assertEqual(result, {"ids": [[]], "metadatas": [[]], "distances": [[]]})

    def test_count_with_no_collection_returns_zero(self):
        """count() on uninitialized collection returns 0."""
        retriever = self._make_retriever(path_exists=False)
        self.assertEqual(retriever.count(), 0)

    def test_add_document_creates_collection_if_needed(self):
        """add_document() triggers _ensure_collection when collection is None."""
        retriever = self._make_retriever(path_exists=False)

        mock_ef = MagicMock()
        mock_ef.return_value = [[0.1, 0.2, 0.3]]
        mock_ef.dimension = 3
        retriever._embedding_function = mock_ef
        retriever._dimension = 3

        mock_collection = MagicMock()
        retriever._zvec.create_and_open.return_value = mock_collection

        with patch("os.makedirs"):
            retriever.add_document(
                document="test content",
                metadata={"summary": "test summary"},
                doc_id="doc-123",
            )

        retriever._zvec.create_and_open.assert_called()

    def test_search_returns_properly_formatted_results(self):
        """search() formats zvec results into the expected dict structure."""
        retriever = self._make_retriever(path_exists=False)

        # Mock the embedding function
        mock_ef = MagicMock()
        mock_ef.return_value = [[0.5, 0.5]]
        retriever._embedding_function = mock_ef

        # Mock the collection with query results
        mock_col = MagicMock()
        mock_doc1 = MagicMock()
        mock_doc1.id = "id-1"
        mock_doc1.score = 0.95
        mock_doc1.fields = {"metadata_json": json.dumps({"name": "Note 1", "tags": '["a","b"]'})}

        mock_col.query.return_value = [mock_doc1]
        retriever.collection = mock_col

        result = retriever.search("find something", k=3)

        self.assertEqual(result["ids"], [["id-1"]])
        self.assertEqual(result["distances"], [[0.95]])
        self.assertEqual(result["metadatas"][0][0]["tags"], ["a", "b"])

    def test_embedding_function_property_lazy_creates(self):
        """The embedding_function property creates the function on first access."""
        retriever = self._make_retriever(path_exists=False)
        retriever._embedding_backend = "ollama"
        retriever._model_name = "my/model"
        retriever._embedding_function = None

        with _embedding_cache_lock:
            _embedding_cache.clear()

        ef = retriever.embedding_function
        self.assertIsInstance(ef, OllamaEmbeddingFunction)
        self.assertIs(retriever.embedding_function, ef)


if __name__ == "__main__":
    unittest.main()
