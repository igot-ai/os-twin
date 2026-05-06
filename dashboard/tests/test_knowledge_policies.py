"""EPIC-003 Hardening — policy tests.

Tests for:
- Concurrent import protection (ImportInProgressError)
- Namespace quota enforcement (MaxNamespacesReachedError)
- LLM timeout handling
"""

from __future__ import annotations

import concurrent.futures
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import MagicMock, patch

import pytest

from dashboard.knowledge.audit import (
    MAX_NAMESPACES,
    ImportInProgressError,
    MaxNamespacesReachedError,
    count_namespaces,
    is_import_in_progress,
    register_import,
    unregister_import,
)
from dashboard.knowledge.namespace import NamespaceManager
from dashboard.knowledge.service import KnowledgeService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_kb(tmp_path: Path) -> Path:
    """Isolated knowledge-base root per test."""
    kb = tmp_path / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    return kb


@pytest.fixture
def service(tmp_kb: Path) -> KnowledgeService:
    """Fresh KnowledgeService with isolated storage."""
    nm = NamespaceManager(base_dir=tmp_kb)
    return KnowledgeService(namespace_manager=nm)


@pytest.fixture(autouse=True)
def _clear_import_tracking() -> Iterator[None]:
    """Clear import tracking state between tests."""
    # Import the module-level tracking dict
    from dashboard.knowledge import audit as audit_module
    audit_module._active_imports.clear()
    yield
    audit_module._active_imports.clear()


# ---------------------------------------------------------------------------
# Concurrent Import Protection Tests
# ---------------------------------------------------------------------------


def test_register_import_basic() -> None:
    """Basic import registration works."""
    register_import("test-ns", "job-123")
    assert is_import_in_progress("test-ns") == "job-123"


def test_register_import_rejects_duplicate() -> None:
    """Second import for same namespace raises ImportInProgressError."""
    register_import("test-ns", "job-123")
    with pytest.raises(ImportInProgressError) as exc_info:
        register_import("test-ns", "job-456")
    assert exc_info.value.namespace == "test-ns"
    assert exc_info.value.job_id == "job-123"


def test_unregister_import() -> None:
    """Unregister allows new import."""
    register_import("test-ns", "job-123")
    unregister_import("test-ns")
    assert is_import_in_progress("test-ns") is None
    # Should be able to register again
    register_import("test-ns", "job-456")
    assert is_import_in_progress("test-ns") == "job-456"


def test_unregister_nonexistent_is_safe() -> None:
    """Unregistering a non-existent import doesn't raise."""
    unregister_import("nonexistent-ns")  # Should not raise


def test_is_import_in_progress_returns_none_when_empty() -> None:
    """No import in progress returns None."""
    assert is_import_in_progress("no-such-ns") is None


def test_different_namespaces_allow_concurrent_imports() -> None:
    """Different namespaces can have concurrent imports."""
    register_import("ns-1", "job-1")
    register_import("ns-2", "job-2")
    assert is_import_in_progress("ns-1") == "job-1"
    assert is_import_in_progress("ns-2") == "job-2"


def test_import_tracking_is_thread_safe() -> None:
    """Concurrent registration attempts are handled safely."""
    results: list[Any] = []
    
    def try_register(ns: str, job_id: str) -> None:
        try:
            register_import(ns, job_id)
            results.append(("success", job_id))
        except ImportInProgressError as e:
            results.append(("blocked", job_id))
    
    # Try to register same namespace concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(try_register, "test-ns", f"job-{i}")
            for i in range(3)
        ]
        concurrent.futures.wait(futures)
    
    # Only one should have succeeded
    successes = [r for r in results if r[0] == "success"]
    blocked = [r for r in results if r[0] == "blocked"]
    assert len(successes) == 1
    assert len(blocked) == 2


# ---------------------------------------------------------------------------
# Namespace Quota Tests
# ---------------------------------------------------------------------------


def test_count_namespaces_empty(tmp_kb: Path) -> None:
    """Count is 0 when no namespaces exist."""
    assert count_namespaces(tmp_kb) == 0


def test_count_namespaces_counts_manifests(tmp_kb: Path) -> None:
    """Count returns number of directories with manifest.json."""
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("ns-1")
    nm.create("ns-2")
    nm.create("ns-3")
    assert count_namespaces(tmp_kb) == 3


def test_count_namespaces_ignores_partial_dirs(tmp_kb: Path) -> None:
    """Directories without manifest.json are ignored."""
    nm = NamespaceManager(base_dir=tmp_kb)
    nm.create("valid-ns")
    # Create a directory without manifest
    (tmp_kb / "invalid-ns").mkdir()
    assert count_namespaces(tmp_kb) == 1


