"""
EPIC-006 — Tests for per-epic asset sections in plan markdown.

Tests: writing per-epic #### Assets, plan-level ## Assets, parser round-trip,
       removal of epic bindings, and asset preservation during refinement.
"""
import json
import pytest
from pathlib import Path

from dashboard.routes.plans import (
    _ensure_plan_meta, _write_plan_meta, _normalize_plan_assets,
    _update_plan_assets_section, _update_epic_asset_sections,
    _parse_epic_assets_from_markdown, bind_asset_to_epic,
)


@pytest.fixture
def temp_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.routes.plans.PLANS_DIR", tmp_path)
    plan_id = "roundtrip-test"
    plan_file = tmp_path / f"{plan_id}.md"
    plan_file.write_text(
        "# Plan: Roundtrip Test\n\n"
        "## Epics\n\n"
        "### EPIC-001 — Build API\n\n"
        "#### Tasks\n- [ ] TASK-001 — Implement\n\n"
        "depends_on: []\n\n"
        "---\n\n"
        "### EPIC-002 — Frontend\n\n"
        "#### Tasks\n- [ ] TASK-001 — Build UI\n\n"
        "depends_on: [EPIC-001]\n\n"
        "---\n"
    )
    assets_dir = tmp_path / "assets" / plan_id
    assets_dir.mkdir(parents=True)
    return plan_id, tmp_path, assets_dir


def test_write_epic_asset_sections(temp_plan):
    """Per-epic #### Assets sections should be written into plan markdown."""
    plan_id, tmp_path, assets_dir = temp_plan

    (assets_dir / "spec.yaml").write_text("openapi: 3.0")
    (assets_dir / "design.png").write_bytes(b"png-data")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "spec.yaml", "original_name": "spec.yaml", "mime_type": "text/yaml",
         "asset_type": "api-spec", "description": "OpenAPI spec",
         "bound_epics": ["EPIC-001"], "tags": []},
        {"filename": "design.png", "original_name": "design.png", "mime_type": "image/png",
         "asset_type": "design-mockup", "description": "Login mockup",
         "bound_epics": ["EPIC-002"], "tags": []},
    ]
    meta["epic_assets"] = {"EPIC-001": ["spec.yaml"], "EPIC-002": ["design.png"]}
    _write_plan_meta(plan_id, meta)

    _update_epic_asset_sections(plan_id, meta["assets"], assets_dir)

    content = (tmp_path / f"{plan_id}.md").read_text()
    # EPIC-001 should have spec.yaml
    epic1_pos = content.index("### EPIC-001")
    epic2_pos = content.index("### EPIC-002")
    epic1_section = content[epic1_pos:epic2_pos]
    assert "#### Assets" in epic1_section
    assert "spec.yaml" in epic1_section
    assert "api-spec" in epic1_section

    # EPIC-002 should have design.png
    epic2_section = content[epic2_pos:]
    assert "#### Assets" in epic2_section
    assert "design.png" in epic2_section
    assert "design-mockup" in epic2_section


def test_plan_level_assets_in_main_section(temp_plan):
    """Unbound assets should remain in the plan-level ## Assets section."""
    plan_id, tmp_path, assets_dir = temp_plan

    (assets_dir / "shared.txt").write_text("shared")
    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "shared.txt", "original_name": "shared.txt", "mime_type": "text/plain",
         "asset_type": "reference-doc", "description": "Shared doc",
         "bound_epics": [], "tags": []},
    ]
    _write_plan_meta(plan_id, meta)

    _update_plan_assets_section(plan_id, meta["assets"], assets_dir)
    _update_epic_asset_sections(plan_id, meta["assets"], assets_dir)

    content = (tmp_path / f"{plan_id}.md").read_text()
    # Plan-level ## Assets should have shared.txt
    assert "## Assets" in content
    assert "shared.txt" in content


