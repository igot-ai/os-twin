"""Unit tests for Skill Enable/Disable feature (EPIC-002) and related fixes."""
import os
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone

TEST_API_KEY = "test_key_toggle"
os.environ["OSTWIN_API_KEY"] = TEST_API_KEY
os.environ.setdefault("OSTWIN_AUTH_KEY", TEST_API_KEY)

from dashboard.models import Skill
from dashboard.api_utils import (
    parse_skill_md, save_skill_md, build_skills_list,
    sync_skills_from_disk, SKILLS_DIRS,
)
from dashboard.routes import skills as skills_routes


HEADERS = {"X-API-Key": TEST_API_KEY, "X-User": "testuser"}


# ── Skill Model Tests ─────────────────────────────────────────────────

class TestSkillModel:
    def test_skill_model_has_enabled_field(self):
        s = Skill(name="test", description="desc")
        assert s.enabled is True  # default

    def test_skill_model_enabled_false(self):
        s = Skill(name="test", description="desc", enabled=False)
        assert s.enabled is False

    def test_skill_model_serialization_includes_enabled(self):
        s = Skill(name="test", description="desc", enabled=False)
        d = s.dict()
        assert "enabled" in d
        assert d["enabled"] is False


# ── parse_skill_md Tests ──────────────────────────────────────────────

class TestParseSkillMdEnabled:
    def test_parse_skill_md_enabled_default_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: my-skill\ndescription: desc\n---\ncontent"
            )
            data = parse_skill_md(skill_dir)
            assert data is not None
            assert data["enabled"] is True

    def test_parse_skill_md_enabled_false_from_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "disabled-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: disabled-skill\ndescription: desc\nenabled: false\n---\ncontent"
            )
            data = parse_skill_md(skill_dir)
            assert data is not None
            assert data["enabled"] is False


# ── save_skill_md Tests ───────────────────────────────────────────────

class TestSaveSkillMdEnabled:
    def test_save_preserves_enabled_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "skill-a"
            save_skill_md({"name": "skill-a", "description": "d", "content": "c", "enabled": True}, path=path)
            data = parse_skill_md(path)
            assert data["enabled"] is True

    def test_save_preserves_enabled_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "skill-b"
            save_skill_md({"name": "skill-b", "description": "d", "content": "c", "enabled": False}, path=path)
            data = parse_skill_md(path)
            assert data["enabled"] is False

    def test_save_defaults_enabled_true_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "skill-c"
            save_skill_md({"name": "skill-c", "description": "d", "content": "c"}, path=path)
            data = parse_skill_md(path)
            assert data["enabled"] is True


# ── build_skills_list Filtering Tests ─────────────────────────────────

class TestBuildSkillsListFiltering:
    @pytest.fixture(autouse=True)
    def setup_temp_skills(self, tmp_path):
        self._orig_dirs = SKILLS_DIRS.copy()
        SKILLS_DIRS.clear()
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        SKILLS_DIRS.append(skills_dir)

        save_skill_md(
            {"name": "active-skill", "description": "an active skill", "content": "x" * 60, "enabled": True},
            path=skills_dir / "active-skill",
        )
        save_skill_md(
            {"name": "disabled-skill", "description": "a disabled skill", "content": "x" * 60, "enabled": False},
            path=skills_dir / "disabled-skill",
        )
        yield
        SKILLS_DIRS.clear()
        SKILLS_DIRS.extend(self._orig_dirs)

    def test_default_excludes_disabled(self):
        import dashboard.global_state as gs
        orig = getattr(gs, "store", None)
        gs.store = None
        try:
            result = build_skills_list(include_disabled=False)
            names = [s.name for s in result]
            assert "active-skill" in names
            assert "disabled-skill" not in names
        finally:
            gs.store = orig

    def test_include_disabled_returns_all(self):
        import dashboard.global_state as gs
        orig = getattr(gs, "store", None)
        gs.store = None
        try:
            result = build_skills_list(include_disabled=True)
            names = [s.name for s in result]
            assert "active-skill" in names
            assert "disabled-skill" in names
        finally:
            gs.store = orig


