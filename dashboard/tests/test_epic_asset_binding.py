import json
import pytest
from fastapi import HTTPException
from dashboard.routes.plans import (
    _ensure_plan_meta, _normalize_plan_assets, _write_plan_meta,
    bind_asset_to_epic, unbind_asset_from_epic, list_epic_assets,
    _safe_asset_filename, _serialize_plan_asset
)


def test_safe_asset_filename():
    name = "my file (v1).txt"
    safe = _safe_asset_filename(name)
    assert "my-file-v1" in safe
    assert safe.endswith(".txt")
    # Should be unique even with same name due to timestamp/fingerprint
    safe2 = _safe_asset_filename(name)
    assert safe != safe2


def test_serialize_plan_asset(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    asset = {
        "filename": "test.txt",
        "original_name": "test.txt"
    }
    serialized = _serialize_plan_asset(plan_id, asset)
    assert serialized["plan_id"] == plan_id
    assert "path" in serialized
    assert serialized["path"].endswith("test.txt")


@pytest.fixture
def temp_plan(tmp_path, monkeypatch):
    # Mock PLANS_DIR to use tmp_path
    monkeypatch.setattr("dashboard.routes.plans.PLANS_DIR", tmp_path)
    plan_id = "test-plan"
    plan_file = tmp_path / f"{plan_id}.md"
    plan_file.write_text(
        "# Plan: Test Plan\n\n## Epics\n\n"
        "### EPIC-001 — First\n\n"
        "### EPIC-002 — Second\n\n"
        "### EPIC-101 — Extra A\n\n"
        "### EPIC-202 — Extra B\n\n"
        "### EPIC-303 — Extra C\n\n"
        "### EPIC-777 — Extra D\n\n"
        "### EPIC-999 — Extra E\n\n"
        "## Assets\n"
    )

    # Create assets directory
    assets_dir = tmp_path / "assets" / plan_id
    assets_dir.mkdir(parents=True)

    return plan_id, tmp_path, assets_dir


def test_legacy_migration(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan

    # Create legacy meta.json without new fields
    meta = {
        "plan_id": plan_id,
        "title": "Test Plan",
        "assets": [
            {"filename": "legacy.txt"}
        ]
    }
    # Create the asset file
    (assets_dir / "legacy.txt").write_text("hello")

    meta_path = tmp_path / f"{plan_id}.meta.json"
    meta_path.write_text(json.dumps(meta))

    # Trigger normalization
    loaded_meta = _ensure_plan_meta(plan_id)
    normalized = _normalize_plan_assets(plan_id, loaded_meta)

    # Verify migration
    assert loaded_meta["epic_assets"] == {}
    assert len(normalized) == 1
    asset = normalized[0]
    assert asset["filename"] == "legacy.txt"
    assert asset["bound_epics"] == []
    assert asset["asset_type"] == "unspecified"
    assert asset["tags"] == []
    assert asset["description"] == ""


def test_bind_unbind_asset(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "asset1.txt").write_text("content")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "asset1.txt"}]
    _write_plan_meta(plan_id, meta)

    # Bind
    bind_asset_to_epic(plan_id, "asset1.txt", "EPIC-101")

    meta = _ensure_plan_meta(plan_id)
    assert "EPIC-101" in meta["epic_assets"]
    assert "asset1.txt" in meta["epic_assets"]["EPIC-101"]

    asset = next(a for a in meta["assets"] if a["filename"] == "asset1.txt")
    assert "EPIC-101" in asset["bound_epics"]

    # Unbind
    unbind_asset_from_epic(plan_id, "asset1.txt", "EPIC-101")

    meta = _ensure_plan_meta(plan_id)
    assert "EPIC-101" not in meta["epic_assets"]

    asset = next(a for a in meta["assets"] if a["filename"] == "asset1.txt")
    assert "EPIC-101" not in asset["bound_epics"]


def test_list_epic_assets(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "bound.txt").write_text("bound")
    (assets_dir / "plan_level.txt").write_text("plan_level")
    (assets_dir / "other_epic.txt").write_text("other")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": "bound.txt"},
        {"filename": "plan_level.txt"},
        {"filename": "other_epic.txt"}
    ]
    _write_plan_meta(plan_id, meta)

    bind_asset_to_epic(plan_id, "bound.txt", "EPIC-101")
    bind_asset_to_epic(plan_id, "other_epic.txt", "EPIC-202")

    # List assets for EPIC-101
    # Should include bound.txt (bound to EPIC-101) and plan_level.txt
    # (not bound to any)
    # Should NOT include other_epic.txt (bound to EPIC-202)
    assets = list_epic_assets(plan_id, "EPIC-101")
    filenames = [a["filename"] for a in assets]

    assert "bound.txt" in filenames
    assert "plan_level.txt" in filenames
    assert "other_epic.txt" not in filenames
    assert len(filenames) == 2


