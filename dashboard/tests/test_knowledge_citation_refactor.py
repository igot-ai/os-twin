"""Tests for the shared citation module and bug fixes.

Covers:
- citation.is_uuid
- citation.format_citation
- citation.resolve_chunk_metadata
- citation.build_citation_dict
- citation.CitationRecord
- citation.extract_file_metadata
- citation.run_async
- llm._effective_provider respects explicit provider (P0 fix)
- llm.plan_query / aggregate_answers graceful fallback (P0 fix)
- query_executioner safe query=None handling (P0 fix)
- llm_client OSTWIN_API_KEY fallback (P1 fix)
- embeddings dimensions guard (P1 fix)
"""

from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# citation.is_uuid
# ---------------------------------------------------------------------------

class TestIsUuid:
    def test_valid_lowercase_uuid(self):
        from dashboard.knowledge.graph.core.citation import is_uuid
        assert is_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_valid_uppercase_uuid_accepted(self):
        from dashboard.knowledge.graph.core.citation import is_uuid
        assert is_uuid("550E8400-E29B-41D4-A716-446655440000") is True

    def test_invalid_uuid(self):
        from dashboard.knowledge.graph.core.citation import is_uuid
        assert is_uuid("not-a-uuid") is False

    def test_empty_string(self):
        from dashboard.knowledge.graph.core.citation import is_uuid
        assert is_uuid("") is False

    def test_non_string(self):
        from dashboard.knowledge.graph.core.citation import is_uuid
        assert is_uuid(123) is False


# ---------------------------------------------------------------------------
# citation.format_citation
# ---------------------------------------------------------------------------

class TestFormatCitation:
    def test_filename_with_page(self):
        from dashboard.knowledge.graph.core.citation import format_citation
        result = format_citation({"filename": "report.pdf", "page_number": "5"})
        assert result == "[report.pdf(5)]"

    def test_filename_with_page_range(self):
        from dashboard.knowledge.graph.core.citation import format_citation
        result = format_citation({"filename": "doc.docx", "page_range": "1-3"})
        assert result == "[doc.docx(1-3)]"

    def test_file_path_only(self):
        from dashboard.knowledge.graph.core.citation import format_citation
        result = format_citation({"file_path": "/data/report.pdf"})
        assert result == "[/data/report.pdf]"

    def test_uuid_fallback(self):
        from dashboard.knowledge.graph.core.citation import format_citation
        result = format_citation({}, uuid_fallback="abc-123")
        assert result == "`abc-123`"

    def test_empty_metadata(self):
        from dashboard.knowledge.graph.core.citation import format_citation
        result = format_citation({})
        assert result == ""


# ---------------------------------------------------------------------------
# citation.CitationRecord
# ---------------------------------------------------------------------------

class TestCitationRecord:
    def test_to_dict(self):
        from dashboard.knowledge.graph.core.citation import CitationRecord
        record = CitationRecord(
            citation="[report.pdf(5)]",
            file_path="/data/report.pdf",
            filename="report.pdf",
        )
        d = record.to_dict()
        assert d["citation"] == "[report.pdf(5)]"
        assert d["file_path"] == "/data/report.pdf"
        assert d["filename"] == "report.pdf"

    def test_frozen(self):
        from dashboard.knowledge.graph.core.citation import CitationRecord
        record = CitationRecord(citation="[x]")
        with pytest.raises(AttributeError):
            record.citation = "[y]"


# ---------------------------------------------------------------------------
# citation.extract_file_metadata
# ---------------------------------------------------------------------------

class TestExtractFileMetadata:
    def test_returns_metadata(self):
        from dashboard.knowledge.graph.core.citation import extract_file_metadata
        props = {"file_path": "/a", "filename": "a.pdf", "page_number": "1"}
        result = extract_file_metadata(props)
        assert result is not None
        assert result["filename"] == "a.pdf"

    def test_returns_none_when_no_file_fields(self):
        from dashboard.knowledge.graph.core.citation import extract_file_metadata
        assert extract_file_metadata({"entity_description": "foo"}) is None

    def test_returns_none_for_empty(self):
        from dashboard.knowledge.graph.core.citation import extract_file_metadata
        assert extract_file_metadata({}) is None
        assert extract_file_metadata(None) is None


# ---------------------------------------------------------------------------
# citation.resolve_chunk_metadata
# ---------------------------------------------------------------------------

