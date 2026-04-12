# Contributing Roles

## Architecture

```
contributes/roles/<role>/       <- source of truth
    role.json                   <- model, timeout, skill_refs
    ROLE.md                     <- system prompt / agent persona
    subcommands.json            <- (optional) custom subcommands

.agents/install.sh             <- standard publish step
    copies contributed roles to:
    ~/.ostwin/.agents/roles/<role>/      (installed runtime reads role.json / ROLE.md)
    ~/.config/opencode/agents/<role>.md  (OpenCode named agent definition)
```

This is how community roles in `contributes/roles/` are expected to behave:
they are defined in the repo, then published into the installed OSTwin runtime
via the installer. This task follows that same contract.

## Runtime Contract

| Concern | Source of Truth | Runtime Reader |
|---|---|---|
| Role definition | `contributes/roles/<role>/role.json` | Installed runtime via `~/.ostwin/.agents/roles/<role>/role.json` |
| System prompt | `contributes/roles/<role>/ROLE.md` | Installed runtime via `~/.ostwin/.agents/roles/<role>/ROLE.md` |
| Agent identity | `contributes/roles/<role>/ROLE.md` | OpenCode via `~/.config/opencode/agents/<role>.md` |
| Discovery in source mode | `contributes/roles/<role>/` | `Resolve-Role.ps1` / `Get-AvailableRoles.ps1` |
| Assignment | Plan `Roles:` lines / `candidate_roles` | Explicit plan metadata only |

Important distinction:

- **Installed mode** is the supported publish path for contributed roles.
- **Source mode** can discover roles directly from `contributes/roles/`, but that is
  not the same as publishing them into the installed runtime.

## Publish / Install

To make contributed roles behave like the other roles already living under
`contributes/roles/`, republish the installed runtime from the repo source:

```bash
cd /path/to/os-twin
bash .agents/install.sh --yes --source-dir "$(pwd)"
```

Relevant installer behavior:

- `.agents/install.sh` loads every role directory from `contributes/roles/`
  into `~/.ostwin/.agents/roles/`
- `.agents/install.sh` syncs every `ROLE.md` into
  `~/.config/opencode/agents/<role>.md`

That is the standard community-role publish step already used by the repo.

## Assignment: Explicit Only

Contributed roles are assigned via explicit plan metadata:

```markdown
## EPIC-001 - My Epic

Roles: requirement-analyst, architecture-advisor, qa
```

Auto-inference from task text is not part of the contract for contributed roles.
If you want a contributed role to run, name it explicitly in the plan.

## Skills

Contributed roles in this task are prompt + MCP driven by default.
Their `skill_refs` are intentionally empty:

- they do not ship local skills
- they do not rely on `~/.ostwin/roles/<role>/role.json`

Do not use the `capabilities` field in contributed `role.json` files. The
current skill resolver merges `capabilities` into skill lookup and will emit
spurious "Skill Not Found" warnings for non-skill tags.

If a contributed role really needs local skills, add a real skill folder under
`.agents/skills/roles/<role>/<skill-name>/SKILL.md` and list that skill in
`skill_refs`.

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
3. Reference it explicitly in a plan with `Roles: your-role, qa`.
4. Republish the installed runtime with `.agents/install.sh`.

## What Is NOT Supported

- Auto-inference from task text for contributed roles
- Capability-based pipeline auto-assembly for contributed roles
- Using `capabilities` in contributed `role.json`
- Expecting source-mode discovery to replace the standard installer publish step
