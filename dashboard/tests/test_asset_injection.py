"""
EPIC-004 — Tests for asset injection into war rooms.

Tests: asset resolution, copy into room directory, asset manifest in TASKS.md,
       asset context in system prompts, graceful handling of missing files.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from dashboard.routes.plans import (
    _ensure_plan_meta, _write_plan_meta, _normalize_plan_assets,
    bind_asset_to_epic, list_epic_assets,
)
from dashboard.epic_manager import EpicSkillsManager


@pytest.fixture
def temp_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.routes.plans.PLANS_DIR", tmp_path)
    plan_id = "inject-test"
    plan_file = tmp_path / f"{plan_id}.md"
    plan_file.write_text("# Plan: Inject Test\n\n### EPIC-001 — Build API\n\n### EPIC-002 — Frontend\n")
    assets_dir = tmp_path / "assets" / plan_id
    assets_dir.mkdir(parents=True)
    return plan_id, tmp_path, assets_dir


@pytest.fixture
def room_dir(tmp_path):
    """Create a mock war room directory."""
    room = tmp_path / "room-001"
    room.mkdir()
    config = {"assignment": {"assigned_role": "engineer", "task_ref": "EPIC-001"}}
    (room / "config.json").write_text(json.dumps(config))
    (room / "TASKS.md").write_text("# Tasks\n\n- [ ] Implement feature\n")
    return room


def test_inject_room_assets_copies_files(temp_plan, room_dir):
    """Assets should be copied into room_dir/assets/ directory."""
    plan_id, tmp_path, assets_dir = temp_plan

    # Create assets
    (assets_dir / "spec.pdf").write_bytes(b"pdf-content")
    (assets_dir / "shared.txt").write_text("shared")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "spec.pdf", "original_name": "spec.pdf", "mime_type": "application/pdf",
         "asset_type": "api-spec", "description": "API specification", "bound_epics": ["EPIC-001"]},
        {"filename": "shared.txt", "original_name": "shared.txt", "mime_type": "text/plain",
         "asset_type": "reference-doc", "description": "Shared doc", "bound_epics": []},
    ]
    meta["epic_assets"] = {"EPIC-001": ["spec.pdf"]}
    _write_plan_meta(plan_id, meta)

    EpicSkillsManager.inject_room_assets(room_dir, plan_id, "EPIC-001")

    room_assets_dir = room_dir / "assets"
    assert room_assets_dir.exists()
    assert (room_assets_dir / "spec.pdf").exists()
    assert (room_assets_dir / "shared.txt").exists()
    assert (room_assets_dir / "spec.pdf").read_bytes() == b"pdf-content"


def test_inject_room_assets_writes_manifest(temp_plan, room_dir):
    """TASKS.md should be updated with an ## Available Assets section."""
    plan_id, tmp_path, assets_dir = temp_plan

    (assets_dir / "design.png").write_bytes(b"png-data")
    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "design.png", "original_name": "design.png", "mime_type": "image/png",
         "asset_type": "design-mockup", "description": "Login mockup", "bound_epics": ["EPIC-001"]},
    ]
    meta["epic_assets"] = {"EPIC-001": ["design.png"]}
    _write_plan_meta(plan_id, meta)

    EpicSkillsManager.inject_room_assets(room_dir, plan_id, "EPIC-001")

    tasks_md = (room_dir / "TASKS.md").read_text()
    assert "## Available Assets" in tasks_md
    assert "design.png" in tasks_md
    assert "design-mockup" in tasks_md
    assert "Login mockup" in tasks_md


def test_inject_room_assets_missing_file_graceful(temp_plan, room_dir):
    """Missing asset files should log a warning but not block room creation."""
    plan_id, tmp_path, assets_dir = temp_plan

    # Don't actually create the file on disk
    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "missing.pdf", "original_name": "missing.pdf", "mime_type": "application/pdf",
         "asset_type": "api-spec", "description": "Missing file", "bound_epics": ["EPIC-001"]},
    ]
    meta["epic_assets"] = {"EPIC-001": ["missing.pdf"]}
    _write_plan_meta(plan_id, meta)

    # Should not raise
    EpicSkillsManager.inject_room_assets(room_dir, plan_id, "EPIC-001")

    # Room assets dir may or may not exist — that's fine
    room_assets_dir = room_dir / "assets"
    if room_assets_dir.exists():
        assert not (room_assets_dir / "missing.pdf").exists()


def test_inject_room_assets_no_assets(temp_plan, room_dir):
    """When there are no assets, injection should be a no-op."""
    plan_id, tmp_path, assets_dir = temp_plan

    meta = _ensure_plan_meta(plan_id)
    _write_plan_meta(plan_id, meta)

    EpicSkillsManager.inject_room_assets(room_dir, plan_id, "EPIC-999")

    assert not (room_dir / "assets").exists()
    # TASKS.md should be unchanged
    assert "Available Assets" not in (room_dir / "TASKS.md").read_text()


