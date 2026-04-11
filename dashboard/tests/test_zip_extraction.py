"""
Tests for ZIP file extraction and batch upload functionality.

Tests: ZIP extraction, file filtering, metadata preservation, error handling.
"""
import pytest
import zipfile
import io
from pathlib import Path
from unittest.mock import patch

from dashboard.routes.plans import (
    _ensure_plan_meta, _write_plan_meta, _normalize_plan_assets,
    _extract_files_from_zip, _plan_assets_dir,
)


@pytest.fixture
def temp_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.routes.plans.PLANS_DIR", tmp_path)
    plan_id = "zip-test-plan"
    plan_file = tmp_path / f"{plan_id}.md"
    plan_file.write_text("# Plan: ZIP Test\n\n### EPIC-001 — Test\n")
    assets_dir = tmp_path / "assets" / plan_id
    assets_dir.mkdir(parents=True)
    return plan_id, tmp_path, assets_dir


def create_zip_file(files: dict) -> bytes:
    """Create a ZIP file in memory with the given files.
    
    Args:
        files: Dict of {filename: content_bytes}
    
    Returns:
        ZIP file as bytes
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    return zip_buffer.getvalue()


def test_extract_simple_zip(temp_plan):
    """ZIP with 3 images should extract all 3 as separate assets."""
    plan_id, tmp_path, assets_dir = temp_plan
    
    # Create ZIP with 3 images
    files = {
        "image1.png": b"fake-png-data-1",
        "image2.png": b"fake-png-data-2",
        "image3.jpg": b"fake-jpg-data",
    }
    zip_data = create_zip_file(files)
    
    extracted = _extract_files_from_zip(
        zip_data=zip_data,
        original_zip_name="images.zip",
        epic_ref="EPIC-001",
        asset_type="design-mockup",
        tags=["batch"],
    )
    
    assert len(extracted) == 3
    assert extracted[0]["original_name"] == "image1.png"
    assert extracted[0]["mime_type"] == "image/png"
    assert extracted[0]["asset_type"] == "design-mockup"
    assert extracted[0]["tags"] == ["batch"]
    assert extracted[0]["bound_epics"] == ["EPIC-001"]
    assert extracted[0]["data"] == b"fake-png-data-1"


def test_extract_zip_with_nested_directories(temp_plan):
    """ZIP with nested directories should extract files from subdirs."""
    plan_id, tmp_path, assets_dir = temp_plan
    
    # Create ZIP with nested structure
    files = {
        "designs/mockup1.png": b"mockup-1",
        "designs/mockup2.png": b"mockup-2",
        "specs/api.yaml": b"openapi: 3.0",
        "root.txt": b"root-file",
    }
    zip_data = create_zip_file(files)
    
    extracted = _extract_files_from_zip(zip_data, "nested.zip")
    
    assert len(extracted) == 4
    names = [e["original_name"] for e in extracted]
    assert "mockup1.png" in names
    assert "mockup2.png" in names
    assert "api.yaml" in names
    assert "root.txt" in names


def test_extract_zip_skips_hidden_files(temp_plan):
    """ZIP with hidden files and macOS metadata should skip them."""
    plan_id, tmp_path, assets_dir = temp_plan
    
    files = {
        "visible.txt": b"visible-content",
        ".hidden": b"hidden-content",
        "__MACOSX/._visible.txt": b"macos-metadata",
        "normal.pdf": b"pdf-content",
    }
    zip_data = create_zip_file(files)
    
    extracted = _extract_files_from_zip(zip_data, "mixed.zip")
    
    # Should only extract visible.txt and normal.pdf
    assert len(extracted) == 2
    names = [e["original_name"] for e in extracted]
    assert "visible.txt" in names
    assert "normal.pdf" in names
    assert ".hidden" not in names


def test_extract_zip_skips_empty_files(temp_plan):
    """ZIP with empty files should skip them."""
    plan_id, tmp_path, assets_dir = temp_plan
    
    files = {
        "nonempty.txt": b"content",
        "empty.txt": b"",
        "another.txt": b"more-content",
    }
    zip_data = create_zip_file(files)
    
    extracted = _extract_files_from_zip(zip_data, "with-empty.zip")
    
    assert len(extracted) == 2
    names = [e["original_name"] for e in extracted]
    assert "nonempty.txt" in names
    assert "another.txt" in names
    assert "empty.txt" not in names


def test_extract_zip_infers_asset_types(temp_plan):
    """ZIP extraction should infer asset types from filenames/MIME."""
    plan_id, tmp_path, assets_dir = temp_plan
    
    files = {
        "design.png": b"png-data",
        "api-spec.yaml": b"openapi: 3.0",
        "config.json": b'{"key": "value"}',
        "data.csv": b"a,b,c",
        "readme.pdf": b"pdf-data",
    }
    zip_data = create_zip_file(files)
    
    extracted = _extract_files_from_zip(zip_data, "mixed-types.zip", asset_type="unspecified")
    
    assert len(extracted) == 5
    
    # Check inferred types
    types = {e["original_name"]: e["asset_type"] for e in extracted}
    assert types["design.png"] == "design-mockup"
    assert types["api-spec.yaml"] == "api-spec"
    assert types["config.json"] == "config"
    assert types["data.csv"] == "test-data"
    assert types["readme.pdf"] == "reference-doc"


def test_extract_zip_50_images(temp_plan):
    """ZIP with 50 images should extract all 50."""
    plan_id, tmp_path, assets_dir = temp_plan
    
    # Create ZIP with 50 images
    files = {f"image{i:03d}.png": f"image-data-{i}".encode() for i in range(1, 51)}
    zip_data = create_zip_file(files)
    
    extracted = _extract_files_from_zip(
        zip_data,
        "50-images.zip",
        epic_ref="EPIC-001",
        asset_type="design-mockup",
    )
    
    assert len(extracted) == 50
    # Check first and last
    assert extracted[0]["original_name"] == "image001.png"
    assert extracted[-1]["original_name"] == "image050.png"
    # All should be bound to EPIC-001
    assert all(e["bound_epics"] == ["EPIC-001"] for e in extracted)


def test_extract_invalid_zip(temp_plan):
    """Invalid ZIP data should return empty list and log error."""
    plan_id, tmp_path, assets_dir = temp_plan
    
    # Not a valid ZIP
    invalid_data = b"this is not a zip file"
    
    extracted = _extract_files_from_zip(invalid_data, "invalid.zip")
    
    assert extracted == []


def test_extract_empty_zip(temp_plan):
    """Empty ZIP should return empty list."""
    plan_id, tmp_path, assets_dir = temp_plan
    
    # Create empty ZIP
    zip_data = create_zip_file({})
    
    extracted = _extract_files_from_zip(zip_data, "empty.zip")
    
    assert extracted == []


def test_extract_zip_with_directories_only(temp_plan):
    """ZIP with only directories (no files) should return empty list."""
    plan_id, tmp_path, assets_dir = temp_plan
    
    # Create ZIP with directory entries only
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        zf.writestr("dir1/", b"")  # Directory entry
        zf.writestr("dir2/", b"")  # Directory entry
    zip_data = zip_buffer.getvalue()
    
    extracted = _extract_files_from_zip(zip_data, "dirs-only.zip")
    
    assert extracted == []


def test_extract_zip_preserves_tags_and_binding(temp_plan):
    """ZIP extraction should preserve tags and epic binding for all files."""
    plan_id, tmp_path, assets_dir = temp_plan
    
    files = {
        "file1.txt": b"content1",
        "file2.txt": b"content2",
    }
    zip_data = create_zip_file(files)
    
    extracted = _extract_files_from_zip(
        zip_data,
        "test.zip",
        epic_ref="EPIC-002",
        tags=["important", "v2"],
    )
    
    assert len(extracted) == 2
    for e in extracted:
        assert e["bound_epics"] == ["EPIC-002"]
        assert e["tags"] == ["important", "v2"]


def test_extract_zip_size_calculation(temp_plan):
    """ZIP extraction should correctly calculate file sizes."""
    plan_id, tmp_path, assets_dir = temp_plan
    
    content1 = b"x" * 100
    content2 = b"y" * 250
    files = {
        "small.txt": content1,
        "large.txt": content2,
    }
    zip_data = create_zip_file(files)
    
    extracted = _extract_files_from_zip(zip_data, "sizes.zip")
    
    assert len(extracted) == 2
    sizes = {e["original_name"]: e["size_bytes"] for e in extracted}
    assert sizes["small.txt"] == 100
    assert sizes["large.txt"] == 250
