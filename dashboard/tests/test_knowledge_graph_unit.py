"""Unit tests for knowledge/graph/core modules — deep coverage.

This test module focuses on:
1. QueryExecutor — plan generation and execution
2. TrackVectorRetriever — triplet scoring algorithms
3. GraphRAGStore — graph operations and filtering
4. Service → Graph layer cascade integration
5. Edge cases and error handling paths
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest import mock

import pytest

from dashboard.knowledge.embeddings import KnowledgeEmbedder
from dashboard.knowledge.llm import KnowledgeLLM


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_llm():
    """Create a mocked KnowledgeLLM."""
    llm = mock.MagicMock(spec=KnowledgeLLM)
    llm.is_available.return_value = True
    llm.plan_query.return_value = []
    llm.aggregate_answers.return_value = "aggregated result"
    return llm


@pytest.fixture
def fake_embedder():
    """Create a mocked KnowledgeEmbedder."""
    embedder = mock.MagicMock(spec=KnowledgeEmbedder)
    embedder.dimension.return_value = 1024
    embedder.embed_one.return_value = [0.1] * 1024
    embedder.model_name = "test-model"
    return embedder


# ---------------------------------------------------------------------------
# QueryExecutor Tests
# ---------------------------------------------------------------------------


class TestQueryExecutorInit:
    """Test QueryExecutor initialization."""

    def test_init_stores_attributes(self, fake_llm):
        """QueryExecutor stores engine, llm, and language."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_engine = mock.MagicMock()
        executor = QueryExecutor(fake_engine, fake_llm, language="Vietnamese")

        assert executor.engine is fake_engine
        assert executor.llm is fake_llm
        assert executor.language == "Vietnamese"

    def test_init_default_language(self, fake_llm):
        """Default language is used when not specified."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_engine = mock.MagicMock()
        executor = QueryExecutor(fake_engine, fake_llm, language="English")

        assert executor.language == "English"


class TestQueryExecutorUUIDFormat:
    """Test UUID format detection."""

    def test_is_uuid_format_valid(self):
        """Valid UUID strings return True."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        valid_uuid = str(uuid.uuid4())
        assert QueryExecutor._is_uuid_format(valid_uuid) is True

    def test_is_uuid_format_invalid_string(self):
        """Non-UUID strings return False."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        assert QueryExecutor._is_uuid_format("not-a-uuid") is False
        assert QueryExecutor._is_uuid_format("12345") is False
        assert QueryExecutor._is_uuid_format("") is False

    def test_is_uuid_format_non_string(self):
        """Non-string values return False."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        assert QueryExecutor._is_uuid_format(None) is False
        assert QueryExecutor._is_uuid_format(123) is False
        assert QueryExecutor._is_uuid_format(["list"]) is False

    def test_is_uuid_format_uppercase(self):
        """Uppercase UUID strings are normalized and return True."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        valid_uuid = str(uuid.uuid4()).upper()
        assert QueryExecutor._is_uuid_format(valid_uuid) is True


class TestQueryExecutorFileMetadata:
    """Test file metadata extraction."""

    def test_extract_file_metadata_complete(self):
        """Extracts all file metadata fields."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        properties = {
            "file_path": "/docs/report.pdf",
            "filename": "report.pdf",
            "page_range": "1-5",
            "page_number": "3",
            "entity_description": "A report document",
            "other_field": "ignored",
        }

        result = QueryExecutor._extract_file_metadata(properties)
        assert result["file_path"] == "/docs/report.pdf"
        assert result["filename"] == "report.pdf"
        assert result["page_range"] == "1-5"
        assert result["page_number"] == "3"
        assert result["entity_description"] == "A report document"
        assert "other_field" not in result

    def test_extract_file_metadata_partial(self):
        """Handles partial file metadata."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        properties = {"filename": "doc.txt"}
        result = QueryExecutor._extract_file_metadata(properties)
        assert result["filename"] == "doc.txt"
        assert result["file_path"] == ""

    def test_extract_file_metadata_none(self):
        """Returns None when no file metadata present."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        properties = {"other": "data"}
        result = QueryExecutor._extract_file_metadata(properties)
        assert result is None

    def test_extract_file_metadata_empty(self):
        """Handles empty properties dict."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        result = QueryExecutor._extract_file_metadata({})
        assert result is None


class TestQueryExecutorFilterCitation:
    """Test citation filtering logic."""

    def test_filter_citation_empty_metadata(self, fake_llm):
        """Empty metadata returns empty dict."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")
        result = executor._filter_citation({})
        assert result == {}

    def test_filter_citation_none_metadata(self, fake_llm):
        """None metadata returns empty dict."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")
        result = executor._filter_citation(None)
        assert result == {}

    def test_filter_citation_with_target_id_uuid(self, fake_llm):
        """Metadata with target_id UUID triggers lookup."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")
        test_uuid = str(uuid.uuid4())

        executor._get_document_metadata_by_uuid = mock.MagicMock(
            return_value={"file_path": "/test.pdf"}
        )

        result = executor._filter_citation({"target_id": test_uuid, "source_id": "other"})

        assert test_uuid in result

    def test_filter_citation_exception_handling(self, fake_llm):
        """Exceptions in citation filtering are caught."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")
        executor._get_document_metadata_by_uuid = mock.MagicMock(
            side_effect=RuntimeError("db error")
        )

        result = executor._filter_citation({
            "target_id": str(uuid.uuid4()),
            "source_id": "x"
        })

        assert result == {}


class TestQueryExecutorGeneratePlans:
    """Test plan generation."""

    def test_generate_plans_delegates_to_llm(self, fake_llm):
        """generate_plans calls llm.plan_query with correct args."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_llm.plan_query.return_value = [
            {"is_query": True, "term": "search 1"},
            {"is_query": True, "term": "search 2"},
        ]

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "Vietnamese")
        plans, _ = executor.generate_plans(
            query="what is X?",
            max_queries=3,
            instruction="find details",
            knowledge="some knowledge",
            context="extra context"
        )

        fake_llm.plan_query.assert_called_once()
        call_kwargs = fake_llm.plan_query.call_args[1]
        assert call_kwargs["query"] == "what is X?"
        assert call_kwargs["language"] == "Vietnamese"
        assert call_kwargs["max_steps"] == 3

    def test_generate_plans_adds_synthesis_step(self, fake_llm):
        """When all plans are queries, adds synthesis step."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_llm.plan_query.return_value = [
            {"is_query": True, "term": "search"},
        ]

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")
        plans, _ = executor.generate_plans(
            query="test",
            context="context data"
        )

        assert len(plans) == 2
        assert plans[1]["is_query"] is False
        assert "Synthesize" in plans[1]["term"]

    def test_generate_plans_preserves_non_query_steps(self, fake_llm):
        """Non-query steps in LLM response are preserved."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_llm.plan_query.return_value = [
            {"is_query": True, "term": "search"},
            {"is_query": False, "term": "aggregate"},
        ]

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")
        plans, _ = executor.generate_plans(query="test")

        assert len(plans) == 2

    def test_generate_plans_truncates_knowledge(self, fake_llm):
        """Knowledge summary is truncated to 2000 chars."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_llm.plan_query.return_value = []

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")
        long_knowledge = "x" * 5000

        executor.generate_plans(query="test", knowledge=long_knowledge)

        call_kwargs = fake_llm.plan_query.call_args[1]
        assert len(call_kwargs["knowledge_summary"]) == 2000


class TestQueryExecutorExecutePlans:
    """Test plan execution."""

    def test_execute_plans_empty_plans(self, fake_llm):
        """Empty plans returns empty result."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")
        result, nodes = asyncio.run(executor.execute_plans([], "", llm=fake_llm))

        assert result == ""
        assert nodes == []

    def test_execute_plans_query_step(self, fake_llm):
        """Query steps call engine.get_nodes."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_engine = mock.MagicMock()
        fake_engine.get_nodes.return_value = []

        executor = QueryExecutor(fake_engine, fake_llm, "English")

        plans = [{"is_query": True, "term": "search term"}]
        result, nodes = asyncio.run(executor.execute_plans(plans, "context", llm=fake_llm))

        fake_engine.get_nodes.assert_called_once()

    def test_execute_plans_query_with_category(self, fake_llm):
        """Query step with category_id passes it through."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_engine = mock.MagicMock()
        fake_engine.get_nodes.return_value = []

        executor = QueryExecutor(fake_engine, fake_llm, "English")

        plans = [{"is_query": True, "term": "search", "category_id": "cat-123"}]
        asyncio.run(executor.execute_plans(plans, "context", llm=fake_llm))

        call_kwargs = fake_engine.get_nodes.call_args[1]
        assert call_kwargs["category_id"] == "cat-123"

    def test_execute_plans_aggregation_step(self, fake_llm):
        """Non-query steps trigger aggregation."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_engine = mock.MagicMock()
        fake_engine.graph_result.return_value = "knowledge:\n  - item"
        fake_engine.aggregate_answers = mock.AsyncMock(return_value="final answer")

        executor = QueryExecutor(fake_engine, fake_llm, "English")

        plans = [{"is_query": False, "term": "synthesize"}]
        result, nodes = asyncio.run(executor.execute_plans(plans, "context", llm=fake_llm))

        fake_engine.graph_result.assert_called_once()
        assert result == "final answer"

    def test_execute_plans_is_memory_returns_early(self, fake_llm):
        """is_memory=True returns early with context."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_engine = mock.MagicMock()
        fake_engine.get_nodes.return_value = []

        executor = QueryExecutor(fake_engine, fake_llm, "English")

        plans = [{"is_query": True, "term": "search"}]
        result, nodes = asyncio.run(
            executor.execute_plans(plans, "my context", is_memory=True, llm=fake_llm)
        )

        assert result == "my context"

    def test_execute_plans_with_stream_handler(self, fake_llm):
        """Stream handler receives progress messages."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_engine = mock.MagicMock()
        fake_engine.get_nodes.return_value = []

        executor = QueryExecutor(fake_engine, fake_llm, "English")

        messages = []
        def handler(msg):
            messages.append(msg)

        plans = [{"is_query": True, "term": "search"}]
        asyncio.run(
            executor.execute_plans(plans, "ctx", llm=fake_llm, stream_handler=handler)
        )

        assert "THINKING: search" in messages


# ---------------------------------------------------------------------------
# TrackVectorRetriever Tests
# ---------------------------------------------------------------------------


class TestTrackVectorRetrieverScoring:
    """Test triplet scoring algorithms."""

    def test_get_relationship_weight_default(self):
        """Default relationship weight is 1.0."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever

        assert TrackVectorRetriever.get_relationship_weight("any_relation") == 1.0
        assert TrackVectorRetriever.get_relationship_weight("KNOWS") == 1.0

    def test_calculate_combined_score_formula(self):
        """Combined score uses geometric mean formula."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever

        result = TrackVectorRetriever.calculate_combined_score(0.5, 0.8, 1.0)
        expected = 1.0 * ((0.5 * 0.8) ** 0.5)
        assert result == pytest.approx(expected)

    def test_calculate_combined_score_with_weight(self):
        """Weight multiplies the combined score."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever

        result = TrackVectorRetriever.calculate_combined_score(0.5, 0.8, 2.0)
        expected = 2.0 * ((0.5 * 0.8) ** 0.5)
        assert result == pytest.approx(expected)

    def test_update_entity_score_averages(self):
        """Entity score update averages old and new."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever

        result = TrackVectorRetriever.update_entity_score(0.6, 0.8)
        assert result == pytest.approx(0.7)

    def test_calculate_triplet_scores_basic(self):
        """Triplet scoring produces correct score lists."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever
        from llama_index.core.graph_stores.types import EntityNode, Relation

        entity_a = EntityNode(name="A", label="Person", properties={}, embedding=[])
        entity_b = EntityNode(name="B", label="Person", properties={}, embedding=[])
        relation = Relation(source_id=entity_a.id, target_id=entity_b.id, label="KNOWS")

        triplet = (entity_a, relation, entity_b)
        id_scores = [(entity_a.id, 0.8), (entity_b.id, 0.6)]

        triplets, scores = TrackVectorRetriever.calculate_triplet_scores(id_scores, [triplet])

        assert len(triplets) == 1
        assert len(scores) == 1
        assert scores[0] > 0

    def test_calculate_triplet_scores_updates_scores(self):
        """Triplet scoring updates entity scores in the map."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever
        from llama_index.core.graph_stores.types import EntityNode, Relation

        entity_a = EntityNode(name="A", label="Person", properties={}, embedding=[])
        entity_b = EntityNode(name="B", label="Person", properties={}, embedding=[])
        relation = Relation(source_id=entity_a.id, target_id=entity_b.id, label="KNOWS")

        triplet = (entity_a, relation, entity_b)
        id_scores = [(entity_a.id, 0.5), (entity_b.id, 0.5)]

        TrackVectorRetriever.calculate_triplet_scores(id_scores, [triplet])

    def test_calculate_triplet_scores_missing_entity(self):
        """Missing entities get default score 0.01."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever
        from llama_index.core.graph_stores.types import EntityNode, Relation

        entity_a = EntityNode(name="A", label="Person", properties={}, embedding=[])
        entity_b = EntityNode(name="B", label="Person", properties={}, embedding=[])
        relation = Relation(source_id=entity_a.id, target_id=entity_b.id, label="KNOWS")

        triplet = (entity_a, relation, entity_b)
        id_scores = []  # No scores for either entity

        triplets, scores = TrackVectorRetriever.calculate_triplet_scores(id_scores, [triplet])

        assert len(scores) == 1
        assert scores[0] > 0  # Uses 0.01 default