def test_bind_non_existent_asset(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    # Note: the code doesn't strictly check if the file exists when binding,
    # but _normalize_plan_assets (called during list) would remove it.
    bind_asset_to_epic(plan_id, "ghost.txt", "EPIC-999")
    meta = _ensure_plan_meta(plan_id)
    assert "ghost.txt" in meta["epic_assets"]["EPIC-999"]


def test_unbind_non_existent(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    # Should not raise
    unbind_asset_from_epic(plan_id, "nothing.txt", "EPIC-000")
    unbind_asset_from_epic(plan_id, "nothing.txt", "NON_EXISTENT_EPIC")


def test_list_epic_assets_no_bound(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "plan_only.txt").write_text("plan_only")
    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "plan_only.txt"}]
    _write_plan_meta(plan_id, meta)

    # EPIC-303 has no bound assets, should return plan_only.txt
    assets = list_epic_assets(plan_id, "EPIC-303")
    assert len(assets) == 1
    assert assets[0]["filename"] == "plan_only.txt"


def test_ensure_plan_meta_new(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    # Delete meta if it exists (though temp_plan only creates .md)
    meta_path = tmp_path / f"{plan_id}.meta.json"
    if meta_path.exists():
        meta_path.unlink()

    meta = _ensure_plan_meta(plan_id)
    assert meta["plan_id"] == plan_id
    assert meta["assets"] == []
    assert meta["epic_assets"] == {}
    assert meta_path.exists()


def test_normalize_missing_filename_or_file(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [
        {"filename": ""},  # Missing filename
        {"filename": "missing.txt"}  # File doesn't exist on disk
    ]
    _write_plan_meta(plan_id, meta)

    normalized = _normalize_plan_assets(plan_id, meta)
    assert len(normalized) == 0


def test_sync_index_from_bound_epics(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "synced.txt").write_text("synced")
    
    meta = {
        "plan_id": plan_id,
        "title": "Test Plan",
        "assets": [
            {"filename": "synced.txt", "bound_epics": ["EPIC-777"]}
        ],
        "epic_assets": {} # Empty index
    }
    _write_plan_meta(plan_id, meta)
    
    # Trigger normalization
    loaded_meta = _ensure_plan_meta(plan_id)
    normalized = _normalize_plan_assets(plan_id, loaded_meta)
    
    # Verify index was rebuilt
    assert "EPIC-777" in loaded_meta["epic_assets"]
    assert "synced.txt" in loaded_meta["epic_assets"]["EPIC-777"]
    assert len(normalized) == 1


def test_normalize_partial_asset(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "partial.txt").write_text("content")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "partial.txt"}]
    _write_plan_meta(plan_id, meta)

    normalized = _normalize_plan_assets(plan_id, meta)
    assert len(normalized) == 1
    asset = normalized[0]
    assert "original_name" in asset
    assert "mime_type" in asset
    assert "size_bytes" in asset
    assert asset["bound_epics"] == []


def test_list_epic_assets_duplicates(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "dupe.txt").write_text("dupe")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "dupe.txt"}]
    _write_plan_meta(plan_id, meta)

    # Manually inject duplicate in epic_assets
    meta = _ensure_plan_meta(plan_id)
    meta["epic_assets"] = {"EPIC-DUPE": ["dupe.txt", "dupe.txt"]}
    _write_plan_meta(plan_id, meta)

    # EPIC-DUPE is not in the plan, so skip validation for this low-level test
    assets = list_epic_assets(plan_id, "EPIC-DUPE", validate=False)
    assert len(assets) == 1
    assert assets[0]["filename"] == "dupe.txt"


