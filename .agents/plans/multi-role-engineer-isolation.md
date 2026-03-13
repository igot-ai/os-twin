# Multi-Role Engineer Isolation — PLAN.md

## Problem Statement

Today, Agent OS has a **single `engineer` config block** in `config.json`. Every war-room spawns the same `Start-Engineer.ps1` with the same model, timeout, and CLI settings. This means:

- You **cannot** run a Frontend Engineer (FE) with `gemini-3-pro` and a Backend Engineer (BE) with `gemini-3-flash` simultaneously.
- The Manager has **no mechanism** to route a task to a specific engineer specialty.
- War-rooms are **not scoped** to an engineer type — everything goes through one `engineer` role.

## Design Goals

1. **Manager creates engineer roles dynamically** — the manager defines FE/BE engineers from the config, no code changes required.
2. **Config-level isolation** — each engineer variant gets its own model, timeout, skills, scope, and file access constraints.
3. **Backward compatible** — existing `engineer` config still works as-is (single-role default).

---

## Architecture: Role Variants via `config.json`

### Current Config (flat, single engineer)

```json
{
  "engineer": {
    "cli": "deepagents",
    "default_model": "gemini-3-flash-preview",
    "timeout_seconds": 600
  }
}
```

### Proposed Config (named engineer instances)

```json
{
  "engineer": {
    "cli": "deepagents",
    "default_model": "gemini-3-flash-preview",
    "timeout_seconds": 600,
    "max_prompt_bytes": 102400,

    "instances": {
      "fe": {
        "display_name": "Frontend Engineer",
        "default_model": "gemini-3-pro-preview",
        "timeout_seconds": 900,
        "scope": {
          "include_paths": ["src/frontend/**", "dashboard/**", "*.css", "*.html", "*.tsx", "*.jsx"],
          "exclude_paths": ["api/**", "server/**", "*.py"]
        },
        "skills": ["javascript", "typescript", "css", "html", "react"],
        "quality_gates": ["lint-clean", "no-hardcoded-secrets", "accessibility-check"]
      },
      "be": {
        "display_name": "Backend Engineer",
        "default_model": "gemini-3-flash-preview",
        "timeout_seconds": 600,
        "scope": {
          "include_paths": ["api/**", "server/**", "*.py", "*.sql"],
          "exclude_paths": ["src/frontend/**", "dashboard/**"]
        },
        "skills": ["python", "sql", "docker", "powershell"],
        "quality_gates": ["unit-tests", "lint-clean", "no-hardcoded-secrets", "security-review"]
      }
    }
  }
}
```

### Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Where do instances live? | Under `engineer.instances.*` | Keeps backward compat — flat `engineer.*` is the default fallback |
| How does manager target an instance? | `assigned_role` in war-room config becomes `engineer:fe` or `engineer:be` | Colon syntax splits cleanly into `role:instance` |
| Model override | Each instance has its own `default_model` | FE can use Pro for visual UI work, BE uses Flash for logic |
| Scope isolation | `scope.include_paths` / `exclude_paths` | Prevents FE from touching backend code and vice versa |

---

## File Changes

### 1. `config.json` — Add `instances` block

Add the `instances` key under `engineer` (and optionally under `qa`). Existing flat keys (`cli`, `default_model`, etc.) become the defaults.

### 2. `roles/_base/Invoke-Agent.ps1` — Instance-aware config resolution

**Current** (line 67-68):
```powershell
$Model = $config.$RoleName.default_model
if (-not $Model) { $Model = $config.engineer.default_model }
```

**Proposed**: Accept a new `-InstanceId` parameter. If provided, resolve `$config.$RoleName.instances.$InstanceId.default_model` first, falling back to `$config.$RoleName.default_model`:

```powershell
param(
    # ... existing params ...
    [string]$InstanceId = ''
)

# Config resolution with instance override
if ($InstanceId -and $config.$RoleName.instances.$InstanceId) {
    $instanceConfig = $config.$RoleName.instances.$InstanceId
    if (-not $Model -and $instanceConfig.default_model) { $Model = $instanceConfig.default_model }
    if ($instanceConfig.timeout_seconds) { $TimeoutSeconds = $instanceConfig.timeout_seconds }
}
if (-not $Model) { $Model = $config.$RoleName.default_model }
if (-not $Model) { $Model = $config.engineer.default_model }
```

### 3. `roles/engineer/Start-Engineer.ps1` — Pass instance ID to Invoke-Agent

Parse `$InstanceId` from the war-room's `config.json` `assignment.assigned_role` field (e.g., `engineer:fe` → instance = `fe`).

