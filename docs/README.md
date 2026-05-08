# OSTwin Documentation

OSTwin is a zero-agent operating system for composable AI engineering teams.
It scales on **skill depth**, not agent count.

## Core Idea

A user starts a **Plan**. That plan contains multiple **Epics** organized as a
**DAG** (directed acyclic graph). Each epic runs inside an isolated **War-Room**
where multiple agents -- assembled from **Roles** and **Skills** at runtime --
collaborate through a file-based message channel until the epic's Definition of
Done is met.

## The Five Pillars

OSTwin separates three axes that other frameworks fuse:

| Axis | Artifact | Question it answers |
|------|----------|---------------------|
| Identity | `role.json` + `ROLE.md` | *Who am I?* |
| Expertise | `SKILL.md` files | *What do I know?* |
| Execution | `war-room/` directory | *Where do I run?* |

These axes are composed independently through five architectural pillars:

| # | Pillar | Doc |
|---|--------|-----|
| 1 | [The Zero-Agent Pattern](roles-and-zero-agent.md) | Roles are config, not code. One universal runner serves all roles. |
| 2 | [Skills as Atomic Expertise](skills.md) | Skills are `SKILL.md` files discovered at runtime, not baked into prompts. |
| 3 | [MCP Isolation Per Role](mcp-isolation.md) | Expensive tool catalogs are opt-in per role, saving tokens and cost. |
| 4 | [War-Rooms: Isolated Execution](war-rooms.md) | Each epic runs in a self-contained directory with its own channel, lifecycle, and PID tracking. |
| 5 | [Layered Memory](memory.md) | Conversation, code artifacts, and shared ledger -- each bounded. |

## Additional Systems

| System | Doc |
|--------|-----|
| [Agentic Memory MCP](agentic-memory.md) | Semantic knowledge base with auto-linking, tagging, and vector search. |

## Execution Model

| Topic | Doc |
|-------|-----|
| [Plans, Epics, and the DAG](plan-epic-dag.md) | How plans are defined, how epics declare DoD/AC/Tasks, how the dependency graph controls ordering. |
| [Epic Lifecycle](lifecycle.md) | State machine, transitions, retries, and escalation. |
| [Architecture Overview](architecture-overview.md) | System-level view: engine, dashboard, bot, and how they connect. |
