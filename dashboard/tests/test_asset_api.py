"""
EPIC-002 — Integration tests for asset management API endpoints.

Tests: upload-with-binding, bind, unbind, list-by-epic, metadata update, error cases.
"""
import json
import pytest
from unittest.mock import patch
from pathlib import Path

from dashboard.routes.plans import (
    _ensure_plan_meta, _normalize_plan_assets, _write_plan_meta,
    _plan_assets_dir, _serialize_plan_asset, _plan_file_path,
    _update_plan_assets_section, _update_epic_asset_sections,
    _merge_markdown_asset_edits_into_meta,
    bind_asset_to_epic, unbind_asset_from_epic, list_epic_assets,
    update_asset_metadata, get_asset_or_404, _get_valid_epic_refs,
)


@pytest.fixture
def temp_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.routes.plans.PLANS_DIR", tmp_path)
    monkeypatch.setattr("dashboard.routes.plans.GLOBAL_PLANS_DIR", tmp_path)
    plan_id = "api-test-plan"
    plan_file = tmp_path / f"{plan_id}.md"
    plan_file.write_text("# Plan: API Test Plan\n\n## Epics\n\n### EPIC-001 — First\n\n### EPIC-002 — Second\n")

    assets_dir = tmp_path / "assets" / plan_id
    assets_dir.mkdir(parents=True)
    return plan_id, tmp_path, assets_dir


# ── get_asset_or_404 ──────────────────────────────────────────────

def test_get_asset_or_404_found(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "file.txt").write_text("hello")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "file.txt", "original_name": "file.txt"}]
    _write_plan_meta(plan_id, meta)

    asset = get_asset_or_404(plan_id, "file.txt")
    assert asset["filename"] == "file.txt"


def test_get_asset_or_404_not_found(temp_plan):
    from fastapi import HTTPException
    plan_id, tmp_path, assets_dir = temp_plan

    with pytest.raises(HTTPException) as exc:
        get_asset_or_404(plan_id, "ghost.txt")
    assert exc.value.status_code == 404


# ── update_asset_metadata ─────────────────────────────────────────

def test_update_metadata_type(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "spec.pdf").write_text("pdf-content")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "spec.pdf", "original_name": "spec.pdf"}]
    _write_plan_meta(plan_id, meta)

    updated = update_asset_metadata(plan_id, "spec.pdf", asset_type="api-spec")
    assert updated["asset_type"] == "api-spec"

    # Verify persisted
    meta = _ensure_plan_meta(plan_id)
    asset = next(a for a in meta["assets"] if a["filename"] == "spec.pdf")
    assert asset["asset_type"] == "api-spec"


def test_update_metadata_tags(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "design.png").write_text("png-content")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "design.png", "original_name": "design.png"}]
    _write_plan_meta(plan_id, meta)

    updated = update_asset_metadata(plan_id, "design.png", tags=["frontend", "v2"])
    assert updated["tags"] == ["frontend", "v2"]


def test_update_metadata_description(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "readme.md").write_text("# readme")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "readme.md", "original_name": "readme.md"}]
    _write_plan_meta(plan_id, meta)

    updated = update_asset_metadata(plan_id, "readme.md", description="Project readme")
    assert updated["description"] == "Project readme"


def test_update_metadata_all_fields(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "all.txt").write_text("content")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "all.txt", "original_name": "all.txt"}]
    _write_plan_meta(plan_id, meta)

    updated = update_asset_metadata(
        plan_id, "all.txt",
        asset_type="config",
        tags=["env", "prod"],
        description="Production config"
    )
    assert updated["asset_type"] == "config"
    assert updated["tags"] == ["env", "prod"]
    assert updated["description"] == "Production config"


def test_update_metadata_nonexistent_asset(temp_plan):
    from fastapi import HTTPException
    plan_id, tmp_path, assets_dir = temp_plan

    with pytest.raises(HTTPException) as exc:
        update_asset_metadata(plan_id, "nope.txt", asset_type="config")
    assert exc.value.status_code == 404


