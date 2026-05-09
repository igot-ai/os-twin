"""TDD tests for the embedding-persistence fixes in the KuzuDB migration.

Covers two critical gaps identified in the pipeline review:

1. **GraphRAGExtractor._create_empty_extraction_result** must embed
   the ChunkNode even when LLM extraction fails, so it remains
   discoverable via KuzuDB's QUERY_VECTOR_INDEX.

2. **KuzuLabelledPropertyGraph.add_node** must reject new nodes that
   have no embedding after all upstream + auto-generation attempts.

Additional coverage for KnowledgeQueryEngine modes ensuring no
regression in the query-routing logic after zvec removal.
"""

from __future__ import annotations

import asyncio
from typing import Any, List
from unittest import mock

import pytest

from dashboard.knowledge.embeddings import KnowledgeEmbedder
from dashboard.knowledge.llm import KnowledgeLLM


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_embedder(*, dim: int = 1024, should_fail: bool = False):
    """Return a mocked KnowledgeEmbedder with controllable behaviour."""
    embedder = mock.MagicMock(spec=KnowledgeEmbedder)
    embedder.dimension.return_value = dim
    embedder.model_name = "test-model"
    if should_fail:
        embedder.embed.side_effect = RuntimeError("embedder offline")
        embedder.embed_one.side_effect = RuntimeError("embedder offline")
    else:
        embedder.embed.return_value = [[0.1] * dim] * 10
        embedder.embed_one.return_value = [0.1] * dim
    return embedder


def _make_fake_llm():
    llm = mock.MagicMock(spec=KnowledgeLLM)
    llm.is_available.return_value = True
    llm.extract_entities.return_value = ([], [])
    return llm


# ===========================================================================
# 1. GraphRAGExtractor — _create_empty_extraction_result embedding guarantee
# ===========================================================================


class TestEmptyExtractionEmbedding:
    """_create_empty_extraction_result MUST embed the ChunkNode."""

    def _make_extractor(self, embedder=None, llm=None):
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            ExtractionConfig,
            GraphRAGExtractor,
        )

        return GraphRAGExtractor(
            llm=llm or _make_fake_llm(),
            embedder=embedder or _make_fake_embedder(),
            config=ExtractionConfig(max_retries=0, timeout_seconds=1.0),
            num_workers=1,
        )

    # -- Happy path: embedding generated for failed-extraction node ---------

    def test_empty_extraction_embeds_node(self):
        """ChunkNode gets an embedding even when extraction fails."""
        from llama_index.core.graph_stores.types import KG_NODES_KEY, KG_RELATIONS_KEY
        from llama_index.core.schema import TextNode

        embedder = _make_fake_embedder()
        extractor = self._make_extractor(embedder=embedder)

        node = TextNode(text="hello world", id_="chunk-001")
        result = extractor._create_empty_extraction_result(node, "timeout")

        # Metadata set correctly
        assert result.metadata[KG_NODES_KEY] == []
        assert result.metadata[KG_RELATIONS_KEY] == []
        assert result.metadata["extraction_error"] == "timeout"
        assert result.metadata["extraction_status"] == "failed"
        # Embedding generated
        assert result.embedding is not None
        assert len(result.embedding) == 1024
        embedder.embed_one.assert_called_once_with("hello world")

    def test_empty_extraction_preserves_existing_embedding(self):
        """If node already has an embedding, don't overwrite it."""
        from llama_index.core.schema import TextNode

        embedder = _make_fake_embedder()
        extractor = self._make_extractor(embedder=embedder)

        existing_embedding = [0.5] * 1024
        node = TextNode(text="hello", id_="chunk-002")
        node.embedding = existing_embedding

        result = extractor._create_empty_extraction_result(node, "llm_crash")

        assert result.embedding == existing_embedding
        embedder.embed_one.assert_not_called()

    def test_empty_extraction_handles_embedder_failure(self):
        """If embedder raises, node.embedding stays None — no crash."""
        from llama_index.core.schema import TextNode

        embedder = _make_fake_embedder(should_fail=True)
        extractor = self._make_extractor(embedder=embedder)

        node = TextNode(text="hello world", id_="chunk-003")
        result = extractor._create_empty_extraction_result(node, "timeout")

        # Should NOT crash — just log a warning
        assert result.embedding is None
        assert result.metadata["extraction_status"] == "failed"

    def test_empty_extraction_skips_blank_text(self):
        """If node text is blank, skip embedding entirely (no point)."""
        from llama_index.core.schema import TextNode

        embedder = _make_fake_embedder()
        extractor = self._make_extractor(embedder=embedder)

        node = TextNode(text="   ", id_="chunk-004")
        result = extractor._create_empty_extraction_result(node, "empty text")

        assert result.embedding is None
        embedder.embed_one.assert_not_called()

    def test_empty_extraction_skips_empty_string(self):
        """Empty string text also skips embedding."""
        from llama_index.core.schema import TextNode

        embedder = _make_fake_embedder()
        extractor = self._make_extractor(embedder=embedder)

        node = TextNode(text="", id_="chunk-005")
        result = extractor._create_empty_extraction_result(node, "no content")

        assert result.embedding is None
        embedder.embed_one.assert_not_called()


