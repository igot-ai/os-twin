# Multi-Role Engineer Isolation — PLAN.md

## Problem Statement

Today, Agent OS has a **single `engineer` config block** in `config.json`. Every war-room spawns the same `Start-Engineer.ps1` with the same model, timeout, and CLI settings. This means:

- You **cannot** run a Frontend Engineer (FE) with `gemini-3-pro` and a Backend Engineer (BE) with `gemini-3-flash` simultaneously.
- The Manager has **no mechanism** to route a task to a specific engineer specialty.
- War-rooms are **not scoped** to an engineer type — everything goes through one `engineer` role.

## Design Goals

1. **Manager creates engineer roles dynamically** — the manager defines FE/BE engineers from the config, no code changes required.
2. **Config-level isolation** — each engineer variant gets its own model, timeout, skills, and **working directory**.
3. **Per-role context** — each role instance writes its own `context.md` inside the war-room's `contexts/` directory, so the whole team shares the room but each role has isolated context.
4. **Backward compatible** — existing `engineer` config still works as-is (single-role default).
5. **QA stays simple** — single QA role for now, extend instances later.

---

## Architecture: Role Variants via `config.json`

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
        "working_dir": "dashboard",
        "skills": ["javascript", "typescript", "css", "html"]
      },
      "be": {
        "display_name": "Backend Engineer",
        "default_model": "gemini-3-flash-preview",
        "timeout_seconds": 600,
        "working_dir": "api",
        "skills": ["python", "sql", "docker", "powershell"]
      }
    }
  }
}
```

### Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Where do instances live? | Under `engineer.instances.*` | Backward compat — flat `engineer.*` is fallback |
| How does manager target? | `assigned_role = "engineer:fe"` | Colon splits cleanly into `role:instance` |
| Scope isolation | `working_dir` per instance | FE starts in `dashboard/`, BE in `api/` |
| Per-role context | `{room}/contexts/engineer-fe.md` | Team shares room, each role has own context |
| QA | Single block, no instances yet | Extend later when needed |

---

## Data Flow

```
PLAN.md
  ├── TASK-001 (FE work)
  │     └── Manager creates room: -AssignedRole "engineer:fe"
  │           └── room config.json: { assignment.assigned_role: "engineer:fe" }
  │                 └── Start-Engineer.ps1 → InstanceId="fe"
  │                       ├── working_dir = config.engineer.instances.fe.working_dir
  │                       ├── model = config.engineer.instances.fe.default_model
  │                       └── writes contexts/engineer-fe.md
  │
  ├── TASK-002 (BE work)
  │     └── Same flow → InstanceId="be" → different working_dir/model
  │
  └── TASK-003 (generic)
        └── assigned_role="engineer" → no instance → uses defaults
```

---

## War-Room Layout (with contexts)

```
room-001/
├── config.json          # goal contract + assigned_role
├── brief.md             # task description
├── status               # state machine
├── task-ref
├── retries
├── channel.jsonl        # team communication
├── contexts/            # 🆕 per-role context files
│   ├── engineer-fe.md   # FE engineer's context
│   └── engineer-be.md   # BE engineer's context (if multi-role room)
├── pids/
└── artifacts/
```

---

## Release Notes

### What Changed
- `config.json` supports **named engineer instances** (`engineer.instances.fe`, `engineer.instances.be`)
- Each instance has own `default_model`, `timeout_seconds`, `working_dir`, `skills`
- War-rooms accept `assigned_role` with `role:instance` syntax
- Each role writes a `context.md` in `{room}/contexts/` for team visibility
- `Invoke-Agent.ps1` resolves: **instance config → role default → global default**
- **Fully backward compatible** — existing configs unchanged