# ── list_epic_assets with binding field ───────────────────────────

def test_list_epic_assets_returns_binding_field(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "bound.txt").write_text("bound")
    (assets_dir / "plan_level.txt").write_text("plan")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "bound.txt", "original_name": "bound.txt"},
        {"filename": "plan_level.txt", "original_name": "plan_level.txt"},
    ]
    _write_plan_meta(plan_id, meta)

    bind_asset_to_epic(plan_id, "bound.txt", "EPIC-001")

    assets = list_epic_assets(plan_id, "EPIC-001")
    bound_asset = next(a for a in assets if a["filename"] == "bound.txt")
    plan_asset = next(a for a in assets if a["filename"] == "plan_level.txt")

    assert "EPIC-001" in bound_asset.get("bound_epics", [])
    assert plan_asset.get("bound_epics", []) == []


# ── bind idempotency ─────────────────────────────────────────────

def test_bind_idempotent(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "idem.txt").write_text("content")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "idem.txt"}]
    _write_plan_meta(plan_id, meta)

    bind_asset_to_epic(plan_id, "idem.txt", "EPIC-001")
    bind_asset_to_epic(plan_id, "idem.txt", "EPIC-001")

    meta = _ensure_plan_meta(plan_id)
    assert meta["epic_assets"]["EPIC-001"].count("idem.txt") == 1

    asset = next(a for a in meta["assets"] if a["filename"] == "idem.txt")
    assert asset["bound_epics"].count("EPIC-001") == 1


# ── upload with epic binding fields ──────────────────────────────

def test_upload_and_bind_to_epic(temp_plan):
    """Simulate uploading a file and binding it to an epic in one flow."""
    plan_id, tmp_path, assets_dir = temp_plan

    # Simulate what the upload endpoint does: save file then bind
    from dashboard.routes.plans import _safe_asset_filename

    original_name = "design-mockup.png"
    stored_name = _safe_asset_filename(original_name)
    (assets_dir / stored_name).write_bytes(b"fake-png-data")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"].append({
        "filename": stored_name,
        "original_name": original_name,
        "mime_type": "image/png",
        "size_bytes": 13,
        "asset_type": "design-mockup",
        "tags": ["ui"],
    })
    _write_plan_meta(plan_id, meta)

    bind_asset_to_epic(plan_id, stored_name, "EPIC-002")

    # Verify listing
    assets = list_epic_assets(plan_id, "EPIC-002")
    filenames = [a["filename"] for a in assets]
    assert stored_name in filenames

    # Verify metadata persisted
    meta = _ensure_plan_meta(plan_id)
    asset = next(a for a in meta["assets"] if a["filename"] == stored_name)
    assert asset["asset_type"] == "design-mockup"
    assert asset["tags"] == ["ui"]
    assert "EPIC-002" in asset["bound_epics"]


# ── error cases ──────────────────────────────────────────────────

def test_update_metadata_no_changes(temp_plan):
    """Calling update with no fields should still succeed (no-op)."""
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "noop.txt").write_text("content")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "noop.txt"}]
    _write_plan_meta(plan_id, meta)

    # Normalize first so extended fields exist
    _normalize_plan_assets(plan_id, meta)

    updated = update_asset_metadata(plan_id, "noop.txt")
    assert updated["filename"] == "noop.txt"


def test_bind_then_list_multiple_epics(temp_plan):
    """Asset bound to EPIC-001 should NOT appear in EPIC-002's exclusive list."""
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "exclusive.txt").write_text("exclusive")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "exclusive.txt"}]
    _write_plan_meta(plan_id, meta)

    bind_asset_to_epic(plan_id, "exclusive.txt", "EPIC-001")

    # EPIC-002 should NOT see exclusive.txt (it's bound to a different epic)
    assets = list_epic_assets(plan_id, "EPIC-002")
    filenames = [a["filename"] for a in assets]
    assert "exclusive.txt" not in filenames


# ── FIX-1: Epic ref validation ───────────────────────────────────

