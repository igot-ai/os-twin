import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, "/Users/paulaan/PycharmProjects/agent-os")

import pytest
import json
from unittest.mock import MagicMock, patch
from dashboard.epic_manager import EpicSkillsManager
from dashboard.api_utils import AGENTS_DIR, SKILLS_DIRS

@pytest.fixture
def mock_room_dir(tmp_path):
    room_dir = tmp_path / "room-003"
    room_dir.mkdir()
    (room_dir / "config.json").write_text(json.dumps({
        "roles": {
            "engineer": {
                "default_model": "gpt-4-override",
                "temperature": 0.1,
                "skill_refs": ["new-skill"]
            }
        }
    }))
    (room_dir / "brief.md").write_text("This is a test epic brief.")
    return room_dir

@pytest.fixture
def mock_agent_roles(tmp_path):
    roles_dir = tmp_path / "agents" / "roles" / "engineer"
    roles_dir.mkdir(parents=True)
    (roles_dir / "ROLE.md").write_text("---\nname: engineer\n---\n# Responsibilities\nDo engineering things.")
    return tmp_path / "agents"

@pytest.fixture
def mock_skills(tmp_path):
    skills_dir = tmp_path / "skills" / "new-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: new-skill\n---\n# Usage\nUse this for testing.")
    return tmp_path / "skills"

def test_resolve_config(mock_room_dir, mock_agent_roles, mock_skills):
    plan_id = "plan-001"
    task_ref = "EPIC-003"
    role_name = "engineer"

    with patch("dashboard.epic_manager._resolve_room_dir", return_value=mock_room_dir), \
         patch("dashboard.epic_manager.get_plan_roles_config", return_value={
             "engineer": {"default_model": "plan-model", "temperature": 0.5},
             "attached_skills": ["plan-skill"]
         }), \
         patch("dashboard.epic_manager.ROLE_DEFAULTS", {"engineer": {"skill_refs": ["default-skill"]}}):
        
        config = EpicSkillsManager.resolve_config(plan_id, task_ref, role_name)
        
        assert config["model"] == "gpt-4-override"
        assert config["temperature"] == 0.1
        assert "new-skill" in config["skill_refs"]
        assert "plan-skill" in config["skill_refs"]
        assert "default-skill" in config["skill_refs"]
        assert config["brief"] == "This is a test epic brief."

def test_generate_system_prompt(mock_room_dir, mock_agent_roles, mock_skills):
    plan_id = "plan-001"
    task_ref = "EPIC-003"
    role_name = "engineer"

    with patch("dashboard.epic_manager._resolve_room_dir", return_value=mock_room_dir), \
         patch("dashboard.epic_manager.get_plan_roles_config", return_value={}), \
         patch("dashboard.epic_manager.AGENTS_DIR", mock_agent_roles), \
         patch("dashboard.epic_manager.SKILLS_DIRS", [mock_skills]), \
         patch("dashboard.epic_manager.ROLE_DEFAULTS", {}):
        
        prompt = EpicSkillsManager.generate_system_prompt(plan_id, task_ref, role_name)
        
        assert "# Role: engineer" in prompt
        assert "Do engineering things." in prompt
        assert "# Current Epic Context" in prompt
        assert "This is a test epic brief." in prompt
        assert "## Skill: new-skill" in prompt
        assert "Use this for testing." in prompt