class TestResolveChunkMetadata:
    def test_returns_none_when_index_is_none(self):
        from dashboard.knowledge.graph.core.citation import resolve_chunk_metadata
        assert resolve_chunk_metadata(None, "some-uuid") is None

    def test_returns_none_when_no_property_graph_store(self):
        from dashboard.knowledge.graph.core.citation import resolve_chunk_metadata
        index = SimpleNamespace()
        assert resolve_chunk_metadata(index, "some-uuid") is None

    def test_resolves_from_store(self):
        from dashboard.knowledge.graph.core.citation import resolve_chunk_metadata
        node = SimpleNamespace(
            text="chunk text",
            properties={"file_path": "/a", "filename": "a.pdf", "page_number": "1"},
        )
        store = MagicMock()
        store.get.return_value = [node]
        index = SimpleNamespace(property_graph_store=store)
        result = resolve_chunk_metadata(index, "some-uuid")
        assert result is not None
        assert result["filename"] == "a.pdf"
        assert result["info"] == "chunk text"

    def test_returns_none_when_no_file_metadata_fields(self):
        from dashboard.knowledge.graph.core.citation import resolve_chunk_metadata
        node = SimpleNamespace(text="x", properties={"entity_description": "foo"})
        store = MagicMock()
        store.get.return_value = [node]
        index = SimpleNamespace(property_graph_store=store)
        assert resolve_chunk_metadata(index, "some-uuid") is None


# ---------------------------------------------------------------------------
# citation.build_citation_dict
# ---------------------------------------------------------------------------

class TestBuildCitationDict:
    def test_returns_none_for_empty_metadata(self):
        from dashboard.knowledge.graph.core.citation import build_citation_dict
        assert build_citation_dict({}, None) is None
        assert build_citation_dict(None, None) is None

    def test_returns_none_when_no_uuid_candidates(self):
        from dashboard.knowledge.graph.core.citation import build_citation_dict
        assert build_citation_dict({"target_id": "not-uuid"}, None) is None

    def test_builds_from_target_id(self):
        from dashboard.knowledge.graph.core.citation import build_citation_dict
        node = SimpleNamespace(
            text="text",
            properties={"file_path": "/b", "filename": "b.pdf"},
        )
        store = MagicMock()
        store.get.return_value = [node]
        index = SimpleNamespace(property_graph_store=store)
        uuid_val = "550e8400-e29b-41d4-a716-446655440000"
        result = build_citation_dict(
            {"target_id": uuid_val, "source_id": uuid_val},
            index,
        )
        assert result is not None
        assert uuid_val in result
        assert result[uuid_val]["citation"] == "[b.pdf]"
        assert result[uuid_val]["filename"] == "b.pdf"


# ---------------------------------------------------------------------------
# citation.run_async
# ---------------------------------------------------------------------------

class TestRunAsync:
    def test_runs_coroutine(self):
        from dashboard.knowledge.graph.core.citation import run_async

        async def coro():
            return 42

        assert run_async(coro()) == 42

    def test_runs_from_within_running_loop(self):
        from dashboard.knowledge.graph.core.citation import run_async

        async def outer():
            async def inner():
                return 99
            return run_async(inner())

        result = asyncio.run(outer())
        assert result == 99


# ---------------------------------------------------------------------------
# P0 Fix: llm._effective_provider respects explicit provider
# ---------------------------------------------------------------------------

class TestEffectiveProvider:
    def test_explicit_provider_overrides_autodetect(self):
        with patch.dict(os.environ, {}, clear=True):
            from dashboard.knowledge.llm import KnowledgeLLM
            llm = KnowledgeLLM(model="gpt-4", provider="ollama")
            assert llm._effective_provider() == "ollama"

    def test_autodetect_when_no_explicit_provider(self):
        from dashboard.knowledge.llm import KnowledgeLLM
        llm = KnowledgeLLM(model="gpt-4", provider=None)
        provider = llm._effective_provider()
        assert provider in ("openai", "openai-compatible")


# ---------------------------------------------------------------------------
# P0 Fix: llm.plan_query / aggregate_answers graceful fallback
# ---------------------------------------------------------------------------

class TestLLMGracefulDegradation:
    def test_plan_query_fallback_when_unavailable(self):
        from dashboard.knowledge.llm import KnowledgeLLM
        llm = KnowledgeLLM(model="", provider=None)
        result = llm.plan_query("test query")
        assert result == [{"term": "test query", "is_query": True}]

    def test_aggregate_answers_fallback_when_unavailable(self):
        from dashboard.knowledge.llm import KnowledgeLLM
        llm = KnowledgeLLM(model="", provider=None)
        result = llm.aggregate_answers(["snippet A", "snippet B"], "query")
        assert result == "snippet A\n\nsnippet B"

    def test_aggregate_answers_empty_snippets(self):
        from dashboard.knowledge.llm import KnowledgeLLM
        llm = KnowledgeLLM(model="", provider=None)
        result = llm.aggregate_answers([], "query")
        assert result == ""


