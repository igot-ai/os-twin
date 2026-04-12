import unittest
from dashboard.models import Skill

class TestSkillModels(unittest.TestCase):
    def test_skill_defaults(self):
        skill = Skill(name="test", description="desc")
        self.assertEqual(skill.tags, [])
        self.assertEqual(skill.trust_level, "experimental")
        self.assertEqual(skill.source, "project")

    def test_skill_custom(self):
        skill = Skill(
            name="test", 
            description="desc", 
            tags=["tag1"], 
            trust_level="core",
            source="built-in"
        )
        self.assertEqual(skill.tags, ["tag1"])
        self.assertEqual(skill.trust_level, "core")
        self.assertEqual(skill.source, "built-in")

if __name__ == "__main__":
    unittest.main()
