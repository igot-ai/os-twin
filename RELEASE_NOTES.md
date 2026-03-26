# Release Notes — Agent OS

## [Unreleased]

### Migration: SKILL.md to ROLE.md (Roles)
- **Architecture Alignment**: Role-specific prompt files have been renamed from `SKILL.md` to `ROLE.md` to clearly distinguish between core agent roles and composable skills.
- All roles (engineer, qa, architect, manager, reporter) now use `ROLE.md` for their primary prompt definition.
- Composable skills in the `skills/` directory continue to use `SKILL.md`.

### Bug Fixes
- Fixed broken test imports in `dashboard/test_qa_coverage.py` following the migration of skills logic to `api_utils.py`.
- Removed redundant `Test-SkillCoverage` definition from `Start-ManagerLoop.ps1` to rely on the centralized logic in `plan/Test-SkillCoverage.ps1` and `Build-SystemPrompt.ps1`.
