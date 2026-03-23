# OS Twin — Tiered Memory Architecture

> Self-learning agents that get smarter over time on YOUR projects.

## The Problem

Today, OS Twin agents are **amnesiac**. Every session starts from zero. An engineer agent that spent 2 hours understanding your codebase's payment module forgets everything when the session ends. The next time it touches payments, it re-reads the same files, makes the same wrong assumptions, and wastes the same tokens.

This is like hiring a contractor who forgets everything every Monday morning.

## The Vision

Agents should **accumulate expertise**. An agent working on your project for a week should be measurably better than one working on day one — knowing your conventions, remembering past decisions, avoiding repeated mistakes, and building domain fluency.

## The Three Memory Tiers

Inspired by how computers manage memory (registers → RAM → disk) and how humans remember (working memory → episodic → long-term):

```
┌─────────────────────────────────────────────────┐
│  Tier 1: WORKING MEMORY (Core)                  │
│  Always loaded. Small. The agent's "RAM."        │
│  ─────────────────────────────────────────────── │
│  • Current task brief & acceptance criteria       │
│  • Active project conventions (from rules/)       │
│  • Agent's role definition & active skills        │
│  • Key facts about current work context           │
│  Budget: ~2,000 tokens                            │
├─────────────────────────────────────────────────┤
│  Tier 2: SESSION MEMORY (Episodic)               │
│  Summaries of recent sessions. Searchable.        │
│  ─────────────────────────────────────────────── │
│  • Compressed digests of past war-room sessions   │
│  • What was attempted, what worked, what failed   │
│  • Decisions made and their rationale             │
│  • Key interactions with other agents             │
│  Budget: ~5,000 tokens (retrieved on demand)      │
├─────────────────────────────────────────────────┤
│  Tier 3: KNOWLEDGE BASE (Semantic + Long-term)   │
│  Persistent facts and patterns. Graph-structured. │
│  ─────────────────────────────────────────────── │
│  • Codebase patterns & architecture insights      │
│  • Domain-specific conventions & gotchas          │
│  • Past mistakes and recovery strategies          │
│  • Cross-project learnings                        │
│  Budget: unlimited storage, retrieved selectively │
└─────────────────────────────────────────────────┘
```

---

## Tier 1: Working Memory (Core)

**What:** A small, curated block of text always embedded in the agent's system prompt. Think of it as the agent's "desktop" — only what's immediately needed.

**Contents:**
- Current task objective and constraints
- Project rules relevant to this task (not all rules — only matching ones)
- Agent role definition and currently-activated skills
- A handful of key facts (e.g., "this project uses Drizzle ORM, not Prisma")

**How it works:**
- Loaded at session start from structured files (rules/, skills/, task brief)
- Agent can **self-edit** working memory during a session via explicit tool calls:
  - `memory_note("this module uses event sourcing, not CRUD")` — adds a fact
  - `memory_drop("Prisma migration note")` — removes a stale fact
- Capped at ~2,000 tokens to prevent attention dilution
- At session end, important working memory items are **promoted** to Tier 2 or Tier 3

**Why it matters:** Research shows LLMs pay strongest attention to the system prompt and most recent messages ("lost-in-the-middle" effect). Working memory ensures critical context lives in the highest-attention zone.

---

## Tier 2: Session Memory (Episodic)

**What:** Compressed summaries of past agent sessions — what happened, what was learned, what decisions were made. Like a developer's work journal.

**Contents per session digest:**
```yaml
session_id: "room-042-session-003"
agent: "engineer-01"
project: "payment-service"
date: "2026-03-23"
duration: "45 min"
task: "Implement Stripe webhook handler"
outcome: "completed"

what_happened:
  - Read existing webhook setup in /src/webhooks/
  - Discovered project uses raw Express handlers, not middleware
  - Implemented checkout.session.completed handler
  - QA flagged missing signature verification — fixed

decisions:
  - Used stripe.webhooks.constructEvent() for signature verification
  - Stored webhook events in events table before processing (idempotency)

learnings:
  - "This project validates webhook signatures at the handler level, not middleware"
  - "The events table has a unique constraint on stripe_event_id for idempotency"

mistakes:
  - Initially forgot signature verification — caught by QA
  - First attempt used wrong env var name (STRIPE_SECRET vs STRIPE_WEBHOOK_SECRET)
```