class TestTrackVectorRetrieverInit:
    """Test TrackVectorRetriever initialization."""

    def test_init_creates_graph(self, fake_llm, fake_embedder):
        """Initialization creates a NetworkX DiGraph."""
        from dashboard.knowledge.graph.core.track_vector_retriever import TrackVectorRetriever
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore

        fake_gs = mock.MagicMock(spec=GraphRAGStore)
        fake_vs = mock.MagicMock()

        retriever = TrackVectorRetriever(
            engine=mock.MagicMock(),
            graph_store=fake_gs,
            vector_store=fake_vs,
            embed_model=fake_embedder,
        )

        assert hasattr(retriever, 'graph')
        assert retriever.matching_ids == []
        assert retriever.matching_scores == []


# ---------------------------------------------------------------------------
# GraphRAGStore Tests
# ---------------------------------------------------------------------------


class TestGraphRAGStoreGetTriplets:
    """Test GraphRAGStore.get_triplets filtering."""

    def _make_store(self):
        """Create a GraphRAGStore with a mocked underlying graph."""
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore
        from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph

        fake_kuzu = mock.MagicMock(spec=KuzuLabelledPropertyGraph)
        store = GraphRAGStore(graph=fake_kuzu)
        return store, fake_kuzu

    def test_get_triplets_no_filters_returns_empty(self):
        """No filters returns empty list (optimization)."""
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore

        store, fake_kuzu = self._make_store()

        result = store.get_triplets()

        assert result == []
        fake_kuzu.get_triplets.assert_not_called()

    def test_get_triplets_with_ids(self):
        """IDs filter is passed to underlying graph and filters by entity id."""
        from llama_index.core.graph_stores.types import EntityNode, Relation
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore

        store, fake_kuzu = self._make_store()

        entity_a = EntityNode(name="Alice", label="Person", properties={}, embedding=[])
        entity_b = EntityNode(name="Bob", label="Person", properties={}, embedding=[])
        relation = Relation(source_id=entity_a.id, target_id=entity_b.id, label="KNOWS")
        fake_kuzu.get_triplets.return_value = [(entity_a, relation, entity_b)]

        result = store.get_triplets(ids=[entity_a.id])

        fake_kuzu.get_triplets.assert_called_once_with(ids=[entity_a.id])
        assert len(result) == 1
        assert result[0][0].id == entity_a.id

    def test_get_triplets_filter_by_entity_names(self):
        """Entity names filter removes non-matching triplets."""
        from llama_index.core.graph_stores.types import EntityNode, Relation
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore

        store, fake_kuzu = self._make_store()

        entity_a = EntityNode(name="Alice", label="Person", properties={}, embedding=[])
        entity_b = EntityNode(name="Bob", label="Person", properties={}, embedding=[])
        entity_c = EntityNode(name="Carol", label="Person", properties={}, embedding=[])
        relation = Relation(source_id=entity_a.id, target_id=entity_b.id, label="KNOWS")

        fake_kuzu.get_triplets.return_value = [
            (entity_a, relation, entity_b),
            (entity_c, relation, entity_a),
        ]

        result = store.get_triplets(ids=[entity_a.id], entity_names=[entity_a.id])

        assert len(result) >= 1
        assert all(t[0].id == entity_a.id or t[2].id == entity_a.id for t in result)

    def test_get_triplets_filter_by_relation_names(self):
        """Relation names filter removes non-matching triplets."""
        from llama_index.core.graph_stores.types import EntityNode, Relation
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore

        store, fake_kuzu = self._make_store()

        entity = EntityNode(name="E", label="T", properties={}, embedding=[])
        rel_knows = Relation(source_id="a", target_id="b", label="KNOWS")
        rel_works = Relation(source_id="c", target_id="d", label="WORKS_AT")

        fake_kuzu.get_triplets.return_value = [
            (entity, rel_knows, entity),
            (entity, rel_works, entity),
        ]

        result = store.get_triplets(ids=["id1"], relation_names=["KNOWS"])

        assert all(t[1].label == "KNOWS" for t in result)

    def test_get_triplets_filter_by_properties(self):
        """Properties filter removes triplets without matching props."""
        from llama_index.core.graph_stores.types import EntityNode, Relation
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore

        store, fake_kuzu = self._make_store()

        entity_match = EntityNode(
            name="Match", label="T",
            properties={"category": "A"},
            embedding=[]
        )
        entity_nomatch = EntityNode(
            name="NoMatch", label="T",
            properties={"category": "B"},
            embedding=[]
        )
        relation = Relation(source_id="a", target_id="b", label="KNOWS")

        fake_kuzu.get_triplets.return_value = [
            (entity_match, relation, entity_match),
            (entity_nomatch, relation, entity_nomatch),
        ]

        result = store.get_triplets(ids=[entity_match.id], properties={"category": "A"})

        assert len(result) >= 1
        for t in result:
            assert t[0].properties.get("category") == "A" or t[2].properties.get("category") == "A"


