"""Functional tests for GraphRAGQueryEngine → TrackVectorRetriever integration.

These tests exercise the engine's public API and verify that the retriever is
correctly wired into the property-graph pipeline:

- ``tracking`` property lazy-initialises ``TrackVectorRetriever``
- ``compute_page_rank`` / ``get_community_relations`` delegate correctly
- ``_get_nodes_with_score`` feeds PageRank→significance→triplet-scoring
- ``graph_result`` produces YAML from the retriever's networkx graph
- ``_create_citation`` produces correct citation strings
- ``custom_query`` / ``acustom_query`` drive the full query plan pipeline
- ``aggregate_answers`` normalises inputs and handles errors
- ``_run_async`` handles both no-loop and in-loop contexts
"""

from __future__ import annotations

import asyncio
from unittest import mock

import pytest
import networkx as nx
from llama_index.core.graph_stores.types import EntityNode, Relation

from dashboard.knowledge.llm import KnowledgeLLM


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_llm():
    llm = mock.MagicMock(spec=KnowledgeLLM)
    llm.is_available.return_value = True
    llm.plan_query.return_value = []
    llm.aggregate_answers.return_value = "aggregated answer"
    return llm


@pytest.fixture()
def engine_components(fake_llm):
    """Build fully-mocked engine dependencies that wire through the retriever."""
    graph_store = mock.MagicMock()
    graph_store.pagerank.return_value = [
        ("e0", 0.9), ("e1", 0.7), ("e2", 0.5),
        ("e3", 0.3), ("e4", 0.2), ("e5", 0.01),
    ]
    graph_store.graph.get_all_nodes.return_value = []

    index = mock.MagicMock()
    index.property_graph_store = mock.MagicMock()
    index.property_graph_store.get.return_value = []
    index.property_graph_store.get_rel_map.return_value = []
    index.vector_store = mock.MagicMock()

    storage_context = mock.MagicMock()
    kg_extractor = mock.MagicMock()
    embed_model = mock.MagicMock()

    return {
        "graph_store": graph_store,
        "index": index,
        "vector_store": index.vector_store,
        "storage_context": storage_context,
        "kg_extractor": kg_extractor,
        "llm": fake_llm,
        "plan_llm": fake_llm,
        "node_id": "test-node",
        "embed_model": embed_model,
    }


def _build_engine(components, **overrides):
    """Construct a real GraphRAGQueryEngine with mocked backends.

    Uses ``model_construct`` to bypass Pydantic field validation so we can
    inject MagicMock instances for typed fields.
    """
    from dashboard.knowledge.graph.core.graph_rag_query_engine import GraphRAGQueryEngine

    kwargs = {**components, **overrides}
    engine = GraphRAGQueryEngine.model_construct(**kwargs)
    # PrivateAttr defaults aren't set by model_construct
    engine._tracking = None
    return engine


# ---------------------------------------------------------------------------
# tracking property – lazy TrackVectorRetriever creation
# ---------------------------------------------------------------------------


class TestTrackingProperty:
    """Engine.tracking should lazy-create a TrackVectorRetriever."""

    def test_tracking_creates_retriever(self, engine_components):
        engine = _build_engine(engine_components)
        retriever = engine.tracking

        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever
        assert isinstance(retriever, TrackVectorRetriever)
        assert hasattr(retriever, "graph")
        assert retriever.matching_ids == []

    def test_tracking_is_cached(self, engine_components):
        engine = _build_engine(engine_components)
        first = engine.tracking
        second = engine.tracking
        assert first is second

    def test_tracking_uses_embed_model(self, engine_components):
        engine = _build_engine(engine_components)
        retriever = engine.tracking
        assert retriever._embed_model is engine_components["embed_model"]

    def test_tracking_fallback_to_index_embed(self, engine_components):
        """When embed_model is None, fall back to index._embed_model."""
        engine_components["embed_model"] = None
        fallback_embed = mock.MagicMock()
        engine_components["index"]._embed_model = fallback_embed

        engine = _build_engine(engine_components)
        retriever = engine.tracking
        assert retriever._embed_model is fallback_embed


# ---------------------------------------------------------------------------
# compute_page_rank / get_community_relations
# ---------------------------------------------------------------------------


