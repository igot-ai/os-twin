# OS Twin — Tiered Memory Architecture

> Self-learning agents that get smarter over time on YOUR projects.

## The Problem

OS Twin agents are **amnesiac** by default. Every session starts from zero. An engineer agent that spent 2 hours understanding your codebase's payment module forgets everything when the session ends. The next time it touches payments, it re-reads the same files, makes the same wrong assumptions, and wastes the same tokens.

## The Solution

Agents **accumulate expertise** through a three-tier memory system. An agent working on your project for a week is measurably better than one on day one — knowing your conventions, remembering past decisions, avoiding repeated mistakes, and building domain fluency.

## The Three Memory Tiers

```
┌─────────────────────────────────────────────────┐
│  Tier 1: WORKING MEMORY (Core)       IMPLEMENTED│
│  Always loaded. The agent's "RAM."               │
│  ─────────────────────────────────────────────── │
│  • Notes saved by the agent during the session   │
│  • Scoped per role + room                        │
│  Budget: 8,000 chars (~2,000 tokens)             │
├─────────────────────────────────────────────────┤
│  Tier 2: SESSION MEMORY (Episodic)   IMPLEMENTED│
│  Compressed digests of past sessions.            │
│  ─────────────────────────────────────────────── │
│  • LLM-generated summaries of what happened      │
│  • Learnings, decisions, mistakes                │
│  • Domain-tagged, filtered by relevance          │
│  Budget: 30% of memory token budget              │
├─────────────────────────────────────────────────┤
│  Tier 3A: KNOWLEDGE BASE (Facts)     IMPLEMENTED│
│  Persistent atomic facts. Domain-tagged.         │
│  ─────────────────────────────────────────────── │
│  • Codebase conventions & gotchas                │
│  • Past mistakes and correct approaches          │
│  • QA-validated learnings                        │
│  Budget: 70% of memory token budget              │
├─────────────────────────────────────────────────┤
│  Tier 3B: RELATIONSHIP GRAPH              FUTURE│
│  Entity connections for multi-hop reasoning.     │
└─────────────────────────────────────────────────┘
```

---

## Tier 1: Working Memory

**Status:** IMPLEMENTED -- `memory-server.py` (MCP), `Resolve-Memory.ps1`

Working memory is a per-session scratch pad. Agents write notes during a session via MCP tools. Notes are loaded into the system prompt at retrieval time.

**Storage:** `.agents/memory/working/{role}-{room_id}.yml`

Falls back to `{role}.yml` if no room-scoped file exists (legacy path).

**MCP tools** (exposed via `memory-server.py`):

| Tool | Parameters | Description |
|---|---|---|
| `memory_note` | `note`, `domains?`, `is_mistake?` | Append a note. Domains tag it for retrieval. `is_mistake=true` marks it as a correction for priority learning. |
| `memory_drop` | `note_substring` | Remove notes matching the substring. |
| `memory_recall` | `domains?`, `keyword?` | Query the Tier 3 knowledge base. Matches by domain overlap or keyword substring. Results sorted by `confidence * access_count`. |

**Token budget enforcement:** Total note text is capped at 8,000 characters (~2,000 tokens). When the budget is exceeded, the oldest notes are evicted FIFO. The agent receives an `evicted_count` warning in the response.

**Lifecycle:** Working memory is cleared after consolidation at session end.

---

## Tier 2: Session Memory (Episodic)

**Status:** IMPLEMENTED -- `Consolidate-Memory.ps1`

At session end, an LLM generates a structured digest from the agent's output, working notes, room brief, and QA feedback.

**Digest schema** (actual file format):

```yaml
session_id: "room-042-engineer-2026-03-23"
room_id: "room-042"
agent_role: "engineer"
date: "2026-03-23"
domain_tags: ["payments", "webhooks"]
summary: "Implemented Stripe webhook handler with signature verification"
what_happened:
  - "Read existing webhook setup in /src/webhooks/"
  - "Implemented checkout.session.completed handler"
decisions:
  - "Used stripe.webhooks.constructEvent() for verification"
learnings:
  - "This project validates webhook signatures at handler level"
mistakes:
  - "Initially forgot signature verification — caught by QA"
```

**Storage:** `.agents/memory/sessions/{YYYYMMDD}-{room_id}-{role}.yml`

**Retrieval** (in `Resolve-Memory.ps1`):
- Filtered by domain overlap with the current task
- Sorted by date descending, limited to the 3 most recent matching digests
- Only `summary`, `learnings`, and `mistakes` are injected (compact format)
- Budget: 30% of the total memory character budget

**Pruning:** Digests older than `max_session_age_days` (default: 30) are deleted by `Run-MemoryDecay.ps1`.

