---
name: discover-skills
description: Use this skill to search and install skills for war-rooms -- scan epic requirements, query the skills API, and populate skill_refs in config."
tags: [manager, skills, discovery, installation]
: core
---

# discover-skills

## Overview

This skill guides the manager through discovering and installing skills that agents need to accomplish their assigned work. Before spawning a war-room, scan the epic's requirements and ensure the assigned role has the right tooling.

## When to Use

- Before creating a new war-room for an epic/task
- When an engineer reports a missing capability
- When an architect recommends a new tool or framework
- When expanding the skill set for a dynamic or custom role

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Updated config | JSON | `<war-room>/config.json`  `skill_refs` |
| Installed skills | Directory | `skills/roles/<role>/<skill>/` or `skills/global/<skill>/` |

## Instructions

### 1. Extract Skill Requirements

Read the epic's `brief.md` and identify:
- **Technologies mentioned** -- languages, frameworks, libraries
- **Domains referenced** -- security, data, infrastructure, frontend
- **Task types** -- generation, review, testing, deployment

Also check the assigned role's `role.json`  `capabilities` to understand baseline skills.

### 2. Search Available Skills

Use the skills API or CLI:

```bash
# Search by keyword
ostwin skills search "<keyword>"

# List skills for a specific role
ostwin skills list --role=<role-name>

# Search by tag
ostwin skills search --tag=<tag>
```

Or via API:
```
GET /api/skills/search?q=<keyword>&role=<role>
```

### 3. Match Skills to Requirements

| Requirement | Matching Skill | Status |
|-------------|---------------|--------|
| <tech/domain> | <skill name> |  Found /  Missing |
| <tech/domain> | <skill name> |  Found /  Missing |

### 4. Install Missing Skills

For each missing skill:

```bash
# Install a skill
ostwin skills install <skill-name>

# Or via API
POST /api/skills/install
{ "name": "<skill-name>", "scope": "global" | "role:<role-name>" }
```

Verify installation:
```bash
# Check SKILL.md exists
cat skills/<scope>/<skill-name>/SKILL.md
```

### 5. Populate War-Room Config

Update the war-room's `config.json` with matched skills:

```json
{
  "skill_refs": [
    "skills/global/lang/SKILL.md",
    "skills/roles/engineer/write-tests/SKILL.md",
    "skills/roles/engineer/implement-epic/SKILL.md"
  ]
}
```

**Rules:**
- Include all skills relevant to the epic's requirements
- Include role-specific skills that match the assigned role
- Include global skills that match any requirement keywords
- Don't include skills for other roles (e.g., don't give `review-epic` to an engineer)

### 6. Log Skill Discovery

Add a note to the war-room's setup log:

```markdown
## Skill Discovery -- <room-id>

| Skill | Source | Matched Requirement |
|-------|--------|-------------------|
| <skill> | <global/role> | <requirement> |
| <skill> | <global/role> | <requirement> |

Skills not found: <list or "none">
```

## Verification

After skill discovery:
1. `config.json` has a populated `skill_refs` array
2. All referenced SKILL.md files exist on disk
3. Skills match the epic's requirements and the assigned role
4. No irrelevant skills are included