def test_get_valid_epic_refs(temp_plan):
    """Should parse EPIC-NNN refs from the plan markdown."""
    plan_id, tmp_path, assets_dir = temp_plan
    refs = _get_valid_epic_refs(plan_id)
    assert "EPIC-001" in refs
    assert "EPIC-002" in refs
    assert len(refs) == 2


def test_bind_rejects_invalid_epic_ref(temp_plan):
    """Binding to a non-existent epic should raise 404."""
    from fastapi import HTTPException
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "file.txt").write_text("content")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "file.txt"}]
    _write_plan_meta(plan_id, meta)

    with pytest.raises(HTTPException) as exc:
        bind_asset_to_epic(plan_id, "file.txt", "EPIC-999")
    assert exc.value.status_code == 404
    assert "EPIC-999" in exc.value.detail


def test_bind_accepts_valid_epic_ref(temp_plan):
    """Binding to a valid epic should succeed."""
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "valid.txt").write_text("content")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "valid.txt"}]
    _write_plan_meta(plan_id, meta)

    # EPIC-001 exists in the plan markdown — should work
    bind_asset_to_epic(plan_id, "valid.txt", "EPIC-001")
    meta = _ensure_plan_meta(plan_id)
    assert "EPIC-001" in meta["epic_assets"]


# ── FIX-2: Asset sections sync on mutations ──────────────────────

def test_bind_updates_plan_markdown(temp_plan):
    """After binding, the plan markdown should have per-epic > Assets: section."""
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "spec.yaml").write_text("openapi: 3.0")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "spec.yaml", "original_name": "spec.yaml", "mime_type": "text/yaml",
         "asset_type": "api-spec", "description": "API spec", "bound_epics": [], "tags": []},
    ]
    _write_plan_meta(plan_id, meta)

    bind_asset_to_epic(plan_id, "spec.yaml", "EPIC-001")

    content = (tmp_path / f"{plan_id}.md").read_text()
    assert "> Assets:" in content
    assert "spec.yaml" in content


def test_unbind_updates_plan_markdown(temp_plan):
    """After unbinding last epic, > Assets: section should be removed from that epic."""
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "doc.txt").write_text("content")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "doc.txt", "original_name": "doc.txt", "mime_type": "text/plain",
         "asset_type": "reference-doc", "description": "", "bound_epics": ["EPIC-001"], "tags": []},
    ]
    meta["epic_assets"] = {"EPIC-001": ["doc.txt"]}
    _write_plan_meta(plan_id, meta)

    # First write the sections
    _update_epic_asset_sections(plan_id, meta["assets"], assets_dir)

    # Now unbind
    unbind_asset_from_epic(plan_id, "doc.txt", "EPIC-001")

    content = (tmp_path / f"{plan_id}.md").read_text()
    # EPIC-001 should no longer have > Assets: with doc.txt
    epic1_pos = content.index("### EPIC-001")
    epic2_pos = content.index("### EPIC-002")
    epic1_section = content[epic1_pos:epic2_pos]
    assert "doc.txt" not in epic1_section
    assert "> Assets:" not in epic1_section


# ── R2-FIX-1: Round-trip — edits in markdown merge back into meta ─

def test_merge_markdown_edits_into_meta(temp_plan):
    """If a user edits a > Assets: section in markdown, the change should be
    picked up and merged into meta.json on save."""
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "spec.yaml").write_text("openapi: 3.0")

    # Set up initial state: spec.yaml bound to EPIC-001
    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "spec.yaml", "original_name": "spec.yaml", "mime_type": "text/yaml",
         "asset_type": "api-spec", "description": "Old desc", "bound_epics": ["EPIC-001"], "tags": []},
    ]
    meta["epic_assets"] = {"EPIC-001": ["spec.yaml"]}
    _write_plan_meta(plan_id, meta)

    # Simulate user editing the markdown to move spec.yaml to EPIC-002
    plan_file = tmp_path / f"{plan_id}.md"
    new_md = (
        "# Plan: API Test Plan\n\n## Epics\n\n"
        "### EPIC-001 — First\n\n"
        "### EPIC-002 — Second\n\n"
        "> Assets: .assets/spec.yaml (api-spec, text/yaml) — New description\n\n"
    )
    plan_file.write_text(new_md)

    _merge_markdown_asset_edits_into_meta(plan_id, new_md)

    meta = _ensure_plan_meta(plan_id)
    asset = next(a for a in meta["assets"] if a["filename"] == "spec.yaml")
    # Should now be bound to EPIC-002 (from markdown) instead of only EPIC-001
    assert "EPIC-002" in asset["bound_epics"]