**How it works:**
- At session end, the agent's conversation is **automatically distilled** into a structured digest (LLM-generated summary, not raw transcript)
- Digests are stored as individual files in `.agents/memory/sessions/`
- At session start, the system retrieves the **most relevant** past sessions (not all of them) using:
  - Recency: more recent sessions rank higher
  - Relevance: sessions about the same module/domain rank higher
  - Importance: sessions with mistakes/learnings rank higher than routine work
- Retrieved session digests are injected after the system prompt but before the current task

**Why it matters:** This gives agents **continuity**. The engineer agent working on payments today knows what the engineer agent (or itself) learned about payments last week — without re-discovering everything from scratch.

---

## Tier 3: Knowledge Base (Semantic Long-Term Memory)

**What:** A persistent, structured store of facts, patterns, and conventions that the agent has learned across many sessions. This is the agent's **expertise**.

**Two sub-layers:**

### 3A. Fact Store (Atomic Knowledge)

Individual facts stored as small, searchable records:

```yaml
# .agents/memory/knowledge/payment-webhook-pattern.yml
fact: "Webhook signature verification happens at handler level, not middleware"
source: "room-042-session-003"
domain: "payments, webhooks, stripe"
confidence: 0.95
created: "2026-03-23"
last_accessed: "2026-03-23"
access_count: 1
```

```yaml
# .agents/memory/knowledge/db-convention-timestamps.yml
fact: "All database tables use created_at/updated_at with UTC timestamps, managed by Drizzle"
source: "room-015-session-001"
domain: "database, conventions"
confidence: 0.99
created: "2026-03-15"
last_accessed: "2026-03-22"
access_count: 7
```

Facts are:
- **Created** when session digests contain learnings worth preserving
- **Strengthened** when re-confirmed across multiple sessions (access_count, confidence go up)
- **Decayed** when not accessed for a long time (Ebbinghaus-inspired forgetting curve)
- **Pruned** when contradicted by newer evidence or explicitly invalidated

### 3B. Relationship Graph (Structured Knowledge)

Connections between entities in the project, stored as a lightweight graph:

```
[payment-service] --uses--> [Stripe API]
[payment-service] --stores-events-in--> [events table]
[events table] --has-constraint--> [unique stripe_event_id]
[webhook handlers] --verify-with--> [stripe.webhooks.constructEvent]
[all tables] --managed-by--> [Drizzle ORM]
[all tables] --convention--> [UTC timestamps]
```

This enables **multi-hop reasoning**: "What do I need to know about adding a new webhook handler?" → traverses the graph to find Stripe API patterns, signature verification, events table schema, and Drizzle conventions — all connected.

**How it works:**
- Facts are extracted from session digests during the **consolidation phase** (see Memory Lifecycle below)
- Relationships are inferred from co-occurrence and explicit agent observations
- At session start, the system queries the knowledge base for facts relevant to the current task
- Query strategies (combined for best results):
  - **Keyword match**: task mentions "webhook" → retrieve all webhook-related facts
  - **Semantic similarity**: task is about "handling Stripe events" → finds payment/webhook facts even without exact keyword match
  - **Graph traversal**: starting from matched entities, follow edges to find related knowledge

**Why it matters:** This is what makes agents genuinely **expert** at your codebase. A new agent joining the project gets the accumulated knowledge of every agent that came before — like onboarding docs written by someone who actually did the work.

---

## The Memory Lifecycle

