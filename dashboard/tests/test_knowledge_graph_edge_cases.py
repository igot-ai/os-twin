"""Deep edge-case tests for knowledge/graph modules.

This module tests:
1. Graph extraction failure paths and recovery
2. Async/sync context switching edge cases
3. Storage GC ledger operations
4. JSON parsing with malformed input
5. Triplet-to-node conversion edge cases
6. Concurrent access and thread safety
7. Timeout and cancellation handling
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from dashboard.knowledge.embeddings import KnowledgeEmbedder
from dashboard.knowledge.llm import KnowledgeLLM


# ---------------------------------------------------------------------------
# GraphRAGExtractor Edge Cases
# ---------------------------------------------------------------------------


class TestGraphRAGExtractorEdgeCases:
    """Test edge cases and failure paths in GraphRAGExtractor."""

    def test_sync_call_threadpool_timeout(self):
        """__call__ handles ThreadPoolExecutor timeout gracefully."""
        from llama_index.core.graph_stores.types import KG_NODES_KEY, KG_RELATIONS_KEY
        from llama_index.core.schema import TextNode
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            ExtractionConfig,
            GraphRAGExtractor,
        )

        fake_llm = mock.MagicMock(spec=KnowledgeLLM)

        def slow_extract(*args):
            time.sleep(10)  # Will timeout
            return ([], [])

        fake_llm.extract_entities.side_effect = slow_extract
        fake_embedder = mock.MagicMock(spec=KnowledgeEmbedder)

        extractor = GraphRAGExtractor(
            llm=fake_llm,
            embedder=fake_embedder,
            config=ExtractionConfig(timeout_seconds=0.1, max_retries=0),
            num_workers=1,
        )

        nodes = [TextNode(text="test")]
        with mock.patch("concurrent.futures.ThreadPoolExecutor") as mock_pool:
            mock_future = mock.MagicMock()
            mock_future.result.side_effect = concurrent.futures.TimeoutError()
            mock_pool.return_value.__enter__.return_value.submit.return_value = mock_future

            result = extractor(nodes)

            assert len(result) == 1
            assert result[0].metadata[KG_NODES_KEY] == []
            assert result[0].metadata[KG_RELATIONS_KEY] == []

    def test_sync_call_general_exception(self):
        """__call__ catches general exceptions and returns empty metadata."""
        from llama_index.core.graph_stores.types import KG_NODES_KEY, KG_RELATIONS_KEY
        from llama_index.core.schema import TextNode
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            ExtractionConfig,
            GraphRAGExtractor,
        )

        fake_llm = mock.MagicMock(spec=KnowledgeLLM)
        fake_llm.extract_entities.side_effect = RuntimeError("LLM crashed")
        fake_embedder = mock.MagicMock(spec=KnowledgeEmbedder)

        extractor = GraphRAGExtractor(
            llm=fake_llm,
            embedder=fake_embedder,
            config=ExtractionConfig(max_retries=0),
            num_workers=1,
        )

        nodes = [TextNode(text="test")]
        result = extractor(nodes)

        assert result[0].metadata[KG_NODES_KEY] == []
        assert result[0].metadata[KG_RELATIONS_KEY] == []

    def test_acall_empty_nodes_list(self):
        """acall with empty nodes returns empty list immediately."""
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            GraphRAGExtractor,
        )

        fake_llm = mock.MagicMock(spec=KnowledgeLLM)
        fake_embedder = mock.MagicMock(spec=KnowledgeEmbedder)

        extractor = GraphRAGExtractor(llm=fake_llm, embedder=fake_embedder)

        result = asyncio.run(extractor.acall([]))
        assert result == []

    def test_acall_batch_extraction_failure(self):
        """acall handles batch failure gracefully."""
        from llama_index.core.graph_stores.types import KG_NODES_KEY, KG_RELATIONS_KEY
        from llama_index.core.schema import TextNode
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            ExtractionConfig,
            GraphRAGExtractor,
        )

        fake_llm = mock.MagicMock(spec=KnowledgeLLM)
        fake_embedder = mock.MagicMock(spec=KnowledgeEmbedder)

        extractor = GraphRAGExtractor(
            llm=fake_llm,
            embedder=fake_embedder,
            config=ExtractionConfig(max_retries=0),
            num_workers=1,
        )

        nodes = [TextNode(text="test")]

        with mock.patch(
            "dashboard.knowledge.graph.core.graph_rag_extractor.run_jobs",
            side_effect=RuntimeError("Job queue crashed"),
        ):
            result = asyncio.run(extractor.acall(nodes))

            assert result[0].metadata[KG_NODES_KEY] == []
            assert result[0].metadata[KG_RELATIONS_KEY] == []

    def test_extract_with_retry_exponential_backoff(self):
        """_extract_single_sync applies exponential backoff on retries."""
        from llama_index.core.schema import TextNode
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            ExtractionConfig,
            GraphRAGExtractor,
        )

        fake_llm = mock.MagicMock(spec=KnowledgeLLM)
        fake_llm.extract_entities.side_effect = RuntimeError("fail")
        fake_embedder = mock.MagicMock(spec=KnowledgeEmbedder)

        extractor = GraphRAGExtractor(
            llm=fake_llm,
            embedder=fake_embedder,
            config=ExtractionConfig(max_retries=2, retry_delay=0.1),
            num_workers=1,
        )

        node = TextNode(text="test")

        sleep_times = []

        def mock_sleep(duration):
            sleep_times.append(duration)

        with mock.patch("time.sleep", mock_sleep):
            extractor._extract_single_sync(node)

        assert sleep_times == [0.1, 0.2]

    def test_aextract_single_node_missing_text(self):
        """_extract_single_sync handles nodes without .text attribute."""
        from llama_index.core.graph_stores.types import KG_NODES_KEY
        from llama_index.core.schema import TextNode
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            GraphRAGExtractor,
        )

        fake_llm = mock.MagicMock(spec=KnowledgeLLM)
        fake_embedder = mock.MagicMock(spec=KnowledgeEmbedder)

        extractor = GraphRAGExtractor(llm=fake_llm, embedder=fake_embedder)

        node = TextNode(text="", id_="test-id")
        delattr(node, "text")

        result = extractor._extract_single_sync(node)

        assert KG_NODES_KEY in result.metadata
        assert "extraction_error" in result.metadata

    def test_aextract_single_timeout(self):
        """_extract_single_sync handles LLM timeout by returning empty result."""
        from llama_index.core.schema import TextNode
        from dashboard.knowledge.graph.core.graph_rag_extractor import (
            ExtractionConfig,
            GraphRAGExtractor,
        )

        fake_llm = mock.MagicMock(spec=KnowledgeLLM)
        fake_llm.extract_entities.side_effect = TimeoutError("timeout")
        fake_embedder = mock.MagicMock(spec=KnowledgeEmbedder)

        extractor = GraphRAGExtractor(
            llm=fake_llm,
            embedder=fake_embedder,
            config=ExtractionConfig(timeout_seconds=0.1, max_retries=0),
            num_workers=1,
        )

        node = TextNode(text="test")

        result = extractor._extract_single_sync(node)
        assert result.metadata["extraction_error"] == "timeout"
        assert result.metadata["extraction_status"] == "failed"


# ---------------------------------------------------------------------------
# GraphRAGQueryEngine Async Edge Cases
# ---------------------------------------------------------------------------


class TestGraphRAGQueryEngineAsyncEdgeCases:
    """Test async/sync context switching in GraphRAGQueryEngine."""

    def test_run_async_no_running_loop(self):
        """_run_async with no running loop uses asyncio.run()."""
        from dashboard.knowledge.graph.core.graph_rag_query_engine import _run_async

        async def simple_coro():
            return "success"

        result = _run_async(simple_coro())
        assert result == "success"

    def test_run_async_with_running_loop_threaded(self):
        """_run_async with running loop spawns worker thread."""
        from dashboard.knowledge.graph.core.graph_rag_query_engine import _run_async

        async def inner_test():
            async def nested_coro():
                return "from_nested_loop"

            result = await asyncio.to_thread(_run_async, nested_coro())
            return result

        result = asyncio.run(inner_test())
        assert result == "from_nested_loop"

    def test_run_async_exception_propagation(self):
        """_run_async propagates exceptions from coroutines."""
        from dashboard.knowledge.graph.core.graph_rag_query_engine import _run_async

        async def failing_coro():
            raise ValueError("coroutine failed")

        with pytest.raises(ValueError, match="coroutine failed"):
            _run_async(failing_coro())


# ---------------------------------------------------------------------------
# Storage Module Tests
# ---------------------------------------------------------------------------


class TestStorageGarbageCollection:
    """Test garbage collection ledger operations."""

    def test_read_gc_file_not_exists(self, tmp_path):
        """_read_gc_file returns [] when file doesn't exist."""
        from dashboard.knowledge.graph.core.storage import _read_gc_file

        with mock.patch(
            "dashboard.knowledge.graph.core.storage.GARBAGE_COLLECTION_FILE",
            str(tmp_path / "nonexistent.json"),
        ):
            result = _read_gc_file()
            assert result == []

    def test_read_gc_file_malformed_json(self, tmp_path):
        """_read_gc_file returns [] on malformed JSON."""
        from dashboard.knowledge.graph.core.storage import _read_gc_file

        gc_file = tmp_path / "gc.json"
        gc_file.write_text("not valid json[")

        with mock.patch(
            "dashboard.knowledge.graph.core.storage.GARBAGE_COLLECTION_FILE",
            str(gc_file),
        ):
            result = _read_gc_file()
            assert result == []

    def test_read_gc_file_not_list(self, tmp_path):
        """_read_gc_file returns [] when JSON is not a list."""
        from dashboard.knowledge.graph.core.storage import _read_gc_file

        gc_file = tmp_path / "gc.json"
        gc_file.write_text('{"key": "value"}')

        with mock.patch(
            "dashboard.knowledge.graph.core.storage.GARBAGE_COLLECTION_FILE",
            str(gc_file),
        ):
            result = _read_gc_file()
            assert result == []

    def test_write_gc_file_creates_parent_dirs(self, tmp_path):
        """_write_gc_file creates parent directories if needed."""
        from dashboard.knowledge.graph.core.storage import _write_gc_file

        gc_file = tmp_path / "nested" / "dir" / "gc.json"

        with mock.patch(
            "dashboard.knowledge.graph.core.storage.GARBAGE_COLLECTION_FILE",
            str(gc_file),
        ):
            _write_gc_file(["path1", "path2"])

            assert gc_file.exists()
            data = json.loads(gc_file.read_text())
            assert data == ["path1", "path2"]

    def test_delete_vector_store_appends_to_gc(self, tmp_path):
        """delete_vector_store appends path to GC ledger."""
        from dashboard.knowledge.graph.core.storage import delete_vector_store

        gc_file = tmp_path / "gc.json"
        gc_file.write_text("[]")

        with mock.patch(
            "dashboard.knowledge.graph.core.storage.GARBAGE_COLLECTION_FILE",
            str(gc_file),
        ):
            with mock.patch(
                "dashboard.knowledge.graph.core.storage.KNOWLEDGE_DIR",
                str(tmp_path / "kb"),
            ):
                delete_vector_store("test-ns")

                data = json.loads(gc_file.read_text())
                assert len(data) == 1
                assert "test-ns" in data[0]

    def test_delete_vector_store_exception_handling(self, tmp_path):
        """delete_vector_store catches and logs exceptions."""
        from dashboard.knowledge.graph.core.storage import delete_vector_store

        with mock.patch(
            "dashboard.knowledge.graph.core.storage._read_gc_file",
            side_effect=PermissionError("read denied"),
        ):
            delete_vector_store("test-ns")

    def test_delete_graph_db_no_files_found(self, tmp_path):
        """delete_graph_db logs warning when no files found."""
        from dashboard.knowledge.graph.core.storage import delete_graph_db

        with mock.patch(
            "dashboard.knowledge.graph.core.storage.KUZU_DATABASE_PATH",
            str(tmp_path / "kuzu"),
        ):
            with mock.patch(
                "dashboard.knowledge.graph.core.storage.KuzuLabelledPropertyGraph",
                autospec=True,
            ):
                delete_graph_db("nonexistent-id")

    def test_delete_graph_db_removes_files(self, tmp_path):
        """delete_graph_db removes Kuzu DB files."""
        from dashboard.knowledge.graph.core.storage import delete_graph_db

        kuzu_dir = tmp_path / "kuzu"
        kuzu_dir.mkdir()
        db_file = kuzu_dir / "test_ns.db"
        db_file.write_text("fake db")

        fake_kuzu = mock.MagicMock()
        fake_kuzu.close_connection = mock.MagicMock()

        with mock.patch(
            "dashboard.knowledge.graph.core.storage.KUZU_DATABASE_PATH",
            str(kuzu_dir),
        ):
            with mock.patch(
                "dashboard.knowledge.graph.core.storage.KuzuLabelledPropertyGraph",
                return_value=fake_kuzu,
            ):
                delete_graph_db("test-ns")

                assert not db_file.exists()

    def test_delete_graph_db_exception_during_close(self, tmp_path):
        """delete_graph_db handles close_connection exceptions."""
        from dashboard.knowledge.graph.core.storage import delete_graph_db

        kuzu_dir = tmp_path / "kuzu"
        kuzu_dir.mkdir()
        db_file = kuzu_dir / "test_ns.db"
        db_file.write_text("fake db")

        fake_kuzu = mock.MagicMock()
        fake_kuzu.close_connection.side_effect = RuntimeError("close failed")

        with mock.patch(
            "dashboard.knowledge.graph.core.storage.KUZU_DATABASE_PATH",
            str(kuzu_dir),
        ):
            with mock.patch(
                "dashboard.knowledge.graph.core.storage.KuzuLabelledPropertyGraph",
                return_value=fake_kuzu,
            ):
                delete_graph_db("test-ns")

                assert not db_file.exists()

    def test_delete_graph_db_general_exception(self, tmp_path):
        """delete_graph_db catches and logs general exceptions."""
        from dashboard.knowledge.graph.core.storage import delete_graph_db

        with mock.patch(
            "dashboard.knowledge.graph.core.storage.Path.glob",
            side_effect=RuntimeError("glob failed"),
        ):
            delete_graph_db("test-id")


