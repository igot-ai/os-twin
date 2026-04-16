"""Tests for Agentic Memory (A-mem-sys) dashboard API routes.

Tests the /api/amem/{plan_id}/... endpoints that serve memory graph data,
note listings, individual notes, and statistics from the .memory/ directory.
"""

import json
import pytest
from fastapi.testclient import TestClient

from dashboard.api import app
from dashboard.auth import get_current_user


# ── Auth mock ─────────────────────────────────────────────────────────


def mock_get_current_user():
    return {"user_id": "test_user"}


app.dependency_overrides[get_current_user] = mock_get_current_user


# ── Fixtures ──────────────────────────────────────────────────────────

SAMPLE_NOTE_SCHEMA = """# Video Platform: Database Schemas

**Tags**: #database, #schema, #postgresql
**Keywords**: users, videos, comments, likes, relational integrity
**Links**: api-contracts, system-architecture

## Problem Statement
Need a relational schema for a video-sharing platform supporting users,
video uploads, comments, and likes with full referential integrity.

## Schema
CREATE TABLE users (id UUID PRIMARY KEY, username VARCHAR(50), email VARCHAR(255));
CREATE TABLE videos (id UUID PRIMARY KEY, user_id UUID REFERENCES users(id), title VARCHAR(255));
CREATE TABLE comments (id UUID PRIMARY KEY, video_id UUID REFERENCES videos(id), content TEXT);
CREATE TABLE likes (id UUID PRIMARY KEY, video_id UUID REFERENCES videos(id), user_id UUID REFERENCES users(id));
"""

SAMPLE_NOTE_API = """# API Contracts — Video Platform

**Tags**: #api, #rest, #video
**Keywords**: REST, endpoints, authentication, pagination
**Links**: database-schemas

## Endpoints
POST /api/users/register
POST /api/users/login
POST /api/videos
GET /api/videos
GET /api/videos/:id
POST /api/videos/:id/comments
"""

SAMPLE_NOTE_DECISION = """# Architecture Decision: CDN Strategy

**Tags**: #architecture, #decision, #cdn
**Keywords**: CloudFront, S3, latency, caching

Chose CloudFront CDN over self-hosted Nginx for video delivery.
Why: automatic edge caching, lower egress costs, global PoPs.
Trade-off: vendor lock-in with AWS, but acceptable for current scale.
"""

SAMPLE_NOTE_MINIMAL = """# Minimal Note

Just a simple note with no metadata.
"""


@pytest.fixture
def memory_workspace(tmp_path):
    """Create a realistic .memory/ directory structure with sample notes."""
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()

    # Create .memory/notes structure
    memory_dir = project_dir / ".memory"
    notes_dir = memory_dir / "notes"

    # architecture/database/
    (notes_dir / "architecture" / "database").mkdir(parents=True)
    (notes_dir / "architecture" / "database" / "database-schemas.md").write_text(
        SAMPLE_NOTE_SCHEMA, encoding="utf-8"
    )

    # architecture/api/
    (notes_dir / "architecture" / "api").mkdir(parents=True)
    (notes_dir / "architecture" / "api" / "api-contracts.md").write_text(
        SAMPLE_NOTE_API, encoding="utf-8"
    )

    # architecture/decisions/
    (notes_dir / "architecture" / "decisions").mkdir(parents=True)
    (notes_dir / "architecture" / "decisions" / "cdn-strategy.md").write_text(
        SAMPLE_NOTE_DECISION, encoding="utf-8"
    )

    # unfiled/
    (notes_dir / "misc").mkdir(parents=True)
    (notes_dir / "misc" / "minimal-note.md").write_text(
        SAMPLE_NOTE_MINIMAL, encoding="utf-8"
    )

    # Create vectordb (empty, just to prove it exists)
    (memory_dir / "vectordb" / "memories").mkdir(parents=True)

    # Create plans directory with meta file pointing to project
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    plan_id = "test-project.plan"
    meta = {
        "plan_id": plan_id,
        "working_dir": str(project_dir),
    }
    (plans_dir / f"{plan_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")

    # Also create the plan .md file with working_dir
    plan_content = f"""# Plan: Test Project

> Created: 2026-04-06T00:00:00Z
> Status: approved

## Config
working_dir: {project_dir}

## Goal
Build a video platform.
"""
    (plans_dir / f"{plan_id}.md").write_text(plan_content, encoding="utf-8")

    return {
        "project_dir": project_dir,
        "memory_dir": memory_dir,
        "notes_dir": notes_dir,
        "plans_dir": plans_dir,
        "plan_id": plan_id,
    }


