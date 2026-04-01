# Agent OS — Multi-Agent War-Room Orchestration

## Vision

An operating system for AI agents where an **Engineer Manager** orchestrates
hundreds of parallel **War-Rooms**, each containing an **Engineer** and a
**QA Engineer** working together through a shared communication channel
until every task passes quality gates and the team agrees on **RELEASE notes**.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      ENGINEER MANAGER                           │
│                    (bash orchestration loop)                     │
│                                                                 │
│  ┌─── reads PLAN.md ──► breaks into tasks ──► spawns rooms ──┐ │
│  │                                                            │ │
│  │  monitors all war-rooms in parallel                        │ │
│  │  routes work: Engineer → QA → Engineer (if fail) → QA...  │ │
│  │  drafts RELEASE.md when all tasks pass                     │ │
│  │  exits only when ALL roles sign off                        │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  WAR-ROOM 1  │  │  WAR-ROOM 2  │  │  WAR-ROOM N  │
│              │  │              │  │              │
│ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │
│ │ Engineer │ │  │ │ Engineer │ │  │ │ Engineer │ │
│ │ (cli.py)  │ │  │ │ (cli.py)  │ │  │ │ (cli.py)  │ │
│ └────┬─────┘ │  │ └────┬─────┘ │  │ └────┬─────┘ │
│      │       │  │      │       │  │      │       │
│  channel.jsonl  │  channel.jsonl  │  channel.jsonl │
│      │       │  │      │       │  │      │       │
│ ┌────┴─────┐ │  │ ┌────┴─────┐ │  │ ┌────┴─────┐ │
│ │    QA    │ │  │ │    QA    │ │  │ │    QA    │ │
│ │ (cli.py)  │ │  │ │ (cli.py)  │ │  │ │ (cli.py)  │ │
│ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Skill Isolation

Agent capabilities are managed through a hierarchical skill resolution system to minimize context bloat:

1. **Global Skills** (`.agents/skills/global/`): Automatically loaded for all agents.
2. **Role-Specific Skills** (`.agents/skills/roles/<role_name>/`): Implicitly loaded based on the agent's assigned role.
3. **Explicit Skills** (`skill_refs` in `role.json`): Manually opted-in for specific personas, resolved from the base `.agents/skills/` directory.

Deduplication ensures that if a skill exists in multiple tiers, the most specific one (Explicit > Role > Global) is used.

## Prompt Limits

The system prompt builder evaluates the final payload size against `max_prompt_bytes` defined in `config.json` for each role. A warning is emitted if the threshold is breached.

## Roles

| Role             | CLI Tool       | Mode              | Responsibility                     |
|------------------|----------------|-------------------|------------------------------------|
| Engineer Manager | bash (loop.sh) | Long-running loop | Orchestrate, monitor, route, release |
| Engineer         | `.agents/bin/cli.py` | Non-interactive   | Write code, fix bugs               |
| QA Engineer      | `.agents/bin/cli.py` | Non-interactive   | Test, review, approve/reject       |
| Architect        | `.agents/bin/cli.py` | Non-interactive   | Design systems, review arch, ADRs |

## Communication Protocol

All agents communicate via **JSONL message channels** — one per war-room.
No external infrastructure needed. Just files.

```json
{"ts":"...","from":"manager","to":"engineer","type":"task","ref":"TASK-001","body":"..."}
{"ts":"...","from":"engineer","to":"manager","type":"done","ref":"TASK-001","body":"..."}
{"ts":"...","from":"manager","to":"qa","type":"review","ref":"TASK-001","body":"..."}
{"ts":"...","from":"qa","to":"manager","type":"pass","ref":"TASK-001","body":"..."}
```

## Message Types

| Type      | Direction           | Meaning                                  |
|-----------|---------------------|------------------------------------------|
| `task`    | manager → engineer  | Assign a coding task                     |
| `done`    | engineer → manager  | Engineer finished the task               |
| `review`  | manager → qa        | Request QA review                        |
| `pass`    | qa → manager        | QA approves the work                     |
| `fail`    | qa → manager        | QA rejects with feedback                 |
| `fix`     | manager → engineer  | Route QA feedback back for fixing        |
| `signoff` | any → manager       | Role approves the final release          |
| `release` | manager → all       | Release is finalized                     |

## Hello World Script

To execute the `hello.py` script, run the following command in the project root:

```bash
python3 hello.py
```

Expected output:
```
Hello from OS Twin
```

```
.agents/
├── README.md                 # This file
├── config.json               # Global configuration
├── channel/
│   ├── post.sh               # Post message to channel
│   ├── read.sh               # Read/filter channel messages
│   └── wait-for.sh           # Block until message type appears
├── roles/
│   ├── manager/
│   │   ├── ROLE.md           # Manager system prompt
│   │   └── loop.sh           # Main orchestration loop
│   ├── engineer/
│   │   ├── ROLE.md           # Engineer system prompt
│   │   └── run.sh            # deepagents wrapper
│   └── qa/
│       ├── ROLE.md           # QA system prompt
│       └── run.sh            # gemini wrapper
├── war-rooms/
│   ├── create.sh             # Create a new war-room
│   └── status.sh             # Show status of all rooms
├── plans/
│   └── PLAN.template.md      # Plan template
├── release/
│   ├── draft.sh              # Draft release notes
│   ├── signoff.sh            # Manage sign-offs
│   └── RELEASE.template.md   # Release notes template
└── run.sh                    # Entry point
```

## Quick Start

```bash
# 1. Create a plan
cp .agents/plans/PLAN.template.md .agents/plans/my-feature.md
# Edit the plan with your tasks

# 2. Launch the Agent OS
.agents/run.sh .agents/plans/my-feature.md

# 3. Watch the war-rooms work
.agents/war-rooms/status.sh

# 4. Release notes appear when all tasks pass and all roles sign off
```

## Scaling

The system scales horizontally — each war-room is independent.
The manager polls all rooms in a loop with configurable concurrency.
You can run 10 or 1000 war-rooms; the bottleneck is only your API rate limits.