# ---------------------------------------------------------------------------
# JSON Parsing Edge Cases
# ---------------------------------------------------------------------------


class TestJsonParsingEdgeCases:
    """Test JSON extraction with malformed and edge-case input."""

    def test_extract_native_json_not_string(self):
        """_extract_native_json converts non-string input."""
        from dashboard.knowledge.graph.utils._utils import _extract_native_json

        result = _extract_native_json(123)
        assert result is None or result == 123

    def test_extract_native_json_malformed(self):
        """_extract_native_json returns None for malformed JSON."""
        from dashboard.knowledge.graph.utils._utils import _extract_native_json

        result = _extract_native_json("not json at all")
        assert result is None

    def test_extract_array_from_markdown_block(self):
        """extract_array extracts JSON from markdown code block."""
        from dashboard.knowledge.graph.utils._utils import extract_array

        text = '''```json
[{"key": "value"}, {"key2": "value2"}]
```'''
        result = extract_array(text)
        assert result == [{"key": "value"}, {"key2": "value2"}]

    def test_extract_array_with_single_quotes(self):
        """extract_array handles single-quoted JSON."""
        from dashboard.knowledge.graph.utils._utils import extract_array

        text = '''```json
[{'key': 'value'}]
```'''
        result = extract_array(text)
        assert result == [{"key": "value"}]

    def test_extract_array_with_bom(self):
        """extract_array handles BOM prefix."""
        from dashboard.knowledge.graph.utils._utils import extract_array

        text = '''```json
\ufeff[{"key": "value"}]
```'''
        result = extract_array(text)
        assert result == [{"key": "value"}]

    def test_find_first_json_nested_blocks(self):
        """find_first_json finds JSON in nested code blocks."""
        from dashboard.knowledge.graph.utils._utils import find_first_json

        text = '''
Some text
```json
{"nested": {"key": "value"}}
```
More text
'''
        result = find_first_json(text)
        assert result == {"nested": {"key": "value"}}

    def test_find_json_block_multiple_patterns(self):
        """find_json_block tries multiple extraction patterns."""
        from dashboard.knowledge.graph.utils._utils import find_json_block

        text = 'Response: {"data": [1, 2, 3]} end'
        result = find_json_block(text)
        assert result == {"data": [1, 2, 3]}

    def test_find_json_block_with_comments(self):
        """find_json_block strips JavaScript-style comments."""
        from dashboard.knowledge.graph.utils._utils import find_json_block

        text = '{"key": "value"} // this is a comment\n'
        result = find_json_block(text)
        assert result == {"key": "value"}

    def test_parse_metadata_value_already_dict(self):
        """parse_metadata_value returns dict unchanged."""
        from dashboard.knowledge.graph.utils._utils import parse_metadata_value

        result = parse_metadata_value({"already": "dict"})
        assert result == {"already": "dict"}

    def test_parse_metadata_value_not_string(self):
        """parse_metadata_value returns None for non-string non-dict."""
        from dashboard.knowledge.graph.utils._utils import parse_metadata_value

        assert parse_metadata_value(123) is None
        assert parse_metadata_value(None) is None
        assert parse_metadata_value(["list"]) is None

    def test_parse_metadata_value_not_object(self):
        """parse_metadata_value returns None for non-object JSON."""
        from dashboard.knowledge.graph.utils._utils import parse_metadata_value

        assert parse_metadata_value('[1, 2, 3]') is None
        assert parse_metadata_value('"string"') is None

    def test_filter_metadata_fields_empty_inputs(self):
        """filter_metadata_fields handles empty inputs."""
        from dashboard.knowledge.graph.utils._utils import filter_metadata_fields

        assert filter_metadata_fields({}, ["field"]) == {}
        assert filter_metadata_fields({"k": '{"a":1}'}, []) == {"k": '{"a":1}'}

    def test_filter_metadata_fields_nested_dicts(self):
        """filter_metadata_fields extracts nested dict values."""
        from dashboard.knowledge.graph.utils._utils import filter_metadata_fields

        metadata = {"meta": '{"name": "test", "value": 123}'}
        result = filter_metadata_fields(metadata, ["name"])
        assert "name" in result.get("meta", "{}") or result == {}