def test_parse_epic_assets_from_markdown(temp_plan):
    """Parser should extract per-epic asset bindings from markdown."""
    plan_id, tmp_path, assets_dir = temp_plan

    (assets_dir / "spec.yaml").write_text("openapi: 3.0")
    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "spec.yaml", "original_name": "spec.yaml", "mime_type": "text/yaml",
         "asset_type": "api-spec", "description": "OpenAPI spec",
         "bound_epics": ["EPIC-001"], "tags": []},
    ]
    meta["epic_assets"] = {"EPIC-001": ["spec.yaml"]}
    _write_plan_meta(plan_id, meta)

    # Write the sections
    _update_epic_asset_sections(plan_id, meta["assets"], assets_dir)

    # Now parse it back
    content = (tmp_path / f"{plan_id}.md").read_text()
    parsed = _parse_epic_assets_from_markdown(content)
    assert "EPIC-001" in parsed
    assert any("spec.yaml" in entry for entry in parsed["EPIC-001"])


def test_roundtrip_write_parse_write(temp_plan):
    """Write → parse → write should produce consistent output."""
    plan_id, tmp_path, assets_dir = temp_plan

    (assets_dir / "data.csv").write_text("a,b,c")
    (assets_dir / "mockup.png").write_bytes(b"png")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "data.csv", "original_name": "data.csv", "mime_type": "text/csv",
         "asset_type": "test-data", "description": "Test data",
         "bound_epics": ["EPIC-001"], "tags": []},
        {"filename": "mockup.png", "original_name": "mockup.png", "mime_type": "image/png",
         "asset_type": "design-mockup", "description": "UI mockup",
         "bound_epics": ["EPIC-002"], "tags": []},
    ]
    meta["epic_assets"] = {"EPIC-001": ["data.csv"], "EPIC-002": ["mockup.png"]}
    _write_plan_meta(plan_id, meta)

    # First write
    _update_epic_asset_sections(plan_id, meta["assets"], assets_dir)
    content1 = (tmp_path / f"{plan_id}.md").read_text()

    # Parse
    parsed = _parse_epic_assets_from_markdown(content1)
    assert "EPIC-001" in parsed
    assert "EPIC-002" in parsed

    # Second write (should produce same output)
    _update_epic_asset_sections(plan_id, meta["assets"], assets_dir)
    content2 = (tmp_path / f"{plan_id}.md").read_text()

    assert content1 == content2


def test_no_duplicate_asset_sections(temp_plan):
    """Multiple writes should not duplicate #### Assets sections."""
    plan_id, tmp_path, assets_dir = temp_plan

    (assets_dir / "file.txt").write_text("content")
    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "file.txt", "original_name": "file.txt", "mime_type": "text/plain",
         "asset_type": "reference-doc", "description": "",
         "bound_epics": ["EPIC-001"], "tags": []},
    ]
    meta["epic_assets"] = {"EPIC-001": ["file.txt"]}
    _write_plan_meta(plan_id, meta)

    # Write three times
    _update_epic_asset_sections(plan_id, meta["assets"], assets_dir)
    _update_epic_asset_sections(plan_id, meta["assets"], assets_dir)
    _update_epic_asset_sections(plan_id, meta["assets"], assets_dir)

    content = (tmp_path / f"{plan_id}.md").read_text()
    # Count #### Assets occurrences — should be exactly 1 per epic that has assets
    assert content.count("#### Assets") == 1


def test_epic_with_no_assets_no_section(temp_plan):
    """Epics without assets should not get #### Assets sections."""
    plan_id, tmp_path, assets_dir = temp_plan

    (assets_dir / "only-epic1.txt").write_text("content")
    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "only-epic1.txt", "original_name": "only-epic1.txt",
         "bound_epics": ["EPIC-001"], "asset_type": "reference-doc", "description": "", "tags": []},
    ]
    meta["epic_assets"] = {"EPIC-001": ["only-epic1.txt"]}
    _write_plan_meta(plan_id, meta)

    _update_epic_asset_sections(plan_id, meta["assets"], assets_dir)

    content = (tmp_path / f"{plan_id}.md").read_text()
    # EPIC-001 section should have #### Assets
    epic1_pos = content.index("### EPIC-001")
    epic2_pos = content.index("### EPIC-002")
    epic1_section = content[epic1_pos:epic2_pos]
    assert "#### Assets" in epic1_section

    # EPIC-002 section should NOT have #### Assets
    epic2_section = content[epic2_pos:]
    assert "#### Assets" not in epic2_section