```powershell
# Read instance from war-room config
$roomConfig = Get-Content (Join-Path $RoomDir "config.json") -Raw | ConvertFrom-Json
$assignedRole = $roomConfig.assignment.assigned_role  # e.g. "engineer:fe"
$InstanceId = ""
if ($assignedRole -match '^engineer:(.+)$') {
    $InstanceId = $Matches[1]
}

# Pass to Invoke-Agent
$result = & $invokeAgent -RoomDir $RoomDir -RoleName "engineer" `
                         -InstanceId $InstanceId `
                         -Prompt $prompt -TimeoutSeconds $TimeoutSeconds
```

Also inject scope constraints into the prompt if the instance has `scope` config.

### 4. `war-rooms/New-WarRoom.ps1` — Accept role with instance

**Current** (line 103): `assigned_role = "engineer"`

**Proposed**: Accept an `-AssignedRole` parameter defaulting to `"engineer"`:

```powershell
param(
    # ... existing params ...
    [string]$AssignedRole = 'engineer'
)

# In config:
assignment = [ordered]@{
    assigned_role = $AssignedRole   # "engineer", "engineer:fe", "engineer:be"
    type          = $assignmentType
}
```

### 5. `roles/manager/Start-ManagerLoop.ps1` — Route to correct instance

**Current** (line 42): `$startEngineer = Join-Path ... "Start-Engineer.ps1"`

The manager loop currently hardcodes one `$startEngineer`. For instance-aware routing, the manager reads each room's `assigned_role` from `config.json` and passes the correct instance context.

No role-runner change needed — `Start-Engineer.ps1` reads instance from the room config itself. The manager just needs to ensure it sets the correct `assigned_role` when creating war-rooms.

### 6. `roles/registry.json` — Document instance support

Add `instance_support: true` to the engineer role entry and extend the extensibility section.

### 7. `roles/engineer/role.json` — Add instance resolution note

Add an `instances` field that references the config.json instances (or leave null for default).

---

## Data Flow

```
PLAN.md
  ├── TASK-001 (FE work) ──► Manager creates room with assigned_role="engineer:fe"
  │                              └── New-WarRoom.ps1 -AssignedRole "engineer:fe"
  │                                    └── room config.json: { assignment.assigned_role: "engineer:fe" }
  │                                          └── Start-Engineer.ps1 reads config → InstanceId="fe"
  │                                                └── Invoke-Agent.ps1 -InstanceId "fe"
  │                                                      └── Resolves model from config.engineer.instances.fe
  │
  ├── TASK-002 (BE work) ──► Manager creates room with assigned_role="engineer:be"
  │                              └── Same flow → InstanceId="be" → different model/scope
  │
  └── TASK-003 (generic) ──► assigned_role="engineer" → no instance → uses defaults
```

---

## Verification Plan

### Automated Tests

All tests use Pester (already established pattern). Run with:

```bash
pwsh -Command "Invoke-Pester -Path .agents/roles/_base/Invoke-Agent.Tests.ps1 -Passthru"
pwsh -Command "Invoke-Pester -Path .agents/roles/engineer/Start-Engineer.Tests.ps1 -Passthru"
pwsh -Command "Invoke-Pester -Path .agents/war-rooms/New-WarRoom.Tests.ps1 -Passthru"
```

#### New test cases to add:

1. **`Invoke-Agent.Tests.ps1`** — "Resolves model from instance config when InstanceId is provided"
2. **`Invoke-Agent.Tests.ps1`** — "Falls back to role default when InstanceId is not in config"
3. **`New-WarRoom.Tests.ps1`** — "Writes assigned_role from parameter into config.json"
4. **`Start-Engineer.Tests.ps1`** — "Parses instance ID from room config assigned_role"
5. **Config validation** — "Validates instance config inherits from parent engineer config"

### Manual Verification

1. Update `config.json` with the proposed `instances` block
2. Run `config.sh --get engineer.instances.fe.default_model` → should return the model
3. Create a test war-room: `New-WarRoom.ps1 -RoomId room-test -TaskRef TASK-TEST -TaskDescription "Test FE task" -AssignedRole "engineer:fe"`
4. Verify `room-test/config.json` contains `assigned_role: "engineer:fe"`

---

## Release Notes

### What Changed
- `config.json` now supports **named engineer instances** (`engineer.instances.fe`, `engineer.instances.be`)
- Each instance can define its own `default_model`, `timeout_seconds`, `scope`, `skills`, and `quality_gates`
- War-rooms accept `assigned_role` with `role:instance` syntax (e.g., `engineer:fe`)
- `Invoke-Agent.ps1` resolves config by instance → role default → global default cascade
- **Fully backward compatible** — existing single-engineer configs work unchanged

### Breaking Changes
None. All changes are additive.
