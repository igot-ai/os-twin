---
title: What is OSTwin?
description: An introduction to OSTwin — the zero-agent operating system for composable AI engineering teams.
sidebar:
  order: 1
---

OSTwin is an **operating system for AI agents**. It takes a markdown plan, decomposes it into a dependency graph of epics, spins up isolated war-rooms, and orchestrates role-based agents to execute each epic — all without writing a single line of agent code.

## The Problem

Building with AI agents today means fighting three unsolved problems:

| Problem | What happens | OSTwin's answer |
|---------|-------------|-----------------|
| **Agent sprawl** | Every task gets a new bespoke agent. Config drifts. Nothing is reusable. | Roles + Skills compose agents from portable building blocks |
| **Context explosion** | Agents share one massive context. Prompt pollution kills quality. | War-rooms isolate each epic's context, memory, and tools |
| **No isolation** | One agent's bad tool call corrupts another's state. No blast radius control. | MCP servers are scoped per war-room. Filesystem boundaries enforced |

Most multi-agent systems treat agents as long-running processes with hardcoded capabilities. OSTwin inverts this: agents are **ephemeral sessions** assembled on demand from composable building blocks. The building blocks are portable, the sessions are disposable, and the coordination is filesystem-native.

## Three Axes of Agent Identity

OSTwin defines every agent through three orthogonal axes. This is the core abstraction that makes the system composable:

```
          Identity (WHO)
              │
              │   role.json + ROLE.md
              │   personality, constraints, style
              │
              ├──────────── Expertise (WHAT)
              │             │
              │             │   SKILL.md files
              │             │   domain knowledge, workflows
              │             │   loaded on demand
              │
              └──────────── Execution (HOW)
                            │
                            │   MCP servers
                            │   scoped tool access
                            │   isolated per war-room
```

**Identity** is stable — an architect role always reasons like an architect. **Expertise** is swappable — the same architect can load Unity skills or web skills. **Execution** is isolated — each war-room gets its own tool sandbox.

## Core Flow

Every OSTwin run follows the same pipeline:

```
PLAN.md → Parse → DAG → Schedule Waves → Spawn War-Rooms → Execute → Report
                   │         │                  │
                   │    Topological sort    Each room gets:
                   │    into parallel       - channel.jsonl
                   │    waves               - progress.json
                   │                        - status file
                   ▼                        - memory ledger
              Dependencies                  - lifecycle.json
              between epics
```

1. The **Engine** (`Engine.ps1`) parses your `PLAN.md` into structured epics
2. A **DAG** resolves dependencies between epics and sorts them into execution waves
3. Each epic gets a **War-Room** — an isolated directory with its own coordination files
4. **Agents** are composed at runtime (Role + Skills + MCP tools) and execute inside their war-room
5. A **lifecycle state machine** governs each room's progress: `developing → review → fixing → passed/failed`

## Key Design Decisions

:::note[Why these choices?]
Every design decision in OSTwin optimizes for one thing: **letting AI agents collaborate reliably at scale without custom code**.
:::

- **Filesystem coordination** — JSONL channels, JSON status files, markdown plans. No database required. Git-friendly. Every agent can read/write with basic file I/O.
- **Scale on depth, not width** — Instead of many shallow agents, OSTwin uses fewer agents with deep skill injection. Quality over quantity.
- **Config over code** — Agents are defined by `role.json` + `ROLE.md` + `SKILL.md`, not Python classes. Non-engineers can modify agent behavior.
- **Ephemeral agents** — No persistent agent processes. Each session is composed fresh from its role, skills, and tools. No state leaks between runs.

## System Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Engine** | PowerShell | Parses plans, builds DAG, orchestrates war-rooms, manages lifecycle |
| **Dashboard** | FastAPI + Next.js | Real-time monitoring, plan status, war-room inspection, memory search |
| **Bot** | TypeScript | Conversational interface for plan management and agent interaction |
| **MCP Servers** | Python (FastAPI) | Tool providers scoped per war-room — filesystem, memory, channel ops |
| **Skills** | Markdown (`SKILL.md`) | Portable domain expertise loaded into agent context on demand |
| **Roles** | JSON + Markdown | Agent identity definitions — personality, constraints, allowed skills |

## What OSTwin is NOT

- **Not an agent framework** — You don't write agents. You write plans and roles.
- **Not a prompt chain** — Agents make autonomous decisions within their war-room scope.
- **Not a wrapper around one LLM** — Provider-agnostic. Works with Anthropic, OpenAI, Google, or local models.
- **Not a chatbot** — There is no conversational loop. Plans go in, artifacts come out.

## Who is OSTwin For?

- **Teams using AI for software engineering** — automate entire feature development cycles
- **Platform engineers** — build internal tooling around composable agent primitives
- **AI researchers** — experiment with multi-agent coordination without framework lock-in
- **Solo developers** — get an entire engineering team (architect, engineer, QA) from a single plan file

:::tip
The fastest way to evaluate OSTwin is the [Quick Start](/getting-started/quick-start/). You'll have a running plan in under 5 minutes.
:::

## Next Steps

Ready to install? Head to [Installation](/getting-started/installation/) to get OSTwin running locally.