# ---------------------------------------------------------------------------
# P0 Fix: query_executioner handles query=None
# ---------------------------------------------------------------------------

class TestQueryExecutorSafeDefaults:
    def test_generate_plans_uses_safe_query_in_synthesize(self):
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor
        mock_engine = MagicMock()
        mock_llm = MagicMock()
        mock_llm.plan_query.return_value = [{"term": "search", "is_query": True}]
        executor = QueryExecutor(mock_engine, mock_llm, "English")
        plans, _ = executor.generate_plans(
            query="", max_queries=2, context="ctx"
        )
        synth = [p for p in plans if not p.get("is_query", True)]
        assert len(synth) == 1
        assert "Synthesize data for:" in synth[0]["term"]

    def test_execute_plans_with_none_query_uses_empty_string(self):
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor
        mock_engine = MagicMock()
        mock_llm = MagicMock()
        executor = QueryExecutor(mock_engine, mock_llm, "English")
        mock_engine.get_nodes.return_value = []
        mock_engine.graph_result.return_value = "graph-data"
        mock_engine.aggregate_answers = AsyncMock(return_value="answer")
        result = asyncio.run(executor.execute_plans(
            [{"is_query": False, "term": "synthesize"}],
            "ctx",
            query=None,
        ))
        assert result[0] == "answer"


class TestExecutePlansSafeQuery:
    @pytest.mark.asyncio
    async def test_query_none_does_not_stringify_as_none(self):
        from dashboard.knowledge.graph.core.query_executioner import QueryExecutor
        mock_engine = MagicMock()
        mock_llm = MagicMock()
        executor = QueryExecutor(mock_engine, mock_llm, "English")
        mock_engine.graph_result.return_value = "graph-yaml"
        mock_engine.aggregate_answers = AsyncMock(return_value="answer")
        result, _ = await executor.execute_plans(
            [{"is_query": False, "term": "synthesize"}],
            "ctx",
            query=None,
        )
        assert result == "answer"
        call_args = mock_engine.aggregate_answers.call_args
        context_arg = call_args[0][1]
        assert "None" not in context_arg


# ---------------------------------------------------------------------------
# P1 Fix: OSTWIN_API_KEY fallback in llm_client
# ---------------------------------------------------------------------------

class TestGoogleApiKeyFallback:
    def test_ostwin_api_key_is_tried(self):
        from dashboard.llm_client import _detect_provider_from_model
        assert _detect_provider_from_model("gemini-3-flash") == "google"


# ---------------------------------------------------------------------------
# P1 Fix: embeddings dimensions guard
# ---------------------------------------------------------------------------

class TestEmbeddingsDimensionsGuard:
    def test_dimension_none_does_not_pass_to_ollama(self):
        from dashboard.knowledge.embeddings import KnowledgeEmbedder
        embedder = KnowledgeEmbedder.__new__(KnowledgeEmbedder)
        embedder.model_name = "test-model"
        embedder.provider = "ollama"
        embedder._dimension = None
        with patch("dashboard.knowledge.embeddings.KnowledgeEmbedder._embed_ollama") as mock:
            mock.return_value = [[0.1]]
            embedder.embed(["test"])
            mock.assert_called_once_with(["test"])


# ---------------------------------------------------------------------------
# Backward compat: old import paths still work
# ---------------------------------------------------------------------------

class TestBackwardCompatImports:
    def test_graph_rag_engine_reexports_run_async(self):
        from dashboard.knowledge.graph.core.graph_rag_query_engine import _run_async
        from dashboard.knowledge.graph.core.citation import run_async
        assert _run_async is run_async

    def test_graph_rag_engine_reexports_file_metadata_fields(self):
        from dashboard.knowledge.graph.core.graph_rag_query_engine import FILE_METADATA_FIELDS
        from dashboard.knowledge.graph.core.citation import FILE_METADATA_FIELDS as shared_fields
        assert FILE_METADATA_FIELDS == shared_fields

    def test_query_executioner_reexports_is_uuid_format(self):
        from dashboard.knowledge.graph.core.query_executioner import _is_uuid_format
        from dashboard.knowledge.graph.core.citation import is_uuid
        assert _is_uuid_format is is_uuid

    def test_graph_rag_engine_is_uuid_node_still_works(self):
        from dashboard.knowledge.graph.core.graph_rag_query_engine import GraphRAGQueryEngine
        assert GraphRAGQueryEngine._is_uuid_node("not-a-uuid") is False
        assert GraphRAGQueryEngine._is_uuid_node("550e8400-e29b-41d4-a716-446655440000") is True


# Helper
class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