def test_read_plan_meta_error(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    meta_path = tmp_path / f"{plan_id}.meta.json"
    meta_path.write_text("invalid json")

    from dashboard.routes.plans import _read_plan_meta
    meta = _read_plan_meta(plan_id)
    assert meta == {}


def test_bind_asset_not_in_assets(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "untracked.txt").write_text("untracked")

    # Bind an asset that exists on disk but is not in meta["assets"]
    bind_asset_to_epic(plan_id, "untracked.txt", "EPIC-777")

    meta = _ensure_plan_meta(plan_id)
    assert "untracked.txt" in meta["epic_assets"]["EPIC-777"]
    # Since it's not in meta["assets"], bound_epics won't be updated there
    # but list_epic_assets should still NOT return it because it's not
    # in assets
    assets = list_epic_assets(plan_id, "EPIC-777")
    assert len(assets) == 0


def test_normalize_plan_assets_changed(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "file.txt").write_text("content")

    meta = _ensure_plan_meta(plan_id)
    # asset without extended metadata
    meta["assets"] = [{"filename": "file.txt"}]
    _write_plan_meta(plan_id, meta)

    # First call should normalize and write to disk
    normalized = _normalize_plan_assets(plan_id, meta)
    assert normalized[0]["asset_type"] == "unspecified"

    # Verify it was written
    loaded = _ensure_plan_meta(plan_id)
    assert loaded["assets"][0]["asset_type"] == "unspecified"


def test_bind_asset_multiple_epics(temp_plan):
    plan_id, tmp_path, assets_dir = temp_plan
    (assets_dir / "multi.txt").write_text("content")

    meta = _ensure_plan_meta(plan_id)
    meta["assets"] = [{"filename": "multi.txt"}]
    _write_plan_meta(plan_id, meta)

    bind_asset_to_epic(plan_id, "multi.txt", "EPIC-001")
    bind_asset_to_epic(plan_id, "multi.txt", "EPIC-002")

    meta = _ensure_plan_meta(plan_id)
    assert "multi.txt" in meta["epic_assets"]["EPIC-001"]
    assert "multi.txt" in meta["epic_assets"]["EPIC-002"]

    asset = next(a for a in meta["assets"] if a["filename"] == "multi.txt")
    assert "EPIC-001" in asset["bound_epics"]
    assert "EPIC-002" in asset["bound_epics"]

    # Listing for EPIC-001
    assets1 = list_epic_assets(plan_id, "EPIC-001")
    assert any(a["filename"] == "multi.txt" for a in assets1)

    # Listing for EPIC-002
    assets2 = list_epic_assets(plan_id, "EPIC-002")
    assert any(a["filename"] == "multi.txt" for a in assets2)

    # Unbind from one
    unbind_asset_from_epic(plan_id, "multi.txt", "EPIC-001")
    meta = _ensure_plan_meta(plan_id)
    assert "EPIC-001" not in meta["epic_assets"]
    assert "multi.txt" in meta["epic_assets"]["EPIC-002"]

    asset = next(a for a in meta["assets"] if a["filename"] == "multi.txt")
    assert "EPIC-001" not in asset["bound_epics"]
    assert "EPIC-002" in asset["bound_epics"]


def test_require_plan_file_missing(temp_plan):
    from dashboard.routes.plans import _require_plan_file
    with pytest.raises(HTTPException) as exc:
        _require_plan_file("non-existent-plan")
    assert exc.value.status_code == 404


def test_update_plan_assets_section(temp_plan):
    from dashboard.routes.plans import _update_plan_assets_section
    plan_id, tmp_path, assets_dir = temp_plan
    plan_file = tmp_path / f"{plan_id}.md"

    all_assets = [
        {"filename": "asset1.txt", "original_name": "asset1.txt", "mime_type": "text/plain"}
    ]

    # Test initial insertion
    _update_plan_assets_section(plan_id, all_assets, assets_dir)
    content = plan_file.read_text()
    assert "## Assets" in content
    assert "path: `.assets/asset1.txt`" in content

    # Test replacement
    all_assets.append({"filename": "asset2.txt", "original_name": "asset2.txt", "mime_type": "text/plain"})
    _update_plan_assets_section(plan_id, all_assets, assets_dir)
    content = plan_file.read_text()
    assert "asset2.txt" in content
    # Should only have one Assets section
    assert content.count("## Assets") == 1


def test_update_plan_assets_section_insert_before(temp_plan):
    from dashboard.routes.plans import _update_plan_assets_section
    plan_id, tmp_path, assets_dir = temp_plan
    plan_file = tmp_path / f"{plan_id}.md"
    plan_file.write_text("# Plan: Test\n\n## Next Section\n")

    all_assets = [{"filename": "asset.txt"}]
    _update_plan_assets_section(plan_id, all_assets, assets_dir)
    content = plan_file.read_text()
    # Should insert Assets BEFORE Next Section
    assert content.index("## Assets") < content.index("## Next Section")


def test_update_plan_assets_section_no_sections(temp_plan):
    from dashboard.routes.plans import _update_plan_assets_section
    plan_id, tmp_path, assets_dir = temp_plan
    plan_file = tmp_path / f"{plan_id}.md"
    plan_file.write_text("# Plan: Test\n")

    all_assets = [{"filename": "asset.txt"}]
    _update_plan_assets_section(plan_id, all_assets, assets_dir)
    content = plan_file.read_text()
    assert "## Assets" in content


def test_update_plan_assets_section_missing_plan(temp_plan):
    from dashboard.routes.plans import _update_plan_assets_section
    plan_id, tmp_path, assets_dir = temp_plan
    # Should return early without error
    _update_plan_assets_section("non-existent", [], assets_dir)
