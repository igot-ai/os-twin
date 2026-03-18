import pytest
from dashboard.api_utils import build_skills_list
from dashboard.models import Skill

def test_build_skills_list_basic():
    # Mocking SKILLS_DIRS or assuming some exist
    skills = build_skills_list()
    assert isinstance(skills, list)
