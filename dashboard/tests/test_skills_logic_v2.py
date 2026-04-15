from dashboard.api_utils import parse_skill_md, sync_skills_from_disk
from unittest.mock import MagicMock

def test_parse_skill_md_yaml(tmp_path):
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    content = """---
name: test-skill
description: A test skill for YAML parsing.
tags: [test, mock]
trust_level: high
---
# Content
This is the skill content.
"""
    skill_md.write_text(content)
    
    data = parse_skill_md(skill_dir)
    assert data is not None
    assert data["name"] == "test-skill"
    assert data["description"] == "A test skill for YAML parsing."
    assert data["tags"] == ["test", "mock"]
    assert data["trust_level"] == "high"
    assert data["content"] == "# Content\nThis is the skill content."

def test_parse_skill_md_no_frontmatter(tmp_path):
    skill_dir = tmp_path / "no-meta"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    content = "# Just Content"
    skill_md.write_text(content)
    
    data = parse_skill_md(skill_dir)
    assert data is not None
    assert data["name"] == "no-meta"
    assert data["content"] == "# Just Content"

def test_sync_skills_from_disk(tmp_path):
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
    
    assert res["synced_count"] == 1
    assert "new-skill" in res["added"]
    assert "old-skill" in res["removed"]
    store.index_skill.assert_called()
    store.delete_skill.assert_called_with("old-skill")