Four phases, inspired by how human memory consolidation works (and validated by OpenAI's reference implementation):

```
  ┌──────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────┐
  │ CAPTURE  │ ──→ │  CONSOLIDATE │ ──→ │   RETRIEVE    │ ──→ │  DECAY   │
  │          │     │              │     │               │     │          │
  │ During   │     │ At session   │     │ At session    │     │ Periodic │
  │ session  │     │ end          │     │ start         │     │ cleanup  │
  └──────────┘     └──────────────┘     └───────────────┘     └──────────┘
```

### Phase 1: Capture (During Session)

As the agent works, it encounters facts worth remembering. Two mechanisms:

- **Explicit**: Agent calls `memory_note()` when it discovers something non-obvious
- **Implicit**: The system monitors agent behavior for signals:
  - Mistakes corrected → "this was wrong, that was right"
  - QA feedback → reviewer-validated learnings
  - Repeated file reads → "agent needed this context, should pre-load next time"
  - Tool errors → "this command doesn't work in this project"

### Phase 2: Consolidate (At Session End)

When a session ends, automatic consolidation runs:

1. **Summarize** the session into a structured digest (Tier 2)
2. **Extract** new facts from the digest
3. **Merge** with existing knowledge:
   - New fact matches existing fact → increase confidence and access_count
   - New fact contradicts existing fact → flag for resolution, keep newer if higher confidence
   - New fact is novel → create new knowledge entry
4. **Update** relationship graph with any new entity connections discovered
5. **Promote** frequently-accessed Tier 2 digests into Tier 3 facts (episodic → semantic)

### Phase 3: Retrieve (At Session Start)

When a new session begins, the system assembles the agent's context:

1. **Load** Tier 1 (working memory): task brief, relevant rules, role definition
2. **Query** Tier 3 (knowledge base): facts relevant to the current task
3. **Fetch** Tier 2 (session memory): recent sessions on the same topic/module
4. **Compose** the context with positional awareness:
   - System prompt: role + rules + retrieved knowledge (high attention zone)
   - Middle: session digests (compressed, summary form)
   - End: current task brief (high attention zone)

### Phase 4: Decay (Periodic)

Not all memories are worth keeping forever. Periodic cleanup prevents knowledge rot:

- **Ebbinghaus forgetting curve**: Facts that haven't been accessed decay over time
  - `retention = e^(-time_since_last_access / (strength * decay_constant))`
  - High access_count = slower decay (well-established facts stick)
  - Low access_count + old = faster decay (one-off observations fade)
- **Contradiction resolution**: When new facts contradict old ones, the old fact's confidence drops. Below a threshold → pruned
- **Staleness check**: Facts tied to files that no longer exist are marked stale
- **Manual override**: Human can always pin (never decay) or delete specific memories

---

## Self-Learning: How Agents Get Smarter

The memory system enables three self-learning mechanisms:

### 1. Mistake-Driven Learning (Reflexion Pattern)

```
Session 1: Agent makes mistake → QA catches it → fix applied
Session 2: Same domain → mistake is in session digest → agent avoids it
Session 5: Pattern consolidated → stored as Tier 3 fact
Session 10+: Fact has high confidence → always retrieved for this domain
```

Example: Agent forgets to add database indexes on foreign keys. QA catches it twice. By session 3, the knowledge base contains: *"Always add indexes on foreign key columns in this project — QA will reject without them."* The agent now proactively adds indexes.

### 2. Convention Discovery (Pattern Extraction)

As agents work across many files, they observe recurring patterns:

```
Session 3:  "Controllers in this project always return { data, error } shape"
Session 7:  "Error handling uses AppError class, not raw Error"
Session 12: "All API routes have rate limiting middleware"
```

These observations accumulate into a rich understanding of project conventions — things that aren't documented anywhere but that every experienced developer "just knows."

### 3. Cross-Agent Knowledge Transfer

When one agent learns something, all agents benefit:

```
Engineer agent discovers: "The CI pipeline fails if you import from @internal/legacy"
    ↓ consolidated into Tier 3
QA agent retrieves this fact → checks for legacy imports in reviews
Architect agent retrieves this fact → avoids legacy dependencies in designs
```

The knowledge base is **shared** across all agent roles within a project. Each agent contributes from its perspective, building a richer collective understanding than any single agent could develop alone.

---

## Storage Structure

```
.agents/
└── memory/
    ├── working/                    # Tier 1: Working memory snapshots
    │   └── {agent_id}.yml          # Current working memory state per agent
    │
    ├── sessions/                   # Tier 2: Session digests
    │   ├── 20260323-room042-s003.yml
    │   ├── 20260322-room041-s001.yml
    │   └── ...
    │
    ├── knowledge/                  # Tier 3A: Atomic facts
    │   ├── payment-webhook-pattern.yml
    │   ├── db-convention-timestamps.yml
    │   ├── ci-legacy-import-ban.yml
    │   └── ...
    │
    ├── graph/                      # Tier 3B: Relationship graph
    │   └── entities.yml            # Entity-relationship definitions
    │
    └── decay.yml                   # Decay schedule and retention scores
```

All files are **plain YAML/Markdown** — human-readable, git-trackable, no database required. This keeps OS Twin local-first and file-based.

---

## How It Fits With Existing OS Twin Architecture

| Existing Component | Memory Integration |
|---|---|
| **War Rooms** (channel.jsonl) | Session transcripts → auto-distilled into Tier 2 digests at room completion |
| **Plans** (markdown epics) | Plan context injected into Tier 1 working memory at session start |
| **Skills** (.agents/skills/) | Skills inform what knowledge domains to retrieve from Tier 3 |
| **Roles** (role definitions) | Role determines which cross-agent knowledge is relevant |
| **QA review cycle** | QA feedback is a high-signal source for mistake-driven learning |
| **Manager agent** | Can query knowledge base to make better task assignment decisions |

---

## Key Design Principles

1. **File-based, no database**: Everything stored as YAML/Markdown in `.agents/memory/`. Git-trackable, human-editable, portable.

2. **Agent-managed, not just system-managed**: Agents actively participate in memory management via `memory_note()` and `memory_drop()` — not just passive consumers of retrieved context.

3. **Forgetting is a feature**: Deliberate decay prevents knowledge rot. Unused memories fade. Contradicted memories are pruned. The system stays clean.

4. **Progressive disclosure**: At session start, load only what's relevant. Don't dump the entire knowledge base into context. Retrieve selectively based on the current task.

5. **Earn trust through verification**: New facts start with moderate confidence. Confidence increases when QA validates, when other agents confirm, or when the fact is re-observed. High-confidence facts are prioritized in retrieval.

6. **Cross-agent, not siloed**: Knowledge is shared across all agents in a project. The engineer's discoveries benefit the QA agent and vice versa.

7. **Human-in-the-loop**: Humans can inspect, edit, pin, or delete any memory. The system is transparent, not a black box.

---

## What Success Looks Like

**Week 1**: Agents work normally. Memory system silently captures session digests and extracts initial facts. Agent performance is baseline.

**Week 2**: Agents start retrieving relevant session history. Fewer repeated mistakes. QA pass rate improves because agents remember past QA feedback.

**Month 1**: Knowledge base has 50-100 facts about the project. Agents understand conventions, common patterns, and known gotchas. New agent sessions start with meaningful context instead of from zero.

**Month 3**: Knowledge base is a genuine asset. It captures institutional knowledge that would otherwise exist only in human developers' heads. Onboarding a new agent role to the project is fast because it inherits the collective knowledge.

**Measurable metrics:**
- Reduction in repeated mistakes (same error across sessions)
- Reduction in tokens spent re-reading the same files
- Increase in QA first-pass rate
- Decrease in session duration for familiar domains
- Growth and quality of knowledge base entries