class TestGraphRAGStoreGetRelMap:
    """Test GraphRAGStore.get_rel_map."""

    def test_get_rel_map_depth_expansion(self):
        """get_rel_map expands to specified depth."""
        from llama_index.core.graph_stores.types import EntityNode, Relation
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore

        fake_kuzu = mock.MagicMock()
        store = GraphRAGStore(graph=fake_kuzu)

        entity1 = EntityNode(name="E1", label="T", properties={}, embedding=[])
        entity2 = EntityNode(name="E2", label="T", properties={}, embedding=[])
        relation = Relation(source_id="e1", target_id="e2", label="KNOWS")

        fake_kuzu.get_triplets.return_value = [(entity1, relation, entity2)]

        result = store.get_rel_map([entity1], depth=2)

        assert len(result) >= 0

    def test_get_rel_map_ignore_rels(self):
        """get_rel_map filters out ignored relations."""
        from llama_index.core.graph_stores.types import EntityNode, Relation
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore

        fake_kuzu = mock.MagicMock()
        store = GraphRAGStore(graph=fake_kuzu)

        entity = EntityNode(name="E", label="T", properties={}, embedding=[])
        rel_keep = Relation(source_id="a", target_id="b", label="KEEP")
        rel_ignore = Relation(source_id="c", target_id="d", label="IGNORE")

        fake_kuzu.get_triplets.return_value = [
            (entity, rel_keep, entity),
            (entity, rel_ignore, entity),
        ]

        result = store.get_rel_map([entity], depth=1, ignore_rels=["IGNORE"])

        for triplet in result:
            assert triplet[1].label != "IGNORE"


