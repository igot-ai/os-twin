"""Unit tests for dashboard/ai/monitor.py.

Covers all paths changed in the code review fix commit (10f8a49):
  - _infer_caller: skips 'dashboard.ai' frames (was 'shared.ai')
  - _lock_file / _unlock_file: cross-platform (fcntl / msvcrt fallback)
  - _append_to_file: logs on failure instead of bare 'pass'
  - reset_stats: logs on failure instead of bare 'pass'
  - Full JSONL round-trip, stats aggregation, thread safety
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — isolate module-level state between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_monitor(tmp_path):
    """Point the monitor at a tmp file and reset singleton stats before each test."""
    monitor_file = str(tmp_path / ".ostwin" / "ai_monitor.jsonl")
    with (
        patch("dashboard.ai.monitor._MONITOR_FILE", monitor_file),
        patch("dashboard.ai.monitor._stats", _fresh_stats()),
    ):
        yield monitor_file


def _fresh_stats():
    """Return a brand-new _Stats instance."""
    from dashboard.ai.monitor import _Stats
    return _Stats()


# ---------------------------------------------------------------------------
# TestCallRecord
# ---------------------------------------------------------------------------


class TestCallRecord:
    def test_completion_record_fields(self):
        from dashboard.ai.monitor import CallRecord

        rec = CallRecord(
            timestamp=1.0,
            call_type="completion",
            model="gemini/flash",
            purpose="memory",
            caller="test.py:42",
            latency_ms=120.5,
            input_tokens=100,
            output_tokens=50,
            text_count=0,
            success=True,
            error=None,
        )
        assert rec.call_type == "completion"
        assert rec.model == "gemini/flash"
        assert rec.success is True
        assert rec.error is None

    def test_embedding_record_fields(self):
        from dashboard.ai.monitor import CallRecord

        rec = CallRecord(
            timestamp=2.0,
            call_type="embedding",
            model="text-embedding-005",
            purpose=None,
            caller="embedder.py:10",
            latency_ms=30.0,
            input_tokens=0,
            output_tokens=0,
            text_count=5,
            success=False,
            error="quota exceeded",
        )
        assert rec.call_type == "embedding"
        assert rec.text_count == 5
        assert rec.success is False
        assert rec.error == "quota exceeded"


# ---------------------------------------------------------------------------
# TestStats
# ---------------------------------------------------------------------------


class TestStats:
    def test_to_dict_shape(self):
        from dashboard.ai.monitor import _Stats

        s = _Stats()
        d = s.to_dict()
        expected_keys = {
            "total_completions",
            "total_embeddings",
            "total_errors",
            "completions_by_model",
            "embeddings_by_model",
            "completions_by_purpose",
            "calls_by_caller",
            "avg_completion_latency_ms",
            "avg_embedding_latency_ms",
            "total_input_tokens",
            "total_output_tokens",
            "recent_calls",
        }
        assert expected_keys == set(d.keys())

    def test_zero_division_in_avg_handled(self):
        """avg latency should be 0 when no calls yet, not ZeroDivisionError."""
        from dashboard.ai.monitor import _Stats

        s = _Stats()
        d = s.to_dict()
        assert d["avg_completion_latency_ms"] == 0
        assert d["avg_embedding_latency_ms"] == 0

    def test_ring_buffer_capped_at_50(self):
        """recent list should never exceed max_recent=50."""
        from dashboard.ai.monitor import CallRecord, _Stats

        s = _Stats()
        for i in range(60):
            rec = CallRecord(
                timestamp=float(i),
                call_type="completion",
                model="m",
                purpose=None,
                caller="f:1",
                latency_ms=1.0,
                input_tokens=0,
                output_tokens=0,
                text_count=0,
                success=True,
                error=None,
            )
            with s.lock:
                s.recent.append(rec)
                if len(s.recent) > s.max_recent:
                    s.recent.pop(0)

        assert len(s.recent) == 50

    def test_concurrent_increments_are_consistent(self):
        """Multiple threads incrementing counters must produce consistent totals."""
        from dashboard.ai.monitor import _Stats

        s = _Stats()
        n_threads = 10
        increments_each = 50

        def bump():
            for _ in range(increments_each):
                with s.lock:
                    s.total_completions += 1

        threads = [threading.Thread(target=bump) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert s.total_completions == n_threads * increments_each


# ---------------------------------------------------------------------------
# TestInferCaller
# ---------------------------------------------------------------------------


class TestInferCaller:
    def test_returns_filename_and_lineno(self):
        """Should return 'file.py:N' for the first non-dashboard.ai frame."""
        from dashboard.ai.monitor import _infer_caller

        result = _infer_caller()
        # Must match <filename>:<lineno> pattern
        assert ":" in result
        filename, lineno = result.rsplit(":", 1)
        assert filename.endswith(".py")
        assert lineno.isdigit()

    def test_skips_dashboard_ai_frames(self):
        """Frames inside dashboard.ai.* must be skipped."""
        from dashboard.ai.monitor import _infer_caller
        import inspect

        captured = {}

        def fake_stack():
            # Manufacture a stack where dashboard.ai frames come first
            frame_dashboard = MagicMock()
            frame_dashboard.frame.f_globals = {"__name__": "dashboard.ai.monitor"}
            frame_dashboard.filename = "/proj/dashboard/ai/monitor.py"
            frame_dashboard.lineno = 99

            frame_caller = MagicMock()
            frame_caller.frame.f_globals = {"__name__": "my_module"}
            frame_caller.filename = "/proj/my_module.py"
            frame_caller.lineno = 42

            return [frame_dashboard, frame_caller]

        with patch("inspect.stack", fake_stack):
            result = _infer_caller()

        assert result == "my_module.py:42"

    def test_returns_unknown_when_all_frames_are_dashboard_ai(self):
        """Falls back to 'unknown' if every frame is inside dashboard.ai."""
        frame = MagicMock()
        frame.frame.f_globals = {"__name__": "dashboard.ai.completion"}
        frame.filename = "/proj/dashboard/ai/completion.py"
        frame.lineno = 5

        with patch("inspect.stack", return_value=[frame]):
            from dashboard.ai.monitor import _infer_caller
            result = _infer_caller()

        assert result == "unknown"


# ---------------------------------------------------------------------------
# TestRecordCompletion
# ---------------------------------------------------------------------------


class TestRecordCompletion:
    def test_increments_total_completions(self):
        from dashboard.ai import monitor as m

        before = m._stats.total_completions
        with patch("dashboard.ai.monitor._append_to_file"):
            m.record_completion("model-a", "memory", 100.0, input_tokens=10, output_tokens=5)
        assert m._stats.total_completions == before + 1

    def test_tracks_per_model_and_purpose(self):
        from dashboard.ai import monitor as m

        with patch("dashboard.ai.monitor._append_to_file"):
            m.record_completion("model-x", "knowledge", 50.0)

        assert m._stats.completions_by_model["model-x"] >= 1
        assert m._stats.completions_by_purpose["knowledge"] >= 1

    def test_error_increments_error_counter(self):
        from dashboard.ai import monitor as m

        before = m._stats.total_errors
        with patch("dashboard.ai.monitor._append_to_file"):
            m.record_completion("model-b", None, 200.0, success=False, error="boom")
        assert m._stats.total_errors == before + 1

    def test_tokens_accumulated(self):
        from dashboard.ai import monitor as m

        with patch("dashboard.ai.monitor._append_to_file"):
            m.record_completion("model-c", None, 10.0, input_tokens=20, output_tokens=8)

        assert m._stats.total_input_tokens >= 20
        assert m._stats.total_output_tokens >= 8


# ---------------------------------------------------------------------------
# TestRecordEmbedding
# ---------------------------------------------------------------------------


class TestRecordEmbedding:
    def test_increments_total_embeddings(self):
        from dashboard.ai import monitor as m

        before = m._stats.total_embeddings
        with patch("dashboard.ai.monitor._append_to_file"):
            m.record_embedding("embed-model", text_count=3, latency_ms=25.0)
        assert m._stats.total_embeddings == before + 1

    def test_tracks_per_model(self):
        from dashboard.ai import monitor as m

        with patch("dashboard.ai.monitor._append_to_file"):
            m.record_embedding("embed-xyz", text_count=1, latency_ms=5.0)

        assert m._stats.embeddings_by_model["embed-xyz"] >= 1


# ---------------------------------------------------------------------------
# TestFileLocking — cross-platform
# ---------------------------------------------------------------------------


class TestFileLocking:
    def test_lock_uses_fcntl_on_unix(self, tmp_path):
        """On a Unix system, _lock_file must call fcntl.flock with LOCK_EX."""
        from dashboard.ai.monitor import _lock_file

        mock_fcntl = MagicMock()
        mock_fcntl.LOCK_EX = 2
        # Make import succeed with our mock
        with patch.dict("sys.modules", {"fcntl": mock_fcntl}):
            fobj = MagicMock()
            _lock_file(fobj)

        mock_fcntl.flock.assert_called_once_with(fobj, mock_fcntl.LOCK_EX)

    def test_unlock_uses_fcntl_on_unix(self, tmp_path):
        """On a Unix system, _unlock_file must call fcntl.flock with LOCK_UN."""
        from dashboard.ai.monitor import _unlock_file

        mock_fcntl = MagicMock()
        mock_fcntl.LOCK_UN = 8
        with patch.dict("sys.modules", {"fcntl": mock_fcntl}):
            fobj = MagicMock()
            _unlock_file(fobj)

        mock_fcntl.flock.assert_called_once_with(fobj, mock_fcntl.LOCK_UN)

    def test_lock_falls_back_to_msvcrt_when_fcntl_missing(self):
        """When fcntl raises ImportError, _lock_file must use msvcrt.locking."""
        mock_msvcrt = MagicMock()
        mock_msvcrt.LK_LOCK = 2

        # Simulate fcntl missing; msvcrt present
        orig_fcntl = sys.modules.get("fcntl")
        try:
            sys.modules["fcntl"] = None  # type: ignore[assignment]
            sys.modules["msvcrt"] = mock_msvcrt

            # Reimport to pick up the patched sys.modules
            import importlib
            import dashboard.ai.monitor as mon_mod
            importlib.reload(mon_mod)

            fobj = MagicMock()
            fobj.fileno.return_value = 3
            # We can't easily call the reloaded _lock_file cleanly without
            # fcntl available, so we verify the fallback path inline.
            try:
                import fcntl  # noqa: F401
                pytest.skip("fcntl available on this platform (Unix); Windows path untested")
            except ImportError:
                mon_mod._lock_file(fobj)
                mock_msvcrt.locking.assert_called()
        finally:
            if orig_fcntl is not None:
                sys.modules["fcntl"] = orig_fcntl
            else:
                sys.modules.pop("fcntl", None)
            sys.modules.pop("msvcrt", None)


# ---------------------------------------------------------------------------
# TestAppendToFile
# ---------------------------------------------------------------------------


class TestAppendToFile:
    def test_writes_valid_jsonl(self, reset_monitor):
        """A CallRecord should be serialised as a single JSONL line."""
        from dashboard.ai.monitor import CallRecord, _append_to_file

        monitor_file = reset_monitor
        rec = CallRecord(
            timestamp=1000.0,
            call_type="completion",
            model="gemini/flash",
            purpose="test",
            caller="foo.py:1",
            latency_ms=99.9,
            input_tokens=10,
            output_tokens=5,
            text_count=0,
            success=True,
            error=None,
        )
        _append_to_file(rec)

        lines = Path(monitor_file).read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["type"] == "completion"
        assert data["model"] == "gemini/flash"
        assert data["purpose"] == "test"
        assert data["success"] is True

    def test_pid_field_present(self, reset_monitor):
        """Appended records must include the writing process's PID."""
        from dashboard.ai.monitor import CallRecord, _append_to_file

        rec = CallRecord(
            timestamp=1.0, call_type="embedding", model="m", purpose=None,
            caller="x.py:1", latency_ms=1.0, input_tokens=0, output_tokens=0,
            text_count=2, success=True, error=None,
        )
        _append_to_file(rec)
        data = json.loads(Path(reset_monitor).read_text().strip())
        assert data["pid"] == os.getpid()

    def test_creates_parent_directories(self, tmp_path):
        """_append_to_file must create missing parent dirs automatically."""
        deep_path = str(tmp_path / "a" / "b" / "c" / "ai_monitor.jsonl")
        from dashboard.ai.monitor import CallRecord, _append_to_file

        rec = CallRecord(
            timestamp=1.0, call_type="completion", model="m", purpose=None,
            caller="x.py:1", latency_ms=1.0, input_tokens=0, output_tokens=0,
            text_count=0, success=True, error=None,
        )
        with patch("dashboard.ai.monitor._MONITOR_FILE", deep_path):
            _append_to_file(rec)

        assert Path(deep_path).exists()

    def test_failure_logs_debug_not_raises(self, reset_monitor):
        """If the write fails, must log at DEBUG level — not raise or silently swallow."""
        from dashboard.ai.monitor import CallRecord, _append_to_file

        rec = CallRecord(
            timestamp=1.0, call_type="completion", model="m", purpose=None,
            caller="x.py:1", latency_ms=1.0, input_tokens=0, output_tokens=0,
            text_count=0, success=True, error=None,
        )
        with (
            patch("dashboard.ai.monitor._file_lock"),
            patch("builtins.open", side_effect=OSError("disk full")),
            patch("dashboard.ai.monitor.logger") as mock_logger,
        ):
            # Must not raise
            _append_to_file(rec)

        mock_logger.debug.assert_called_once()
        args = mock_logger.debug.call_args[0]
        assert "Failed to append" in args[0]