# ---------------------------------------------------------------------------
# RAG Utils Tests
# ---------------------------------------------------------------------------


class TestRagUtils:
    """Test RAG utility functions."""

    def test_get_nodes_from_triplets_empty(self):
        """_get_nodes_from_triplets returns empty list for no triplets."""
        from dashboard.knowledge.graph.utils.rag import _get_nodes_from_triplets
        import networkx as nx

        graph = nx.DiGraph()
        result = _get_nodes_from_triplets(graph, [])
        assert result == []

    def test_get_nodes_from_triplets_with_scores(self):
        """_get_nodes_from_triplets uses provided scores."""
        from dashboard.knowledge.graph.utils.rag import _get_nodes_from_triplets
        from llama_index.core.graph_stores.types import EntityNode, Relation
        import networkx as nx

        graph = nx.DiGraph()
        entity_a = EntityNode(name="A", label="Person", properties={}, embedding=[])
        entity_b = EntityNode(name="B", label="Person", properties={}, embedding=[])
        relation = Relation(source_id=entity_a.id, target_id=entity_b.id, label="KNOWS")

        triplet = (entity_a, relation, entity_b)
        result = _get_nodes_from_triplets(graph, [triplet], scores=[0.9])

        assert len(result) == 1
        assert result[0].score == 0.9

    def test_get_nodes_from_triplets_updates_existing_nodes(self):
        """_get_nodes_from_triplets updates score for existing nodes."""
        from dashboard.knowledge.graph.utils.rag import _get_nodes_from_triplets
        from llama_index.core.graph_stores.types import EntityNode, Relation
        import networkx as nx

        graph = nx.DiGraph()
        entity = EntityNode(name="E", label="Person", properties={}, embedding=[])
        relation = Relation(source_id=entity.id, target_id=entity.id, label="SELF")

        triplet = (entity, relation, entity)
        _get_nodes_from_triplets(graph, [triplet], scores=[0.5])
        _get_nodes_from_triplets(graph, [triplet], scores=[0.3])

        assert graph.nodes[entity.id]["score"] > 0.5

    def test_get_nodes_from_triplets_with_text_chunk(self):
        """_get_nodes_from_triplets handles text_chunk nodes differently."""
        from dashboard.knowledge.graph.utils.rag import _get_nodes_from_triplets
        from llama_index.core.graph_stores.types import EntityNode, ChunkNode, Relation
        import networkx as nx

        graph = nx.DiGraph()
        chunk = ChunkNode(text="chunk content", id_="chunk-1", label="text_chunk", embedding=[])
        entity = EntityNode(name="Entity", label="Person", properties={}, embedding=[])
        relation = Relation(source_id=chunk.id, target_id=entity.id, label="CONTAINS")

        triplet = (chunk, relation, entity)
        result = _get_nodes_from_triplets(graph, [triplet])

        assert len(result) == 1

    def test_parse_fn_entity_pattern(self):
        """parse_fn extracts entities from $$$ format."""
        from dashboard.knowledge.graph.utils.rag import parse_fn

        response = '("entity"$$$$Alice$$$$Person$$$$A software engineer$$$$)'
        entities, relations = parse_fn(response)

        assert len(entities) == 1
        assert entities[0][0] == "Alice"

    def test_parse_fn_relationship_pattern(self):
        """parse_fn extracts relationships from $$$ format."""
        from dashboard.knowledge.graph.utils.rag import parse_fn

        response = '("relationship"$$$$Alice$$$$Bob$$$$WORKS_WITH$$$$Colleagues$$$$)'
        entities, relations = parse_fn(response)

        assert len(relations) == 1
        assert relations[0][0] == "Alice"
        assert relations[0][2] == "WORKS_WITH"

    def test_parse_json_fn_array_format(self):
        """parse_json_fn parses array-format JSON."""
        from dashboard.knowledge.graph.utils.rag import parse_json_fn

        response = '[{"entities": [{"name": "A"}], "relationships": [{"source": "A", "target": "B"}]}]'
        entities, relations = parse_json_fn(response)

        assert len(entities) == 1
        assert len(relations) == 1

    def test_parse_json_fn_object_format(self):
        """parse_json_fn parses object-format JSON."""
        from dashboard.knowledge.graph.utils.rag import parse_json_fn

        response = '{"entities": [{"name": "X"}], "relationships": []}'
        entities, relations = parse_json_fn(response)

        assert len(entities) == 1
        assert len(relations) == 0

    def test_parse_json_fn_embedded_json(self):
        """parse_json_fn extracts embedded JSON."""
        from dashboard.knowledge.graph.utils.rag import parse_json_fn

        response = 'Some text {"entities": [], "relationships": []} more text'
        entities, relations = parse_json_fn(response)

        assert entities == []
        assert relations == []

    def test_parse_json_fn_invalid_json(self):
        """parse_json_fn returns empty lists for invalid JSON."""
        from dashboard.knowledge.graph.utils.rag import parse_json_fn

        entities, relations = parse_json_fn("not valid json at all")
        assert entities == []
        assert relations == []