# ── sync_skills_from_disk Tests ───────────────────────────────────────

class TestSyncSkillsFromDisk:
    def test_sync_runs_on_success_path(self):
        """Regression: sync loop must run even when get_all_skills succeeds (fix for indentation bug)."""
        with tempfile.TemporaryDirectory() as tmp:
            skills_dir = Path(tmp) / "skills"
            skills_dir.mkdir()
            skill_dir = skills_dir / "sync-test"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: sync-test\ndescription: A sync test skill\n---\nContent here for testing"
            )

            store = MagicMock()
            store.get_all_skills.return_value = []  # success path, empty store
            store.get_skill.return_value = None
            store.index_skill.return_value = True
            store.delete_skill.return_value = True

            result = sync_skills_from_disk(store, [skills_dir])

            assert result["synced_count"] == 1
            assert "sync-test" in result["added"]
            store.index_skill.assert_called_once()

    def test_sync_preserves_enabled_state_from_zvec(self):
        """When re-syncing, enabled state from zvec is preserved over disk value."""
        with tempfile.TemporaryDirectory() as tmp:
            skills_dir = Path(tmp) / "skills"
            skills_dir.mkdir()
            skill_dir = skills_dir / "preserved"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: preserved\ndescription: test\nenabled: true\n---\ncontent"
            )

            store = MagicMock()
            store.get_all_skills.return_value = [
                {"name": "preserved", "content": "old-content", "enabled": False}
            ]
            store.get_skill.return_value = {"name": "preserved", "content": "old-content", "enabled": False}
            store.index_skill.return_value = True

            result = sync_skills_from_disk(store, [skills_dir])

            assert result["synced_count"] == 1
            call_kwargs = store.index_skill.call_args
            assert call_kwargs.kwargs.get("enabled") is False or call_kwargs[1].get("enabled") is False

    def test_sync_handles_get_all_skills_failure(self):
        """Sync loop still runs when get_all_skills raises an exception."""
        with tempfile.TemporaryDirectory() as tmp:
            skills_dir = Path(tmp) / "skills"
            skills_dir.mkdir()
            skill_dir = skills_dir / "fallback-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: fallback-skill\ndescription: test\n---\nContent for fallback"
            )

            store = MagicMock()
            store.get_all_skills.side_effect = RuntimeError("zvec crash")
            store.get_skill.return_value = None
            store.index_skill.return_value = True

            result = sync_skills_from_disk(store, [skills_dir])

            assert result["synced_count"] == 1
            assert "fallback-skill" in result["added"]


# ── index_skill Accepts enabled Parameter ─────────────────────────────

class TestIndexSkillEnabledParam:
    """Verify that OSTwinStore.index_skill() accepts the enabled keyword argument."""

    def test_index_skill_signature_accepts_enabled(self):
        from dashboard.zvec_store import OSTwinStore
        import inspect
        sig = inspect.signature(OSTwinStore.index_skill)
        assert "enabled" in sig.parameters
        assert sig.parameters["enabled"].default is True

    def test_index_skill_with_enabled_false_no_type_error(self):
        """Calling index_skill(enabled=False) must not raise TypeError."""
        from dashboard.zvec_store import OSTwinStore
        store = OSTwinStore.__new__(OSTwinStore)
        store._skills = None  # guard: returns False immediately
        store._embed_fn = None
        store._embed_available = False
        result = store.index_skill(
            name="test", description="desc", tags=[], path="/tmp",
            enabled=False,
        )
        assert result is False  # _skills is None, but no TypeError


# ── Toggle Logic Tests (unit-level, no FastAPI app import) ────────────