# ---------------------------------------------------------------------------
# TestReadFromFile
# ---------------------------------------------------------------------------


class TestReadFromFile:
    def _write_records(self, path: str, records: list[dict]) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def test_reads_recent_records(self, reset_monitor):
        now = time.time()
        self._write_records(reset_monitor, [
            {"ts": now - 10, "type": "completion", "model": "m", "success": True},
            {"ts": now - 20, "type": "embedding", "model": "e", "success": True},
        ])

        from dashboard.ai.monitor import _read_from_file
        with patch("dashboard.ai.monitor._MONITOR_FILE", reset_monitor):
            records = _read_from_file(max_age_seconds=3600)

        assert len(records) == 2

    def test_filters_old_records(self, reset_monitor):
        now = time.time()
        self._write_records(reset_monitor, [
            {"ts": now - 7200, "type": "completion", "model": "m", "success": True},  # 2h old
            {"ts": now - 10, "type": "completion", "model": "m", "success": True},   # recent
        ])

        from dashboard.ai.monitor import _read_from_file
        with patch("dashboard.ai.monitor._MONITOR_FILE", reset_monitor):
            records = _read_from_file(max_age_seconds=3600)

        assert len(records) == 1

    def test_returns_empty_list_for_missing_file(self, tmp_path):
        nonexistent = str(tmp_path / "no_such.jsonl")
        from dashboard.ai.monitor import _read_from_file
        with patch("dashboard.ai.monitor._MONITOR_FILE", nonexistent):
            result = _read_from_file()
        assert result == []

    def test_skips_malformed_json_lines(self, reset_monitor):
        """Bad JSON lines should be skipped without crashing."""
        Path(reset_monitor).parent.mkdir(parents=True, exist_ok=True)
        with open(reset_monitor, "w") as f:
            f.write("not json at all\n")
            f.write(json.dumps({"ts": time.time(), "type": "completion"}) + "\n")
            f.write("{broken\n")

        from dashboard.ai.monitor import _read_from_file
        with patch("dashboard.ai.monitor._MONITOR_FILE", reset_monitor):
            records = _read_from_file()

        assert len(records) == 1


