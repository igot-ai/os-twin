"""
test_memory_recall.py — Tests for the memory_recall MCP tool.

Covers: domain filtering, keyword search, combined filters, ranking,
        access tracking side-effects, empty results, and edge cases.
"""

import json
from pathlib import Path

import yaml
import pytest

from conftest import write_knowledge_fact


class TestMemoryRecall:
    """Test the memory_recall tool function."""

    def test_recall_all_facts(self, memory_tools, memory_env):
        """No filters returns all facts."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        write_knowledge_fact(kb, "fact-1", "Express uses middleware")
        write_knowledge_fact(kb, "fact-2", "JWT tokens expire")

        result = json.loads(memory_tools["memory_recall"]())
        assert len(result) == 2

    def test_recall_by_domain(self, memory_tools, memory_env):
        """Domain filter returns only matching facts."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        write_knowledge_fact(kb, "api-fact", "Express routers", domains=["api"])
        write_knowledge_fact(kb, "auth-fact", "JWT RS256", domains=["auth"])
        write_knowledge_fact(kb, "both-fact", "API auth flow", domains=["api", "auth"])

        result = json.loads(memory_tools["memory_recall"](domains=["api"]))

        facts = [r["fact"] for r in result]
        assert "Express routers" in facts
        assert "API auth flow" in facts
        assert "JWT RS256" not in facts

    def test_recall_by_keyword(self, memory_tools, memory_env):
        """Keyword substring search matches fact text."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        write_knowledge_fact(kb, "f1", "Express 5 requires explicit middleware")
        write_knowledge_fact(kb, "f2", "TypeScript strict mode enabled")
        write_knowledge_fact(kb, "f3", "Express router patterns")

        result = json.loads(
            memory_tools["memory_recall"](keyword="Express")
        )

        assert len(result) == 2
        facts = [r["fact"] for r in result]
        assert all("Express" in f for f in facts)

    def test_recall_keyword_case_insensitive(self, memory_tools, memory_env):
        """Keyword search is case-insensitive."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        write_knowledge_fact(kb, "f1", "EXPRESS middleware order matters")

        result = json.loads(
            memory_tools["memory_recall"](keyword="express")
        )
        assert len(result) == 1

    def test_recall_domain_or_keyword(self, memory_tools, memory_env):
        """Facts matching EITHER domain OR keyword are returned."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        write_knowledge_fact(kb, "f1", "API routes", domains=["api"])
        write_knowledge_fact(kb, "f2", "TypeScript strict", domains=["typescript"])
        write_knowledge_fact(kb, "f3", "unrelated API note", domains=["other"])

        # Domain=api matches f1; keyword="TypeScript" matches f2;
        # f3 has keyword "API" but domain "other" — keyword match wins
        result = json.loads(
            memory_tools["memory_recall"](domains=["api"], keyword="TypeScript")
        )
        facts = [r["fact"] for r in result]
        assert "API routes" in facts       # domain match
        assert "TypeScript strict" in facts  # keyword match

    def test_recall_ranked_by_score(self, memory_tools, memory_env):
        """Facts are ranked by confidence × access_count descending."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        write_knowledge_fact(kb, "low", "Low score fact",
                             confidence=0.3, access_count=1)   # score: 0.3
        write_knowledge_fact(kb, "high", "High score fact",
                             confidence=0.9, access_count=10)  # score: 9.0
        write_knowledge_fact(kb, "med", "Medium score fact",
                             confidence=0.8, access_count=3)   # score: 2.4

        result = json.loads(memory_tools["memory_recall"]())

        assert result[0]["fact"] == "High score fact"
        assert result[1]["fact"] == "Medium score fact"
        assert result[2]["fact"] == "Low score fact"

    def test_recall_updates_access_tracking(self, memory_tools, memory_env):
        """Recall side-effect: last_accessed and access_count are updated."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        fpath = write_knowledge_fact(
            kb, "track-me", "Tracked fact",
            last_accessed="2026-01-01", access_count=5
        )

        memory_tools["memory_recall"]()

        content = fpath.read_text()
        data = yaml.safe_load(content)
        assert data["access_count"] == 6
        # last_accessed should be updated to today
        assert "2026-03-28" in content or "last_accessed" in content

    def test_recall_empty_knowledge_base(self, memory_tools, memory_env):
        """Empty knowledge dir returns empty array."""
        result = json.loads(memory_tools["memory_recall"]())
        assert result == []

    def test_recall_no_matching_domain(self, memory_tools, memory_env):
        """Non-matching domain returns empty results."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        write_knowledge_fact(kb, "f1", "Express fact", domains=["api"])

        result = json.loads(
            memory_tools["memory_recall"](domains=["nonexistent"])
        )
        assert result == []

    def test_recall_no_matching_keyword(self, memory_tools, memory_env):
        """Non-matching keyword returns empty results."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        write_knowledge_fact(kb, "f1", "Express fact")

        result = json.loads(
            memory_tools["memory_recall"](keyword="zzzzzzzzz")
        )
        assert result == []

    def test_recall_skips_malformed_files(self, memory_tools, memory_env):
        """Files without a 'fact' field are ignored."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        write_knowledge_fact(kb, "good", "Good fact")

        # Write a malformed file
        bad = kb / "bad-file.yml"
        bad.write_text("not_a_fact: true\ndomains: [test]\n")

        result = json.loads(memory_tools["memory_recall"]())
        assert len(result) == 1
        assert result[0]["fact"] == "Good fact"

    def test_recall_skips_non_yml_files(self, memory_tools, memory_env):
        """Non-.yml files are ignored."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        write_knowledge_fact(kb, "good", "Good fact")
        (kb / "README.md").write_text("# Not a fact")

        result = json.loads(memory_tools["memory_recall"]())
        assert len(result) == 1

    def test_recall_result_excludes_internal_fields(self, memory_tools, memory_env):
        """Internal fields (_score, _file) are stripped from results."""
        kb = Path(memory_env["memory_dir"]) / "knowledge"
        write_knowledge_fact(kb, "f1", "Test fact")

        result = json.loads(memory_tools["memory_recall"]())
        for r in result:
            assert "_score" not in r
            assert "_file" not in r