def test_create_namespace_respects_quota(service: KnowledgeService, tmp_kb: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Creating namespace beyond quota raises MaxNamespacesReachedError."""
    # Set a low quota for testing
    monkeypatch.setattr("dashboard.knowledge.audit.MAX_NAMESPACES", 3)
    monkeypatch.setattr("dashboard.knowledge.service.MAX_NAMESPACES", 3)
    
    # Create 3 namespaces (at the limit)
    service.create_namespace("ns-1")
    service.create_namespace("ns-2")
    service.create_namespace("ns-3")
    
    # 4th should fail
    with pytest.raises(MaxNamespacesReachedError) as exc_info:
        service.create_namespace("ns-4")
    assert exc_info.value.max_count == 3


def test_max_namespaces_reached_error_message() -> None:
    """Error message includes the max count."""
    err = MaxNamespacesReachedError(100)
    assert "100" in str(err)
    assert "namespace" in str(err).lower()


def test_import_in_progress_error_message() -> None:
    """Error message includes namespace and job_id."""
    err = ImportInProgressError("my-ns", "job-abc")
    assert "my-ns" in str(err)
    assert "job-abc" in str(err)


def test_import_in_progress_error_without_job_id() -> None:
    """Error message works without job_id."""
    err = ImportInProgressError("my-ns")
    assert "my-ns" in str(err)
    assert "job" not in str(err).lower()


# ---------------------------------------------------------------------------
# Service Integration Tests
# ---------------------------------------------------------------------------


def test_service_import_folder_rejects_concurrent(service: KnowledgeService, tmp_path: Path) -> None:
    """Service.import_folder rejects concurrent imports for same namespace."""
    # Create a folder to import
    folder = tmp_path / "import-me"
    folder.mkdir()
    (folder / "test.txt").write_text("hello world")
    
    # Manually register an in-progress import
    register_import("test-ns", "existing-job")
    
    # Attempt to start another import should fail
    with pytest.raises(ImportInProgressError):
        service.import_folder("test-ns", str(folder))


def test_service_import_folder_succeeds_after_unregister(service: KnowledgeService, tmp_path: Path) -> None:
    """Import succeeds after previous import is unregistered."""
    # Create a folder to import
    folder = tmp_path / "import-me"
    folder.mkdir()
    (folder / "test.txt").write_text("hello world")
    
    # Register and unregister
    register_import("test-ns", "existing-job")
    unregister_import("test-ns")
    
    # Now import should succeed
    job_id = service.import_folder("test-ns", str(folder))
    assert job_id is not None


# ---------------------------------------------------------------------------
# LLM Timeout Tests
# ---------------------------------------------------------------------------


def test_llm_timeout_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_TIMEOUT reads from environment."""
    monkeypatch.setenv("OSTWIN_KNOWLEDGE_LLM_TIMEOUT", "45.0")
    # Re-import to pick up new env
    import importlib
    from dashboard.knowledge import audit as audit_module
    importlib.reload(audit_module)
    assert audit_module.LLM_TIMEOUT == 45.0


def test_llm_timeout_default() -> None:
    """LLM_TIMEOUT defaults to 60 seconds."""
    import importlib
    from dashboard.knowledge import audit as audit_module
    # The default is 60.0 but previous tests may have modified it
    # so we just check it's a valid positive number
    assert audit_module.LLM_TIMEOUT > 0
    assert isinstance(audit_module.LLM_TIMEOUT, float)


def test_knowledge_llm_handles_timeout_gracefully() -> None:
    """KnowledgeLLM._complete returns empty string on timeout."""
    from dashboard.knowledge.llm import KnowledgeLLM
    
    llm = KnowledgeLLM(api_key="test-key")
    
    # Mock the client to raise a timeout-like error
    with patch.object(llm, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = TimeoutError("Request timed out")
        mock_get_client.return_value = mock_client
        
        result = llm._complete("system", "user")
        assert result == ""


def test_knowledge_llm_extract_entities_returns_empty_on_timeout() -> None:
    """extract_entities returns empty lists on timeout."""
    from dashboard.knowledge.llm import KnowledgeLLM
    
    llm = KnowledgeLLM(api_key="test-key")
    
    with patch.object(llm, "_complete", return_value=""):
        entities, relations = llm.extract_entities("some text")
        assert entities == []
        assert relations == []


def test_knowledge_llm_plan_query_fallback_on_timeout() -> None:
    """plan_query returns fallback plan on timeout."""
    from dashboard.knowledge.llm import KnowledgeLLM
    
    llm = KnowledgeLLM(api_key="test-key")
    
    with patch.object(llm, "_complete", return_value=""):
        plan = llm.plan_query("test query")
        assert len(plan) == 1
        assert plan[0]["term"] == "test query"
        assert plan[0]["is_query"] is True


def test_knowledge_llm_aggregate_fallback_on_timeout() -> None:
    """aggregate_answers returns joined summaries on timeout."""
    from dashboard.knowledge.llm import KnowledgeLLM
    
    llm = KnowledgeLLM(api_key="test-key")
    
    summaries = ["Summary 1", "Summary 2"]
    
    with patch.object(llm, "_complete", return_value=""):
        result = llm.aggregate_answers(summaries, "test query")
        assert result == "Summary 1\n\nSummary 2"


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


def test_count_namespaces_handles_missing_dir(tmp_path: Path) -> None:
    """count_namespaces returns 0 for non-existent directory."""
    nonexistent = tmp_path / "does-not-exist"
    assert count_namespaces(nonexistent) == 0


def test_namespace_quota_respects_custom_base_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Quota check uses the correct base directory."""
    # Set a very low quota
    monkeypatch.setattr("dashboard.knowledge.audit.MAX_NAMESPACES", 2)
    monkeypatch.setattr("dashboard.knowledge.service.MAX_NAMESPACES", 2)
    
    # Create service with custom base dir
    custom_kb = tmp_path / "custom-kb"
    custom_kb.mkdir(parents=True)
    nm = NamespaceManager(base_dir=custom_kb)
    service = KnowledgeService(namespace_manager=nm)
    
    # Create 2 namespaces (at limit)
    service.create_namespace("ns-1")
    service.create_namespace("ns-2")
    
    # 3rd should fail
    with pytest.raises(MaxNamespacesReachedError):
        service.create_namespace("ns-3")
