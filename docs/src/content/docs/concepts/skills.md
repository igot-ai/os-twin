---
title: "Pillar 2: Skills as Atomic Expertise"
description: "Skills are self-contained markdown documents that give any role instant expertise. No code wiring required."
sidebar:
  order: 2
  badge:
    text: Pillar
    variant: tip
---

OSTwin's second pillar treats expertise as **portable, composable documents** rather than hard-coded tool integrations. A skill is a single `SKILL.md` file that teaches any agent how to perform a specific task.

## SKILL.md Format

Every skill is a markdown file with YAML frontmatter followed by instructional content:

```markdown
---
name: implement-epic
description: >
  Break an epic into sub-tasks, implement them sequentially,
  write tests, and deliver a structured done report.
triggers:
  - "implement epic"
  - "build feature"
  - "start development"
requires_mcp: false
---

# Implement Epic

When assigned an epic, follow this workflow:

1. Read the brief.md and TASKS.md in the war-room
2. Break the epic into ordered sub-tasks
3. Implement each task, running tests after each
4. Post a structured done report to the channel
...
```

### Frontmatter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | Yes | Unique skill identifier |
| `description` | `string` | Yes | What this skill teaches the agent |
| `triggers` | `string[]` | No | Phrases that activate this skill |
| `requires_mcp` | `bool` | No | Whether the skill needs MCP servers |
| `tags` | `string[]` | No | Discovery tags for marketplace search |
| `version` | `string` | No | Semver version for compatibility |
| `author` | `string` | No | Creator attribution |
| `dependencies` | `string[]` | No | Other skills this one requires |

## Directory Layout

Skills are organized into two top-level categories:

```
.agents/skills/
  global/                        # Available to ALL roles
    auto-memory/SKILL.md
    war-room-communication/SKILL.md
    create-architecture/SKILL.md
    create-lifecycle/SKILL.md
    lang/SKILL.md
  roles/                         # Scoped to specific roles
    engineer/
      implement-epic/SKILL.md
      fix-from-qa/SKILL.md
      write-tests/SKILL.md
      refactor-code/SKILL.md
    qa/
      review-epic/SKILL.md
      review-task/SKILL.md
      build-verify/SKILL.md
    architect/
      create-role/SKILL.md
      design-review/SKILL.md
      write-adr/SKILL.md
    manager/
      assign-epic/SKILL.md
      triage-failure/SKILL.md
      discover-skills/SKILL.md
```

**Global skills** are injected into every agent session regardless of role. **Role-scoped skills** are only available when that specific role is invoked.

## How Skills Reach the Agent

Skills travel from disk to prompt through a 5-step pipeline:

### Step 1: Resolve

The runner collects skill references from three sources (union-merged):

- Role-level `skill_refs` in `role.json`
- Room-level `skill_refs` in the war-room's `config.json`
- Plan-level `skill_refs` in the plan metadata

### Step 2: Copy

Resolved skills are staged into the war-room's working directory so the agent has local access during execution.

### Step 3: Environment Variable

The skill manifest is written to an environment variable that the LLM client reads at session start, providing a table of available skills with descriptions.

### Step 4: Discover

The agent receives a **lean skill index** -- just names and one-line descriptions. This keeps base prompt size small while letting the agent know what expertise is available.

### Step 5: Load on Demand

When the agent recognizes it needs a skill, it calls the `skill` tool with the skill name. The full `SKILL.md` content is injected into the conversation at that point.

:::tip[Token Efficiency]
The lean-prompt pattern means an agent with access to 50 skills only pays ~2K tokens for the index, not 50K+ tokens for all skill content upfront. Skills are loaded only when actually needed.
:::

## 3-Tier Runtime Resolution

When the agent requests a skill by name, resolution follows three tiers:

| Priority | Source | Example Path |
|----------|--------|-------------|
| 1 | War-room local | `.agents/war-rooms/room-042/skills/{name}/SKILL.md` |
| 2 | Project-level | `.agents/skills/roles/{role}/{name}/SKILL.md` |
| 3 | User-global | `~/.agents/skills/{name}/SKILL.md` |

The first match wins. This allows room-specific skill overrides without modifying project-level defaults.

## Linking via skill_refs

Skills are linked to agents through `skill_refs` arrays at three levels:

```json
// role.json -- role-level defaults
{ "skill_refs": ["implement-epic", "write-tests"] }

// config.json -- war-room override
{ "skill_refs": ["fix-from-qa", "security-review"] }

// plan metadata -- plan-wide additions
{ "skill_refs": ["create-architecture"] }
```

At invocation time, all three arrays are **union-merged** -- duplicates are removed, and the agent receives the combined set. This means a plan can grant temporary skills to all rooms without modifying role configs.

## Skill Marketplace: ClawhHub

OSTwin includes a skill discovery and installation system called **ClawhHub**:

```powershell
# Search for skills
Invoke-SkillSearch -Query "testing" -Tags "qa,automation"

# Install from marketplace
Install-Skill -Name "performance-testing" -Source "clawhhub"
```

:::note[Community Skills]
ClawhHub hosts 50+ community-contributed skills spanning game development, web engineering, DevOps, documentation, and more. Skills are versioned and reviewed before publication.
:::

## Search Directories

The skill discovery system searches these directories in order:

1. `.agents/skills/global/` -- Global skills for all roles
2. `.agents/skills/roles/{current_role}/` -- Role-specific skills
3. `~/.agents/skills/` -- User-installed global skills
4. `.agents/war-rooms/{room}/skills/` -- Room-local overrides
5. ClawhHub remote index -- Online marketplace (if enabled)

## Key Source Files

| File | Purpose |
|------|---------|
| `.agents/skills/*/SKILL.md` | Skill definitions |
| `engine/Resolve-Skills.ps1` | 3-tier skill resolution |
| `engine/Install-Skill.ps1` | ClawhHub installation |
| `engine/Get-SkillIndex.ps1` | Lean prompt generation |
| `.agents/skills/global/` | Skills available to all roles |
| `.agents/skills/roles/` | Role-scoped skill directories |

:::caution[Skill Size]
Keep individual SKILL.md files under 8K tokens. If a skill exceeds this, split it into a primary skill and reference sub-documents in a `references/` subdirectory. The build-ui skill demonstrates this pattern with 64 sub-skills.
:::