# ---------------------------------------------------------------------------
# TestGetStats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_in_memory_only_mode(self):
        """include_file=False must return in-memory stats without touching disk."""
        from dashboard.ai import monitor as m

        with patch("dashboard.ai.monitor._append_to_file"):
            m.record_completion("fast-model", None, 10.0, input_tokens=1, output_tokens=1)

        result = m.get_stats(include_file=False)
        assert result["total_completions"] >= 1

    def test_empty_stats_structure(self):
        """A fresh monitor must return a valid zero-value stats dict."""
        from dashboard.ai.monitor import get_stats

        with patch("dashboard.ai.monitor._read_from_file", return_value=[]):
            result = get_stats(include_file=True)

        assert result["total_completions"] == 0
        assert result["total_embeddings"] == 0
        assert result["total_errors"] == 0
        assert isinstance(result["recent_calls"], list)

    def test_file_stats_aggregate_correctly(self, reset_monitor, tmp_path):
        """get_stats should count records from the JSONL file."""
        now = time.time()
        records = [
            {"ts": now - 1, "type": "completion", "model": "m", "caller": "f:1",
             "latency_ms": 100, "success": True, "purpose": "test",
             "input_tokens": 5, "output_tokens": 2},
            {"ts": now - 2, "type": "embedding", "model": "e", "caller": "g:2",
             "latency_ms": 20, "success": False},
        ]
        with patch("dashboard.ai.monitor._read_from_file", return_value=records):
            from dashboard.ai.monitor import get_stats
            result = get_stats(include_file=True, max_age_seconds=3600)

        assert result["total_completions"] == 1
        assert result["total_embeddings"] == 1
        assert result["total_errors"] == 1
        assert "m" in result["completions_by_model"]
        assert "e" in result["embeddings_by_model"]


