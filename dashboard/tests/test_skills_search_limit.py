"""Tests for skills search with limit parameter and build_skills_list."""
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

# Add project root to sys.path
sys.path.insert(0, "/Users/paulaan/PycharmProjects/agent-os")

from dashboard.api_utils import build_skills_list, parse_skill_md


def _make_skill(i):
    """Helper to create a mock skill dict."""
    return {
        "name": f"skill-{i}",
        "description": f"Desc {i}",
        "tags": [],
        "path": f"/fake/skill-{i}",
        "relative_path": f"skills/skill-{i}",
        "content": f"Content {i}",
        "trust_level": "core",
        "source": "user",
    }


class TestBuildSkillsListLimit(unittest.TestCase):
    """Tests for the limit parameter in build_skills_list."""

    def _patch_store(self, store):
        """Mock global_state.store."""
        return patch("dashboard.global_state.store", store)

    @patch("dashboard.api_utils.SKILLS_DIRS", new=[])
    def test_limit_caps_results_from_store(self):
        """When store returns many results, limit should cap them."""
        store = MagicMock()
        store.search_skills.return_value = [_make_skill(i) for i in range(10)]

        with self._patch_store(store):
            results = build_skills_list(query="test query", limit=5)
            self.assertLessEqual(len(results), 5)

    @patch("dashboard.api_utils.SKILLS_DIRS", new=[])
    def test_limit_defaults_to_50(self):
        """Default limit should be 50."""
        store = MagicMock()
        store.search_skills.return_value = []

        with self._patch_store(store):
            build_skills_list(query="test")
            store.search_skills.assert_called_with("test", limit=50)

    @patch("dashboard.api_utils.SKILLS_DIRS", new=[])
    def test_limit_passed_to_store_search(self):
        """Limit parameter should be forwarded to store.search_skills."""
        store = MagicMock()
        store.search_skills.return_value = []

        with self._patch_store(store):
            build_skills_list(query="my search", limit=5)
            store.search_skills.assert_called_with("my search", limit=5)

    def test_limit_applies_after_role_filter(self):
        """Limit should apply after post-filtering by role."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            skills_dir = Path(tmp_dir) / "skills"
            skills_dir.mkdir()

            # Create 10 skills, all tagged with 'engineer'
            for i in range(10):
                sd = skills_dir / f"eng-skill-{i}"
                sd.mkdir()
                (sd / "SKILL.md").write_text(
                    f"---\nname: eng-skill-{i}\ndescription: Engineer skill {i}\n"
                    f"tags: [engineer, test]\ntrust_level: core\n---\n# content"
                )

            with self._patch_store(MagicMock(store=None)):
                with patch("dashboard.api_utils.SKILLS_DIRS", new=[skills_dir]):
                    results = build_skills_list(role="engineer", limit=3)
                    self.assertLessEqual(len(results), 3)

    @patch("dashboard.api_utils.SKILLS_DIRS", new=[])
    def test_limit_of_1_returns_single_result(self):
        """Limit=1 should return at most 1 result."""
        store = MagicMock()
        store.search_skills.return_value = [_make_skill(i) for i in range(5)]

        with self._patch_store(store):
            results = build_skills_list(query="test", limit=1)
            self.assertEqual(len(results), 1)

    @patch("dashboard.api_utils.SKILLS_DIRS", new=[])
    def test_no_query_returns_all_skills_up_to_limit(self):
        """Without query, get_all_skills is called and limit is respected."""
        store = MagicMock()
        store.get_all_skills.return_value = [_make_skill(i) for i in range(20)]

        with self._patch_store(store):
            results = build_skills_list(limit=5)
            self.assertLessEqual(len(results), 5)


class TestSkillSearchRelativePath(unittest.TestCase):
    """Tests that relative_path is correctly set in parse_skill_md."""

    def test_relative_path_set_for_skill(self):
        """parse_skill_md should set a relative_path field."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = Path(tmp_dir) / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: test-skill\ndescription: desc\ntags: []\n---\n# content"
            )
            data = parse_skill_md(skill_dir)
            self.assertIsNotNone(data)
            self.assertIn("relative_path", data)
            # Fallback: should at least contain the skill name
            self.assertIn("test-skill", data["relative_path"])


if __name__ == "__main__":
    unittest.main()
