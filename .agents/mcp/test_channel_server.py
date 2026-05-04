#!/usr/bin/env python3
"""Tests for channel-server.py (cross-platform, works without fcntl)."""

import json
import os
import sys
import tempfile
from pathlib import Path
import importlib.util


def _load_channel_server():
    """Load channel-server.py as a module (handles hyphen in filename)."""
    spec = importlib.util.spec_from_file_location(
        "channel_server",
        Path(__file__).parent / "channel-server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_import_without_fcntl():
    """Verify module imports when fcntl is unavailable (Windows)."""
    # Module should load successfully on Windows where fcntl doesn't exist
    module = _load_channel_server()

    # Should have flagged fcntl availability
    assert hasattr(module, "_HAS_FCNTL")
    assert module._HAS_FCNTL is False  # On Windows

    # Should have msvcrt fallback on Windows
    assert hasattr(module, "_HAS_MSVCRT")
    # On Windows, msvcrt should be available
    import platform
    if platform.system() == "Windows":
        assert module._HAS_MSVCRT is True


def test_post_message_writes_jsonl():
    """Verify post_message writes valid JSONL to channel file."""
    module = _load_channel_server()

    with tempfile.TemporaryDirectory() as tmpdir:
        result = module.post_message(
            room_dir=tmpdir,
            from_role="engineer",
            to_role="qa",
            msg_type="done",
            ref="TASK-001",
            body="Implementation complete"
        )

        assert result.startswith("posted:")

        # Verify file exists
        channel_file = Path(tmpdir) / "channel.jsonl"
        assert channel_file.exists()

        # Verify content
        lines = channel_file.read_text().strip().split("\n")
        assert len(lines) == 1

        msg = json.loads(lines[0])
        assert msg["from"] == "engineer"
        assert msg["to"] == "qa"
        assert msg["type"] == "done"
        assert msg["ref"] == "TASK-001"
        assert msg["body"] == "Implementation complete"
        assert "id" in msg
        assert "ts" in msg


def test_read_messages_reads_written():
    """Verify read_messages returns messages written by post_message."""
    module = _load_channel_server()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Post two messages
        module.post_message(
            room_dir=tmpdir,
            from_role="manager",
            to_role="engineer",
            msg_type="task",
            ref="TASK-001",
            body="Implement feature X"
        )
        module.post_message(
            room_dir=tmpdir,
            from_role="engineer",
            to_role="manager",
            msg_type="done",
            ref="TASK-001",
            body="Feature X done"
        )

        # Read all
        all_msgs = json.loads(module.read_messages(room_dir=tmpdir))
        assert len(all_msgs) == 2

        # Filter by type
        done_msgs = json.loads(module.read_messages(room_dir=tmpdir, msg_type="done"))
        assert len(done_msgs) == 1
        assert done_msgs[0]["type"] == "done"

        # Filter by from_role
        mgr_msgs = json.loads(module.read_messages(room_dir=tmpdir, from_role="manager"))
        assert len(mgr_msgs) == 1
        assert mgr_msgs[0]["from"] == "manager"

        # Filter by ref
        task_msgs = json.loads(module.read_messages(room_dir=tmpdir, ref="TASK-001"))
        assert len(task_msgs) == 2

        # Last N
        last_one = json.loads(module.read_messages(room_dir=tmpdir, last_n=1))
        assert len(last_one) == 1
        assert last_one[0]["type"] == "done"


def test_read_messages_empty_channel():
    """Verify read_messages returns empty array for non-existent channel."""
    module = _load_channel_server()

    with tempfile.TemporaryDirectory() as tmpdir:
        result = module.read_messages(room_dir=tmpdir)
        assert result == "[]"


def test_get_latest():
    """Verify get_latest returns most recent message of given type."""
    module = _load_channel_server()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Post messages
        module.post_message(
            room_dir=tmpdir,
            from_role="engineer",
            to_role="qa",
            msg_type="done",
            ref="TASK-001",
            body="First done"
        )
        module.post_message(
            room_dir=tmpdir,
            from_role="engineer",
            to_role="qa",
            msg_type="done",
            ref="TASK-002",
            body="Second done"
        )

        # Get latest done
        latest = json.loads(module.get_latest(room_dir=tmpdir, msg_type="done"))
        assert latest is not None
        assert latest["ref"] == "TASK-002"
        assert latest["body"] == "Second done"

        # Get latest task (none exist)
        latest_task = json.loads(module.get_latest(room_dir=tmpdir, msg_type="task"))
        assert latest_task is None


if __name__ == "__main__":
    test_import_without_fcntl()
    test_post_message_writes_jsonl()
    test_read_messages_reads_written()
    test_read_messages_empty_channel()
    test_get_latest()
    print("All tests passed!")
