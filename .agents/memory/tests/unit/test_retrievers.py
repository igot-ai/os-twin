"""Unit tests for agentic_memory.retrievers module.

All external dependencies (litellm, zvec, sentence_transformers) are mocked
to ensure pure unit testing without network/disk I/O.
"""
import json
import sys
import types
import unittest
from unittest.mock import MagicMock, Mock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Pre-import mocks: zvec and sentence_transformers are not installed in CI,
# so we inject lightweight stubs into sys.modules BEFORE importing the SUT.
# ---------------------------------------------------------------------------
_mock_zvec = MagicMock()
_mock_zvec.DataType = MagicMock()
_mock_zvec.DataType.STRING = "STRING"
_mock_zvec.DataType.VECTOR_FP32 = "VECTOR_FP32"
_mock_zvec.MetricType = MagicMock()
_mock_zvec.MetricType.COSINE = "COSINE"
sys.modules.setdefault("zvec", _mock_zvec)

_mock_st = MagicMock()
sys.modules.setdefault("sentence_transformers", _mock_st)

from agentic_memory.retrievers import (
    GeminiEmbeddingFunction,
    SentenceTransformerEmbedding,
    ZvecRetriever,
    _create_embedding_function,
)


# =========================================================================
# GeminiEmbeddingFunction
# =========================================================================
class TestGeminiEmbeddingFunction(unittest.TestCase):
    """Tests for the Gemini embedding wrapper around litellm."""

    def test_init_prefixes_model_name_with_gemini(self):
        """Model names without 'gemini/' prefix get it added automatically."""
        fn = GeminiEmbeddingFunction(model_name="gemini-embedding-001")
        self.assertEqual(fn.model_name, "gemini/gemini-embedding-001")

    def test_init_keeps_existing_gemini_prefix(self):
        """Model names already prefixed with 'gemini/' are left unchanged."""
        fn = GeminiEmbeddingFunction(model_name="gemini/text-embedding-004")
        self.assertEqual(fn.model_name, "gemini/text-embedding-004")

    @patch("agentic_memory.retrievers.litellm")
    def test_call_returns_embeddings_from_litellm(self, mock_litellm):
        """__call__ delegates to litellm.embedding and unpacks .data items."""
        mock_item_1 = {"embedding": [0.1, 0.2, 0.3]}
        mock_item_2 = {"embedding": [0.4, 0.5, 0.6]}
        mock_response = MagicMock()
        mock_response.data = [mock_item_1, mock_item_2]
        mock_litellm.embedding.return_value = mock_response

        fn = GeminiEmbeddingFunction(model_name="gemini/test-model")
        result = fn(["hello", "world"])

        mock_litellm.embedding.assert_called_once_with(
            model="gemini/test-model", input=["hello", "world"]
        )
        self.assertEqual(result, [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

    @patch("agentic_memory.retrievers.litellm")
    def test_call_sets_dimension_on_first_invocation(self, mock_litellm):
        """_dimension is lazily set from the first non-empty response."""
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [1.0, 2.0]}]
        mock_litellm.embedding.return_value = mock_response

        fn = GeminiEmbeddingFunction()
        self.assertIsNone(fn._dimension)

        fn(["test"])
        self.assertEqual(fn._dimension, 2)

    @patch("agentic_memory.retrievers.litellm")
    def test_dimension_property_lazy_initializes(self, mock_litellm):
        """Accessing .dimension when _dimension is None triggers a test embed."""
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.0] * 768}]
        mock_litellm.embedding.return_value = mock_response

        fn = GeminiEmbeddingFunction()
        dim = fn.dimension

        self.assertEqual(dim, 768)
        # Should have called embedding once (for the lazy init)
        mock_litellm.embedding.assert_called_once()

    @patch("agentic_memory.retrievers.litellm")
    def test_dimension_returns_768_if_empty_response(self, mock_litellm):
        """dimension falls back to 768 when the test call returns empty list."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_litellm.embedding.return_value = mock_response

        fn = GeminiEmbeddingFunction()
        dim = fn.dimension

        self.assertEqual(dim, 768)


# =========================================================================
# SentenceTransformerEmbedding
# =========================================================================
class TestSentenceTransformerEmbedding(unittest.TestCase):
    """Tests for the SentenceTransformer embedding wrapper."""

    def test_init_stores_model_name_and_model_is_none(self):
        """Constructor stores the model name but does NOT load the model."""
        fn = SentenceTransformerEmbedding(model_name="my/model")
        self.assertEqual(fn._model_name, "my/model")
        self.assertIsNone(fn._model)

    @patch("agentic_memory.retrievers.SentenceTransformerEmbedding._ensure_model")
    def test_ensure_model_loads_lazily(self, mock_ensure):
        """_ensure_model is called on __call__ to lazy-load."""
        import numpy as np

        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [[0.1, 0.2]])
        mock_ensure.return_value = mock_model

        fn = SentenceTransformerEmbedding()
        result = fn(["test"])

        mock_ensure.assert_called_once()
        mock_model.encode.assert_called_once_with(["test"])
        self.assertEqual(result, [[0.1, 0.2]])

    def test_ensure_model_imports_sentence_transformer(self):
        """_ensure_model imports and instantiates SentenceTransformer."""
        fn = SentenceTransformerEmbedding(model_name="test/model")

        mock_st_class = MagicMock()
        mock_instance = MagicMock()
        mock_st_class.return_value = mock_instance

        with patch.dict("sys.modules", {"sentence_transformers": MagicMock(SentenceTransformer=mock_st_class)}):
            result = fn._ensure_model()

        self.assertIs(result, mock_instance)
        mock_st_class.assert_called_once_with("test/model")

    @patch("agentic_memory.retrievers.SentenceTransformerEmbedding._ensure_model")
    def test_call_sets_dimension_on_first_invocation(self, mock_ensure):
        """_dimension is lazily set from the first non-empty result."""
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [[1.0, 2.0, 3.0]])
        mock_ensure.return_value = mock_model

        fn = SentenceTransformerEmbedding()
        self.assertIsNone(fn._dimension)

        fn(["hello"])
        self.assertEqual(fn._dimension, 3)

    @patch("agentic_memory.retrievers.SentenceTransformerEmbedding._ensure_model")
    def test_dimension_property_lazy_initializes(self, mock_ensure):
        """Accessing .dimension triggers a test embed when _dimension is None."""
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [[0.0] * 384])
        mock_ensure.return_value = mock_model

        fn = SentenceTransformerEmbedding()
        dim = fn.dimension

        self.assertEqual(dim, 384)

    @patch("agentic_memory.retrievers.SentenceTransformerEmbedding._ensure_model")
    def test_dimension_returns_384_if_empty_response(self, mock_ensure):
        """dimension falls back to 384 when the test call returns empty list."""
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [])
        mock_ensure.return_value = mock_model

        fn = SentenceTransformerEmbedding()
        dim = fn.dimension

        self.assertEqual(dim, 384)


# =========================================================================
# _create_embedding_function factory
# =========================================================================
class TestCreateEmbeddingFunction(unittest.TestCase):
    """Tests for the factory function that dispatches by backend name."""

    def test_gemini_backend_creates_gemini_function(self):
        fn = _create_embedding_function("gemini", "my-model")
        self.assertIsInstance(fn, GeminiEmbeddingFunction)
        self.assertEqual(fn.model_name, "gemini/my-model")

    def test_sentence_transformer_backend_creates_st_function(self):
        fn = _create_embedding_function("sentence-transformer", "my/model")
        self.assertIsInstance(fn, SentenceTransformerEmbedding)
        self.assertEqual(fn._model_name, "my/model")

    def test_unknown_backend_defaults_to_sentence_transformer(self):
        fn = _create_embedding_function("unknown-backend", "model")
        self.assertIsInstance(fn, SentenceTransformerEmbedding)


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
                embedding_backend="sentence-transformer",
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

    def test_delete_document_on_none_collection_no_error(self):
        """delete_document() is a no-op when collection is None."""
        retriever = self._make_retriever(path_exists=False)
        # Should not raise
        retriever.delete_document("nonexistent-id")

    def test_add_document_creates_collection_if_needed(self):
        """add_document() triggers _ensure_collection when collection is None."""
        retriever = self._make_retriever(path_exists=False)

        # Mock the embedding function to return a fixed embedding
        mock_ef = MagicMock()
        mock_ef.return_value = [[0.1, 0.2, 0.3]]
        mock_ef.dimension = 3
        retriever._embedding_function = mock_ef
        retriever._dimension = 3

        # Mock collection creation
        mock_collection = MagicMock()
        retriever._zvec.create_and_open.return_value = mock_collection

        with patch("os.makedirs"):
            retriever.add_document(
                document="test content",
                metadata={"summary": "test summary", "context": "General"},
                doc_id="doc-123",
            )

        # Collection should now be set
        self.assertIs(retriever.collection, mock_collection)
        # insert should have been called
        mock_collection.insert.assert_called_once()

    def test_search_returns_properly_formatted_results(self):
        """search() formats zvec results into the expected dict structure."""
        retriever = self._make_retriever(path_exists=False)

        # Set up a mock collection
        mock_collection = MagicMock()
        retriever.collection = mock_collection

        # Mock the embedding function
        mock_ef = MagicMock()
        mock_ef.return_value = [[0.5, 0.5]]
        retriever._embedding_function = mock_ef

        # Mock query results
        mock_doc1 = MagicMock()
        mock_doc1.id = "id-1"
        mock_doc1.score = 0.95
        mock_doc1.fields = {"metadata_json": json.dumps({"name": "Note 1", "tags": '["a","b"]'})}

        mock_doc2 = MagicMock()
        mock_doc2.id = "id-2"
        mock_doc2.score = 0.80
        mock_doc2.fields = {"metadata_json": json.dumps({"name": "Note 2"})}

        mock_collection.query.return_value = [mock_doc1, mock_doc2]

        result = retriever.search("find something", k=3)

        self.assertEqual(result["ids"], [["id-1", "id-2"]])
        self.assertEqual(result["distances"], [[0.95, 0.80]])
        self.assertEqual(len(result["metadatas"][0]), 2)
        self.assertEqual(result["metadatas"][0][0]["name"], "Note 1")
        # tags should be deserialized from JSON string
        self.assertEqual(result["metadatas"][0][0]["tags"], ["a", "b"])

    def test_search_with_non_json_metadata(self):
        """search() gracefully handles non-JSON-string metadata fields."""
        retriever = self._make_retriever(path_exists=False)

        mock_collection = MagicMock()
        retriever.collection = mock_collection

        mock_ef = MagicMock()
        mock_ef.return_value = [[0.1]]
        retriever._embedding_function = mock_ef

        mock_doc = MagicMock()
        mock_doc.id = "id-x"
        mock_doc.score = 0.5
        mock_doc.fields = {"metadata_json": json.dumps({"plain": "text", "num": "42"})}
        mock_collection.query.return_value = [mock_doc]

        result = retriever.search("q")
        # "text" doesn't start with [ or {, so should stay a string
        self.assertEqual(result["metadatas"][0][0]["plain"], "text")
        self.assertEqual(result["metadatas"][0][0]["num"], "42")

    def test_embedding_function_property_lazy_creates(self):
        """The embedding_function property creates the function on first access."""
        retriever = self._make_retriever(path_exists=False)
        retriever._embedding_backend = "sentence-transformer"
        retriever._model_name = "my/model"

        ef = retriever.embedding_function
        self.assertIsInstance(ef, SentenceTransformerEmbedding)
        # Second access returns the same object
        self.assertIs(retriever.embedding_function, ef)

    def test_add_document_enhances_text_with_metadata(self):
        """add_document() appends context, keywords, and tags to the document text."""
        retriever = self._make_retriever(path_exists=False)

        embedded_texts = []

        def capture_embed(texts):
            embedded_texts.extend(texts)
            return [[0.1, 0.2]]

        mock_ef = MagicMock(side_effect=capture_embed)
        mock_ef.dimension = 2
        retriever._embedding_function = mock_ef
        retriever._dimension = 2

        mock_collection = MagicMock()
        retriever.collection = mock_collection  # Skip _ensure_collection

        retriever.add_document(
            document="raw text",
            metadata={
                "summary": "summary text",
                "context": "Backend",
                "keywords": ["db", "sql"],
                "tags": ["#database"],
            },
            doc_id="doc-1",
        )

        # The enhanced document should contain context, keywords, and tags
        enhanced = embedded_texts[0]
        self.assertIn("summary text", enhanced)
        self.assertIn("context: Backend", enhanced)
        self.assertIn("keywords: db, sql", enhanced)
        self.assertIn("tags: #database", enhanced)

    def test_add_document_uses_summary_over_document(self):
        """When metadata has 'summary', it's used as base text, not 'document'."""
        retriever = self._make_retriever(path_exists=False)

        embedded_texts = []

        def capture_embed(texts):
            embedded_texts.extend(texts)
            return [[0.1]]

        mock_ef = MagicMock(side_effect=capture_embed)
        mock_ef.dimension = 1
        retriever._embedding_function = mock_ef
        retriever._dimension = 1

        mock_collection = MagicMock()
        retriever.collection = mock_collection

        retriever.add_document(
            document="original long content",
            metadata={"summary": "short summary", "context": "General"},
            doc_id="d1",
        )

        # Should start with the summary, not the document
        self.assertTrue(embedded_texts[0].startswith("short summary"))

    def test_add_document_skips_general_context(self):
        """Context is not appended when it's 'General'."""
        retriever = self._make_retriever(path_exists=False)

        embedded_texts = []

        def capture_embed(texts):
            embedded_texts.extend(texts)
            return [[0.1]]

        mock_ef = MagicMock(side_effect=capture_embed)
        mock_ef.dimension = 1
        retriever._embedding_function = mock_ef
        retriever._dimension = 1

        mock_collection = MagicMock()
        retriever.collection = mock_collection

        retriever.add_document(
            document="text",
            metadata={"context": "General"},
            doc_id="d2",
        )

        self.assertNotIn("context:", embedded_texts[0])

    def test_clear_destroys_existing_collection(self):
        """clear() calls destroy() on the existing collection."""
        retriever = self._make_retriever(path_exists=False)

        mock_collection = MagicMock()
        retriever.collection = mock_collection

        retriever._dimension = 3

        with patch("os.makedirs"):
            retriever.clear()

        mock_collection.destroy.assert_called_once()

    def test_clear_on_none_collection_still_ensures_collection(self):
        """clear() with no existing collection still calls _ensure_collection."""
        retriever = self._make_retriever(path_exists=False)
        self.assertIsNone(retriever.collection)

        new_collection = MagicMock()
        retriever._zvec.create_and_open.return_value = new_collection
        retriever._dimension = 3

        with patch("os.makedirs"):
            retriever.clear()

        # _ensure_collection should create the collection
        self.assertIs(retriever.collection, new_collection)


if __name__ == "__main__":
    unittest.main()
