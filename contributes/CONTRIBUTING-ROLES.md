# Contributing Roles

## Architecture

```
contributes/roles/<role>/       <- source of truth
    role.json                   <- model, timeout, skill_refs
    ROLE.md                     <- system prompt / agent persona
    subcommands.json            <- (optional) custom subcommands

Materialize-PlanRoles.ps1       <- runtime prep (non-core)
    copies ALL artifacts to:
    ~/.ostwin/.agents/roles/<role>/   (Invoke-Agent model/timeout + prompt)
    ~/.ostwin/roles/<role>/           (Resolve-RoleSkills skill_refs)
    ~/.config/opencode/agents/<role>.md  (OpenCode agent definition)
    ~/.ostwin/.agents/plans/<plan>.roles.json  (plan-level overrides)
    $RoomDir/overrides/<role>/        (room-level override for Start-DynamicRole)
```

## Contract

| Concern | Source of Truth | Runtime Reader |
|---|---|---|
| Role definition | `contributes/roles/<role>/role.json` | `Get-RoleDefinition.ps1` via override dir or `~/.ostwin/.agents/roles/` |
| System prompt | `contributes/roles/<role>/ROLE.md` | `Build-SystemPrompt.ps1` via same path |
| Model / timeout | `contributes/roles/<role>/role.json` | `Invoke-Agent.ps1` via `plan.roles.json` or `~/.ostwin/.agents/roles/` |
| Skill resolution | `contributes/roles/<role>/role.json` `skill_refs` | `Resolve-RoleSkills.ps1` via `~/.ostwin/roles/` |
| Agent identity | `contributes/roles/<role>/ROLE.md` | OpenCode CLI via `~/.config/opencode/agents/<role>.md` |
| Assignment | Plan `Roles:` lines / `candidate_roles` | `Resolve-Pipeline.ps1` via explicit list |

## Assignment: Explicit Only

Contributed roles are assigned via **explicit plan metadata**:

```markdown
## EPIC-001 - My Epic

Roles: requirement-analyst, architecture-advisor, qa
```

Auto-inference from task text (e.g., "write a test plan" -> `qa-test-planner`) is
**not supported** for contributed roles. The core `Analyze-TaskRequirements.ps1`
keyword mappings only cover builtin roles. This is intentional -- contributed roles
are opt-in via explicit `Roles:` directives.

## Skills

Contributed roles are **prompt + MCP driven** by default. They do not ship with
local skill folders. The `skill_refs` field in `role.json` should only list
skills that actually exist in `.agents/skills/`.

Do **not** use the `capabilities` field in `role.json` for contributed roles.
The core `Resolve-RoleSkills.ps1` merges `capabilities` into the skill search
and will produce "Skill Not Found" warnings for tags that are not real skill names.

If a contributed role needs local skills, create a skill folder at
`.agents/skills/roles/<role>/<skill-name>/SKILL.md` and add the skill name
to `skill_refs`.

## Usage

```powershell
# Before running a plan with contributed roles:
pwsh .agents/scripts/Materialize-PlanRoles.ps1 \
    -PlanFile .agents/plans/my-plan.md \
    -ProjectDir /path/to/project

# With room overrides (after war-rooms are created):
pwsh .agents/scripts/Materialize-PlanRoles.ps1 \
    -PlanFile .agents/plans/my-plan.md \
    -WarRoomsDir .war-rooms \
    -ProjectDir /path/to/project

# Dry run:
pwsh .agents/scripts/Materialize-PlanRoles.ps1 \
    -PlanFile .agents/plans/my-plan.md \
    -DryRun
```

## Adding a New Role

1. Create `contributes/roles/<your-role>/role.json`:
   ```json
   {
     "name": "your-role",
     "description": "What this role does",
     "prompt_file": "ROLE.md",
     "model": "google-vertex/gemini-3-flash-preview",
     "timeout": 600,
     "skill_refs": [],
     "cli": "agent",
     "instance_type": "worker"
   }
   ```

2. Create `contributes/roles/<your-role>/ROLE.md` with the agent persona.

3. Reference it in your plan: `Roles: your-role, qa`

4. Run materialization before execution.

## What Is NOT Supported

- Auto-inference from task text for contributed roles
- Capability-based pipeline auto-assembly for contributed roles
- Running contributed roles without prior materialization
- `capabilities` field in role.json (causes spurious skill warnings)
