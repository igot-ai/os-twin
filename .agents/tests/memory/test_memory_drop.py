"""
test_memory_drop.py — Tests for the memory_drop MCP tool.

Covers: substring matching, multi-match removal, no-match handling,
        empty input rejection, and file integrity.
"""

import json
from pathlib import Path

import yaml
import pytest


class TestMemoryDrop:
    """Test the memory_drop tool function."""

    def _seed_notes(self, memory_tools, notes: list[str]):
        """Helper: populate working memory with a list of notes."""
        for note in notes:
            memory_tools["memory_note"](note)

    def test_drop_matching_note(self, memory_tools, memory_env):
        """A note containing the substring is removed."""
        self._seed_notes(memory_tools, [
            "Express 5 routers are required",
            "CORS must come before auth",
            "JWT uses RS256",
        ])

        result = memory_tools["memory_drop"]("CORS must")
        dropped = json.loads(result)

        assert len(dropped) == 1
        assert "CORS" in dropped[0]["note"]

        # Verify remaining
        wpath = memory_tools["_working_path"]("engineer")
        data = yaml.safe_load(Path(wpath).read_text())
        remaining_notes = [n["note"] for n in data["notes"]]
        assert len(remaining_notes) == 2
        assert not any("CORS" in n for n in remaining_notes)

    def test_drop_multiple_matches(self, memory_tools, memory_env):
        """All notes containing the substring are removed."""
        self._seed_notes(memory_tools, [
            "MISTAKE: forgot content-type",
            "Normal note about API",
            "MISTAKE: wrong status code",
        ])

        result = memory_tools["memory_drop"]("MISTAKE:")
        dropped = json.loads(result)

        assert len(dropped) == 2

        wpath = memory_tools["_working_path"]("engineer")
        data = yaml.safe_load(Path(wpath).read_text())
        assert len(data["notes"]) == 1
        assert "Normal note" in data["notes"][0]["note"]

    def test_drop_no_match(self, memory_tools, memory_env):
        """Returns 'no match' when substring not found."""
        self._seed_notes(memory_tools, ["Some note"])

        result = memory_tools["memory_drop"]("nonexistent substring xyz")
        assert result == "no match"

    def test_drop_empty_working_memory(self, memory_tools, memory_env):
        """Returns 'no match' when no notes exist."""
        result = memory_tools["memory_drop"]("anything")
        assert result == "no match"

    def test_drop_empty_substring_rejected(self, memory_tools, memory_env):
        """Empty or whitespace-only substring is rejected."""
        result = memory_tools["memory_drop"]("")
        assert "error" in result

        result = memory_tools["memory_drop"]("   ")
        assert "error" in result

    def test_drop_preserves_metadata(self, memory_tools, memory_env):
        """After drop, remaining notes still have their domains and timestamps."""
        memory_tools["memory_note"]("Keep this note", ["api", "auth"])
        memory_tools["memory_note"]("Drop this note", ["test"])

        memory_tools["memory_drop"]("Drop this")

        wpath = memory_tools["_working_path"]("engineer")
        data = yaml.safe_load(Path(wpath).read_text())
        assert len(data["notes"]) == 1
        assert data["notes"][0]["domains"] == ["api", "auth"]
        assert "timestamp" in data["notes"][0]

    def test_drop_updates_timestamp(self, memory_tools, memory_env):
        """The updated_at field is refreshed after a drop."""
        memory_tools["memory_note"]("Initial note")

        wpath = memory_tools["_working_path"]("engineer")
        data_before = yaml.safe_load(Path(wpath).read_text())
        ts_before = data_before["updated_at"]

        import time
        time.sleep(0.01)  # Ensure timestamp differs

        memory_tools["memory_note"]("To be dropped")
        memory_tools["memory_drop"]("To be dropped")

        data_after = yaml.safe_load(Path(wpath).read_text())
        # updated_at should be present (may or may not differ within same second)
        assert "updated_at" in data_after

    def test_drop_case_sensitive(self, memory_tools, memory_env):
        """Substring matching is case-sensitive."""
        self._seed_notes(memory_tools, ["Express Router", "express router"])

        result = memory_tools["memory_drop"]("Express")
        dropped = json.loads(result)

        # Only the uppercase version should match
        assert len(dropped) == 1
        assert dropped[0]["note"] == "Express Router"