def test_merge_markdown_no_assets_is_noop(temp_plan):
    """If no > Assets: sections exist, merge should not crash."""
    plan_id, tmp_path, assets_dir = temp_plan
    md = "# Plan: API Test Plan\n\n## Epics\n\n### EPIC-001 — First\n"
    _merge_markdown_asset_edits_into_meta(plan_id, md)
    # No crash = success


# ── R2-FIX-2: Broad epic header matching ─────��───────────────────

def test_get_valid_epic_refs_alternate_format(tmp_path, monkeypatch):
    """Should match '## Epic: EPIC-001' format as well as '### EPIC-001'."""
    monkeypatch.setattr("dashboard.routes.plans.PLANS_DIR", tmp_path)
    monkeypatch.setattr("dashboard.routes.plans.GLOBAL_PLANS_DIR", tmp_path)
    plan_id = "alt-fmt"
    plan_file = tmp_path / f"{plan_id}.md"
    plan_file.write_text(
        "# Plan: Alt\n\n"
        "## Epic: EPIC-100 — One\n\n"
        "## Task: EPIC-200 — Two\n\n"
        "### EPIC-300 — Three\n\n"
    )
    refs = _get_valid_epic_refs(plan_id)
    assert "EPIC-100" in refs
    assert "EPIC-200" in refs
    assert "EPIC-300" in refs


# ── R2-FIX-3: list_epic_assets rejects unknown refs ─────────────

def test_list_epic_assets_unknown_ref_raises_404(temp_plan):
    """Listing assets for a non-existent epic should raise 404."""
    from fastapi import HTTPException
    plan_id, tmp_path, assets_dir = temp_plan

    with pytest.raises(HTTPException) as exc:
        list_epic_assets(plan_id, "EPIC-FAKE")
    assert exc.value.status_code == 404


# ── R2-FIX-4: Re-upload replaces instead of accumulating ────────

def test_reupload_replaces_existing_asset(temp_plan):
    """Uploading a file with the same original_name should replace the old one."""
    from dashboard.routes.plans import _safe_asset_filename
    plan_id, tmp_path, assets_dir = temp_plan

    # First upload
    stored_v1 = _safe_asset_filename("readme.md")
    (assets_dir / stored_v1).write_text("version 1")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": stored_v1, "original_name": "readme.md", "mime_type": "text/markdown",
         "size_bytes": 9, "asset_type": "reference-doc", "description": "", "bound_epics": ["EPIC-001"], "tags": []},
    ]
    meta["epic_assets"] = {"EPIC-001": [stored_v1]}
    _write_plan_meta(plan_id, meta)

    # Second upload with same original_name
    stored_v2 = _safe_asset_filename("readme.md")
    (assets_dir / stored_v2).write_text("version 2")

    from dashboard.routes.plans import _replace_existing_assets
    existing = _normalize_plan_assets(plan_id, _ensure_plan_meta(plan_id))
    new_assets = [
        {"filename": stored_v2, "original_name": "readme.md", "mime_type": "text/markdown",
         "size_bytes": 9, "bound_epics": [], "asset_type": "unspecified", "tags": [], "description": ""},
    ]
    cleaned = _replace_existing_assets(plan_id, existing, new_assets)

    # Old asset should be removed, only new one remains
    names = [a["original_name"] for a in cleaned + new_assets]
    assert names.count("readme.md") == 1
    # Old stored file should be deleted
    assert not (assets_dir / stored_v1).exists()