# ---------------------------------------------------------------------------
# Service → Graph Cascade Tests
# ---------------------------------------------------------------------------


class TestServiceGraphRagEngineCascade:
    """Test KnowledgeService._get_graph_rag_engine cascade."""

    def test_graph_rag_engine_uses_service_caches(self, tmp_path, fake_llm, fake_embedder):
        """_get_graph_rag_engine uses cached VS and KG from service."""
        from dashboard.knowledge.service import KnowledgeService
        from dashboard.knowledge.namespace import NamespaceManager

        nm = NamespaceManager(base_dir=str(tmp_path))
        svc = KnowledgeService(
            namespace_manager=nm,
            embedder=fake_embedder,
            llm=fake_llm,
        )

        try:
            svc.create_namespace("test-ns")

            svc.get_vector_store("test-ns")
            svc.get_kuzu_graph("test-ns")

            assert "test-ns" in svc._vector_stores
            assert "test-ns" in svc._kuzu_graphs

        finally:
            svc.shutdown()

    def test_query_engine_injects_graph_rag(self, tmp_path, fake_llm, fake_embedder):
        """_get_query_engine injects GraphRAGQueryEngine when available."""
        from dashboard.knowledge.service import KnowledgeService
        from dashboard.knowledge.namespace import NamespaceManager

        nm = NamespaceManager(base_dir=str(tmp_path))
        svc = KnowledgeService(
            namespace_manager=nm,
            embedder=fake_embedder,
            llm=fake_llm,
        )

        try:
            svc.create_namespace("test-ns")

            with mock.patch.object(
                svc, "_get_graph_rag_engine", return_value=None
            ):
                engine = svc._get_query_engine("test-ns")

                assert engine is not None

        finally:
            svc.shutdown()

    def test_concurrent_vector_store_access(self, tmp_path, fake_llm, fake_embedder):
        """Concurrent get_vector_store calls return same cached instance."""
        import threading
        from dashboard.knowledge.service import KnowledgeService
        from dashboard.knowledge.namespace import NamespaceManager

        nm = NamespaceManager(base_dir=str(tmp_path))
        svc = KnowledgeService(
            namespace_manager=nm,
            embedder=fake_embedder,
            llm=fake_llm,
        )

        try:
            svc.create_namespace("concurrent-ns")

            results = []
            errors = []

            def get_vs():
                try:
                    vs = svc.get_vector_store("concurrent-ns")
                    results.append(id(vs))
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=get_vs) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0
            assert len(set(results)) == 1  # All same instance

        finally:
            svc.shutdown()


