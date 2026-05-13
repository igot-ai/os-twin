# Pillar 1: The Zero-Agent Pattern

## Claim

> Adding a new role to OSTwin requires zero lines of code.

## How It Works

OSTwin has exactly one universal agent runner: `Invoke-Agent.ps1`. It accepts
a `RoleName`, a pre-built `Prompt`, a `TimeoutSeconds`, and an optional `Model`.
There is no role-specific branching anywhere in the runner. Engineer, QA,
architect, manager, and any custom role all execute through the same code path.

A **role** is a configuration directory, not a Python class:

```
contributes/roles/security-auditor/
  role.json        # Structured metadata
  ROLE.md          # Identity prompt (who am I, how do I behave)
```

That is the entire integration.

## Role Definition: `role.json`

```json
{
  "name": "security-auditor",
  "description": "Reviews code for OWASP vulnerabilities",
  "capabilities": ["security-analysis", "vulnerability-assessment"],
  "prompt_file": "ROLE.md",
  "skill_refs": ["threat-modeling", "owasp-top-10", "dependency-audit"],
  "quality_gates": ["no-hardcoded-secrets", "no-known-cves"],
  "model": "google-vertex/gemini-3.1-pro-preview",
  "timeout": 1800
}
```

Key fields:

| Field | Purpose |
|-------|---------|
| `capabilities` | Abstract capability tags (used for capability-based role matching) |
| `skill_refs` | Links to skill packs loaded at runtime |
| `quality_gates` | Verification gates checked before marking work as done |
| `model` | Default LLM for this role |
| `timeout` | Max execution time in seconds |

## Role Definition: `ROLE.md`

The identity prompt. Uses YAML frontmatter for metadata, followed by markdown
instructions that tell the LLM *who it is* and *how to behave*. No expertise
content -- that comes from skills.

```markdown
---
name: engineer
description: Software engineer
tags: [code, implementation]
trust_level: core
---

# Engineer

You are a senior software engineer. You write clean, tested,
production-quality code. You follow the project's coding standards.
...
```

## 5-Tier Role Discovery

`Resolve-Role.ps1` finds a role through five tiers:

| Tier | Location | Purpose |
|------|----------|---------|
| 0 | Explicit `RolePath` parameter | Direct path override |
| 1 | `.agents/roles/registry.json` | Static registry lookup |
| 2 | `.war-rooms/../roles/{role}/` | Project-level override |
| 2 | `contributes/roles/{role}/` | Community/contributed roles |
| 2 | `.agents/roles/{role}/` | Core roles shipped with OSTwin |
| 3 | Capability-based matching | Finds the role with highest capability overlap |
| 4 | `Start-EphemeralAgent.ps1` | Catch-all ephemeral fallback |

This means a user can override any core role by placing a directory at the
project level, or add community roles by dropping directories under
`contributes/roles/`.

## Role Registry

`.agents/roles/registry.json` is the master catalog (~700 lines) defining
20+ roles with:

- `runner` -- PowerShell entry point
- `capabilities` -- abstract capability tags
- `quality_gates` -- verification requirements
- `default_model` -- fallback LLM
- `supported_task_types` -- task, epic, review, design, orchestration
- `assignment_rules` -- which role handles which task type by default

The registry also declares extensibility rules:
```json
{
  "auto_discover": true,
  "required_files": ["role.json"],
  "optional_files": ["ROLE.md", "skills/"]
}
```

## Model Resolution Priority

When determining which LLM model a role uses in a war-room:

1. Plan-specific `{plan_id}.roles.json` -- highest priority
2. Global `.agents/config.json` -- with instance suffix support (e.g., `engineer:fe`)
3. Role's own `role.json` file
4. Default model (`google-vertex/gemini-3-flash-preview`)

## Dynamic Role Creation

The manager can invent roles at runtime. From the manager's instructions:

> *Be creative with role assignment. You are not limited to predefined roles.
> Invent the ideal specialist for each epic (e.g., security-auditor,
> database-architect, performance-engineer).*

`New-DynamicRole.ps1` and `Start-DynamicRole.ps1` handle creating and
launching roles that don't exist as pre-defined directories.

## Current Roles

### Core Roles (`.agents/roles/`)
engineer, qa, architect, manager, reporter, audit, technical-writer,
macos-automation-engineer

### Community Roles (`contributes/roles/`)
50+ roles including: game-architect, game-designer, game-engineer, game-qa,
frontend-engineer, backend-engineer, data-engineer, data-analyst,
narrative-designer, ux-researcher, sound-designer, level-designer, and many
domain-specific variants.

## Why This Matters

Experimentation cost approaches zero. A team lead who wonders "what if our QA
also did dependency-license review?" can fork the qa role, add `license-audit`
to its `skill_refs`, save it as `qa-strict`, and assign one war-room to it --
all in two minutes. If it works, ship it. If it doesn't, delete the directory.

## Key Source Files

| File | Purpose |
|------|---------|
| `.agents/roles/_base/Invoke-Agent.ps1` | Universal agent runner |
| `.agents/roles/_base/Resolve-Role.ps1` | 5-tier role discovery |
| `.agents/roles/_base/Build-SystemPrompt.ps1` | Prompt composition |
| `.agents/roles/_base/New-DynamicRole.ps1` | Runtime role creation |
| `.agents/roles/registry.json` | Master role catalog |
| `.agents/roles/{name}/role.json` | Per-role structured metadata |
| `.agents/roles/{name}/ROLE.md` | Per-role identity prompt |
| `dashboard/routes/roles.py` | REST API for role management |
| `dashboard/models.py` | Pydantic Role model |