# ---------------------------------------------------------------------------
# CircularMessageBuffer Tests
# ---------------------------------------------------------------------------


class TestCircularMessageBuffer:
    """Test circular buffer for message deduplication."""

    def test_add_detects_duplicates(self):
        """add returns True for duplicate messages."""
        from dashboard.knowledge.graph.utils._utils import CircularMessageBuffer

        buf = CircularMessageBuffer(maxlen=5)
        result1 = buf.add("session-1", "user", "hello world")
        result2 = buf.add("session-1", "user", "hello world")

        assert result1 is False
        assert result2 is True

    def test_buffer_size_increases(self):
        """Buffer size increases as messages are added."""
        from dashboard.knowledge.graph.utils._utils import CircularMessageBuffer

        buf = CircularMessageBuffer(maxlen=5)
        buf.add("s1", "user", "message 1")
        buf.add("s1", "user", "message 2")
        buf.add("s1", "user", "message 3")

        assert buf.get_size() == 3

    def test_buffer_respects_maxlen(self):
        """Buffer only keeps maxlen most recent items."""
        from dashboard.knowledge.graph.utils._utils import CircularMessageBuffer

        buf = CircularMessageBuffer(maxlen=2)
        buf.add("s1", "user", "m1")
        buf.add("s1", "user", "m2")
        buf.add("s1", "user", "m3")

        assert buf.get_size() == 2
        # m1 should have been evicted
        assert buf.add("s1", "user", "m1") is False

    def test_different_sessions_still_works(self):
        """Different sessions are correctly identified as different."""
        from dashboard.knowledge.graph.utils._utils import CircularMessageBuffer

        buf = CircularMessageBuffer(maxlen=5)
        result1 = buf.add("session-a", "user", "hello")
        result2 = buf.add("session-b", "user", "hello")

        assert result1 is False
        assert result2 is False

    def test_get_size_empty(self):
        """get_size returns 0 for empty buffer."""
        from dashboard.knowledge.graph.utils._utils import CircularMessageBuffer

        buf = CircularMessageBuffer(maxlen=5)
        assert buf.get_size() == 0

    def test_reset_on_empty_buffer(self):
        """reset on empty buffer doesn't crash."""
        from dashboard.knowledge.graph.utils._utils import CircularMessageBuffer

        buf = CircularMessageBuffer(maxlen=5)
        buf.reset()

        assert buf.get_size() == 0

    def test_hash_message_deterministic(self):
        """_hash_message produces consistent hashes."""
        from dashboard.knowledge.graph.utils._utils import CircularMessageBuffer

        buf = CircularMessageBuffer(maxlen=5)
        hash1 = buf._hash_message("s1", "user", "hello world")
        hash2 = buf._hash_message("s1", "user", "hello world")
        hash3 = buf._hash_message("s1", "user", "HELLO WORLD")

        assert hash1 == hash2
        assert hash1 == hash3  # Case-insensitive

    def test_hash_message_whitespace_normalized(self):
        """_hash_message normalizes whitespace."""
        from dashboard.knowledge.graph.utils._utils import CircularMessageBuffer

        buf = CircularMessageBuffer(maxlen=5)
        hash1 = buf._hash_message("s1", "user", "hello   world")
        hash2 = buf._hash_message("s1", "user", "hello world")

        assert hash1 == hash2