class TestPageRankAndCommunityRelations:
    """Test the engine delegates to the graph store properly."""

    def test_compute_page_rank_filters_by_threshold(self, engine_components):
        engine = _build_engine(engine_components)
        result = engine.compute_page_rank({"e0": 1.0})

        engine_components["graph_store"].pagerank.assert_called_once_with(
            {"e0": 1.0}
        )
        # Should filter out entries below PAGERANK_SCORE_THRESHOLD
        for entity_id, score in result:
            from dashboard.knowledge.config import PAGERANK_SCORE_THRESHOLD
            assert score > PAGERANK_SCORE_THRESHOLD

    def test_compute_page_rank_none_fallback(self, engine_components):
        """When pagerank returns None, fall back to enumerate-based scores."""
        engine_components["graph_store"].pagerank.return_value = None
        engine = _build_engine(engine_components)

        personalize = {"a": 1.0, "b": 2.0}
        result = engine.compute_page_rank(personalize)

        assert isinstance(result, list)
        assert len(result) == len(personalize)

    def test_get_community_relations_delegates(self, engine_components):
        engine = _build_engine(engine_components)
        engine.get_community_relations(["id1", "id2"])

        engine_components["index"].property_graph_store.get.assert_called_once_with(
            ids=["id1", "id2"]
        )
        engine_components["index"].property_graph_store.get_rel_map.assert_called_once()


# ---------------------------------------------------------------------------
# _create_citation
# ---------------------------------------------------------------------------


class TestCreateCitation:
    """Test citation string builder — all branches."""

    def test_citation_with_filename_and_page_range(self, engine_components):
        engine = _build_engine(engine_components)
        result = engine._create_citation(
            {"filename": "report.pdf", "page_range": "1-3"},
            "uuid-123",
        )
        assert "report.pdf" in result
        assert "(1-3)" in result
        assert "uuid:uuid-123" in result

    def test_citation_with_file_path_fallback(self, engine_components):
        engine = _build_engine(engine_components)
        result = engine._create_citation(
            {"file_path": "/data/report.pdf"},
            "uuid-456",
        )
        assert "/data/report.pdf" in result

    def test_citation_with_page_number_fallback(self, engine_components):
        engine = _build_engine(engine_components)
        result = engine._create_citation(
            {"filename": "doc.txt", "page_number": "5"},
            "uuid-789",
        )
        assert "(5)" in result

    def test_citation_no_file_identifier(self, engine_components):
        engine = _build_engine(engine_components)
        result = engine._create_citation({}, "uuid-000")
        assert result == "`uuid-000`"

    def test_citation_no_page_info(self, engine_components):
        engine = _build_engine(engine_components)
        result = engine._create_citation({"filename": "data.csv"}, "uuid-111")
        assert "data.csv" in result
        assert "(" not in result  # no page suffix


# ---------------------------------------------------------------------------
# graph_result — NetworkX graph → YAML snapshot
# ---------------------------------------------------------------------------


class TestGraphResult:
    """Test graph_result reads from the retriever's graph and produces YAML."""

    def test_graph_result_empty(self, engine_components):
        engine = _build_engine(engine_components)
        result = engine.graph_result()

        assert isinstance(result, str)
        assert "knowledge" in result

    def test_graph_result_with_nodes_and_edges(self, engine_components):
        engine = _build_engine(engine_components)
        graph = engine.tracking.graph

        # Populate the retriever's networkx graph
        graph.add_node(
            "n1", label="EntityA", score=0.9,
            properties={"filename": "doc.pdf", "page_range": "1-2"},
        )
        graph.add_node(
            "n2", label="EntityB", score=0.5,
            properties={},
        )
        graph.add_edge(
            "n1", "n2",
            label="RELATES_TO",
            relationship_description="is related to",
        )

        result = engine.graph_result()
        assert "EntityA" in result
        assert "RELATES_TO" in result

    def test_graph_result_handles_node_error(self, engine_components):
        """If _create_citation raises for one node, it still processes others."""
        engine = _build_engine(engine_components)
        graph = engine.tracking.graph

        graph.add_node("n1", label="Good", score=0.8, properties={"filename": "ok.pdf"})
        graph.add_node("n2", label="Bad", score=0.3, properties=None)  # will cause error

        # Force _create_citation to raise on None properties
        original = engine._create_citation

        def explode_on_none(metadata, uuid):
            if metadata is None:
                raise TypeError("NoneType")
            return original(metadata, uuid)

        with mock.patch.object(engine, "_create_citation", side_effect=explode_on_none):
            result = engine.graph_result()

        assert "Good" in result or "n1" in result
        assert "n2" in result  # error-path node still appears


