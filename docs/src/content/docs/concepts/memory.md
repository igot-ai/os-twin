---
title: "Pillar 5: Structured Memory"
description: "Three-layer memory architecture that gives agents cross-room context without breaking isolation."
sidebar:
  order: 5
  icon: rocket
---

OSTwin's fifth pillar addresses the fundamental challenge of multi-agent systems: **how do agents share knowledge without breaking isolation?** The answer is a three-layer memory architecture where each layer serves a different scope and lifetime.

The memory server is intentionally lightweight — its structured entries are compact enough to run as a **single global MCP server** shared by all agents across every plan and war-room. Instead of spinning up per-room memory instances, one MCP memory server serves the entire project, providing a unified knowledge surface that agents query and publish to in real time.

## Three Memory Layers

```
┌─────────────────────────────────────────────────────┐
│  Layer 3: Shared Ledger (ledger.jsonl)              │
│  Cross-room knowledge: decisions, interfaces,       │
│  conventions, warnings. Queryable by all rooms.     │
├─────────────────────────────────────────────────────┤
│  Layer 2: Code Artifacts                            │
│  Files produced by agents: source code, configs,    │
│  tests. Live in war-room artifacts/ directory.      │
├─────────────────────────────────────────────────────┤
│  Layer 1: Conversation (channel.jsonl)              │
│  Per-room message log. Task assignments, done       │
│  reports, reviews, verdicts. Room-scoped.           │
└─────────────────────────────────────────────────────┘
```

### Layer 1: Conversation Memory

The `channel.jsonl` file in each war-room captures every inter-agent message. This is the agent's short-term, task-specific memory. It answers: "What has happened in this room so far?"

- **Scope**: Single war-room
- **Lifetime**: Duration of the room's execution
- **Access**: Only agents within the room

### Layer 2: Code Artifacts

Files in the war-room's `artifacts/` directory represent durable work product. Source code, configuration files, test results, and reports all live here.

- **Scope**: Single war-room (but committed to the repo)
- **Lifetime**: Permanent (survives room completion)
- **Access**: All agents via filesystem, post-merge via git

### Layer 3: Shared Ledger

The `ledger.jsonl` file is the cross-room knowledge base. When an agent makes a decision, defines an interface, or discovers a convention, it publishes to the ledger so other rooms can benefit.

- **Scope**: All war-rooms in the project
- **Lifetime**: Permanent (soft-delete only)
- **Access**: All agents via `memory_query` and `memory_search` tools

## Entry Structure

Each ledger entry follows this JSON structure:

```json
{
  "id": "mem-a1b2c3d4",
  "ts": "2025-01-15T10:30:00Z",
  "kind": "decision",
  "room_id": "room-042",
  "author_role": "architect",
  "ref": "EPIC-007",
  "tags": ["auth", "database", "users-table"],
  "summary": "Chose bcrypt over argon2 for password hashing due to broader library support in Python 3.11",
  "detail": "Evaluated bcrypt, argon2, and scrypt. Argon2 is theoretically stronger but requires the argon2-cffi package which has C compilation issues on Alpine. Bcrypt with work factor 12 meets OWASP recommendations.",
  "supersedes": null
}
```

## Entry Kinds

The `kind` field categorizes memories for filtered retrieval:

| Kind | Purpose | Example |
|------|---------|---------|
| `artifact` | "I created/modified files X, Y, Z" | New API endpoint added at `/api/v1/auth` |
| `decision` | "I chose approach A over B because..." | Selected PostgreSQL over MongoDB for ACID compliance |
| `interface` | "Module X exports function Y with signature Z" | `AuthService.verify(token: str) -> User` |
| `convention` | "All code follows pattern X" | All API endpoints use `/api/v1/` prefix |
| `warning` | "Don't do X, it breaks Y" | Don't modify `config.py` -- it has circular import fragility |
| `code` | Code snippets and implementation details | Helper function for JWT validation |

## Memory Isolation via Filtered Views

The key innovation is **filtered views**. When an agent queries the ledger, it sees memories from **all other rooms** but not its own:

```
// Agent in room-042 queries for auth-related memories
results = memory_query(
    tags=["auth"],
    exclude_room="room-042"  // Don't show my own entries
)
```

:::tip[Why Exclude Self?]
An agent already has its own conversation history in `channel.jsonl`. Showing its own ledger entries would be redundant. Excluding self ensures the agent sees only genuinely new information from other rooms.
:::

This design means:

- Room-042 (auth) can see decisions made by room-038 (database schema)
- Room-038 cannot accidentally see room-042's in-progress work
- Each room gets a **curated view** of cross-room knowledge relevant to its needs

## BM25 + Time Decay Scoring

The `memory_search` tool uses BM25 text matching combined with exponential time decay:

```
score(entry) = BM25(query, entry.summary + entry.tags) × decay(entry.ts)

decay(ts) = exp(-λ × age_hours)
```

Where `λ` varies by entry kind, giving different half-lives:

| Kind | Half-Life | Rationale |
|------|-----------|-----------|
| `convention` | 720 hours (30 days) | Conventions stay relevant long-term |
| `interface` | 480 hours (20 days) | Interfaces are durable but may evolve |
| `decision` | 336 hours (14 days) | Decisions matter most when fresh |
| `artifact` | 168 hours (7 days) | Artifacts are quickly superseded |
| `warning` | 168 hours (7 days) | Warnings are time-sensitive |
| `code` | 72 hours (3 days) | Code snippets become stale quickly |

:::note[Recency Bias]
The time decay intentionally biases toward recent entries. In a fast-moving multi-agent project, a decision made yesterday is far more relevant than one made two weeks ago. The `supersedes` field handles explicit invalidation.
:::

## Memory Bounds

To prevent unbounded growth and token explosion, the memory system enforces limits:

| Bound | Limit | Purpose |
|-------|-------|---------|
| Summary size | 4 KB max | Keeps entries scannable |
| Detail size | 16 KB max | Allows rich content when needed |
| Query results | 50 entries max | Prevents prompt overflow |
| Search results | 10 entries default | Focuses on most relevant |
| Context summary | 15 entries max | Cross-room context stays lean |

## Predecessor Context

When a war-room starts, the manager can inject **predecessor context** -- a curated summary of memories from upstream rooms in the DAG:

```
context = memory_get_context(
    room_id="room-042",
    brief_keywords=["auth", "login", "users"],
    max_entries=15
)
```

This generates a markdown document (~10KB max) containing the most relevant memories from other rooms, filtered by the room's brief keywords. The document is injected into the agent's initial context.

## Plan-Based Memory Connection

Because the MCP memory server is lightweight and global, it connects automatically when a user launches a new plan. The lifecycle works like this:

1. **Plan starts** — The global MCP memory server is already running. No new instance is spawned; the existing server is simply made aware of the new plan's scope (epic IDs, brief keywords, room assignments).

2. **War-rooms spin up** — Each room's manager agent inherits the plan's keyword scope and queries the memory server for predecessor context before issuing its first task.

3. **Development syncs** — As agents in each room publish decisions, interfaces, and warnings, those entries become immediately visible to agents in other rooms via filtered queries. The memory server acts as a real-time synchronization layer across the epic DAG.

4. **Plan completes** — When all war-rooms finish, the accumulated memories persist in the ledger. Future plans can query them as predecessor context, creating a continuous knowledge chain across project iterations.

This means the memory server is never "per-plan" or "per-room" — it is a **single, always-on global service** that accumulates project knowledge over time. Each new plan simply taps into the existing knowledge surface and begins contributing back to it.

## Three Core Operations

### Publish

Write a new entry to the ledger:

```
memory_publish(kind="decision", summary="...", tags=["auth"], ...)
```

### Query

Read entries with structured filters:

```
memory_query(tags=["auth"], kind="interface", last_n=5)
```

### Search

Full-text search with BM25 scoring:

```
memory_search(text="authentication flow", max_results=10)
```

## Soft Delete via Supersedes

Entries are never physically deleted. Instead, a new entry can **supersede** an old one:

```json
{
  "id": "mem-x9y8z7",
  "kind": "decision",
  "summary": "Switched from bcrypt to argon2 after resolving Alpine build issues",
  "supersedes": "mem-a1b2c3d4"
}
```

The superseded entry (`mem-a1b2c3d4`) is excluded from all future queries but remains in the ledger file for audit purposes.

:::caution[Supersedes is One-Way]
Once an entry is superseded, it cannot be un-superseded. If the new decision is itself wrong, publish a third entry that supersedes the second. This creates an auditable chain of decisions.
:::

## Key Source Files

| File | Purpose |
|------|---------|
| `.agents/memory/` | Memory MCP server (publish, query, search) |
| `.agents/ledger.jsonl` | Shared memory ledger |
| `.agents/war-rooms/*/channel.jsonl` | Per-room conversation log |
| `.agents/plan/` | Plan startup and predecessor context generation |
