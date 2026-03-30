"""
conftest.py — Shared fixtures for the memory test suite.

All tests use isolated temp directories so they never touch real memory data.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml


# ── Paths ────────────────────────────────────────────────────────────────────

TESTS_DIR = Path(__file__).resolve().parent
AGENTS_DIR = TESTS_DIR.parent.parent  # .agents/
MEMORY_SERVER = AGENTS_DIR / "mcp" / "memory-server.py"
PROJECT_ROOT = AGENTS_DIR.parent


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_agents_dir(tmp_path: Path) -> Path:
    """Create a minimal .agents/ structure in a temp directory."""
    agents = tmp_path / ".agents"
    (agents / "memory" / "working").mkdir(parents=True)
    (agents / "memory" / "knowledge").mkdir(parents=True)
    (agents / "memory" / "sessions").mkdir(parents=True)

    # Minimal config.json with memory enabled
    config = {
        "version": "0.1.0",
        "project_name": "test",
        "engineer": {"cli": "echo", "default_model": "test-model", "timeout_seconds": 10},
        "memory": {
            "enabled": True,
            "consolidation_model": "gemini-3-flash-preview",
            "decay_constant": 7.0,
            "retention_threshold": 0.2,
            "session_digest_enabled": True,
            "max_session_age_days": 30,
        },
    }
    (agents / "config.json").write_text(
        __import__("json").dumps(config, indent=2)
    )
    return agents


@pytest.fixture()
def tmp_room(tmp_agents_dir: Path) -> Path:
    """Create a minimal war room inside the temp .agents/ structure."""
    room = tmp_agents_dir.parent / "war-rooms" / "room-test-001"
    (room / "artifacts").mkdir(parents=True)
    (room / "pids").mkdir(parents=True)

    brief = room / "brief.md"
    brief.write_text("# Test Task\nBuild a REST API with Express and JWT auth.\n")
    return room


@pytest.fixture()
def memory_env(tmp_agents_dir: Path, tmp_room: Path, monkeypatch):
    """Set environment variables as the real MCP server would see them."""
    monkeypatch.setenv("AGENT_OS_ROLE", "engineer")
    monkeypatch.setenv("AGENT_OS_ROOM_DIR", str(tmp_room))
    return {
        "agents_dir": tmp_agents_dir,
        "room_dir": tmp_room,
        "memory_dir": tmp_agents_dir / "memory",
    }


@pytest.fixture()
def memory_tools(memory_env, monkeypatch):
    """
    Import the three MCP tool functions from memory-server.py by exec'ing
    the module source with MEMORY_DIR patched to our temp directory.

    Returns a namespace dict with: memory_note, memory_drop, memory_recall,
    _working_path, _read_working, MEMORY_DIR.
    """
    import re as _re

    source = MEMORY_SERVER.read_text()

    # We only need the code up to `if __name__`, not the server entrypoint
    code = source.split('if __name__')[0]

    # Strip the FastMCP decorator lines — we call functions directly
    code = _re.sub(r'@mcp\.tool\(\)\n', '', code)

    # Strip the FastMCP instantiation line
    code = _re.sub(r'^mcp\s*=\s*FastMCP\(.*\)\s*$', '', code, flags=_re.MULTILINE)

    # Strip the MEMORY_DIR and MAX_WORKING_CHARS definitions —
    # we inject our own values before exec
    code = _re.sub(
        r'^MEMORY_DIR\s*=\s*os\.path\.join\([^)]*\)[^)]*\)\s*$',
        '',
        code,
        flags=_re.MULTILINE | _re.DOTALL,
    )
    # More robust: remove the multi-line MEMORY_DIR assignment
    code = _re.sub(
        r'MEMORY_DIR\s*=\s*os\.path\.join\(\s*os\.path\.dirname.*?"memory",\s*\)',
        '',
        code,
        flags=_re.DOTALL,
    )
    code = _re.sub(r'^MAX_WORKING_CHARS\s*=.*$', '', code, flags=_re.MULTILINE)

    # Build a namespace with the required imports pre-loaded
    ns = {
        "__file__": str(MEMORY_SERVER),  # memory-server.py needs __file__
    }
    exec(
        "import json, os, re, yaml\n"
        "from datetime import datetime, timezone\n"
        "from typing import Annotated\n"
        "from pydantic import Field\n",
        ns,
    )

    # Override MEMORY_DIR and MAX_WORKING_CHARS to point to temp
    ns["MEMORY_DIR"] = str(memory_env["memory_dir"])
    ns["MAX_WORKING_CHARS"] = 8000

    # Execute the functions into our namespace
    exec(code, ns)

    # Ensure MEMORY_DIR wasn't overwritten by the exec (belt and suspenders)
    ns["MEMORY_DIR"] = str(memory_env["memory_dir"])
    ns["MAX_WORKING_CHARS"] = 8000

    return ns


# ── Helpers ──────────────────────────────────────────────────────────────────

def write_knowledge_fact(knowledge_dir: Path, slug: str, fact: str, **kwargs) -> Path:
    """Write a knowledge fact YAML file. Returns the file path."""
    data = {
        "fact": fact,
        "source": kwargs.get("source", "test-room"),
        "source_role": kwargs.get("source_role", "engineer"),
        "domains": kwargs.get("domains", ["test"]),
        "origin": kwargs.get("origin", "discovery"),
        "confidence": kwargs.get("confidence", 0.7),
        "created": kwargs.get("created", "2026-03-26"),
        "last_accessed": kwargs.get("last_accessed", "2026-03-26"),
        "access_count": kwargs.get("access_count", 1),
    }
    fpath = knowledge_dir / f"{slug}.yml"
    fpath.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return fpath


def write_session_digest(sessions_dir: Path, filename: str, **kwargs) -> Path:
    """Write a session digest YAML file. Returns the file path."""
    data = {
        "session_id": kwargs.get("session_id", "room-test-001-engineer-2026-03-26"),
        "room_id": kwargs.get("room_id", "room-test-001"),
        "agent_role": kwargs.get("agent_role", "engineer"),
        "date": kwargs.get("date", "2026-03-26"),
        "domain_tags": kwargs.get("domain_tags", ["test"]),
        "summary": kwargs.get("summary", "Test session summary"),
        "what_happened": kwargs.get("what_happened", ["Did thing 1"]),
        "decisions": kwargs.get("decisions", ["Decision 1"]),
        "learnings": kwargs.get("learnings", ["Learning 1"]),
        "mistakes": kwargs.get("mistakes", []),
    }
    fpath = sessions_dir / filename
    fpath.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return fpath