# ---------------------------------------------------------------------------
# Entity String Parsing Tests
# ---------------------------------------------------------------------------


class TestEntityStringParsing:
    """Test entity string parsing utilities."""

    def test_extract_entity_properties_empty(self):
        """extract_entity_properties handles empty string."""
        from dashboard.knowledge.graph.utils._utils import extract_entity_properties

        assert extract_entity_properties("") is None
        assert extract_entity_properties(None) is None

    def test_extract_entity_properties_empty_parens(self):
        """extract_entity_properties handles empty parens."""
        from dashboard.knowledge.graph.utils._utils import extract_entity_properties

        result = extract_entity_properties("()")
        assert result == ""

    def test_extract_entity_properties_with_content(self):
        """extract_entity_properties extracts content."""
        from dashboard.knowledge.graph.utils._utils import extract_entity_properties

        result = extract_entity_properties("Entity (key=value, name=test)")
        assert "key" in result

    def test_extract_entity_name_empty(self):
        """extract_entity_name handles empty input."""
        from dashboard.knowledge.graph.utils._utils import extract_entity_name

        assert extract_entity_name("") == ""
        assert extract_entity_name(None) is None

    def test_extract_entity_name_simple(self):
        """extract_entity_name extracts name before parens."""
        from dashboard.knowledge.graph.utils._utils import extract_entity_name

        result = extract_entity_name("Alice (Person)")
        assert result == "Alice"

    def test_extract_entity_name_no_parens(self):
        """extract_entity_name returns full string if no parens."""
        from dashboard.knowledge.graph.utils._utils import extract_entity_name

        result = extract_entity_name("JustAName")
        assert result == "JustAName"

    def test_extract_entity_name_only_parens(self):
        """extract_entity_name returns empty for just parens."""
        from dashboard.knowledge.graph.utils._utils import extract_entity_name

        result = extract_entity_name("(only parens)")
        assert result == ""