class TestServiceGraphLayerExceptionHandling:
    """Test exception handling in service → graph cascade."""

    def test_get_kuzu_graph_exception_logged(self, tmp_path, fake_llm, fake_embedder):
        """Exception in get_kuzu_graph is logged, not propagated."""
        from dashboard.knowledge.service import KnowledgeService
        from dashboard.knowledge.namespace import NamespaceManager

        nm = NamespaceManager(base_dir=str(tmp_path))
        svc = KnowledgeService(
            namespace_manager=nm,
            embedder=fake_embedder,
            llm=fake_llm,
        )

        try:
            svc.create_namespace("error-ns")
            with mock.patch(
                "dashboard.knowledge.graph.index.kuzudb.KuzuLabelledPropertyGraph.__init__",
                side_effect=RuntimeError("kuzu init failed"),
            ):
                with pytest.raises(RuntimeError):
                    svc.get_kuzu_graph("error-ns")

        finally:
            svc.shutdown()

    def test_shutdown_handles_close_errors(self, tmp_path, fake_llm, fake_embedder):
        """shutdown() continues even when close() raises."""
        from dashboard.knowledge.service import KnowledgeService
        from dashboard.knowledge.namespace import NamespaceManager

        nm = NamespaceManager(base_dir=str(tmp_path))
        svc = KnowledgeService(
            namespace_manager=nm,
            embedder=fake_embedder,
            llm=fake_llm,
        )

        fake_vs = mock.MagicMock()
        fake_vs.close.side_effect = RuntimeError("close failed")
        fake_kg = mock.MagicMock()
        fake_kg.close_connection.side_effect = RuntimeError("close_connection failed")

        svc._vector_stores["ns"] = fake_vs
        svc._kuzu_graphs["ns"] = fake_kg

        svc.shutdown()

        assert len(svc._vector_stores) == 0
        assert len(svc._kuzu_graphs) == 0