# ---------------------------------------------------------------------------
# _query_plan — knowledge filtering + plan execution
# ---------------------------------------------------------------------------


class TestQueryPlan:
    """Test the query plan pipeline through the engine."""

    def test_query_plan_include_graph_false(self, engine_components):
        """When include_graph=False, knowledge list stays empty."""
        engine = _build_engine(engine_components)

        with mock.patch(
            "dashboard.knowledge.graph.core.graph_rag_query_engine.QueryExecutor"
        ) as MockExecutor:
            mock_executor = MockExecutor.return_value
            mock_executor.generate_plans.return_value = (None, "")

            answer, _ = asyncio.run(
                engine._query_plan("test query", include_graph=False)
            )

        assert answer == ""
        engine_components["graph_store"].graph.get_all_nodes.assert_not_called()

    def test_query_plan_filters_text_chunks_and_long_names(self, engine_components):
        """text_chunk entities and long-name entities are excluded."""
        chunk_node = mock.MagicMock()
        chunk_node.label = "text_chunk"
        chunk_node.name = "short"
        chunk_node.id = "chunk1"
        chunk_node.properties = {}

        long_node = mock.MagicMock()
        long_node.label = "entity"
        long_node.name = "x" * 200  # > 100 chars
        long_node.id = "long1"
        long_node.properties = {}

        good_node = mock.MagicMock()
        good_node.label = "entity"
        good_node.name = "ShortEntity"
        good_node.id = "good1"
        good_node.properties = {"entity_description": "desc", "category_id": "cat"}

        engine_components["graph_store"].graph.get_all_nodes.return_value = [
            chunk_node, long_node, good_node,
        ]

        engine = _build_engine(engine_components)

        with mock.patch(
            "dashboard.knowledge.graph.core.graph_rag_query_engine.QueryExecutor"
        ) as MockExecutor:
            mock_executor = MockExecutor.return_value
            mock_executor.generate_plans.return_value = (None, "")

            asyncio.run(engine._query_plan("test query", include_graph=True))

            # generate_plans should have been called with knowledge containing only good_node
            call_args = mock_executor.generate_plans.call_args
            knowledge_yaml = call_args.kwargs.get("knowledge") or call_args[1].get("knowledge")
            assert "ShortEntity" in knowledge_yaml or "good1" in knowledge_yaml

    def test_query_plan_max_queries_one_skips_planning(self, engine_components):
        """When max_queries=1, skip plan generation and use direct query."""
        engine = _build_engine(engine_components, max_queries=1)

        with mock.patch(
            "dashboard.knowledge.graph.core.graph_rag_query_engine.QueryExecutor"
        ) as MockExecutor:
            mock_executor = MockExecutor.return_value
            mock_executor.execute_plans = mock.AsyncMock(return_value=("answer", []))

            answer, _ = asyncio.run(engine._query_plan("direct query"))

            # generate_plans should NOT be called
            mock_executor.generate_plans.assert_not_called()
            # execute_plans should be called with is_memory=True
            call_kwargs = mock_executor.execute_plans.call_args
            assert call_kwargs.kwargs.get("is_memory") is True

    def test_query_plan_executes_plans(self, engine_components):
        """Full plan generation → execution flow."""
        engine = _build_engine(engine_components, max_queries=3)

        with mock.patch(
            "dashboard.knowledge.graph.core.graph_rag_query_engine.QueryExecutor"
        ) as MockExecutor:
            mock_executor = MockExecutor.return_value
            mock_executor.generate_plans.return_value = (
                [{"is_query": True, "term": "sub-query"}], ""
            )
            mock_executor.execute_plans = mock.AsyncMock(
                return_value=("final answer", [])
            )

            answer, _ = asyncio.run(engine._query_plan("test query"))

            assert answer == "final answer"
            mock_executor.generate_plans.assert_called_once()
            mock_executor.execute_plans.assert_called_once()


