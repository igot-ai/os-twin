"""
test_memory_note.py — Tests for the memory_note MCP tool.

Covers: basic append, domains, mistake tagging, FIFO eviction,
        room isolation, and file creation.
"""

import json
from pathlib import Path

import yaml
import pytest


class TestMemoryNote:
    """Test the memory_note tool function."""

    def test_basic_note_append(self, memory_tools, memory_env):
        """A simple note gets appended to the working memory file."""
        result = json.loads(
            memory_tools["memory_note"]("Express 5 uses explicit routers")
        )

        assert result["note"] == "Express 5 uses explicit routers"
        assert result["domains"] == []
        assert "timestamp" in result

        # Verify file on disk
        wpath = memory_tools["_working_path"]("engineer")
        data = yaml.safe_load(Path(wpath).read_text())
        assert len(data["notes"]) == 1
        assert data["notes"][0]["note"] == "Express 5 uses explicit routers"
        assert data["role"] == "engineer"

    def test_note_with_domains(self, memory_tools, memory_env):
        """Domains are persisted correctly."""
        result = json.loads(
            memory_tools["memory_note"](
                "Use RS256 for JWT", ["auth", "jwt"], False
            )
        )

        assert result["domains"] == ["auth", "jwt"]

        wpath = memory_tools["_working_path"]("engineer")
        data = yaml.safe_load(Path(wpath).read_text())
        assert data["notes"][0]["domains"] == ["auth", "jwt"]

    def test_mistake_flag(self, memory_tools, memory_env):
        """is_mistake=True sets type: mistake on the note."""
        memory_tools["memory_note"](
            "Forgot to validate token expiry", ["auth"], True
        )

        wpath = memory_tools["_working_path"]("engineer")
        data = yaml.safe_load(Path(wpath).read_text())
        assert data["notes"][0]["type"] == "mistake"

    def test_non_mistake_has_no_type(self, memory_tools, memory_env):
        """Regular notes do not have a type field."""
        memory_tools["memory_note"]("Normal note", None, False)

        wpath = memory_tools["_working_path"]("engineer")
        data = yaml.safe_load(Path(wpath).read_text())
        assert "type" not in data["notes"][0]

    def test_multiple_notes_append(self, memory_tools, memory_env):
        """Multiple notes accumulate in order."""
        memory_tools["memory_note"]("Note 1")
        memory_tools["memory_note"]("Note 2")
        memory_tools["memory_note"]("Note 3")

        wpath = memory_tools["_working_path"]("engineer")
        data = yaml.safe_load(Path(wpath).read_text())
        assert len(data["notes"]) == 3
        assert data["notes"][0]["note"] == "Note 1"
        assert data["notes"][2]["note"] == "Note 3"

    def test_eviction_when_budget_exceeded(self, memory_tools, memory_env):
        """When total note chars exceed MAX_WORKING_CHARS, oldest notes are evicted."""
        # Each note ~300 chars × 30 = 9000 > 8000 budget
        for i in range(30):
            result = memory_tools["memory_note"](f"Note {i}: {'x' * 280}")

        parsed = json.loads(result)
        assert "evicted_count" in parsed
        assert parsed["evicted_count"] > 0
        assert "warning" in parsed

        # Remaining notes should be within budget
        wpath = memory_tools["_working_path"]("engineer")
        data = yaml.safe_load(Path(wpath).read_text())
        total_chars = sum(len(n.get("note", "")) for n in data["notes"])
        assert total_chars <= 8000

    def test_eviction_preserves_newest(self, memory_tools, memory_env):
        """FIFO eviction removes oldest notes; newest are kept."""
        for i in range(30):
            memory_tools["memory_note"](f"Note {i}: {'x' * 280}")

        wpath = memory_tools["_working_path"]("engineer")
        data = yaml.safe_load(Path(wpath).read_text())
        # The last note should always survive
        last_notes = [n["note"] for n in data["notes"]]
        assert any("Note 29" in n for n in last_notes)

    def test_room_isolation(self, memory_tools, memory_env, monkeypatch):
        """Different room dirs produce different working memory files."""
        memory_tools["memory_note"]("Room A note")

        # Switch to a different room
        room_b = Path(memory_env["room_dir"]).parent / "room-test-002"
        room_b.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("AGENT_OS_ROOM_DIR", str(room_b))

        memory_tools["memory_note"]("Room B note")

        # Verify separate files
        wdir = Path(memory_env["memory_dir"]) / "working"
        files = list(wdir.glob("engineer-*.yml"))
        assert len(files) == 2

    def test_creates_directory_if_missing(self, memory_env, memory_tools):
        """Working dir is created automatically if it doesn't exist."""
        wdir = Path(memory_env["memory_dir"]) / "working"
        if wdir.exists():
            import shutil
            shutil.rmtree(wdir)

        memory_tools["memory_note"]("Auto-create test")

        assert wdir.exists()

    def test_updated_at_timestamp(self, memory_tools, memory_env):
        """The updated_at field is set on each write."""
        memory_tools["memory_note"]("First note")

        wpath = memory_tools["_working_path"]("engineer")
        data = yaml.safe_load(Path(wpath).read_text())
        assert "updated_at" in data
        assert data["updated_at"].endswith("Z")