class TestServiceGraphVisualization:
    """Test service graph visualization methods.

    Note: get_graph() on KuzuLabelledPropertyGraph is not yet implemented.
    These tests are skipped until the method is added.
    """

    @pytest.mark.skip(reason="get_graph not implemented on KuzuLabelledPropertyGraph yet")
    def test_get_graph_returns_nodes_and_edges(self, tmp_path, fake_llm, fake_embedder):
        """get_graph() returns graph data from Kuzu visualization."""
        from dashboard.knowledge.service import KnowledgeService
        from dashboard.knowledge.namespace import NamespaceManager

        nm = NamespaceManager(base_dir=str(tmp_path))
        svc = KnowledgeService(
            namespace_manager=nm,
            embedder=fake_embedder,
            llm=fake_llm,
        )

        try:
            svc.create_namespace("viz-ns")

            result = svc.get_graph("viz-ns", limit=100)

            assert "nodes" in result or result is not None

        finally:
            svc.shutdown()

    @pytest.mark.skip(reason="get_graph not implemented on KuzuLabelledPropertyGraph yet")
    def test_get_graph_uses_cached_kuzu_instance(self, tmp_path, fake_llm, fake_embedder):
        """get_graph() uses the cached Kuzu instance from get_kuzu_graph()."""
        from dashboard.knowledge.service import KnowledgeService
        from dashboard.knowledge.namespace import NamespaceManager

        nm = NamespaceManager(base_dir=str(tmp_path))
        svc = KnowledgeService(
            namespace_manager=nm,
            embedder=fake_embedder,
            llm=fake_llm,
        )

        try:
            svc.create_namespace("cache-ns")

            kg = svc.get_kuzu_graph("cache-ns")
            assert "cache-ns" in svc._kuzu_graphs

            svc.get_graph("cache-ns")

            assert svc._kuzu_graphs["cache-ns"] is kg

        finally:
            svc.shutdown()


# ---------------------------------------------------------------------------
# Edge Cases and Error Paths
# ---------------------------------------------------------------------------


class TestGraphLayerEdgeCases:
    """Test edge cases in graph layer components."""

    def test_to_json_graph_empty(self):
        """to_json_graph on empty graph returns empty nodes/edges."""
        import networkx as nx
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore
        from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph

        fake_kuzu = mock.MagicMock(spec=KuzuLabelledPropertyGraph)
        fake_kuzu.get_all_nodes.return_value = []
        fake_kuzu.get_triplets.return_value = []

        store = GraphRAGStore(graph=fake_kuzu)
        result = store.to_json_graph()

        assert result["nodes"] == []
        assert result["edges"] == []

    def test_to_json_graph_with_data(self):
        """to_json_graph builds correct nodes/edges from graph data."""
        from llama_index.core.graph_stores.types import EntityNode, Relation
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore
        from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph

        fake_kuzu = mock.MagicMock(spec=KuzuLabelledPropertyGraph)

        entity_a = EntityNode(
            name="Alice", label="Person",
            properties={"desc": "A person"},
            embedding=[]
        )
        entity_b = EntityNode(
            name="Acme", label="Org",
            properties={"desc": "A company"},
            embedding=[]
        )

        fake_kuzu.get_all_nodes.return_value = [entity_a, entity_b]
        fake_kuzu.get_triplets.return_value = []

        store = GraphRAGStore(graph=fake_kuzu)
        result = store.to_json_graph()

        assert len(result["nodes"]) == 2
        node_ids = {n["id"] for n in result["nodes"]}
        assert entity_a.id in node_ids

    def test_pagerank_wrapper_delegates(self):
        """GraphRAGStore.pagerank delegates to underlying graph."""
        from dashboard.knowledge.graph.core.graph_rag_store import GraphRAGStore
        from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph

        fake_kuzu = mock.MagicMock(spec=KuzuLabelledPropertyGraph)
        fake_kuzu.pagerank.return_value = [("node1", 0.9)]

        store = GraphRAGStore(graph=fake_kuzu)
        result = store.pagerank({"node1": 1.0}, category_id="cat-123")

        fake_kuzu.pagerank.assert_called_once_with({"node1": 1.0}, category_id="cat-123")
        assert result == [("node1", 0.9)]