def test_inject_room_assets_only_epic_bound(temp_plan, room_dir):
    """Only assets bound to the target epic (or plan-level) should be injected."""
    plan_id, tmp_path, assets_dir = temp_plan

    (assets_dir / "for-epic-001.txt").write_text("epic-001")
    (assets_dir / "for-epic-002.txt").write_text("epic-002")
    (assets_dir / "shared.txt").write_text("shared")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "for-epic-001.txt", "original_name": "for-epic-001.txt",
         "bound_epics": ["EPIC-001"], "asset_type": "reference-doc", "description": ""},
        {"filename": "for-epic-002.txt", "original_name": "for-epic-002.txt",
         "bound_epics": ["EPIC-002"], "asset_type": "reference-doc", "description": ""},
        {"filename": "shared.txt", "original_name": "shared.txt",
         "bound_epics": [], "asset_type": "reference-doc", "description": ""},
    ]
    meta["epic_assets"] = {"EPIC-001": ["for-epic-001.txt"], "EPIC-002": ["for-epic-002.txt"]}
    _write_plan_meta(plan_id, meta)

    EpicSkillsManager.inject_room_assets(room_dir, plan_id, "EPIC-001")

    room_assets_dir = room_dir / "assets"
    assert (room_assets_dir / "for-epic-001.txt").exists()
    assert (room_assets_dir / "shared.txt").exists()
    assert not (room_assets_dir / "for-epic-002.txt").exists()


def test_generate_system_prompt_with_assets(temp_plan, room_dir, monkeypatch):
    """System prompt should include asset references when assets exist."""
    plan_id, tmp_path, assets_dir = temp_plan

    (assets_dir / "spec.yaml").write_text("openapi: 3.0")
    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "spec.yaml", "original_name": "spec.yaml", "mime_type": "text/yaml",
         "asset_type": "api-spec", "description": "OpenAPI spec", "bound_epics": ["EPIC-001"]},
    ]
    meta["epic_assets"] = {"EPIC-001": ["spec.yaml"]}
    _write_plan_meta(plan_id, meta)

    # Inject assets into room first
    EpicSkillsManager.inject_room_assets(room_dir, plan_id, "EPIC-001")

    # Build asset context string
    context = EpicSkillsManager.build_asset_context(plan_id, "EPIC-001")
    assert "spec.yaml" in context
    assert "api-spec" in context
    assert "OpenAPI spec" in context


def test_build_asset_context_no_assets(temp_plan):
    """When there are no assets, context should be empty."""
    plan_id, tmp_path, assets_dir = temp_plan
    meta = _ensure_plan_meta(plan_id)
    _write_plan_meta(plan_id, meta)

    context = EpicSkillsManager.build_asset_context(plan_id, "EPIC-999")
    assert context == ""


# ── FIX-3: Symlink for large files ──────────────────────────────

LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB


def test_inject_room_assets_symlinks_large_files(temp_plan, room_dir):
    """Files >10MB should be symlinked, not copied."""
    plan_id, tmp_path, assets_dir = temp_plan

    # Create a file that's just over the threshold (we'll fake it with a small file
    # and check the logic by creating a real large-ish marker)
    large_file = assets_dir / "big-video.mp4"
    # Write exactly 10MB + 1 byte
    large_file.write_bytes(b"\x00" * (LARGE_FILE_THRESHOLD + 1))

    small_file = assets_dir / "small.txt"
    small_file.write_text("small")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "big-video.mp4", "original_name": "big-video.mp4", "mime_type": "video/mp4",
         "asset_type": "media", "description": "Large video", "bound_epics": ["EPIC-001"]},
        {"filename": "small.txt", "original_name": "small.txt", "mime_type": "text/plain",
         "asset_type": "reference-doc", "description": "", "bound_epics": ["EPIC-001"]},
    ]
    meta["epic_assets"] = {"EPIC-001": ["big-video.mp4", "small.txt"]}
    _write_plan_meta(plan_id, meta)

    EpicSkillsManager.inject_room_assets(room_dir, plan_id, "EPIC-001")

    room_assets = room_dir / "assets"
    big_dest = room_assets / "big-video.mp4"
    small_dest = room_assets / "small.txt"

    # Both should exist
    assert big_dest.exists()
    assert small_dest.exists()

    # Large file should be a symlink
    assert big_dest.is_symlink()
    assert big_dest.resolve() == large_file.resolve()

    # Small file should be a regular copy (not a symlink)
    assert not small_dest.is_symlink()
    assert small_dest.read_text() == "small"
