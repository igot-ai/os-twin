import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dashboard.api_utils import (
    AGENTS_DIR, SKILLS_DIRS, get_plan_roles_config, 
    parse_skill_md
)
from dashboard.routes.plans import _resolve_room_dir
from dashboard.constants import ROLE_DEFAULTS

class EpicSkillsManager:
    @staticmethod
    def get_role_instructions(role_name: str) -> str:
        role_dir = AGENTS_DIR / "roles" / role_name
        role_md = role_dir / "ROLE.md"
        if role_md.exists():
            content = role_md.read_text()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip()
            return content.strip()
        return f"You are a {role_name}."

    @staticmethod
    def get_skill_content(skill_name: str) -> str:
        for sdir in SKILLS_DIRS:
            # Skill might be in a subdirectory or direct
            # Try direct first
            skill_dir = sdir / skill_name
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                data = parse_skill_md(skill_dir)
                return data["content"] if data else ""
            
            # Try searching in subdirs (rglob)
            for smd in sdir.rglob("SKILL.md"):
                if smd.parent.name == skill_name:
                    data = parse_skill_md(smd.parent)
                    return data["content"] if data else ""
        return ""

    @staticmethod
    def sync_room_skills(room_dir: Path, plan_id: str):
        """Inject plan-level skill_refs into a warroom's config.json."""
        config_file = room_dir / "config.json"
        if not config_file.exists():
            return

        try:
            config = json.loads(config_file.read_text())
        except (json.JSONDecodeError, OSError):
            return

        if "skill_refs" in config:
            return

        assigned_role = config.get("assignment", {}).get("assigned_role", "")
        if not assigned_role:
            return

        plan_config = get_plan_roles_config(plan_id)
        role_config = plan_config.get(assigned_role, {})

        skill_refs = set(role_config.get("skill_refs", []))
        skill_refs.update(plan_config.get("attached_skills", []))

        disabled = set(role_config.get("disabled_skills", []))
        skill_refs -= disabled

        if skill_refs:
            config["skill_refs"] = sorted(skill_refs)
            config_file.write_text(json.dumps(config, indent=2))

    @classmethod
    def resolve_config(cls, plan_id: str, task_ref: str, role_name: str) -> Dict[str, Any]:
        plan_config = get_plan_roles_config(plan_id)
        room_dir = _resolve_room_dir(plan_id, task_ref)
        
        room_overrides = {}
        room_brief = ""
        if room_dir:
            room_config_file = room_dir / "config.json"
            if room_config_file.exists():
                try:
                    rc = json.loads(room_config_file.read_text())
                    room_overrides = rc.get("roles", {}).get(role_name, {})
                except json.JSONDecodeError: pass
            
            brief_file = room_dir / "brief.md"
            if brief_file.exists():
                room_brief = brief_file.read_text()

        role_defaults = ROLE_DEFAULTS.get(role_name, {})
        plan_role_config = plan_config.get(role_name, {})
        
        # Skill refs resolution: Combine all
        skill_refs = set()
        skill_refs.update(role_defaults.get("skill_refs", []))
        skill_refs.update(plan_config.get("attached_skills", [])) # Global plan skills
        skill_refs.update(plan_role_config.get("skill_refs", [])) # Plan-Role specific
        skill_refs.update(room_overrides.get("skill_refs", []))    # Epic-Role specific

        disabled = set()
        disabled.update(plan_role_config.get("disabled_skills", []))
        disabled.update(room_overrides.get("disabled_skills", []))
        skill_refs -= disabled

        merged = {
            "model": room_overrides.get("default_model") or plan_role_config.get("default_model") or role_defaults.get("default_model", "gemini-3-flash-preview"),
            "temperature": room_overrides.get("temperature") if room_overrides.get("temperature") is not None else plan_role_config.get("temperature") if plan_role_config.get("temperature") is not None else 0.7,
            "skill_refs": list(skill_refs),
            "brief": room_brief
        }
        return merged

    @classmethod
    def generate_system_prompt(cls, plan_id: str, task_ref: str, role_name: str) -> str:
        config = cls.resolve_config(plan_id, task_ref, role_name)
        role_instr = cls.get_role_instructions(role_name)
        
        skills_instr = []
        for skill_name in config["skill_refs"]:
            content = cls.get_skill_content(skill_name)
            if content:
                skills_instr.append(f"## Skill: {skill_name}\n\n{content}")
        
        prompt = []
        prompt.append(f"# Role: {role_name}\n")
        prompt.append(role_instr)
        
        if config["brief"]:
            prompt.append("\n# Current Epic Context\n")
            prompt.append(config["brief"])
            
        if skills_instr:
            prompt.append("\n# Available Skills\n")
            prompt.extend(skills_instr)
            
        return "\n\n".join(prompt)