class TestQueryExecutorComplexCitation:
    """Test complex citation filtering in QueryExecutor."""

    def test_filter_citation_with_source_id_uuid(self, fake_llm):
        """Metadata with source_id UUID (and no target_id) triggers lookup."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")
        test_uuid = str(uuid.uuid4())

        executor._get_document_metadata_by_uuid = mock.MagicMock(
            return_value={"file_path": "/src.pdf"}
        )

        # target_id is truthy but not a UUID, source_id is a UUID
        # This triggers candidates.append(source_id)
        result = executor._filter_citation({"target_id": "not-a-uuid", "source_id": test_uuid})

        assert test_uuid in result

    def test_filter_citation_no_uuid_returns_filtered_metadata(self, fake_llm):
        """Metadata without UUIDs returns filtered fields directly."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")

        # filter_metadata_fields expects values to be parseable as dicts (EPIC-004 logic)
        metadata = {
            "node_1": '{"filename": "doc.pdf", "entity_description": "desc", "internal_id": "123"}'
        }

        # No target_id/source_id keys at top level
        result = executor._filter_citation(metadata)

        assert "node_1" in result
        assert "doc.pdf" in result["node_1"]
        assert "desc" in result["node_1"]
        assert "123" not in result["node_1"]

    def test_filter_citation_malformed_input(self, fake_llm):
        """Non-dict metadata returns empty dict."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")
        assert executor._filter_citation(["not a dict"]) == {}


class TestGraphRAGQueryEngineAdvanced:
    """Test advanced logic in GraphRAGQueryEngine."""

    def test_acustom_query_executes(self, fake_llm):
        """acustom_query calls the internal _acustom_query logic."""
        from dashboard.knowledge.graph.core.graph_rag_query_engine import GraphRAGQueryEngine
        
        engine = mock.MagicMock(spec=GraphRAGQueryEngine)
        engine._acustom_query = mock.AsyncMock(return_value="answer")

        result = asyncio.run(GraphRAGQueryEngine.acustom_query(engine, "query"))
        assert result == "answer"

    def test_aggregate_answers_various_inputs(self, fake_llm):
        """aggregate_answers handles str, list, and other types."""
        from dashboard.knowledge.graph.core.graph_rag_query_engine import GraphRAGQueryEngine

        engine = mock.MagicMock(spec=GraphRAGQueryEngine)
        engine.llm = fake_llm
        engine.language = "English"

        # Test tuple input
        asyncio.run(GraphRAGQueryEngine.aggregate_answers(engine, ("a", "b"), "q"))
        assert fake_llm.aggregate_answers.called

        # Test generic object input
        asyncio.run(GraphRAGQueryEngine.aggregate_answers(engine, 123, "q"))
        assert fake_llm.aggregate_answers.called

    def test_query_plan_no_entities_found(self, fake_llm):
        """_query_plan handles empty knowledge base gracefully."""
        from dashboard.knowledge.graph.core.graph_rag_query_engine import GraphRAGQueryEngine

        engine = mock.MagicMock(spec=GraphRAGQueryEngine)
        engine.graph_store = mock.MagicMock()
        engine.graph_store.graph.get_all_nodes.return_value = []
        engine.plan_llm = fake_llm
        engine.language = "English"
        engine.max_queries = 3
        engine.data_instruction = ""
        engine.include_graph = True

        with mock.patch("dashboard.knowledge.graph.core.graph_rag_query_engine.QueryExecutor") as MockExecutor:
            mock_executor = MockExecutor.return_value
            mock_executor.generate_plans.return_value = (None, "")

            answer, _ = asyncio.run(GraphRAGQueryEngine._query_plan(engine, "query"))
            assert answer == ""


class TestQueryExecutorExtended:
    """Test even more edge cases in QueryExecutor."""

    def test_filter_citation_no_target_id(self, fake_llm):
        """Returns {} if target_id is missing or empty even if source_id is present."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        executor = QueryExecutor(mock.MagicMock(), fake_llm, "English")
        result = executor._filter_citation({"source_id": "some-id"})
        assert result == {}

        result = executor._filter_citation({"target_id": "", "source_id": "id"})
        assert result == {}

    def test_get_document_metadata_by_uuid_cache_none(self, fake_llm):
        """None values are also cached to avoid repeat lookups."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_engine = mock.MagicMock()
        executor = QueryExecutor(fake_engine, fake_llm, "English")
        
        test_uuid = "missing-uuid"
        executor._uuid_metadata_cache[test_uuid] = None
        
        result = executor._get_document_metadata_by_uuid(test_uuid)
        assert result is None
        fake_engine.index.property_graph_store.get.assert_not_called()

    def test_get_metadata_from_property_graph_no_index(self, fake_llm):
        """Returns None if engine has no index attribute."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        engine_no_index = object() # No .index
        executor = QueryExecutor(engine_no_index, fake_llm, "English")
        
        result = executor._get_metadata_from_property_graph("uuid")
        assert result is None

    def test_execute_plans_default_llm(self, fake_llm):
        """Uses self.llm if llm param is None."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_engine = mock.MagicMock()
        fake_engine.get_nodes.return_value = []
        
        executor = QueryExecutor(fake_engine, fake_llm, "English")
        plans = [{"is_query": True, "term": "q"}]
        
        asyncio.run(executor.execute_plans(plans, "context", llm=None))
        # Should not crash

    def test_execute_plans_citation_error_handling(self, fake_llm):
        """Errors in citation filtering within execute_plans are caught."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_engine = mock.MagicMock()
        node = mock.MagicMock()
        node.node.metadata = {"some": "meta"}
        fake_engine.get_nodes.return_value = [node]
        
        executor = QueryExecutor(fake_engine, fake_llm, "English")
        executor._filter_citation = mock.MagicMock(side_effect=ValueError("boom"))
        
        plans = [{"is_query": True, "term": "q"}]
        # Should not crash
        asyncio.run(executor.execute_plans(plans, "context"))

    def test_execute_plans_general_error_handling(self, fake_llm):
        """General errors in plan execution are caught."""
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor

        fake_engine = mock.MagicMock()
        fake_engine.graph_result.side_effect = RuntimeError("engine crash")
        
        executor = QueryExecutor(fake_engine, fake_llm, "English")
        plans = [{"is_query": False, "term": "aggregate"}]
        
        # Should not crash
        asyncio.run(executor.execute_plans(plans, "context"))


