"""Skill loader for CLI commands.

This module provides filesystem-based skill discovery for CLI operations
(list, create, info, delete). It wraps the prebuilt middleware functionality from
deepagents.middleware.skills and adapts it for direct filesystem access
needed by CLI commands.

For middleware usage within agents, use
deepagents.middleware.skills.SkillsMiddleware directly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from deepagents.backends.filesystem import FilesystemBackend

if TYPE_CHECKING:
    from pathlib import Path
from deepagents.middleware.skills import (
    SkillMetadata,
    _list_skills as list_skills_from_backend,  # noqa: PLC2701  # Intentional access to internal skill listing
)

from deepagents_cli._version import __version__ as _cli_version

logger = logging.getLogger(__name__)


class ExtendedSkillMetadata(SkillMetadata):
    """Extended skill metadata for CLI display, adds source tracking.

    Attributes:
        source: Origin of the skill. One of `'built-in'`, `'user'`, or `'project'`.
        tags: List of tags for categorization.
        trust_level: Trust level of the skill (core, trusted, experimental).
    """

    source: str
    tags: list[str] = []
    trust_level: str = "experimental"


# Re-export for CLI commands
__all__ = ["SkillMetadata", "list_skills"]


def list_skills(
    *,
    built_in_skills_dir: Path | None = None,
    user_skills_dir: Path | None = None,
    project_skills_dir: Path | None = None,
    user_agent_skills_dir: Path | None = None,
    project_agent_skills_dir: Path | None = None,
) -> list[ExtendedSkillMetadata]:
    """List skills from built-in, user, and/or project directories.

    This is a CLI-specific wrapper around the prebuilt middleware's skill loading
    functionality. It uses FilesystemBackend to load skills from local directories.

    Precedence order (lowest to highest):
    0. `built_in_skills_dir` (`<package>/built_in_skills/`)
    1. `user_skills_dir` (`~/.deepagents/{agent}/skills/`)
    2. `user_agent_skills_dir` (`~/.agents/skills/`)
    3. `project_skills_dir` (`.deepagents/skills/`)
    4. `project_agent_skills_dir` (`.agents/skills/`)

    Skills from higher-precedence directories override those with the same name.

    Args:
        built_in_skills_dir: Path to built-in skills shipped with the package.
        user_skills_dir: Path to `~/.deepagents/{agent}/skills/`.
        project_skills_dir: Path to `.deepagents/skills/`.
        user_agent_skills_dir: Path to `~/.agents/skills/` (alias).
        project_agent_skills_dir: Path to `.agents/skills/` (alias).

    Returns:
        Merged list of skill metadata from all sources, with higher-precedence
            directories taking priority when names conflict.
    """
    all_skills: dict[str, ExtendedSkillMetadata] = {}

    def enrich_skill(skill, source):
        # SKILL.md frontmatter keys: tags, trust_level
        # Some loaders might place them in 'metadata'
        metadata = skill.get("metadata", {})
        tags = skill.get("tags") or metadata.get("tags") or []
        trust_level = skill.get("trust_level") or metadata.get("trust_level") or "experimental"
        return cast(
            "ExtendedSkillMetadata",
            {
                **skill,
                "source": source,
                "tags": tags,
                "trust_level": trust_level,
            }
        )

    # Load in precedence order (lowest to highest).
    # Each source is wrapped in try/except so that a single inaccessible
    # directory (e.g. permission error) does not prevent skills from other
    # healthy directories from being listed.

    # 0. Built-in skills (<package>/built_in_skills/) - lowest priority
    if built_in_skills_dir and built_in_skills_dir.exists():
        try:
            built_in_backend = FilesystemBackend(root_dir=str(built_in_skills_dir))
            built_in_skills = list_skills_from_backend(
                backend=built_in_backend, source_path="."
            )
            for skill in built_in_skills:
                # Inject the installed CLI version into built-in skill metadata
                # so consumers can see which version shipped the skill.
                enriched_metadata = {
                    **skill.get("metadata", {}),
                    "deepagents-cli-version": _cli_version,
                }
                all_skills[skill["name"]] = enrich_skill({**skill, "metadata": enriched_metadata}, "built-in")
        except OSError:
            logger.warning(
                "Could not load built-in skills from %s",
                built_in_skills_dir,
                exc_info=True,
            )

    # 1. User deepagents skills (~/.deepagents/{agent}/skills/)
    if user_skills_dir and user_skills_dir.exists():
        try:
            user_backend = FilesystemBackend(root_dir=str(user_skills_dir))
            user_skills = list_skills_from_backend(
                backend=user_backend, source_path="."
            )
            for skill in user_skills:
                all_skills[skill["name"]] = enrich_skill(skill, "user")
        except OSError:
            logger.warning(
                "Could not load user skills from %s",
                user_skills_dir,
                exc_info=True,
            )

    # 2. User agent skills (~/.agents/skills/) - overrides user deepagents
    if user_agent_skills_dir and user_agent_skills_dir.exists():
        try:
            user_agent_backend = FilesystemBackend(root_dir=str(user_agent_skills_dir))
            user_agent_skills = list_skills_from_backend(
                backend=user_agent_backend, source_path="."
            )
            for skill in user_agent_skills:
                all_skills[skill["name"]] = enrich_skill(skill, "user")
        except OSError:
            logger.warning(
                "Could not load user agent skills from %s",
                user_agent_skills_dir,
                exc_info=True,
            )

    # 3. Project deepagents skills (.deepagents/skills/)
    if project_skills_dir and project_skills_dir.exists():
        try:
            project_backend = FilesystemBackend(root_dir=str(project_skills_dir))
            project_skills = list_skills_from_backend(
                backend=project_backend, source_path="."
            )
            for skill in project_skills:
                all_skills[skill["name"]] = enrich_skill(skill, "project")
        except OSError:
            logger.warning(
                "Could not load project skills from %s",
                project_skills_dir,
                exc_info=True,
            )

    # 4. Project agent skills (.agents/skills/) - highest priority
    if project_agent_skills_dir and project_agent_skills_dir.exists():
        try:
            project_agent_backend = FilesystemBackend(
                root_dir=str(project_agent_skills_dir)
            )
            project_agent_skills = list_skills_from_backend(
                backend=project_agent_backend, source_path="."
            )
            for skill in project_agent_skills:
                all_skills[skill["name"]] = enrich_skill(skill, "project")
        except OSError:
            logger.warning(
                "Could not load project agent skills from %s",
                project_agent_skills_dir,
                exc_info=True,
            )

    return list(all_skills.values())