**Config toggle:** `memory.session_digest_enabled` (default: `true`).

---

## Tier 3: Knowledge Base

### 3A. Fact Store (Atomic Knowledge)

**Status:** IMPLEMENTED -- `Consolidate-Memory.ps1`, `Resolve-Memory.ps1`, `memory-server.py`

Individual facts stored as small YAML files, one per fact.

**Fact schema** (actual file format):

```yaml
fact: "Webhook signature verification happens at handler level, not middleware"
source: "room-042"
source_role: "engineer"
domains: ["payments", "webhooks", "stripe"]
origin: "qa-feedback"
confidence: 0.85
created: "2026-03-23"
last_accessed: "2026-03-23"
access_count: 1
```

**Key fields:**

| Field | Description |
|---|---|
| `origin` | `"qa-feedback"` or `"discovery"`. QA-feedback facts start at confidence 0.85; discovery facts start at 0.70. |
| `confidence` | 0.0-0.99. Boosted +0.15 on re-confirmation from QA feedback, +0.10 from discovery. Capped at 0.99. |
| `access_count` | Incremented each time the fact is retrieved or re-confirmed. Slows decay. |
| `source_role` | Which agent role extracted this fact. |

**Storage:** `.agents/memory/knowledge/{domain}-{slug}.yml`

Slug is auto-generated from the first domain tag and first 5 significant words of the fact text (max 80 chars).

### 3B. Relationship Graph

**Status:** FUTURE -- not implemented. The current system uses flat domain-tagged facts. A graph layer for multi-hop reasoning (e.g., entity-relationship traversal) is a potential future enhancement.

---

## The Memory Lifecycle

```
  ┌──────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────┐
  │ CAPTURE  │ --> │  CONSOLIDATE │ --> │   RETRIEVE    │ --> │  DECAY   │
  │          │     │              │     │               │     │          │
  │ During   │     │ At session   │     │ At session    │     │ After    │
  │ session  │     │ end          │     │ start         │     │ consol.  │
  └──────────┘     └──────────────┘     └───────────────┘     └──────────┘
```

### Phase 1: Capture (During Session)

**Implementation:** `memory-server.py` MCP tools

Agents call `memory_note()` when they discover something worth remembering. The `is_mistake` flag marks corrections for priority learning.

QA feedback is captured separately -- the consolidation phase extracts it from `channel.jsonl` (see Phase 2).

### Phase 2: Consolidate (At Session End)

**Implementation:** `Consolidate-Memory.ps1`

Runs automatically after an agent session ends. Steps:

1. **Gather inputs**: agent output (last 5,000 chars), working notes, room brief
2. **Extract QA feedback**: Scans `channel.jsonl` for messages from the `qa` role or containing `PASS`/`FAIL` verdicts (last matching message, max 2,000 chars)
3. **LLM extraction**: Sends all inputs to a lightweight model (`consolidation_model`, default: `gemini-3-flash-preview`) to extract atomic facts as YAML
4. **Origin tagging**: The LLM is instructed to tag facts derived from QA feedback or mistake corrections with `origin: qa-feedback`; others get `origin: discovery`
5. **Dedup and merge** against existing knowledge:
   - Word-overlap similarity >= 50% with matching domains = existing fact
   - Match found: bump confidence (+0.15 for qa-feedback, +0.10 for discovery), increment access_count, update last_accessed
   - No match: create new fact file (confidence 0.85 for qa-feedback, 0.70 for discovery)
6. **Generate session digest** (Tier 2): A second LLM call produces the structured digest YAML
7. **Clear working memory**: Delete the role's working memory file
8. **Trigger decay**: Calls `Run-MemoryDecay.ps1`

### Phase 3: Retrieve (At Session Start)

**Implementation:** `Resolve-Memory.ps1`, called from `Build-SystemPrompt.ps1`

Assembles an `## Agent Memory` section for the system prompt:

1. **Extract task domains** from the war room:
   - First: check `config.json` in the room directory for explicit `domains` array
   - Fallback: scan `brief.md` text against a vocabulary built dynamically from all existing knowledge base domain tags
2. **Load working notes** (Tier 1): Parse `{role}-{room_id}.yml`, format as bullet list
3. **Load knowledge facts** (Tier 3A): Filter by domain overlap, sort by `confidence * access_count` descending, select within 70% of the character budget
   - QA-feedback facts are prefixed with a warning marker in the output
   - Access tracking is updated (last_accessed, access_count) for retrieved facts
4. **Load session digests** (Tier 2): Filter by domain overlap, sort by date descending, take top 3, select within 30% of the character budget
5. **Return** the composed markdown section

