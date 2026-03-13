# Plan: Extensible Role Engine

> Priority: 1 (foundation — unblocks Plan 5)
> Parallel: ✅ No dependencies

## Goal

Upgrade the role engine to support `role.yaml` declarative configs, composable skills, context injection, and new role definitions.

## Epics

### EPIC-001 — Role YAML Config System

#### Definition of Done
- [ ] `Get-RoleDefinition.ps1` reads `role.yaml` (YAML format, not JSON)
- [ ] Skills directory loading: role-specific `.md` files injected into system prompt
- [ ] Context injection: project-specific files loaded at spawn time
- [ ] Capability permissions: read/write/shell/delete per role

#### Acceptance Criteria
- [ ] `Get-RoleDefinition -RoleName engineer` returns parsed YAML config
- [ ] Engineer role loads skills from `roles/engineer/skills/*.md`
- [ ] QA role has `delete_files: false` capability restriction
- [ ] Changing `role.yaml` is picked up on next war-room spawn

#### Tasks
- [ ] TASK-001 — Add PowerYaml module or YAML parser to Get-RoleDefinition.ps1
- [ ] TASK-002 — Implement skills directory loading into Build-SystemPrompt.ps1
- [ ] TASK-003 — Implement context file injection from role config
- [ ] TASK-004 — Add capability permission checks to Invoke-Agent.ps1

### EPIC-002 — New Role Definitions

#### Definition of Done
- [ ] Architect role: `role.yaml` + `ROLE.md` + skills
- [ ] DevOps role: `role.yaml` + `ROLE.md` + skills
- [ ] Security role: `role.yaml` + `ROLE.md` + skills
- [ ] Tech Writer role: `role.yaml` + `ROLE.md` + skills

#### Acceptance Criteria
- [ ] `registry.json` lists all roles with capabilities
- [ ] Each role has at least 2 skill files
- [ ] Pester tests verify role loading for all new roles

#### Tasks
- [ ] TASK-005 — Create architect role with architecture review skills
- [ ] TASK-006 — Create devops role with deployment and CI/CD skills
- [ ] TASK-007 — Create security role with security audit skills
- [ ] TASK-008 — Create tech-writer role with documentation skills

---

## Configuration

```json
{
    "plan_id": "002-role-engine",
    "priority": 1,
    "goals": {
        "definition_of_done": [
            "Get-RoleDefinition reads role.yaml format",
            "Skills directory loaded into system prompt",
            "Context files injected at spawn time",
            "Capability permissions enforced per role",
            "4 new roles defined with skills and ROLE.md"
        ],
        "acceptance_criteria": [
            "registry.json lists all roles with capabilities",
            "Each role has at least 2 skill files",
            "role.yaml hot-reload works on next spawn"
        ]
    }
}
```