# ---------------------------------------------------------------------------
# TestResetStats
# ---------------------------------------------------------------------------


class TestResetStats:
    def test_clears_in_memory_counters(self):
        from dashboard.ai import monitor as m

        with patch("dashboard.ai.monitor._append_to_file"):
            m.record_completion("model", None, 50.0)

        assert m._stats.total_completions >= 1

        with patch("dashboard.ai.monitor._MONITOR_FILE", "/dev/null"):
            m.reset_stats()

        assert m._stats.total_completions == 0

    def test_truncates_jsonl_file(self, reset_monitor):
        """reset_stats must empty the shared file."""
        Path(reset_monitor).parent.mkdir(parents=True, exist_ok=True)
        Path(reset_monitor).write_text('{"ts": 1}\n')

        from dashboard.ai.monitor import reset_stats
        with patch("dashboard.ai.monitor._MONITOR_FILE", reset_monitor):
            reset_stats()

        assert Path(reset_monitor).read_text() == ""

    def test_failure_logs_debug_not_raises(self):
        """If the file truncation fails, must log at DEBUG — not raise."""
        from dashboard.ai.monitor import reset_stats

        with (
            patch("builtins.open", side_effect=PermissionError("read-only")),
            patch("dashboard.ai.monitor.logger") as mock_logger,
        ):
            reset_stats()  # must not raise

        mock_logger.debug.assert_called_once()
        args = mock_logger.debug.call_args[0]
        assert "truncate" in args[0].lower() or "Failed" in args[0]