class TestToggleLogic:
    """Tests the toggle cycle via save_skill_md + parse_skill_md (the core logic
    used by the PATCH /api/skills/{name}/toggle endpoint)."""

    def test_toggle_disables_skill(self, tmp_path):
        skill_dir = tmp_path / "toggleable"
        save_skill_md({"name": "toggleable", "description": "desc", "content": "x" * 60, "enabled": True}, path=skill_dir)
        data = parse_skill_md(skill_dir)
        assert data["enabled"] is True

        data["enabled"] = not data["enabled"]  # toggle
        save_skill_md(data, path=skill_dir)

        reloaded = parse_skill_md(skill_dir)
        assert reloaded["enabled"] is False

    def test_toggle_reenables_skill(self, tmp_path):
        skill_dir = tmp_path / "toggleable2"
        save_skill_md({"name": "toggleable2", "description": "desc", "content": "x" * 60, "enabled": False}, path=skill_dir)
        data = parse_skill_md(skill_dir)
        assert data["enabled"] is False

        data["enabled"] = not data["enabled"]
        save_skill_md(data, path=skill_dir)

        reloaded = parse_skill_md(skill_dir)
        assert reloaded["enabled"] is True

    def test_toggle_roundtrip_preserves_other_fields(self, tmp_path):
        skill_dir = tmp_path / "roundtrip"
        original = {
            "name": "roundtrip", "description": "Roundtrip test",
            "content": "x" * 60, "enabled": True, "tags": ["a", "b"],
            "version": "2.0.0", "author": "tester",
        }
        save_skill_md(original, path=skill_dir)

        data = parse_skill_md(skill_dir)
        data["enabled"] = False
        save_skill_md(data, path=skill_dir)

        reloaded = parse_skill_md(skill_dir)
        assert reloaded["enabled"] is False
        assert reloaded["name"] == "roundtrip"
        assert reloaded["tags"] == ["a", "b"]
        assert reloaded["version"] == "2.0.0"
        assert reloaded["author"] == "tester"


class TestSkillRouteLookupByFrontmatterName:
    @pytest.fixture(autouse=True)
    def setup_temp_skill(self, tmp_path):
        self._orig_dirs = SKILLS_DIRS.copy()
        SKILLS_DIRS.clear()
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        SKILLS_DIRS.append(skills_dir)

        self.skill_dir = skills_dir / "add-ui"
        save_skill_md(
            {
                "name": "Add UGUI View",
                "description": "Create a UI screen",
                "content": "x" * 60,
                "enabled": True,
                "version": "1.1.0",
                "category": "Implementation",
                "applicable_roles": ["game-engineer"],
                "author": "Agent OS Core",
            },
            path=self.skill_dir,
        )

        import dashboard.global_state as gs
        self._orig_store = getattr(gs, "store", None)
        yield
        gs.store = self._orig_store
        SKILLS_DIRS.clear()
        SKILLS_DIRS.extend(self._orig_dirs)

    @pytest.mark.asyncio
    async def test_get_skill_finds_skill_when_folder_name_differs(self):
        import dashboard.global_state as gs
        gs.store = None

        skill = await skills_routes.get_skill("Add UGUI View", {"username": "tester"})

        assert skill.name == "Add UGUI View"
        assert skill.path == str(self.skill_dir)

    @pytest.mark.asyncio
    async def test_toggle_skill_uses_disk_lookup_when_store_path_missing(self):
        import dashboard.global_state as gs

        store = MagicMock()
        store.get_skill.return_value = {
            "name": "Add UGUI View",
            "description": "stale description",
            "tags": [],
            "path": None,
            "relative_path": "",
            "trust_level": "core",
            "source": "project",
            "content": "stale content",
            "version": "1.1.0",
            "category": "Implementation",
            "applicable_roles": [],
            "params": [],
            "changelog": [],
            "author": "Agent OS Core",
            "forked_from": None,
            "is_draft": False,
            "enabled": True,
        }
        store.index_skill.return_value = True
        gs.store = store

        updated_skill = await skills_routes.toggle_skill("Add UGUI View", {"username": "tester"})
        reloaded = parse_skill_md(self.skill_dir)

        assert reloaded["enabled"] is False
        assert updated_skill.enabled is False
        assert store.index_skill.call_count == 1
        index_kwargs = store.index_skill.call_args.kwargs or store.index_skill.call_args[1]
        assert index_kwargs["path"] == str(self.skill_dir)

    @pytest.mark.asyncio
    async def test_search_endpoint_backfills_disk_skills_missing_from_store(self):
        import dashboard.global_state as gs

        store = MagicMock()
        store.search_skills.return_value = []
        gs.store = store

        results = await skills_routes.search_skills_endpoint(
            q="ugui",
            role=None,
            tags=[],
            limit=50,
            include_disabled=True,
            user={"username": "tester"},
        )

        names = [skill.name for skill in results]
        assert "Add UGUI View" in names