# ===========================================================================
# 2. GraphRAGExtractor — _create_extraction_result (existing behaviour)
# ===========================================================================


class TestExtractionResultEmbedding:
    """Verify _create_extraction_result embeds ChunkNode and entities."""

    def _make_extractor(self, embedder=None, llm=None):
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            ExtractionConfig,
            GraphRAGExtractor,
        )

        return GraphRAGExtractor(
            llm=llm or _make_fake_llm(),
            embedder=embedder or _make_fake_embedder(),
            config=ExtractionConfig(max_retries=0),
            num_workers=1,
        )

    def test_successful_extraction_embeds_source_chunk(self):
        """ChunkNode gets an embedding after successful extraction."""
        from llama_index.core.graph_stores.types import KG_NODES_KEY
        from llama_index.core.schema import TextNode

        embedder = _make_fake_embedder()
        llm = _make_fake_llm()
        # Return one entity and one relation
        llm.extract_entities.return_value = (
            [("Alice", "Person", "A person named Alice")],
            [("Alice", "Bob", "KNOWS", "colleagues")],
        )
        extractor = self._make_extractor(embedder=embedder, llm=llm)

        node = TextNode(text="Alice works with Bob at Acme Corp.", id_="chunk-010")

        # Run the full single-node extraction
        result = extractor._extract_single_sync(node)

        # ChunkNode should have an embedding
        assert result.embedding is not None
        assert len(result.embedding) == 1024

    def test_successful_extraction_entities_have_embeddings(self):
        """EntityNodes get embeddings during successful extraction."""
        from llama_index.core.graph_stores.types import KG_NODES_KEY
        from llama_index.core.schema import TextNode

        embedder = _make_fake_embedder()
        llm = _make_fake_llm()
        llm.extract_entities.return_value = (
            [("Alice", "Person", "A person named Alice")],
            [],
        )
        extractor = self._make_extractor(embedder=embedder, llm=llm)

        node = TextNode(text="Alice works at Acme.", id_="chunk-011")
        result = extractor._extract_single_sync(node)

        # Entity nodes should have embeddings
        entity_nodes = result.metadata[KG_NODES_KEY]
        assert len(entity_nodes) >= 1
        for entity in entity_nodes:
            assert entity.embedding is not None
            assert len(entity.embedding) == 1024


# ===========================================================================
# 3. GraphRAGExtractor — full __call__ / acall TDD for failure paths
# ===========================================================================