# ---------------------------------------------------------------------------
# custom_query / acustom_query — entry points
# ---------------------------------------------------------------------------


class TestQueryEntryPoints:
    """Test sync and async query entry points."""

    def test_acustom_query(self, engine_components):
        engine = _build_engine(engine_components, max_queries=1)

        with mock.patch(
            "dashboard.knowledge.graph.core.graph_rag_query_engine.QueryExecutor"
        ) as MockExecutor:
            mock_executor = MockExecutor.return_value
            mock_executor.execute_plans = mock.AsyncMock(
                return_value=("async answer", [])
            )

            result = asyncio.run(engine.acustom_query("hello"))
            assert result == "async answer"

    def test_custom_query_sync(self, engine_components):
        engine = _build_engine(engine_components, max_queries=1)

        with mock.patch(
            "dashboard.knowledge.graph.core.graph_rag_query_engine.QueryExecutor"
        ) as MockExecutor:
            mock_executor = MockExecutor.return_value
            mock_executor.execute_plans = mock.AsyncMock(
                return_value=("sync answer", [])
            )

            result = engine.custom_query("hello")
            assert result == "sync answer"

    def test_custom_query_with_parameter(self, engine_components):
        engine = _build_engine(engine_components, max_queries=1)

        with mock.patch(
            "dashboard.knowledge.graph.core.graph_rag_query_engine.QueryExecutor"
        ) as MockExecutor:
            mock_executor = MockExecutor.return_value
            mock_executor.execute_plans = mock.AsyncMock(
                return_value=("ctx answer", [])
            )

            result = asyncio.run(
                engine.acustom_query("hello", parameter="context info")
            )
            assert result == "ctx answer"


# ---------------------------------------------------------------------------
# aggregate_answers — input normalisation + error handling
# ---------------------------------------------------------------------------


class TestAggregateAnswers:
    """Test aggregate_answers handles all input types and errors."""

    def test_aggregate_string_input(self, engine_components, fake_llm):
        engine = _build_engine(engine_components)

        result = asyncio.run(engine.aggregate_answers("single answer", "query"))

        fake_llm.aggregate_answers.assert_called_once()
        args = fake_llm.aggregate_answers.call_args[0]
        assert args[0] == ["single answer"]  # normalised to list

    def test_aggregate_list_input(self, engine_components, fake_llm):
        engine = _build_engine(engine_components)

        asyncio.run(engine.aggregate_answers(["a1", "a2"], "query"))
        args = fake_llm.aggregate_answers.call_args[0]
        assert args[0] == ["a1", "a2"]

    def test_aggregate_non_string_input(self, engine_components, fake_llm):
        engine = _build_engine(engine_components)

        asyncio.run(engine.aggregate_answers(42, "query"))
        args = fake_llm.aggregate_answers.call_args[0]
        assert args[0] == ["42"]

    def test_aggregate_with_custom_llm(self, engine_components):
        custom_llm = mock.MagicMock(spec=KnowledgeLLM)
        custom_llm.aggregate_answers.return_value = "custom"

        engine = _build_engine(engine_components)
        result = asyncio.run(
            engine.aggregate_answers("data", "query", llm=custom_llm)
        )

        custom_llm.aggregate_answers.assert_called_once()
        assert result == "custom"

    def test_aggregate_error_handling(self, engine_components, fake_llm):
        fake_llm.aggregate_answers.side_effect = RuntimeError("LLM crashed")
        engine = _build_engine(engine_components)

        result = asyncio.run(engine.aggregate_answers("data", "query"))
        assert "Error" in result
        assert "LLM crashed" in result


# ---------------------------------------------------------------------------
# _run_async — sync-to-async runner
# ---------------------------------------------------------------------------


