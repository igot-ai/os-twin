# OpenCode Integration

OSTwin uses [OpenCode](https://opencode.ai) as its agent runtime. Every role --
engineer, QA, architect, manager -- executes as an OpenCode agent process. This
document explains how that integration works and how to verify it.

## How It Fits

```
PLAN.md
  |
  v
War-Room (isolated directory)
  |
  |-- lifecycle.json   (state machine)
  |-- brief.md         (task description)
  |-- channel.jsonl    (message bus)
  |
  v
Invoke-Agent.ps1
  |
  |-- resolves role   (ROLE.md -> ~/.config/opencode/agents/<role>.md)
  |-- resolves skills (SKILL.md files injected into prompt)
  |-- resolves MCP    (~/.config/opencode/opencode.json)
  |
  v
OpenCode CLI process
  |-- reads agent definition from ~/.config/opencode/agents/<role>.md
  |-- connects to MCP servers defined in ~/.config/opencode/opencode.json
  |-- executes the task, posts results to channel.jsonl
```

## MCP Configuration

### Where Config Lives

MCP configuration is **global**, not per-project. There is one source of truth:

| File | Purpose |
|------|---------|
| `~/.ostwin/.agents/mcp/config.json` | Source config -- defines all MCP servers with `{env:*}` placeholders |
| `~/.config/opencode/opencode.json` | Compiled config -- consumed by OpenCode at runtime |

The source config uses the OpenCode MCP schema:

```json
{
  "mcp": {
    "channel": {
      "type": "local",
      "command": ["python", "{env:HOME}/.ostwin/.agents/mcp/channel-server.py"],
      "environment": {
        "AGENT_OS_ROOT": ".",
        "GOOGLE_API_KEY": "{env:GOOGLE_API_KEY}"
      }
    }
  }
}
```

### How Config Gets Compiled

Running `ostwin install` (or `bash .agents/install.sh`) triggers the full
compilation pipeline:

1. **Normalize** -- `validate_mcp.py` converts any legacy format to the
   OpenCode schema (e.g., `mcpServers` -> `mcp`, shell `${VAR}` -> `{env:VAR}`,
   string commands -> arrays, `env` -> `environment`).
2. **Validate** -- each server is checked against the OpenCode MCP spec (local
   servers need `type`, `command`, `environment`; remote servers need `type`,
   `url`). Invalid servers are skipped with a warning.
3. **Build tools deny + agent grants** -- `build_opencode_config()` generates:
   - A global `tools` block that denies non-core MCP servers by default
   - Per-agent overrides that grant privileged roles (manager, architect, qa,
     audit, reporter) access to all servers
4. **Merge** -- the result is merged into `~/.config/opencode/opencode.json`,
   preserving any existing user settings (theme, model, keybinds).

Core servers (`channel`, `warroom`, `memory`) are available to **all** agents.
Non-core servers (e.g., `github`) are denied globally and only granted to
privileged agents.

### Validation CLI

You can validate any config file directly:

```bash
# Validate the global config
python .agents/mcp/validate_mcp.py ~/.ostwin/.agents/mcp/config.json

# Validate a single server inline
python .agents/mcp/validate_mcp.py --server '{"type":"local","command":["npx","-y","my-mcp"],"environment":{}}'

# Validate and write only valid servers to a new file
python .agents/mcp/validate_mcp.py config.json --output validated.json
```

Output shows per-server status:

```
  [OK]    channel
  [OK]    warroom
  [OK]    memory
  [WARN]  github
          - no authentication configured
  [FAIL]  broken-server
          - missing 'command' (required for local servers)

  3 passed, 1 warnings, 1 failed (out of 5 servers)
```

## Role Sync

Each role's `ROLE.md` is copied to `~/.config/opencode/agents/<role>.md` during
install. This is how OpenCode discovers available agents.

**Source locations** (checked in order):

| Directory | Purpose |
|-----------|---------|
| `.agents/roles/<role>/` | Core roles shipped with OSTwin |
| `contributes/roles/<role>/` | Community-contributed roles |

A directory must contain both `role.json` and `ROLE.md` to be synced. The
`_base` directory (infrastructure scripts) is skipped.

To re-sync after adding a role:

```bash
ostwin install
```

## Skill Resolution

Skills are `SKILL.md` files discovered at runtime and injected into the agent's
system prompt. Resolution follows a hierarchical search:

| Priority | Location | Example |
|----------|----------|---------|
| 1 | Plan-level override | `~/.ostwin/.agents/plans/{plan_id}.roles.json` |
| 2 | War-room config | `{room_dir}/config.json -> skill_refs` |
| 3 | Global role.json | `~/.ostwin/roles/{role}/role.json -> skill_refs` |
| 4 | Brief keyword match | Keywords in `brief.md` matched against skill names |

For each skill ref, the resolver searches:

1. **Role-private skills**: `.agents/skills/roles/<RoleName>/*/SKILL.md` --
   auto-discovered, no explicit `skill_refs` entry needed
2. **Global skills**: `.agents/skills/global/*/SKILL.md`
3. **Cross-role skills**: `.agents/skills/roles/<OtherRole>/*/SKILL.md`

Skills are filtered by platform (`macos`/`linux`/`windows`) and an
`enabled: false` frontmatter flag before injection.

## Lifecycle Pipeline

Each war-room gets a lifecycle state machine generated by
`Resolve-Pipeline.ps1`. The pipeline uses **position-based role assignment**:

```
Roles[0]    = worker      ->  "developing" + "optimize" states
Roles[1..N] = evaluators  ->  "{role}-review" states
```

If no evaluators are listed, a default QA `review` state is injected
automatically.

State transitions:

```
developing --> [first evaluator]-review --> ... --> [last evaluator]-review --> passed
     ^                  |
     |                  | (fail signal)
     +--- optimize <----+
```

Triage (manager) handles escalations, with options to fix, redesign, or reject.

## Verifying the Setup

### 1. Check MCP config is compiled

```bash
cat ~/.config/opencode/opencode.json | python -m json.tool
```

Confirm it has `mcp`, `tools`, and `agent` keys. The `mcp` block should list
your servers (channel, warroom, memory at minimum).

### 2. Validate MCP servers

```bash
python .agents/mcp/validate_mcp.py ~/.ostwin/.agents/mcp/config.json
```

All servers should show `[OK]` or `[WARN]` (warnings are non-fatal).

### 3. Check agent definitions are synced

```bash
ls ~/.config/opencode/agents/
```

Should list `engineer.md`, `qa.md`, `architect.md`, `manager.md`, etc.

### 4. Verify no legacy config remnants

```bash
# These should NOT exist:
test -f ~/.ostwin/.agents/mcp/mcp-config.json && echo "LEGACY FILE EXISTS" || echo "OK"
test -f .agents/mcp/mcp-config.json && echo "LEGACY FILE EXISTS" || echo "OK"
```

### 5. Run the test suites

```bash
# MCP validation tests (1,241 lines of coverage)
python -m pytest .agents/mcp/test_validate_mcp.py -v

# Role resolution tests
pwsh -Command "Invoke-Pester .agents/tests/roles/_base/Resolve-RoleSkills.Tests.ps1 -Output Detailed"

# Skill coverage tests
pwsh -Command "Invoke-Pester .agents/tests/plan/Test-SkillCoverage.Tests.ps1 -Output Detailed"
```

### 6. Test a single agent invocation

```bash
ostwin agent -a engineer -n "List all files in the current directory"
```

If MCP is configured correctly, the agent will connect to channel/warroom/memory
servers and execute the task.

## Key Source Files

| File | Purpose |
|------|---------|
| `.agents/mcp/config.json` | Source MCP config (OpenCode schema) |
| `.agents/mcp/validate_mcp.py` | Normalization + validation + tools-deny builder |
| `.agents/mcp/resolve_opencode.py` | `{env:*}` placeholder resolution |
| `.agents/mcp/mcp-extension.sh` | MCP extension manager (install, sync, compile) |
| `.agents/install.sh` | Full install pipeline (MCP compile + agent sync) |
| `.agents/roles/_base/Invoke-Agent.ps1` | Universal agent runner |
| `.agents/roles/_base/Resolve-RoleSkills.ps1` | Hierarchical skill resolution |
| `.agents/lifecycle/Resolve-Pipeline.ps1` | Position-based lifecycle generator |
