import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.insert(0, "/Users/paulaan/PycharmProjects/agent-os")

from dashboard.api_utils import parse_skill_md, sync_skills_from_disk

class TestSkillsLogic(unittest.TestCase):
    def test_parse_skill_md_yaml(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            skill_dir = tmp_path / "test-skill"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            content = """---
name: Test Skill
description: A test skill for YAML parsing.
tags: [test, mock]
trust_level: high
---
# Content
This is the skill content.
"""
            skill_md.write_text(content)
            
            data = parse_skill_md(skill_dir)
            self.assertIsNotNone(data)
            self.assertEqual(data["name"], "Test Skill")
            self.assertEqual(data["description"], "A test skill for YAML parsing.")
            self.assertEqual(data["tags"], ["test", "mock"])
            self.assertEqual(data["trust_level"], "high")
            self.assertEqual(data["content"], "# Content\nThis is the skill content.")

    def test_parse_skill_md_no_frontmatter(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            skill_dir = tmp_path / "no-meta"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            content = "# Just Content"
            skill_md.write_text(content)
            
            data = parse_skill_md(skill_dir)
            self.assertIsNotNone(data)
            self.assertEqual(data["name"], "no-meta")
            self.assertEqual(data["content"], "# Just Content")

    def test_sync_skills_from_disk(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Setup mock store
            store = MagicMock()
            store.get_all_skills.return_value = [
                {"name": "old-skill", "content": "removed"}
            ]
            store.get_skill.side_effect = lambda name: None
            store.index_skill.return_value = True
            store.delete_skill.return_value = True

            # Setup disk skills
            skills_dir = tmp_path / "skills"
            skills_dir.mkdir()
            skill_dir = skills_dir / "new-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("---\nname: new-skill\ndescription: desc\n---\ncontent")

            res = sync_skills_from_disk(store, [skills_dir])
            
            self.assertEqual(res["synced_count"], 1)
            self.assertIn("new-skill", res["added"])
            self.assertIn("old-skill", res["removed"])
            store.index_skill.assert_called()
            store.delete_skill.assert_called_with("old-skill")

if __name__ == "__main__":
    unittest.main()