class TestExtractorCallEmbeddingGuarantee:
    """Verify the full call path guarantees embeddings in failure scenarios."""

    def _make_extractor(self, embedder=None, llm=None):
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            ExtractionConfig,
            GraphRAGExtractor,
        )

        return GraphRAGExtractor(
            llm=llm or _make_fake_llm(),
            embedder=embedder or _make_fake_embedder(),
            config=ExtractionConfig(max_retries=0, timeout_seconds=0.5),
            num_workers=1,
        )

    def test_sync_call_with_llm_crash_still_embeds_node(self):
        """__call__ with LLM crash → node has empty KG metadata but retains embedding."""
        from llama_index.core.graph_stores.types import KG_NODES_KEY, KG_RELATIONS_KEY
        from llama_index.core.schema import TextNode
        import concurrent.futures

        embedder = _make_fake_embedder()
        llm = _make_fake_llm()
        llm.extract_entities.side_effect = RuntimeError("LLM crashed")

        extractor = self._make_extractor(embedder=embedder, llm=llm)
        nodes = [TextNode(text="test content for embedding", id_="chunk-020")]

        result = extractor(nodes)

        assert len(result) == 1
        assert result[0].metadata[KG_NODES_KEY] == []
        assert result[0].metadata[KG_RELATIONS_KEY] == []
        # The node MUST have an embedding despite extraction failure
        assert result[0].embedding is not None
        assert len(result[0].embedding) == 1024

    def test_acall_with_llm_crash_still_embeds_node(self):
        """acall with LLM crash → node has embedding despite extraction failure."""
        from llama_index.core.graph_stores.types import KG_NODES_KEY, KG_RELATIONS_KEY
        from llama_index.core.schema import TextNode

        embedder = _make_fake_embedder()
        llm = _make_fake_llm()
        llm.extract_entities.side_effect = RuntimeError("LLM offline")

        extractor = self._make_extractor(embedder=embedder, llm=llm)
        nodes = [TextNode(text="content for async embedding test", id_="chunk-021")]

        result = asyncio.run(extractor.acall(nodes))

        assert len(result) == 1
        assert result[0].metadata[KG_NODES_KEY] == []
        assert result[0].metadata[KG_RELATIONS_KEY] == []
        assert result[0].embedding is not None

    def test_acall_with_batch_crash_still_embeds_nodes(self):
        """acall with run_jobs crash → all nodes have empty metadata + embeddings."""
        from llama_index.core.graph_stores.types import KG_NODES_KEY, KG_RELATIONS_KEY
        from llama_index.core.schema import TextNode

        embedder = _make_fake_embedder()
        extractor = self._make_extractor(embedder=embedder)

        nodes = [
            TextNode(text="node A", id_="chunk-022a"),
            TextNode(text="node B", id_="chunk-022b"),
        ]

        with mock.patch(
            "dashboard.knowledge.graph.core.graph_rag_extractor.run_jobs",
            side_effect=RuntimeError("Job queue crashed"),
        ):
            result = asyncio.run(extractor.acall(nodes))

        assert len(result) == 2
        for r in result:
            assert r.metadata[KG_NODES_KEY] == []
            assert r.metadata[KG_RELATIONS_KEY] == []
            # Each node MUST have an embedding
            assert r.embedding is not None


# ===========================================================================
# 4. KuzuDB add_node — null embedding guard
# ===========================================================================


class TestKuzuDBNullEmbeddingGuard:
    """KuzuDB must reject new nodes with null embeddings."""

    def test_add_node_skips_null_embedding_on_create(self):
        """New node with null embedding after auto-gen failure is rejected."""
        from llama_index.core.graph_stores.types import EntityNode
        from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph

        node = EntityNode(
            name="TestEntity",
            label="Person",
            properties={"entity_description": "A test entity"},
            embedding=None,  # No embedding
        )

        with mock.patch.object(
            KuzuLabelledPropertyGraph, "_database", lambda self: None
        ):
            graph = KuzuLabelledPropertyGraph(index="test-index", ws_id="ws-001")

            # Mock the connection property
            mock_conn = mock.MagicMock()
            mock_result = mock.MagicMock()
            mock_result.has_next.return_value = False  # node doesn't exist yet
            mock_conn.execute.return_value = mock_result
            type(graph).connection = mock.PropertyMock(return_value=mock_conn)

            # Mock _escape_string as no-op
            graph._escape_string = mock.MagicMock(return_value="escaped")

            # Make auto-generation fail
            with mock.patch(
                "dashboard.knowledge.graph.index.kuzudb._get_embedder"
            ) as mock_get_embedder:
                mock_embedder = _make_fake_embedder(should_fail=True)
                mock_get_embedder.return_value = mock_embedder

                graph.add_node(node)

                # The CREATE should NOT have been called (only the existence check)
                calls = mock_conn.execute.call_args_list
                create_calls = [
                    c for c in calls
                    if "CREATE" in str(c)
                ]
                assert len(create_calls) == 0, (
                    "CREATE should not be called when embedding is null"
                )

    def test_add_node_proceeds_when_embedding_present(self):
        """Node with a valid embedding proceeds to CREATE."""
        from llama_index.core.graph_stores.types import EntityNode
        from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph

        node = EntityNode(
            name="TestEntity",
            label="Person",
            properties={"entity_description": "A test entity"},
            embedding=[0.1] * 1024,  # Has embedding
        )

        with mock.patch.object(
            KuzuLabelledPropertyGraph, "_database", lambda self: None
        ):
            graph = KuzuLabelledPropertyGraph(index="test-index", ws_id="ws-001")

            mock_conn = mock.MagicMock()
            mock_result = mock.MagicMock()
            mock_result.has_next.return_value = False  # new node
            mock_conn.execute.return_value = mock_result
            type(graph).connection = mock.PropertyMock(return_value=mock_conn)
            graph._escape_string = mock.MagicMock(return_value="escaped")

            graph.add_node(node)

            # CREATE SHOULD have been called
            calls = mock_conn.execute.call_args_list
            create_calls = [
                c for c in calls
                if "CREATE" in str(c)
            ]
            assert len(create_calls) >= 1, (
                "CREATE should be called when embedding is present"
            )


