"""
test_working_path.py — Tests for the _working_path resolution logic.

Covers: room-specific paths, legacy fallback, no-room fallback, and safety.
"""

from pathlib import Path

import yaml
import pytest


class TestWorkingPath:
    """Test the _working_path helper function."""

    def test_room_specific_path_new_file(self, memory_tools, memory_env):
        """When no file exists, returns room-specific path."""
        path = memory_tools["_working_path"]("engineer")
        assert "engineer-room-test-001.yml" in path

    def test_room_specific_path_existing(self, memory_tools, memory_env):
        """When room-specific file exists, returns it."""
        wdir = Path(memory_env["memory_dir"]) / "working"
        target = wdir / "engineer-room-test-001.yml"
        target.write_text("notes: []\n")

        path = memory_tools["_working_path"]("engineer")
        assert path == str(target)

    def test_legacy_fallback(self, memory_tools, memory_env):
        """Falls back to {role}.yml if room-specific doesn't exist but legacy does."""
        wdir = Path(memory_env["memory_dir"]) / "working"
        legacy = wdir / "engineer.yml"
        legacy.write_text("notes: []\n")

        path = memory_tools["_working_path"]("engineer")
        assert path == str(legacy)

    def test_no_room_dir(self, memory_tools, memory_env, monkeypatch):
        """Without AGENT_OS_ROOM_DIR, uses {role}.yml directly."""
        monkeypatch.setenv("AGENT_OS_ROOM_DIR", "")

        path = memory_tools["_working_path"]("engineer")
        assert path.endswith("engineer.yml")
        assert "room" not in Path(path).name

    def test_role_name_sanitized(self, memory_tools, memory_env):
        """Path traversal in role name is prevented by os.path.basename."""
        path = memory_tools["_working_path"]("../../../etc/passwd")
        # Should use only the basename
        assert "etc" not in path
        assert "passwd" in Path(path).name
