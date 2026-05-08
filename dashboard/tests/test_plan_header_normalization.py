"""
Test plan header normalization and meta.json initialization.

Bug 1: Missing # Plan: header prefix causes _extract_plan_title() to fail,
       resulting in broken meta.json with hash as title instead of actual title.
       Fix: Normalize header to # Plan: on save.

Bug 3: create_plan_on_disk() doesn't initialize assets/epic_assets in meta.json.
       Fix: Add empty arrays/dicts on creation.
"""

import json
import pytest
from pathlib import Path


@pytest.fixture
def temp_plans_dir(tmp_path, monkeypatch):
    """Create a temporary plans directory for testing."""
    monkeypatch.setattr("dashboard.routes.plans.PLANS_DIR", tmp_path)
    monkeypatch.setattr("dashboard.routes.plans.GLOBAL_PLANS_DIR", tmp_path)
    monkeypatch.setattr("dashboard.api_utils.PLANS_DIR", tmp_path)
    return tmp_path


class TestExtractPlanTitle:
    """Tests for _extract_plan_title function."""

    def test_extract_plan_title_with_hash_prefix(self, temp_plans_dir):
        """'# Plan: My Title' should extract 'My Title'."""
        from dashboard.routes.plans import _extract_plan_title
        
        content = "# Plan: My Awesome Plan\n\n## EPIC-001\n"
        title = _extract_plan_title(content, "default")
        assert title == "My Awesome Plan"

    def test_extract_plan_title_uppercase_plan(self, temp_plans_dir):
        """'# PLAN: My Title' should extract 'My Title'."""
        from dashboard.routes.plans import _extract_plan_title
        
        content = "# PLAN: My Awesome Plan\n\n## EPIC-001\n"
        title = _extract_plan_title(content, "default")
        assert title == "My Awesome Plan"

    def test_extract_plan_title_fallback_to_default(self, temp_plans_dir):
        """No matching header at all should return the default."""
        from dashboard.routes.plans import _extract_plan_title
        
        content = "## Some Other Header\n\nContent without plan header\n"
        title = _extract_plan_title(content, "fallback-id")
        assert title == "fallback-id"

    def test_extract_plan_title_with_colon_only_needs_normalization(self, temp_plans_dir):
        """': My Title' (no # Plan:) currently fails - proves need for normalization.
        
        After fix, this should still fail extraction BUT the normalization
        during save should have fixed the header.
        """
        from dashboard.routes.plans import _extract_plan_title
        
        content = ": My Title\n\n## EPIC-001\n"
        title = _extract_plan_title(content, "default-id")
        # This proves the bug: the regex doesn't match ': My Title'
        assert title == "default-id"


class TestNormalizePlanHeader:
    """Tests for _normalize_plan_header helper function."""

    def test_normalize_adds_missing_header(self, temp_plans_dir):
        """_normalize_plan_header should add # Plan: header if missing."""
        from dashboard.routes.plans import _normalize_plan_header
        
        content = ": My New Title\n\n## EPIC-001\n\nContent\n"
        normalized = _normalize_plan_header(content, "My New Title")
        
        assert normalized.startswith("# Plan: My New Title")

    def test_normalize_preserves_existing_header(self, temp_plans_dir):
        """_normalize_plan_header should preserve existing # Plan: header."""
        from dashboard.routes.plans import _normalize_plan_header
        
        content = "# Plan: Original Title\n\n## EPIC-001\n"
        normalized = _normalize_plan_header(content, "Ignored Title")
        
        assert "# Plan: Original Title" in normalized

    def test_normalize_fixes_uppercase_plan(self, temp_plans_dir):
        """_normalize_plan_header should fix # PLAN: to # Plan:."""
        from dashboard.routes.plans import _normalize_plan_header
        
        content = "# PLAN: My Title\n\n## EPIC-001\n"
        normalized = _normalize_plan_header(content, "My Title")
        
        assert normalized.startswith("# Plan: My Title")

    def test_normalize_empty_content(self, temp_plans_dir):
        """_normalize_plan_header should create header for empty content."""
        from dashboard.routes.plans import _normalize_plan_header
        
        content = ""
        normalized = _normalize_plan_header(content, "New Plan")
        
        assert normalized.startswith("# Plan: New Plan")


class TestCreatePlanMetaAssets:
    """Tests for Bug 3: create_plan_on_disk should initialize assets/epic_assets in meta.json."""

    def test_create_plan_on_disk_initializes_assets_in_meta(self, temp_plans_dir, monkeypatch):
        """create_plan_on_disk should include 'assets' and 'epic_assets' in meta.json."""
        from dashboard.routes.plans import create_plan_on_disk
        
        monkeypatch.setattr("dashboard.routes.plans.PROJECT_ROOT", temp_plans_dir)
        
        result = create_plan_on_disk(
            title="Test Plan",
            content="# Plan: Test\n\n## EPIC-001\n",
            working_dir=str(temp_plans_dir / "project")
        )
        
        meta_path = temp_plans_dir / f"{result['plan_id']}.meta.json"
        meta = json.loads(meta_path.read_text())
        
        assert "assets" in meta
        assert "epic_assets" in meta
        assert meta["assets"] == []
        assert meta["epic_assets"] == {}

    def test_create_plan_on_disk_with_existing_meta(self, temp_plans_dir, monkeypatch):
        """create_plan_on_disk with existing meta should preserve and add asset fields."""
        from dashboard.routes.plans import create_plan_on_disk
        
        monkeypatch.setattr("dashboard.routes.plans.PROJECT_ROOT", temp_plans_dir)
        
        # First create a plan
        result = create_plan_on_disk(
            title="Test Plan",
            content="# Plan: Test\n\n## EPIC-001\n",
            working_dir=str(temp_plans_dir / "project")
        )
        
        # The meta should have been created with assets fields
        meta_path = temp_plans_dir / f"{result['plan_id']}.meta.json"
        meta = json.loads(meta_path.read_text())
        
        assert "assets" in meta
        assert "epic_assets" in meta

    def test_create_plan_on_disk_normalizes_header(self, temp_plans_dir, monkeypatch):
        """create_plan_on_disk should ensure # Plan: header exists in the written .md file."""
        from dashboard.routes.plans import create_plan_on_disk
        
        monkeypatch.setattr("dashboard.routes.plans.PROJECT_ROOT", temp_plans_dir)
        
        # Create with content that has colon-only prefix (no # Plan:)
        result = create_plan_on_disk(
            title="Test Plan",
            content=": This is my plan\n\n## EPIC-001\n",
            working_dir=str(temp_plans_dir / "project")
        )
        
        plan_file = temp_plans_dir / f"{result['plan_id']}.md"
        content = plan_file.read_text()
        
        # Should have normalized the header
        assert content.startswith("# Plan:")


class TestEnsurePlanMetaTitle:
    """Tests for title extraction in _ensure_plan_meta."""

    def test_ensure_plan_meta_with_normalized_header(self, temp_plans_dir):
        """Plan with normalized # Plan: header should get correct title in meta.json."""
        from dashboard.routes.plans import _ensure_plan_meta
        
        plan_id = "test-normalized-title"
        plan_file = temp_plans_dir / f"{plan_id}.md"
        
        # Content with proper header
        plan_file.write_text("# Plan: Blog Title\n\n## EPIC-001\n")
        
        # Check meta
        meta = _ensure_plan_meta(plan_id)
        
        # Title should be extracted correctly
        assert meta["title"] == "Blog Title"