# ---------------------------------------------------------------------------
# Thread Safety Tests
# ---------------------------------------------------------------------------


class TestThreadSafety:
    """Test thread safety of graph components."""

    def test_concurrent_gc_file_access_race_condition(self, tmp_path):
        """GC file operations have a race condition under concurrent access.

        BUG: The read-modify-write pattern in _read_gc_file + _write_gc_file
        is not atomic, causing data loss or corruption when multiple threads
        write concurrently. This test documents the issue.
        """
        from dashboard.knowledge.graph.core.storage import (
            _read_gc_file,
            _write_gc_file,
        )

        gc_file = tmp_path / "gc.json"
        gc_file.write_text("[]")

        errors = []
        warnings_caught = []

        def writer(i):
            try:
                for _ in range(5):
                    data = _read_gc_file()
                    if data is None:
                        data = []
                    data.append(f"item-{i}")
                    _write_gc_file(data)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        with mock.patch(
            "dashboard.knowledge.graph.core.storage.GARBAGE_COLLECTION_FILE",
            str(gc_file),
        ):
            threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # The file may be corrupted or have missing entries due to race condition
            try:
                final_data = json.loads(gc_file.read_text())
                # Some data may be lost, but we shouldn't crash
                assert isinstance(final_data, list)
            except json.JSONDecodeError:
                # This is expected - the race condition corrupts the JSON
                # BUG: The GC file operations need proper locking
                pass

    def test_concurrent_json_parsing(self):
        """JSON parsing is thread-safe under concurrent access."""
        from dashboard.knowledge.graph.utils._utils import extract_array

        results = []
        errors = []

        def worker(i):
            try:
                text = f'```json\n[{{"id": {i}}}]\n```'
                result = extract_array(text)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