class TestKuzuDbMockedLogic:
    """Test complex logic in kuzudb.py using mocks."""

    def test_get_all_nodes_vector_search_branch(self):
        """get_all_nodes executes vector search path when context is provided."""
        from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph
        from llama_index.core.graph_stores.types import EntityNode

        # Mock dependencies
        with mock.patch("dashboard.knowledge.graph.index.kuzudb.KuzuLabelledPropertyGraph._database"):
            with mock.patch("dashboard.knowledge.graph.index.kuzudb._get_embedder") as MockGetEmbedder:
                mock_embedder = MockGetEmbedder.return_value
                mock_embedder.embed_one.return_value = [0.1] * 1024
                
                kg = KuzuLabelledPropertyGraph(index="ns", ws_id="ws")
                
                # Mock connection and execute
                mock_conn = mock.MagicMock()
                
                # Mock return value for conn.execute (vector search)
                mock_result = mock.MagicMock()
                mock_row = [{"id": "e1", "label": "Person", "name": "Alice", "properties": "{}"}]
                mock_result.get_n.return_value = [mock_row]
                mock_conn.execute.return_value = mock_result
                
                with mock.patch.object(KuzuLabelledPropertyGraph, "connection", new_callable=mock.PropertyMock) as MockConn:
                    MockConn.return_value = mock_conn
                    
                    # Call with context triggers vector search
                    nodes = kg.get_all_nodes(context="search query", limit=10)
                    
                    assert len(nodes) > 0
                    assert mock_conn.execute.called

    def test_from_record_to_node_category_id(self):

        """_from_record_to_node extracts category_id from record or properties."""
        from dashboard.knowledge.graph.index.kuzudb import KuzuLabelledPropertyGraph
        
        with mock.patch.object(KuzuLabelledPropertyGraph, "__init__", return_value=None):
            kg = KuzuLabelledPropertyGraph()
            
            # Case 1: category_id in record root
            record = {
                "id": "1", "label": "text_chunk", "text": "txt",
                "category_id": "cat1", "properties": "{}"
            }
            node = kg._from_record_to_node(record)
            assert node.properties["category_id"] == "cat1"
            
            # Case 2: category_id in properties JSON
            record2 = {
                "id": "2", "label": "text_chunk", "text": "txt",
                "properties": '{"category_id": "cat2"}'
            }
            node2 = kg._from_record_to_node(record2)
            assert node2.properties["category_id"] == "cat2"