class TestRunAsync:
    """Test _run_async handles both no-loop and in-loop contexts."""

    def test_run_async_no_loop(self):
        """When no event loop is running, _run_async uses asyncio.run."""
        from dashboard.knowledge.graph.core.graph_rag_query_engine import _run_async

        async def sample():
            return 42

        result = _run_async(sample())
        assert result == 42

    def test_run_async_inside_loop(self):
        """When already in a loop, _run_async uses a worker thread."""
        from dashboard.knowledge.graph.core.graph_rag_query_engine import _run_async

        async def inner():
            return "from_thread"

        async def outer():
            return _run_async(inner())

        result = asyncio.run(outer())
        assert result == "from_thread"


# ---------------------------------------------------------------------------
# get_nodes — retriever-based node fetch
# ---------------------------------------------------------------------------


class TestGetNodes:
    """Test get_nodes wires through the index retriever."""

    def test_get_nodes_calls_index_retriever(self, engine_components):
        engine = _build_engine(engine_components)

        mock_retriever = mock.MagicMock()
        mock_retriever.retrieve.return_value = []
        engine_components["index"].as_retriever.return_value = mock_retriever

        result = engine.get_nodes("test query")

        engine_components["index"].as_retriever.assert_called_once()
        mock_retriever.retrieve.assert_called_once_with("test query")
        assert result == []


# ---------------------------------------------------------------------------
# End-to-end: engine → retriever → significance → triplets → nodes
# ---------------------------------------------------------------------------


class TestEngineRetrieverIntegration:
    """Verify that engine methods exercise the retriever's _get_nodes_with_score
    pipeline, which feeds through compute_page_rank → get_community_relations →
    calculate_triplet_scores → _get_nodes_from_triplets.

    This is the critical integration path that reaches line 103-104 in
    track_vector_retriever.py (matching_id index-based lookup).
    """

    def test_full_retriever_pipeline_through_engine(self, engine_components):
        """Engine.tracking._get_nodes_with_score exercises the full pipeline."""
        engine = _build_engine(engine_components)
        retriever = engine.tracking

        # Create entities with IDs that will appear in matching_ids
        a = EntityNode(name="Alpha", label="E", properties={}, embedding=[])
        b = EntityNode(name="Beta", label="E", properties={}, embedding=[])
        rel = Relation(source_id=a.id, target_id=b.id, label="LINKS")

        # Set matching_ids with numeric index values (to hit line 103-104)
        retriever.matching_ids = [0, 1]

        # Configure engine backend
        engine_components["graph_store"].pagerank.return_value = [
            (a.id, 0.95), (b.id, 0.80),
            ("e2", 0.6), ("e3", 0.4), ("e4", 0.3), ("e5", 0.01),
        ]
        engine_components["index"].property_graph_store.get.return_value = [a, b]
        engine_components["index"].property_graph_store.get_rel_map.return_value = [
            (a, rel, b),
        ]

        triplets = [(a, rel, b)]
        scores = [0.9]

        result = retriever._get_nodes_with_score(triplets, scores)

        # Verify the full chain was exercised
        engine_components["graph_store"].pagerank.assert_called_once()
        engine_components["index"].property_graph_store.get.assert_called_once()
        assert isinstance(result, list)

    def test_retriever_pipeline_with_matching_id_index_hit(self, engine_components):
        """Exercise the index-based matching_id lookup (lines 102-104)."""
        engine = _build_engine(engine_components)
        retriever = engine.tracking

        a = EntityNode(name="X", label="E", properties={}, embedding=[])
        b = EntityNode(name="Y", label="E", properties={}, embedding=[])
        rel = Relation(source_id=a.id, target_id=b.id, label="R")

        # matching_ids[0] should be checked against index 0
        # To hit `if i in self.matching_ids`, matching_ids must contain
        # the integer index value
        retriever.matching_ids = [0]

        engine_components["graph_store"].pagerank.return_value = [
            (a.id, 0.9), (b.id, 0.8),
            ("e2", 0.5), ("e3", 0.3), ("e4", 0.2), ("e5", 0.01),
        ]
        engine_components["index"].property_graph_store.get.return_value = [a, b]
        engine_components["index"].property_graph_store.get_rel_map.return_value = [
            (a, rel, b),
        ]

        result = retriever._get_nodes_with_score([(a, rel, b)], [0.85])

        assert isinstance(result, list)