# ── _map_skill_doc Returns enabled ────────────────────────────────────

class TestMapSkillDocEnabled:
    def test_map_skill_doc_includes_enabled_true(self):
        from dashboard.zvec_store import OSTwinStore
        doc = MagicMock()
        fields = {
            "time_id": "abc", "name": "s", "description": "d",
            "tags": "a,b", "path": "/p", "relative_path": "skills/s",
            "trust_level": "experimental", "source": "project",
            "content": "c", "version": "1.0.0", "category": None,
            "applicable_roles": "", "params": "[]", "changelog": "[]",
            "author": None, "forked_from": None, "is_draft": 0,
            "enabled": 1,
        }
        doc.field.side_effect = lambda k: fields[k]

        store = OSTwinStore.__new__(OSTwinStore)
        result = store._map_skill_doc(doc)
        assert result["enabled"] is True

    def test_map_skill_doc_includes_enabled_false(self):
        from dashboard.zvec_store import OSTwinStore
        doc = MagicMock()
        fields = {
            "time_id": "abc", "name": "s", "description": "d",
            "tags": "", "path": "/p", "relative_path": "skills/s",
            "trust_level": "experimental", "source": "project",
            "content": "c", "version": "1.0.0", "category": None,
            "applicable_roles": "", "params": "[]", "changelog": "[]",
            "author": None, "forked_from": None, "is_draft": 0,
            "enabled": 0,
        }
        doc.field.side_effect = lambda k: fields[k]

        store = OSTwinStore.__new__(OSTwinStore)
        result = store._map_skill_doc(doc)
        assert result["enabled"] is False


# ── Embedder Query vs Document Prefix (EPIC-003) ─────────────────────

class TestEmbedTextQueryPrefix:
    def test_embed_text_adds_instruction_prefix_for_query(self):
        from dashboard.zvec_store import OSTwinStore
        store = OSTwinStore.__new__(OSTwinStore)

        captured = {}
        mock_model = MagicMock()
        def capture_encode(text, **kwargs):
            captured["text"] = text
            import numpy as np
            return np.zeros(384)
        mock_model.encode = capture_encode

        store._embed_fn = mock_model
        store._embed_available = True

        store._embed_text("hello world", is_query=True)
        assert captured["text"].startswith("Instruct: Retrieve semantically similar text\nQuery: ")
        assert "hello world" in captured["text"]

    def test_embed_text_no_prefix_for_document(self):
        from dashboard.zvec_store import OSTwinStore
        store = OSTwinStore.__new__(OSTwinStore)

        captured = {}
        mock_model = MagicMock()
        def capture_encode(text, **kwargs):
            captured["text"] = text
            import numpy as np
            return np.zeros(384)
        mock_model.encode = capture_encode

        store._embed_fn = mock_model
        store._embed_available = True

        store._embed_text("hello world", is_query=False)
        assert captured["text"] == "hello world"

    def test_embed_text_returns_none_for_empty_input(self):
        from dashboard.zvec_store import OSTwinStore
        store = OSTwinStore.__new__(OSTwinStore)
        store._embed_fn = MagicMock()
        store._embed_available = True

        assert store._embed_text("") is None
        assert store._embed_text("   ") is None
        assert store._embed_text(None) is None  # type: ignore