# ===========================================================================
# 5. KnowledgeQueryEngine — query mode routing (no-regression after zvec removal)
# ===========================================================================


class TestQueryEngineModesNoRegression:
    """Verify all three query modes still work correctly after zvec removal."""

    def _make_engine(self, *, graph_rag_engine=None):
        from dashboard.knowledge.query import KnowledgeQueryEngine

        embedder = _make_fake_embedder()
        llm = _make_fake_llm()

        fake_kg = mock.MagicMock()
        fake_kg.get_all_nodes.return_value = []
        fake_kg.pagerank.return_value = []
        fake_kg.get_all_relations.return_value = []

        return KnowledgeQueryEngine(
            namespace="test-ns",
            kuzu_graph=fake_kg,
            embedder=embedder,
            llm=llm,
            graph_rag_engine=graph_rag_engine,
        )

    def test_raw_mode_returns_immediately_after_vector_search(self):
        """Raw mode: only vector search, no graph expansion or LLM."""
        from dashboard.knowledge.query import QueryResult

        engine = self._make_engine()

        # Fake some vector hits
        class _FakeNode:
            def __init__(self, id_, text):
                self.id = id_
                self.name = text
                self.label = "text_chunk"
                self.properties = {
                    "file_hash": "h1",
                    "file_path": "/test.md",
                    "filename": "test.md",
                    "text": text,
                }

        engine.kg.get_all_nodes.return_value = [
            _FakeNode("c1", "chunk text 1"),
            _FakeNode("c2", "chunk text 2"),
        ]

        result = engine.query("what is X?", mode="raw", threshold=0.0)

        assert isinstance(result, QueryResult)
        assert result.mode == "raw"
        assert result.answer is None  # raw never aggregates
        assert len(result.chunks) == 2

    def test_graph_mode_expands_entities(self):
        """Graph mode: vector search + entity expansion, no LLM."""
        from dashboard.knowledge.query import QueryResult

        engine = self._make_engine()
        engine.kg.get_all_nodes.return_value = []

        result = engine.query("entity query", mode="graph", threshold=0.0)

        assert isinstance(result, QueryResult)
        assert result.mode == "graph"
        assert result.answer is None  # graph mode never summarizes

    def test_summarized_mode_delegates_to_graph_rag_engine(self):
        """Summarized mode: delegates to GraphRAGQueryEngine.custom_query.

        The engine first runs graph expansion (step 2) via get_nodes() +
        graph_result(), then calls custom_query() (step 3).  All three
        methods must be properly mocked to avoid hangs (yaml.safe_load on
        a bare MagicMock blocks indefinitely).
        """
        fake_rag_engine = mock.MagicMock()
        fake_rag_engine.get_nodes.return_value = None
        fake_rag_engine.graph_result.return_value = "knowledge: '[]'"
        fake_rag_engine.custom_query.return_value = "Summarized answer"

        engine = self._make_engine(graph_rag_engine=fake_rag_engine)
        engine.kg.get_all_nodes.return_value = []

        result = engine.query("summarize X", mode="summarized", threshold=0.0)

        assert result.answer == "Summarized answer"
        fake_rag_engine.custom_query.assert_called_once()

    def test_summarized_mode_fallback_when_rag_engine_fails(self):
        """Summarized mode: falls back to simple LLM when GraphRAGQueryEngine fails.

        get_nodes and graph_result must be properly mocked to avoid hangs
        during graph expansion (step 2) before custom_query (step 3) is reached.
        """
        fake_rag_engine = mock.MagicMock()
        fake_rag_engine.get_nodes.return_value = None
        fake_rag_engine.graph_result.return_value = "knowledge: '[]'"
        fake_rag_engine.custom_query.side_effect = RuntimeError("engine crashed")

        engine = self._make_engine(graph_rag_engine=fake_rag_engine)
        engine.kg.get_all_nodes.return_value = []

        # Mock fallback LLM
        engine.llm.is_available.return_value = False

        result = engine.query("summarize X", mode="summarized", threshold=0.0)

        assert result.answer is None  # LLM unavailable
        assert any("graph_rag_summarization_failed" in w for w in result.warnings)

    def test_summarized_without_graph_rag_engine_uses_llm_directly(self):
        """Summarized mode without GraphRAGQueryEngine falls back to LLM."""
        engine = self._make_engine(graph_rag_engine=None)
        engine.kg.get_all_nodes.return_value = []
        engine.llm.is_available.return_value = False

        result = engine.query("summarize X", mode="summarized", threshold=0.0)

        assert result.answer is None
        assert any("llm_unavailable" in w for w in result.warnings)

    def test_invalid_mode_falls_through_gracefully(self):
        """Unknown mode falls through to end without crashing.

        Mode validation happens at the service layer, not in query().
        An unknown mode simply skips all processing and returns an
        empty result."""
        engine = self._make_engine()
        result = engine.query("test", mode="bogus")
        assert result.chunks == []
        assert result.answer is None

    def test_embed_failure_returns_empty_result(self):
        """If KG vector search fails, engine returns empty result.

        The KG layer (not engine.embedder) owns the embedding call.
        We mock the KG's get_all_nodes to raise, which query() catches
        and records as a vector_search_failed warning."""
        engine = self._make_engine()
        engine.kg.get_all_nodes.side_effect = RuntimeError("model offline")

        result = engine.query("test query", mode="raw")

        assert result.chunks == []
        assert any("vector_search_failed" in w for w in result.warnings)


