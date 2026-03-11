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
│ │(deepagents│ │  │ │(deepagents│ │  │ │(deepagents│ │
│ └────┬─────┘ │  │ └────┬─────┘ │  │ └────┬─────┘ │
│      │       │  │      │       │  │      │       │
│  channel.jsonl  │  channel.jsonl  │  channel.jsonl │
│      │       │  │      │       │  │      │       │
│ ┌────┴─────┐ │  │ ┌────┴─────┐ │  │ ┌────┴─────┐ │
│ │    QA    │ │  │ │    QA    │ │  │ │    QA    │ │
│ │(gemini)  │ │  │ │(gemini)  │ │  │ │(gemini)  │ │
│ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │
└──────────────┘  └──────────────┘  └──────────────┘
```

## Roles

| Role             | CLI Tool       | Mode              | Responsibility                     |
|------------------|----------------|-------------------|------------------------------------|
| Engineer Manager | bash (loop.sh) | Long-running loop | Orchestrate, monitor, route, release |
| Engineer         | `deepagents`   | Non-interactive   | Write code, fix bugs               |
| QA Engineer      | `gemini`       | Non-interactive   | Test, review, approve/reject       |

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

## War-Room Lifecycle

```
create → pending → engineering → qa-review ─┬─► passed → signoff
                       ▲                     │
                       └──── fixing ◄────────┘ (on fail)
```

## Directory Structure

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
