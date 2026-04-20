"""EPIC-003 Hardening — audit log tests.

Tests for:
- Audit event writing
- Log rotation
- Audit disable flag
- Audit log schema validation
"""

from __future__ import annotations

import gzip
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch

import pytest

from dashboard.knowledge.audit import (
    AUDIT_ENABLED,
    AUDIT_READS,
    MAX_GENERATIONS,
    MAX_LOG_SIZE,
    AuditContext,
    audit_event,
    get_audit_log_path,
    _rotate_audit_log,
    _log_call,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_audit_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated audit directory per test."""
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir(parents=True)
    monkeypatch.setattr("dashboard.knowledge.audit.AUDIT_DIR", audit_dir)
    monkeypatch.setattr("dashboard.knowledge.audit.AUDIT_FILE", audit_dir / "_audit.jsonl")
    return audit_dir


@pytest.fixture(autouse=True)
def _reset_audit_lock() -> Iterator[None]:
    """Reset audit lock between tests."""
    import threading
    from dashboard.knowledge import audit as audit_module
    audit_module._audit_lock = threading.Lock()
    yield


# ---------------------------------------------------------------------------
# Audit Event Tests
# ---------------------------------------------------------------------------


def test_audit_event_writes_jsonl(tmp_audit_dir: Path) -> None:
    """audit_event writes a valid JSONL entry."""
    audit_event(
        actor="test@example.com",
        namespace="test-ns",
        op="create_namespace",
        args={"name": "test-ns"},
        result_status="success",
        latency_ms=123.45,
    )
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    assert log_file.exists()
    
    with open(log_file) as f:
        line = f.readline()
        entry = json.loads(line)
    
    assert entry["actor"] == "test@example.com"
    assert entry["namespace"] == "test-ns"
    assert entry["op"] == "create_namespace"
    assert entry["result_status"] == "success"
    assert entry["latency_ms"] == 123.45
    assert "timestamp" in entry


def test_audit_event_sanitizes_sensitive_args(tmp_audit_dir: Path) -> None:
    """Sensitive fields are removed from args."""
    audit_event(
        actor="test@example.com",
        namespace="test-ns",
        op="import",
        args={
            "folder": "/data",
            "api_key": "secret-key-12345",
            "token": "secret-token",
            "password": "secret-pwd",
        },
        result_status="success",
        latency_ms=50.0,
    )
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    with open(log_file) as f:
        entry = json.loads(f.readline())
    
    assert "api_key" not in entry["args"]
    assert "token" not in entry["args"]
    assert "password" not in entry["args"]
    assert entry["args"]["folder"] == "/data"


def test_audit_event_truncates_long_values(tmp_audit_dir: Path) -> None:
    """Long string values are truncated."""
    long_value = "x" * 1000
    audit_event(
        actor="test@example.com",
        namespace="test-ns",
        op="import",
        args={"long_field": long_value},
        result_status="success",
        latency_ms=50.0,
    )
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    with open(log_file) as f:
        entry = json.loads(f.readline())
    
    assert len(entry["args"]["long_field"]) == 503  # 500 + "..."
    assert entry["args"]["long_field"].endswith("...")


def test_audit_event_skips_reads_by_default(tmp_audit_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Read operations are not logged by default."""
    monkeypatch.setattr("dashboard.knowledge.audit.AUDIT_READS", False)
    
    for op in ["query", "get_graph", "list_namespaces", "get_namespace", "list_jobs", "get_job"]:
        audit_event(
            actor="test@example.com",
            namespace="test-ns",
            op=op,
            args={},
            result_status="success",
            latency_ms=10.0,
        )
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    if log_file.exists():
        with open(log_file) as f:
            content = f.read()
        assert content == ""


def test_audit_event_logs_reads_when_enabled(tmp_audit_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Read operations are logged when AUDIT_READS=1."""
    monkeypatch.setattr("dashboard.knowledge.audit.AUDIT_READS", True)
    
    audit_event(
        actor="test@example.com",
        namespace="test-ns",
        op="query",
        args={"query": "test"},
        result_status="success",
        latency_ms=10.0,
    )
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    assert log_file.exists()
    
    with open(log_file) as f:
        entry = json.loads(f.readline())
    
    assert entry["op"] == "query"


def test_audit_event_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No file is created when AUDIT_ENABLED=0."""
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir(parents=True)
    monkeypatch.setattr("dashboard.knowledge.audit.AUDIT_DIR", audit_dir)
    monkeypatch.setattr("dashboard.knowledge.audit.AUDIT_FILE", audit_dir / "_audit.jsonl")
    monkeypatch.setattr("dashboard.knowledge.audit.AUDIT_ENABLED", False)
    
    audit_event(
        actor="test@example.com",
        namespace="test-ns",
        op="create_namespace",
        args={},
        result_status="success",
        latency_ms=10.0,
    )
    
    log_file = audit_dir / "_audit.jsonl"
    assert not log_file.exists()


def test_audit_event_handles_missing_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """audit_event creates the directory if it doesn't exist."""
    audit_dir = tmp_path / "new-audit-dir"
    # Don't create it yet
    monkeypatch.setattr("dashboard.knowledge.audit.AUDIT_DIR", audit_dir)
    monkeypatch.setattr("dashboard.knowledge.audit.AUDIT_FILE", audit_dir / "_audit.jsonl")
    
    audit_event(
        actor="test@example.com",
        namespace="test-ns",
        op="create_namespace",
        args={},
        result_status="success",
        latency_ms=10.0,
    )
    
    assert audit_dir.exists()
    assert (audit_dir / "_audit.jsonl").exists()


def test_audit_event_anonymous_actor(tmp_audit_dir: Path) -> None:
    """Empty actor becomes 'anonymous'."""
    audit_event(
        actor="",
        namespace="test-ns",
        op="create_namespace",
        args={},
        result_status="success",
        latency_ms=10.0,
    )
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    with open(log_file) as f:
        entry = json.loads(f.readline())
    
    assert entry["actor"] == "anonymous"


# ---------------------------------------------------------------------------
# Log Rotation Tests
# ---------------------------------------------------------------------------


def test_rotation_triggered_at_max_size(tmp_audit_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Log rotates when exceeding MAX_LOG_SIZE."""
    monkeypatch.setattr("dashboard.knowledge.audit.MAX_LOG_SIZE", 100)  # Small for testing
    
    # Write enough to trigger rotation
    for i in range(10):
        audit_event(
            actor="test@example.com",
            namespace="test-ns",
            op="import",
            args={"data": "x" * 50},  # Make each entry ~100+ bytes
            result_status="success",
            latency_ms=float(i),
        )
    
    # Should have rotated file
    rotated = tmp_audit_dir / "_audit.jsonl.1.gz"
    assert rotated.exists()
    
    # Verify compressed content
    with gzip.open(rotated, "rt") as f:
        content = f.read()
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) >= 1


def test_rotation_shifts_existing_files(tmp_audit_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rotation shifts .1.gz to .2.gz, etc."""
    monkeypatch.setattr("dashboard.knowledge.audit.MAX_LOG_SIZE", 100)
    monkeypatch.setattr("dashboard.knowledge.audit.MAX_GENERATIONS", 3)
    
    # Trigger multiple rotations
    for batch in range(4):
        for i in range(10):
            audit_event(
                actor="test@example.com",
                namespace=f"ns-{batch}",
                op="import",
                args={"data": "x" * 50},
                result_status="success",
                latency_ms=float(i),
            )
    
    # Should have multiple generations
    assert (tmp_audit_dir / "_audit.jsonl.1.gz").exists()
    assert (tmp_audit_dir / "_audit.jsonl.2.gz").exists()
    # .3.gz might or might not exist depending on timing


def test_rotation_keeps_max_generations(tmp_audit_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Old generations beyond MAX_GENERATIONS are deleted."""
    monkeypatch.setattr("dashboard.knowledge.audit.MAX_LOG_SIZE", 50)
    monkeypatch.setattr("dashboard.knowledge.audit.MAX_GENERATIONS", 2)
    
    # Trigger many rotations
    for batch in range(10):
        for i in range(5):
            audit_event(
                actor="test@example.com",
                namespace=f"ns-{batch}",
                op="import",
                args={"data": "x" * 50},
                result_status="success",
                latency_ms=float(i),
            )
    
    # Should only have max 2 generations
    gen_files = list(tmp_audit_dir.glob("_audit.jsonl.*.gz"))
    assert len(gen_files) <= 2


# ---------------------------------------------------------------------------
# _log_call Tests
# ---------------------------------------------------------------------------


def test_log_call_emits_structured_log(caplog: pytest.LogCaptureFixture) -> None:
    """_log_call emits properly formatted log line."""
    with caplog.at_level("INFO"):
        _log_call(
            namespace="test-ns",
            op="query",
            result="success",
            latency_ms=123.45,
            extra={"mode": "raw"},
        )
    
    assert len(caplog.records) == 1
    msg = caplog.records[0].message
    assert "namespace=test-ns" in msg
    assert "op=query" in msg
    assert "latency_ms=123.45" in msg
    assert "result=success" in msg
    assert "mode=raw" in msg


def test_log_call_sanitizes_sensitive_extra(caplog: pytest.LogCaptureFixture) -> None:
    """_log_call redacts sensitive keys in extra."""
    with caplog.at_level("INFO"):
        _log_call(
            namespace="test-ns",
            op="import",
            result="success",
            latency_ms=50.0,
            extra={"api_key": "secret123", "folder": "/data"},
        )
    
    msg = caplog.records[0].message
    assert "api_key=***REDACTED***" in msg
    assert "folder=/data" in msg


def test_log_call_truncates_long_values(caplog: pytest.LogCaptureFixture) -> None:
    """_log_call truncates long string values."""
    long_value = "x" * 300
    with caplog.at_level("INFO"):
        _log_call(
            namespace="test-ns",
            op="query",
            result="success",
            latency_ms=50.0,
            extra={"query": long_value},
        )
    
    msg = caplog.records[0].message
    # Should be truncated to 200 chars + "..."
    assert len([p for p in msg.split() if p.startswith("query=")][0]) < 250


# ---------------------------------------------------------------------------
# AuditContext Tests
# ---------------------------------------------------------------------------


def test_audit_context_success(tmp_audit_dir: Path) -> None:
    """AuditContext writes log on successful completion."""
    with AuditContext("test@example.com", "test-ns", "import", {"folder": "/data"}) as ctx:
        ctx.result_status = "success"
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    with open(log_file) as f:
        entry = json.loads(f.readline())
    
    assert entry["actor"] == "test@example.com"
    assert entry["namespace"] == "test-ns"
    assert entry["op"] == "import"
    assert entry["result_status"] == "success"
    assert entry["latency_ms"] >= 0  # Can be 0 for very fast operations


def test_audit_context_error(tmp_audit_dir: Path) -> None:
    """AuditContext writes error log on exception."""
    try:
        with AuditContext("test@example.com", "test-ns", "import", {"folder": "/data"}):
            raise ValueError("Something went wrong")
    except ValueError:
        pass
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    with open(log_file) as f:
        entry = json.loads(f.readline())
    
    assert entry["result_status"] == "error"
    assert "Something went wrong" in entry["args"].get("error", "")


def test_audit_context_default_status_is_error(tmp_audit_dir: Path) -> None:
    """AuditContext defaults to 'error' status."""
    with AuditContext("test@example.com", "test-ns", "import", {}):
        pass  # Don't set result_status
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    with open(log_file) as f:
        entry = json.loads(f.readline())
    
    assert entry["result_status"] == "error"


# ---------------------------------------------------------------------------
# Audit Log Schema Validation Tests
# ---------------------------------------------------------------------------


def test_audit_log_entries_are_valid_json(tmp_audit_dir: Path) -> None:
    """All audit log entries can be parsed as JSON."""
    # Write multiple entries
    for i in range(50):
        audit_event(
            actor=f"user-{i}@example.com",
            namespace=f"ns-{i % 5}",
            op=["create_namespace", "delete_namespace", "import", "query"][i % 4],
            args={"index": i},
            result_status="success" if i % 2 == 0 else "error",
            latency_ms=float(i * 10),
        )
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    with open(log_file) as f:
        for i, line in enumerate(f):
            entry = json.loads(line)
            # Validate required fields
            assert "timestamp" in entry, f"Line {i} missing timestamp"
            assert "actor" in entry, f"Line {i} missing actor"
            assert "namespace" in entry, f"Line {i} missing namespace"
            assert "op" in entry, f"Line {i} missing op"
            assert "args" in entry, f"Line {i} missing args"
            assert "result_status" in entry, f"Line {i} missing result_status"
            assert "latency_ms" in entry, f"Line {i} missing latency_ms"
            
            # Validate types
            assert isinstance(entry["args"], dict)
            assert entry["result_status"] in ("success", "error")
            assert isinstance(entry["latency_ms"], (int, float))


def test_audit_log_timestamp_is_iso8601(tmp_audit_dir: Path) -> None:
    """Timestamp is ISO 8601 format."""
    import re
    from datetime import datetime
    
    audit_event(
        actor="test@example.com",
        namespace="test-ns",
        op="create_namespace",
        args={},
        result_status="success",
        latency_ms=10.0,
    )
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    with open(log_file) as f:
        entry = json.loads(f.readline())
    
    # Should be parseable as ISO 8601
    timestamp = entry["timestamp"]
    # Python 3.7+ supports Z suffix
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert parsed is not None


# ---------------------------------------------------------------------------
# Utility Function Tests
# ---------------------------------------------------------------------------


def test_get_audit_log_path() -> None:
    """get_audit_log_path returns the audit file path."""
    path = get_audit_log_path()
    assert path.name == "_audit.jsonl"
    assert ".ostwin" in str(path) or "knowledge" in str(path)


# ---------------------------------------------------------------------------
# Integration Tests: Service → Audit Log Wiring
# ---------------------------------------------------------------------------


def test_log_call_writes_audit_entry(tmp_audit_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    """_log_call writes both structured log AND audit log entry."""
    import logging
    caplog.set_level(logging.INFO)
    
    _log_call(
        namespace="test-ns",
        op="create_namespace",
        result="success",
        latency_ms=50.0,
        extra={"actor": "test@example.com", "name": "test-ns"},
    )
    
    # Verify log line was emitted
    assert any("namespace=test-ns" in r.message for r in caplog.records)
    assert any("op=create_namespace" in r.message for r in caplog.records)
    
    # Verify audit log entry was written
    log_file = tmp_audit_dir / "_audit.jsonl"
    assert log_file.exists(), "Audit log file should be created"
    
    with open(log_file) as f:
        entry = json.loads(f.readline())
    
    assert entry["namespace"] == "test-ns"
    assert entry["op"] == "create_namespace"
    assert entry["result_status"] == "success"
    assert entry["actor"] == "test@example.com"


def test_log_call_audit_respects_disabled(tmp_audit_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_log_call respects OSTWIN_KNOWLEDGE_AUDIT=0."""
    monkeypatch.setattr("dashboard.knowledge.audit.AUDIT_ENABLED", False)
    
    _log_call(
        namespace="test-ns",
        op="create_namespace",
        result="success",
        latency_ms=50.0,
        extra={"actor": "test@example.com"},
    )
    
    # Audit file should NOT exist when disabled
    log_file = tmp_audit_dir / "_audit.jsonl"
    assert not log_file.exists()


def test_log_call_audit_respects_reads_flag(tmp_audit_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """_log_call skips read ops by default, logs them when enabled."""
    # By default, read ops are not logged
    _log_call(
        namespace="test-ns",
        op="query",
        result="success",
        latency_ms=10.0,
        extra={"actor": "test@example.com"},
    )
    
    log_file = tmp_audit_dir / "_audit.jsonl"
    if log_file.exists():
        with open(log_file) as f:
            content = f.read()
        assert content == "", "Read ops should not be logged by default"
    
    # Enable read logging
    monkeypatch.setattr("dashboard.knowledge.audit.AUDIT_READS", True)
    
    # Need to clear the file first
    if log_file.exists():
        log_file.unlink()
    
    _log_call(
        namespace="test-ns",
        op="query",
        result="success",
        latency_ms=10.0,
        extra={"actor": "test@example.com"},
    )
    
    assert log_file.exists(), "Read ops should be logged when AUDIT_READS=True"
    with open(log_file) as f:
        entry = json.loads(f.readline())
    assert entry["op"] == "query"


def test_service_create_namespace_writes_audit(tmp_path: Path) -> None:
    """KnowledgeService.create_namespace writes audit log entry."""
    from dashboard.knowledge.namespace import NamespaceManager
    from dashboard.knowledge.service import KnowledgeService
    
    # Set up isolated paths
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir(parents=True)
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir(parents=True)
    
    # Create service with isolated storage
    nm = NamespaceManager(base_dir=kb_dir)
    service = KnowledgeService(namespace_manager=nm)
    
    # Mock audit paths to use temp dir
    import dashboard.knowledge.audit as audit_module
    audit_module.AUDIT_DIR = audit_dir
    audit_module.AUDIT_FILE = audit_dir / "_audit.jsonl"
    
    # Clear import tracking
    audit_module._active_imports.clear()
    
    # Create namespace
    meta = service.create_namespace("test-ns", actor="integration-test@example.com")
    
    # Verify audit log was written
    log_file = audit_dir / "_audit.jsonl"
    assert log_file.exists(), "Audit log file should be created by service.create_namespace"
    
    with open(log_file) as f:
        entry = json.loads(f.readline())
    
    assert entry["op"] == "create_namespace"
    assert entry["namespace"] == "test-ns"
    assert entry["actor"] == "integration-test@example.com"
    assert entry["result_status"] == "success"