# ===========================================================================
# 6. KnowledgeQueryEngine — vector search uses KuzuDB only (no zvec)
# ===========================================================================


class TestQueryEngineNoZvec:
    """Confirm KnowledgeQueryEngine has zero dependency on zvec/vector_store."""

    def test_engine_has_no_vs_attribute(self):
        """KnowledgeQueryEngine must NOT have a self.vs attribute."""
        from dashboard.knowledge.query import KnowledgeQueryEngine

        embedder = _make_fake_embedder()
        llm = _make_fake_llm()
        fake_kg = mock.MagicMock()

        engine = KnowledgeQueryEngine(
            namespace="ns", kuzu_graph=fake_kg, embedder=embedder, llm=llm,
        )

        assert not hasattr(engine, "vs"), "self.vs must not exist after zvec removal"

    def test_engine_constructor_accepts_no_vector_store_param(self):
        """Constructor signature must not accept vector_store parameter."""
        import inspect
        from dashboard.knowledge.query import KnowledgeQueryEngine

        params = inspect.signature(KnowledgeQueryEngine.__init__).parameters
        assert "vector_store" not in params, (
            "KnowledgeQueryEngine should not accept vector_store parameter"
        )
        assert "vs" not in params, (
            "KnowledgeQueryEngine should not accept vs parameter"
        )

    def test_query_routes_through_kuzu_graph(self):
        """Query must call self.kg.get_all_nodes, not any zvec method."""
        from dashboard.knowledge.query import KnowledgeQueryEngine

        embedder = _make_fake_embedder()
        llm = _make_fake_llm()
        fake_kg = mock.MagicMock()
        fake_kg.get_all_nodes.return_value = []

        engine = KnowledgeQueryEngine(
            namespace="ns", kuzu_graph=fake_kg, embedder=embedder, llm=llm,
        )

        result = engine.query("hello", mode="raw", threshold=0.0)

        fake_kg.get_all_nodes.assert_called_once()
        assert result.chunks == []


# ===========================================================================
# 7. GraphRAGExtractor — metrics tracking for embedding failures
# ===========================================================================


class TestExtractorMetrics:
    """Verify metrics are tracked correctly during extraction."""

    def test_metrics_increment_on_failure(self):
        """ExtractionMetrics tracks failed extractions."""
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            ExtractionConfig,
            ExtractionMetrics,
            GraphRAGExtractor,
        )
        from llama_index.core.schema import TextNode

        embedder = _make_fake_embedder()
        llm = _make_fake_llm()
        llm.extract_entities.side_effect = RuntimeError("crash")

        extractor = GraphRAGExtractor(
            llm=llm, embedder=embedder,
            config=ExtractionConfig(max_retries=0),
            num_workers=1,
        )

        nodes = [TextNode(text="test")]
        extractor(nodes)

        metrics = extractor.get_metrics()
        assert metrics.failed_extractions >= 1

    def test_metrics_increment_on_success(self):
        """ExtractionMetrics tracks successful extractions."""
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            ExtractionConfig,
            ExtractionMetrics,
            GraphRAGExtractor,
        )
        from llama_index.core.schema import TextNode

        embedder = _make_fake_embedder()
        llm = _make_fake_llm()
        llm.extract_entities.return_value = ([], [])

        extractor = GraphRAGExtractor(
            llm=llm, embedder=embedder,
            config=ExtractionConfig(max_retries=0),
            num_workers=1,
        )

        nodes = [TextNode(text="test content")]
        extractor(nodes)

        metrics = extractor.get_metrics()
        assert metrics.successful_extractions >= 1