@pytest.fixture
def empty_memory_workspace(tmp_path):
    """Create a project with an empty .memory/notes/ directory."""
    project_dir = tmp_path / "empty-project"
    project_dir.mkdir()

    memory_dir = project_dir / ".memory"
    (memory_dir / "notes").mkdir(parents=True)

    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    plan_id = "empty-project.plan"
    meta = {"plan_id": plan_id, "working_dir": str(project_dir)}
    (plans_dir / f"{plan_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")

    return {
        "project_dir": project_dir,
        "plans_dir": plans_dir,
        "plan_id": plan_id,
    }


@pytest.fixture
def no_memory_workspace(tmp_path):
    """Create a project with NO .memory/ directory at all."""
    project_dir = tmp_path / "no-memory-project"
    project_dir.mkdir()

    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    plan_id = "no-memory.plan"
    meta = {"plan_id": plan_id, "working_dir": str(project_dir)}
    (plans_dir / f"{plan_id}.meta.json").write_text(json.dumps(meta), encoding="utf-8")

    return {
        "project_dir": project_dir,
        "plans_dir": plans_dir,
        "plan_id": plan_id,
    }


# ── Graph endpoint tests ─────────────────────────────────────────────


class TestMemoryGraph:
    """Tests for GET /api/amem/{plan_id}/graph"""

    def test_graph_returns_nodes_and_links(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        resp = client.get(f"/api/amem/{memory_workspace['plan_id']}/graph")
        assert resp.status_code == 200

        data = resp.json()
        assert "groups" in data
        assert "nodes" in data
        assert "links" in data
        assert "stats" in data

    def test_graph_has_correct_node_count(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/graph").json()
        assert data["stats"]["total_memories"] == 4

    def test_graph_nodes_have_required_fields(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/graph").json()
        required_fields = {
            "id",
            "title",
            "path",
            "pathLabel",
            "excerpt",
            "tags",
            "keywords",
            "groupId",
            "color",
        }

        for node in data["nodes"]:
            for field in required_fields:
                assert field in node, f"Node missing field: {field}"

    def test_graph_groups_from_directory_structure(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/graph").json()
        group_ids = {g["id"] for g in data["groups"]}
        assert "architecture" in group_ids
        assert "misc" in group_ids

    def test_graph_links_between_notes(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/graph").json()
        # database-schemas has links to api-contracts and system-architecture
        # api-contracts has link to database-schemas
        # Links are only created if target ID exists in notes
        # Our note IDs are filenames without .md, so links should match
        assert isinstance(data["links"], list)

    def test_graph_groups_have_colors(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/graph").json()
        for group in data["groups"]:
            assert "color" in group
            assert group["color"].startswith("#")

    def test_graph_empty_memory(self, empty_memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", empty_memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{empty_memory_workspace['plan_id']}/graph").json()
        assert data["stats"]["total_memories"] == 0
        assert data["nodes"] == []
        assert data["links"] == []
        assert data["groups"] == []

    def test_graph_no_memory_dir_returns_404(self, no_memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", no_memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        resp = client.get(f"/api/amem/{no_memory_workspace['plan_id']}/graph")
        assert resp.status_code == 404

    def test_graph_nonexistent_plan_returns_404(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        resp = client.get("/api/amem/nonexistent-plan/graph")
        assert resp.status_code == 404


# ── Notes list endpoint tests ────────────────────────────────────────


class TestMemoryNotesList:
    """Tests for GET /api/amem/{plan_id}/notes"""

    def test_list_notes_returns_all(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/notes").json()
        assert len(data) == 4

    def test_list_notes_excludes_content(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/notes").json()
        for note in data:
            assert "content" not in note

    def test_list_notes_has_metadata(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/notes").json()
        for note in data:
            assert "id" in note
            assert "title" in note
            assert "path" in note
            assert "tags" in note

    def test_list_notes_parses_tags(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/notes").json()
        schema_note = next((n for n in data if n["id"] == "database-schemas"), None)
        assert schema_note is not None
        assert "database" in schema_note["tags"]
        assert "schema" in schema_note["tags"]

    def test_list_notes_parses_keywords(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/notes").json()
        schema_note = next((n for n in data if n["id"] == "database-schemas"), None)
        assert schema_note is not None
        assert "users" in schema_note["keywords"]

    def test_list_notes_empty(self, empty_memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", empty_memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{empty_memory_workspace['plan_id']}/notes").json()
        assert data == []


# ── Single note endpoint tests ───────────────────────────────────────


class TestMemoryNoteDetail:
    """Tests for GET /api/amem/{plan_id}/notes/{note_id}"""

    def test_get_note_by_id(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        resp = client.get(
            f"/api/amem/{memory_workspace['plan_id']}/notes/database-schemas"
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["id"] == "database-schemas"
        assert "content" in data
        assert "CREATE TABLE" in data["content"]

    def test_get_note_has_title_from_h1(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(
            f"/api/amem/{memory_workspace['plan_id']}/notes/database-schemas"
        ).json()
        assert data["title"] == "Video Platform: Database Schemas"

    def test_get_note_has_links(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(
            f"/api/amem/{memory_workspace['plan_id']}/notes/database-schemas"
        ).json()
        assert "api-contracts" in data["links"]
        assert "system-architecture" in data["links"]

    def test_get_note_nonexistent_returns_404(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        resp = client.get(
            f"/api/amem/{memory_workspace['plan_id']}/notes/does-not-exist"
        )
        assert resp.status_code == 404

    def test_get_note_minimal_has_defaults(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(
            f"/api/amem/{memory_workspace['plan_id']}/notes/minimal-note"
        ).json()
        assert data["title"] == "Minimal Note"
        assert data["tags"] == []
        assert data["keywords"] == []
        assert data["links"] == []


# ── Stats endpoint tests ─────────────────────────────────────────────


class TestMemoryStats:
    """Tests for GET /api/amem/{plan_id}/stats"""

    def test_stats_returns_counts(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/stats").json()
        assert data["total_notes"] == 4
        assert data["total_tags"] > 0
        assert data["total_keywords"] > 0

    def test_stats_includes_all_tags(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/stats").json()
        assert "database" in data["tags"]
        assert "api" in data["tags"]
        assert "architecture" in data["tags"]

    def test_stats_includes_paths(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/stats").json()
        assert len(data["paths"]) > 0

    def test_stats_includes_memory_dir(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{memory_workspace['plan_id']}/stats").json()
        assert "memory_dir" in data
        assert ".memory" in data["memory_dir"]

    def test_stats_empty_memory(self, empty_memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", empty_memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        data = client.get(f"/api/amem/{empty_memory_workspace['plan_id']}/stats").json()
        assert data["total_notes"] == 0
        assert data["total_tags"] == 0
        assert data["tags"] == []

    def test_stats_no_memory_returns_404(self, no_memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", no_memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        resp = client.get(f"/api/amem/{no_memory_workspace['plan_id']}/stats")
        assert resp.status_code == 404


# ── Plan resolution tests ────────────────────────────────────────────


class TestPlanResolution:
    """Tests for _resolve_memory_dir — resolving .memory/ from plan_id."""

    def test_resolves_from_meta_json(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        resp = client.get(f"/api/amem/{memory_workspace['plan_id']}/stats")
        assert resp.status_code == 200

    def test_resolves_from_plan_md_fallback(self, tmp_path, monkeypatch):
        """When meta.json doesn't exist, falls back to parsing the .md file."""
        project_dir = tmp_path / "fallback-project"
        project_dir.mkdir()
        (project_dir / ".memory" / "notes").mkdir(parents=True)

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_id = "fallback.plan"
        # Only create .md, no .meta.json
        (plans_dir / f"{plan_id}.md").write_text(
            f"# Plan: Fallback\n\nworking_dir: {project_dir}\n",
            encoding="utf-8",
        )

        monkeypatch.setattr("dashboard.routes.amem.PLANS_DIR", plans_dir)
        client = TestClient(app)

        resp = client.get(f"/api/amem/{plan_id}/stats")
        assert resp.status_code == 200

    def test_nonexistent_plan_returns_404(self, memory_workspace, monkeypatch):
        monkeypatch.setattr(
            "dashboard.routes.amem.PLANS_DIR", memory_workspace["plans_dir"]
        )
        client = TestClient(app)

        resp = client.get("/api/amem/this-plan-does-not-exist/graph")
        assert resp.status_code == 404


# ── Note parsing edge cases ──────────────────────────────────────────


class TestNoteParsing:
    """Tests for note parsing edge cases in _load_notes."""

    def test_note_without_h1_uses_filename(self, tmp_path, monkeypatch):
        """Notes without a # heading use the filename as title."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        notes_dir = project_dir / ".memory" / "notes"
        notes_dir.mkdir(parents=True)
        (notes_dir / "no-heading.md").write_text(
            "Just content, no heading.", encoding="utf-8"
        )

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_id = "test.plan"
        (plans_dir / f"{plan_id}.meta.json").write_text(
            json.dumps({"plan_id": plan_id, "working_dir": str(project_dir)}),
            encoding="utf-8",
        )

        monkeypatch.setattr("dashboard.routes.amem.PLANS_DIR", plans_dir)
        client = TestClient(app)

        data = client.get(f"/api/amem/{plan_id}/notes").json()
        assert len(data) == 1
        assert data[0]["title"] == "No Heading"  # filename-based title

    def test_note_with_empty_tags(self, tmp_path, monkeypatch):
        """Notes with **Tags**: but empty value."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        notes_dir = project_dir / ".memory" / "notes"
        notes_dir.mkdir(parents=True)
        (notes_dir / "empty-tags.md").write_text(
            "# Test\n\n**Tags**: \n\nContent here.", encoding="utf-8"
        )

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_id = "test.plan"
        (plans_dir / f"{plan_id}.meta.json").write_text(
            json.dumps({"plan_id": plan_id, "working_dir": str(project_dir)}),
            encoding="utf-8",
        )

        monkeypatch.setattr("dashboard.routes.amem.PLANS_DIR", plans_dir)
        client = TestClient(app)

        data = client.get(f"/api/amem/{plan_id}/notes").json()
        assert len(data) == 1
        # Empty tags line should produce empty or single-element list
        assert isinstance(data[0]["tags"], list)

    def test_non_md_files_ignored(self, tmp_path, monkeypatch):
        """Only .md files are loaded, other files are ignored."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        notes_dir = project_dir / ".memory" / "notes"
        notes_dir.mkdir(parents=True)
        (notes_dir / "note.md").write_text("# Real Note\nContent.", encoding="utf-8")
        (notes_dir / "data.json").write_text('{"not": "a note"}', encoding="utf-8")
        (notes_dir / "image.png").write_bytes(b"\x89PNG")

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_id = "test.plan"
        (plans_dir / f"{plan_id}.meta.json").write_text(
            json.dumps({"plan_id": plan_id, "working_dir": str(project_dir)}),
            encoding="utf-8",
        )

        monkeypatch.setattr("dashboard.routes.amem.PLANS_DIR", plans_dir)
        client = TestClient(app)

        data = client.get(f"/api/amem/{plan_id}/notes").json()
        assert len(data) == 1
        assert data[0]["id"] == "note"

    def test_deeply_nested_notes(self, tmp_path, monkeypatch):
        """Notes in deeply nested directories are found."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        deep_dir = project_dir / ".memory" / "notes" / "a" / "b" / "c"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep-note.md").write_text("# Deep\nContent.", encoding="utf-8")

        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        plan_id = "test.plan"
        (plans_dir / f"{plan_id}.meta.json").write_text(
            json.dumps({"plan_id": plan_id, "working_dir": str(project_dir)}),
            encoding="utf-8",
        )

        monkeypatch.setattr("dashboard.routes.amem.PLANS_DIR", plans_dir)
        client = TestClient(app)

        data = client.get(f"/api/amem/{plan_id}/notes").json()
        assert len(data) == 1
        assert data[0]["path"] == "a/b/c"