### Phase 4: Decay (After Consolidation)

**Implementation:** `Run-MemoryDecay.ps1`

Called at the end of every consolidation run. Two operations:

**Knowledge fact decay** (Ebbinghaus forgetting curve):
```
retention = e^(-days_since_last_access / (access_count * decay_constant))
```
- `decay_constant`: configurable (default: 7.0 days)
- `retention_threshold`: configurable (default: 0.2)
- Facts below the threshold are moved to `.agents/memory/pruned/` (not deleted)
- High access_count = slower decay; low access_count + old = fast decay

**Session digest pruning:**
- Digests older than `max_session_age_days` (default: 30) are deleted

---

## Self-Learning Mechanisms

### 1. QA Feedback Extraction

The consolidation pipeline scans `channel.jsonl` for QA review messages. Facts derived from QA feedback get:
- `origin: qa-feedback` tag
- Higher initial confidence (0.85 vs 0.70)
- Larger confidence boost on re-confirmation (+0.15 vs +0.10)
- Visual marker in retrieval output (prefixed with warning indicator)

This means QA-validated learnings are surfaced more prominently and persist longer than casual observations.

### 2. Mistake-Driven Learning

Agents can flag notes with `is_mistake=true` via `memory_note()`. During consolidation, the LLM is instructed to identify mistakes and mark them with `origin: qa-feedback` for priority treatment.

The result: mistakes caught in session N surface as high-confidence warnings in session N+1 for the same domain.

### 3. Cross-Agent Knowledge Transfer

The knowledge base is **shared** across all agent roles. Facts include `source_role` to track provenance, but retrieval is role-agnostic -- an engineer's discovery benefits the QA agent and vice versa.

### 4. Agent Instructions

`Build-SystemPrompt.ps1` injects a "How to use memory effectively" guide into every agent's system prompt when memory is enabled:

1. At task START, call `memory_recall` with relevant domains
2. Pay special attention to QA-feedback facts
3. Save discoveries immediately with `memory_note`
4. Tag domains accurately for future discoverability

---

## Storage Structure

```
.agents/
├── memory/
│   ├── working/                         # Tier 1
│   │   └── {role}-{room_id}.yml         # Per-agent, per-room working notes
│   │
│   ├── sessions/                        # Tier 2
│   │   └── {YYYYMMDD}-{room_id}-{role}.yml
│   │
│   ├── knowledge/                       # Tier 3A
│   │   └── {domain}-{slug}.yml          # One fact per file
│   │
│   └── pruned/                          # Decayed facts (moved, not deleted)
│       └── {domain}-{slug}.yml
│
├── mcp/
│   └── memory-server.py                 # MCP server (stdio transport)
│
└── config.json                          # Memory config section
```

All files are plain YAML -- human-readable, git-trackable, no database required.

---

## Configuration

Memory settings live in `.agents/config.json` under the `memory` key:

```json
{
  "memory": {
    "enabled": true,
    "consolidation_model": "gemini-3-flash-preview",
    "decay_constant": 7.0,
    "retention_threshold": 0.2,
    "session_digest_enabled": true,
    "max_session_age_days": 30
  }
}
```

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Master switch for the memory system |
| `consolidation_model` | string | `"gemini-3-flash-preview"` | LLM model used for fact extraction and digest generation |
| `decay_constant` | float | `7.0` | Days-based constant in the decay formula. Higher = slower decay. |
| `retention_threshold` | float | `0.2` | Facts with retention below this are pruned |
| `session_digest_enabled` | bool | `true` | Whether to generate Tier 2 session digests |
| `max_session_age_days` | int | `30` | Session digests older than this are deleted |

The consolidation CLI is resolved from `memory.consolidation_cli`, or falls back to `bin/agent`, the role's configured CLI, or `deepagents`.

---

## Implementation Map

| Component | File | Role |
|---|---|---|
| MCP server (agent tools) | `.agents/mcp/memory-server.py` | Provides `memory_note`, `memory_drop`, `memory_recall` |
| Session-end consolidation | `.agents/roles/_base/Consolidate-Memory.ps1` | Extracts facts, generates digests, merges knowledge, clears working memory |
| Session-start retrieval | `.agents/roles/_base/Resolve-Memory.ps1` | Composes memory section for system prompt |
| Decay and pruning | `.agents/roles/_base/Run-MemoryDecay.ps1` | Exponential decay + session age pruning |
| System prompt injection | `.agents/roles/_base/Build-SystemPrompt.ps1` (lines 94-137) | Injects memory tools guide + resolved memory context |
| Configuration | `.agents/config.json` (`memory` section) | All tunable parameters |
