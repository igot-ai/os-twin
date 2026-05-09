# Plan: OSTwin System Documentation & Design Improvement

> Created: 2026-05-08
> Status: draft
> Author: technical-writer

## Config

working_dir: .

## Goal

Compose a comprehensive, authoritative documentation suite for every component in the OSTwin system, and identify + plan design improvements that address the architectural gaps revealed by cross-component analysis.

## Problem Statement

OSTwin has grown organically into a powerful orchestration system with 15+ subsystems. While individual component docs exist (architecture-overview.md, mcp-isolation.md, memory.md, agentic-memory.md, etc.), there are critical gaps:

1. **No unified component reference** -- each doc is a standalone pillar description, but there's no map showing how all 15 subsystems interconnect.
2. **Dual memory systems are undocumented as a pair** -- Layered Memory (ledger.jsonl) and Agentic Memory (.memory/) coexist but their relationship, data flow, and overlap are only partially addressed by the bridge index.
3. **Knowledge Service is undocumented at the pillar level** -- dashboard/knowledge/ is a 20-file subsystem with namespace management, ingestion pipelines, GraphRAG query engine, MCP server, bridge index, and retention sweeper -- but it has no top-level doc.
4. **Design gaps between components** -- embedding model fragmentation (gemini-embedding-001 vs BAAI/bge-base-en-v1.5), vector store duplication (two Zvec instances), MCP server proliferation (5+ servers), poll-based architecture without event bus, and no systematic token budget tracking.
5. **No deployment/runbook documentation** -- how to operate the system in production, debug stuck rooms, monitor health, or handle failures.

## Architecture: Component Dependency Map

```
                              PLAN.md
                                |
                 +--------------+--------------+
                 v              v              v
          Start-Plan.ps1  Build-DAG.ps1  Expand-Plan.ps1
                 |              |
                 v              v
         +-----------------------------+
         |        DAG.json             |
         +----------+------------------+
                    |
          +---------+---------+
          v         v         v
      room-001  room-002  room-N    <-- War-Rooms (filesystem state)
          |         |         |
          v         v         v
    +----------- Manager Loop -------------+
    |  polls rooms, spawns workers,        |
    |  enforces lifecycle, tracks retries  |
    +--+---------+---------+---------+----+
       v         v         v
   Engineer   QA      Architect     <-- Roles (Zero-Agent Pattern)
       |         |         |
       v         v         v
   Invoke-Agent.ps1 (universal runner)
       |
       +-- Resolve-Role.ps1 (5-tier discovery)
       +-- Build-SystemPrompt.ps1 (identity + capabilities + gates)
       +-- Resolve-RoleSkills.ps1 (3-tier skill resolution)
       |
       +-- MCP Config Resolution --> opencode.json (per-room)
       |   +-- channel-server.py
       |   +-- warroom-server.py
       |   +-- memory-server.py (.agents/memory/)
       |   +-- knowledge-mcp-server (dashboard/knowledge/)
       |   +-- mcp-proxy.py (audit wrapper)
       |
       +-- OpenCode CLI Process
           +-- Reads ~/.config/opencode/agents/<role>.md
           +-- Connects to MCP servers from opencode.json
           +-- Discovers skills from AGENT_OS_SKILLS_DIR
           +-- Executes task, writes artifacts, posts to channel

    +=================================================+
    |            MEMORY & KNOWLEDGE LAYER              |
    +=================================================+
    |                                                  |
    |  Layer 1: Conversation (channel.jsonl per-room)  |
    |                                                  |
    |  Layer 2: Code Artifacts (brief.md, TASKS.md,    |
    |           artifacts/, contexts/)                  |
    |                                                  |
    |  Layer 3a: Shared Ledger (ledger.jsonl)          |
    |            BM25 + time-decay, cross-room          |
    |            .agents/memory/ledger.jsonl            |
    |                                                  |
    |  Layer 3b: Agentic Memory (.memory/)             |
    |            Vector search + auto-linking,          |
    |            project-level persistence              |
    |            .agents/memory/mcp_server.py           |
    |                                                  |
    |  Layer 4: Knowledge Service (dashboard/)          |
    |            Namespaces + ingestion + GraphRAG      |
    |            dashboard/knowledge/                   |
    |                                                  |
    |  Bridge: SQLite backlink index                   |
    |          (namespace, file_hash, chunk) -> note_id |
    |          dashboard/knowledge/bridge.py            |
    |                                                  |
    +=================================================+

    +=================================================+
    |            DASHBOARD & BOT LAYER                 |
    +=================================================+
    |                                                  |
    |  FastAPI Backend (dashboard/)                    |
    |  +-- 15+ route modules (plans, rooms, skills,    |
    |  |   roles, memory, knowledge, MCP, settings)    |
    |  +-- KnowledgeService (namespace + ingest + query)|
    |  +-- PlanAgent (AI plan refinement)              |
    |  +-- Background tasks (room polling, SSE events) |
    |  +-- Prometheus metrics                          |
    |                                                  |
    |  Next.js Frontend (dashboard/fe/)                |
    |  +-- React 19 + Tailwind 4 + zustand            |
    |  +-- DAG visualization, epic cards, channel view |
    |  +-- Role/skill browsers, knowledge management   |
    |                                                  |
    |  Bot (bot/)                                      |
    |  +-- Connector architecture (Tg/Dc/Slack)        |
    |  +-- Shared command registry (COMMAND_REGISTRY)  |
    |  +-- Agent bridge (Gemini AI Q&A)                |
    |  +-- Notification router (WebSocket -> platforms) |
    |                                                  |
    +=================================================+
```

## Design Gaps & Improvement Opportunities

### GAP-1: Dual Memory System Integration

**Current State**: Layered Memory (ledger.jsonl with BM25) and Agentic Memory (.memory/ with vector search) are separate systems. The Bridge index (bridge.py) exists but is opt-in (`OSTWIN_KNOWLEDGE_MEMORY_BRIDGE=0` by default) and only provides reverse lookup from knowledge chunks to memory notes.

**Problem**: Agents must decide which memory system to query. Information is duplicated across both. No unified search spans both.

**Proposed Improvement**:
- Unified memory facade that searches both systems with result merging
- Bidirectional bridge (currently only knowledge->memory; add memory->knowledge)
- Auto-promotion: high-retrieval-count notes in Agentic Memory get published to the shared ledger for cross-room propagation
- Deprecation path: consolidate toward Agentic Memory as the primary, with Layered Memory as the ephemeral cross-room broadcast channel

### GAP-2: Embedding Model Fragmentation

**Current State**:
- Agentic Memory: `gemini-embedding-001` (768-dim via Gemini API)
- Knowledge Service: `BAAI/bge-base-en-v1.5` (768-dim via sentence-transformers or Ollama)

**Problem**: Two different embedding models means vectors from one system cannot be compared with vectors from the other. Dimension matching is coincidental (both 768) but the vector spaces are different.

**Proposed Improvement**:
- ADR for a single embedding model across both systems
- Configuration unification: `MasterSettings.knowledge.embedding_model` should also govern Agentic Memory embeddings
- Migration path for existing namespaces created with the old model

### GAP-3: Vector Store Duplication

**Current State**:
- Agentic Memory: `.memory/vectordb/memories/` (Zvec)
- Knowledge Service: `~/.ostwin/knowledge/{ns}/vectors/` (Zvec per namespace)
- Knowledge Service: `~/.ostwin/knowledge/{ns}/graph.db` (KuzuDB per namespace)

**Problem**: Two separate Zvec instances with different schemas, different locking semantics. Agentic Memory has 30s lock retry; Knowledge Service has thread-safe centralized cache. No shared infrastructure.

**Proposed Improvement**:
- Shared vector store abstraction layer
- Common lock management (centralize the Zvec lock-retry pattern from Agentic Memory into a shared module)
- Optional: merge Agentic Memory's vectordb into a knowledge namespace for unified search

### GAP-4: MCP Server Proliferation

**Current State**: 5+ MCP servers (channel, warroom, memory, knowledge, proxy), each with its own Python process.

**Problem**: Each MCP server adds ~2-3K tokens to the tool catalog. Multiple servers mean multiple process lifecycles to manage. No shared health checking.

**Proposed Improvement**:
- MCP server consolidation strategy (keep functional separation but share process where possible)
- Health check endpoint aggregation
- Per-server token budget tracking and reporting
- Implement the planned `mcp_allowed_servers` per-role allowlist (infrastructure already exists)

### GAP-5: Poll-Based Architecture

**Current State**:
- Manager loop polls filesystem every 5 seconds
- Dashboard polls war-room directories every 1 second
- Bot receives push events from dashboard via WebSocket

**Problem**: 1-second polling on the dashboard is expensive. No event propagation from filesystem changes to interested consumers without polling.

**Proposed Improvement**:
- Filesystem watcher (watchdog/inotify) for war-room status changes
- Event bus for internal events (room state changed, message posted, namespace updated)
- Dashboard subscribes to events instead of polling
- Manager loop subscribes to events for faster dependency gating

### GAP-6: No Token Budget Accounting

**Current State**: System prompt, skills, MCP tool catalogs, predecessor context, and memory injection all consume token budget, but there's no systematic tracking or enforcement.

**Problem**: Agents can hit context window limits silently. The 100KB system prompt warning is the only guardrail.

**Proposed Improvement**:
- Token budget calculator that estimates total context before agent launch
- Per-component budget allocation (system prompt: X tokens, MCP tools: Y tokens, skills: Z tokens)
- Warning when budget exceeds 80% of model context window
- Hard block when budget exceeds 95%

### GAP-7: No Production Operations Guide

**Current State**: Developer context doc exists but focuses on dev-mode usage. No runbooks for production operation.

**Problem**: No guidance on debugging stuck rooms, monitoring system health, handling MCP server failures, or performing maintenance.

**Proposed Improvement**:
- Operations runbook for common failure modes
- Health check aggregation endpoint
- Monitoring dashboard with key metrics (room status distribution, MCP call latency, memory usage)
- Incident response playbook

---

## Epics

### EPIC-001 -- Engine Core Documentation
Roles: technical-writer
Objective: Document the PowerShell orchestration engine comprehensively

#### Definition of Done
- [ ] All 9 key engine scripts documented with flow diagrams
- [ ] Manager loop lifecycle fully described with state transitions
- [ ] DAG construction algorithm (Kahn's) documented with examples
- [ ] Error handling and retry logic documented

#### Acceptance Criteria
- [ ] New developer can trace a plan from PLAN.md to room completion
- [ ] All script interdependencies mapped
- [ ] Configuration resolution chains documented for each subsystem

depends_on: []

### EPIC-002 -- War-Room Architecture Documentation
Roles: technical-writer
Objective: Document war-room isolation, lifecycle, and coordination

#### Definition of Done
- [ ] Room creation flow documented end-to-end
- [ ] All 12+ room files described with schemas
- [ ] Channel message protocol fully specified
- [ ] Multi-agent collaboration patterns documented
- [ ] Room teardown and archiving documented

#### Acceptance Criteria
- [ ] config.json schema documented with all fields
- [ ] lifecycle.json state machine documented with all transitions
- [ ] Isolation guarantees enumerated with enforcement mechanisms

depends_on: ["EPIC-001"]

### EPIC-003 -- Roles & Zero-Agent Pattern Documentation
Roles: technical-writer
Objective: Document the zero-code role system and 5-tier discovery

#### Definition of Done
- [ ] role.json schema documented with all fields
- [ ] ROLE.md format and best practices documented
- [ ] 5-tier discovery chain documented with resolution examples
- [ ] Model resolution priority chain documented
- [ ] Dynamic role creation flow documented

#### Acceptance Criteria
- [ ] New role can be added by following the documentation alone
- [ ] All 20+ roles cataloged with their skill_refs and capabilities
- [ ] Capability-based matching algorithm described

depends_on: ["EPIC-001"]

### EPIC-004 -- Skills System Documentation
Roles: technical-writer
Objective: Document the skills architecture, resolution, and marketplace

#### Definition of Done
- [ ] SKILL.md format documented with all frontmatter fields
- [ ] 3-tier resolution chain documented
- [ ] Platform and enabled gating documented
- [ ] Skill-to-room injection flow documented
- [ ] ClawHub marketplace API documented

#### Acceptance Criteria
- [ ] New skill can be created by following the documentation
- [ ] Skill search directories enumerated
- [ ] Runtime skill injection path traced from plan to agent

depends_on: ["EPIC-003"]

### EPIC-005 -- MCP Isolation & Configuration Documentation
Roles: technical-writer
Objective: Document the MCP isolation architecture and configuration resolution

#### Definition of Done
- [ ] 4-tier MCP config resolution chain documented
- [ ] Vault-based secret resolution documented
- [ ] no_mcp flag and per-room config generation documented
- [ ] All built-in MCP servers cataloged
- [ ] Audit logging format documented
- [ ] Future per-server allowlist design documented

#### Acceptance Criteria
- [ ] New MCP server can be added by following the documentation
- [ ] Token budget impact table complete
- [ ] Config resolution traceable from template to runtime

depends_on: ["EPIC-001"]

### EPIC-006 -- Memory System Unified Documentation
Roles: technical-writer
Objective: Document both memory systems as a unified architecture with bridge integration

#### Definition of Done
- [ ] Layered Memory (ledger.jsonl) fully documented
- [ ] Agentic Memory (.memory/) fully documented
- [ ] Bridge index documented with bidirectional lookup
- [ ] Memory isolation via filtering documented
- [ ] Relevance scoring (BM25 + time decay) documented
- [ ] Concurrency model (multi-agent access) documented
- [ ] Data flow diagram showing both systems and their interconnection

#### Acceptance Criteria
- [ ] Clear answer to "which memory system should an agent use and when"
- [ ] All 14 MCP tools documented with arguments and return types
- [ ] Memory bounds table complete with enforcement locations
- [ ] Auto-sync mechanism documented with timing guarantees

depends_on: ["EPIC-001", "EPIC-005"]

### EPIC-007 -- Knowledge Service Documentation
Roles: technical-writer
Objective: Document the dashboard knowledge subsystem comprehensively

#### Definition of Done
- [ ] Namespace lifecycle documented (CRUD, retention, backup/restore)
- [ ] Ingestion pipeline documented (folder walk, parse, chunk, embed, graph)
- [ ] Query engine documented (raw/graph/summarized modes)
- [ ] GraphRAG architecture documented (KuzuDB + PageRank + entity extraction)
- [ ] MCP server tools documented
- [ ] Metrics and monitoring documented
- [ ] Bridge index documented (reverse lookup from chunks to memory notes)

#### Acceptance Criteria
- [ ] New namespace can be created and populated by following the docs
- [ ] All 20 files in dashboard/knowledge/ described
- [ ] Query mode comparison table complete
- [ ] Embedding dimension mismatch error documented with fix

depends_on: ["EPIC-006"]

### EPIC-008 -- Dashboard Architecture Documentation
Roles: technical-writer
Objective: Document the FastAPI backend + Next.js frontend

#### Definition of Done
- [ ] All 15+ route modules cataloged with endpoints
- [ ] Frontend architecture documented (React 19, Tailwind 4, zustand stores)
- [ ] SSE/WebSocket event system documented
- [ ] Background task polling documented
- [ ] Settings management documented (MasterSettings, ADR-15)
- [ ] Dev mode vs build mode documented with caveats

#### Acceptance Criteria
- [ ] New API endpoint can be added by following the docs
- [ ] Frontend component structure described
- [ ] Dashboard project-dir resolution documented for source mode

depends_on: ["EPIC-007"]

### EPIC-009 -- Bot & Connectors Documentation
Roles: technical-writer
Objective: Document the multi-platform bot architecture

#### Definition of Done
- [ ] Connector interface documented
- [ ] ConnectorRegistry lifecycle documented
- [ ] Command routing flow documented
- [ ] Platform-specific response translation documented
- [ ] Session management documented
- [ ] Notification router documented
- [ ] All 30+ commands cataloged

#### Acceptance Criteria
- [ ] New connector can be added by following the docs
- [ ] New command can be added by following the docs
- [ ] Platform differences (message limits, formatting) tabulated

depends_on: ["EPIC-008"]

### EPIC-010 -- Plan/Epic/DAG System Documentation
Roles: technical-writer
Objective: Document the plan management and dependency graph system

#### Definition of Done
- [ ] Plan markdown format documented with all directives
- [ ] Epic structure (DoD, AC, Tasks) documented
- [ ] DAG construction algorithm documented
- [ ] Two-stage DAG generation (advisory vs solid) documented
- [ ] Dependency gating mechanism documented
- [ ] Progress tracking documented

#### Acceptance Criteria
- [ ] New plan can be written by following the docs
- [ ] DAG.json structure documented with all fields
- [ ] Wave execution and critical path explained

depends_on: ["EPIC-001"]

### EPIC-011 -- OpenCode Integration Documentation
Roles: technical-writer
Objective: Document the OpenCode runtime integration

#### Definition of Done
- [ ] Agent execution flow documented (role -> prompt -> MCP -> skills -> task)
- [ ] MCP config compilation pipeline documented
- [ ] Role sync mechanism documented
- [ ] Skill resolution at runtime documented
- [ ] Lifecycle pipeline generation documented
- [ ] Verification checklist documented

#### Acceptance Criteria
- [ ] Setup can be verified by following the docs
- [ ] MCP config compilation traceable from source to runtime
- [ ] All verification steps documented with expected outputs

depends_on: ["EPIC-005"]

### EPIC-012 -- Design Improvement: Unified Memory Facade
Roles: architect, engineer
Objective: Design and implement a unified memory search across Layered Memory + Agentic Memory + Knowledge Service

#### Definition of Done
- [ ] ADR for unified memory architecture
- [ ] Unified search API that queries all three memory systems
- [ ] Result merging with source attribution
- [ ] Bidirectional bridge (knowledge <-> memory, not just knowledge->memory)
- [ ] Auto-promotion rules for high-value memories
- [ ] Migration guide for existing deployments

#### Acceptance Criteria
- [ ] Single search query returns results from all systems
- [ ] Results tagged with source system (ledger/agentic/knowledge)
- [ ] Bridge bidirectional: memory notes can reference knowledge chunks and vice versa
- [ ] No performance regression for individual system queries

depends_on: ["EPIC-006", "EPIC-007"]

### EPIC-013 -- Design Improvement: Embedding Model Unification
Roles: architect, engineer
Objective: Unify embedding models across Memory and Knowledge systems

#### Definition of Done
- [ ] ADR for embedding model selection (one model for both systems)
- [ ] Configuration unification (MasterSettings governs both)
- [ ] Migration tool for re-embedding existing namespaces
- [ ] Dimension mismatch detection and auto-migration
- [ ] Rollback procedure if migration fails

#### Acceptance Criteria
- [ ] Same embedding model used by Agentic Memory and Knowledge Service
- [ ] Existing namespaces can be migrated without data loss
- [ ] Settings change takes effect without restart

depends_on: ["EPIC-012"]

### EPIC-014 -- Design Improvement: Event-Driven Architecture
Roles: architect, engineer
Objective: Replace poll-based patterns with event-driven architecture

#### Definition of Done
- [ ] ADR for event bus selection (in-process vs external)
- [ ] Filesystem watcher for war-room status changes
- [ ] Event types defined (room_state_changed, message_posted, namespace_updated)
- [ ] Dashboard subscribes to events instead of polling
- [ ] Manager loop uses events for dependency gating
- [ ] Backward-compatible: polling still works as fallback

#### Acceptance Criteria
- [ ] Room state change propagates to dashboard in <1 second (vs current 1s poll)
- [ ] Manager loop reacts to dependency resolution immediately (vs 5s poll)
- [ ] No events lost during high load
- [ ] Graceful degradation when event bus is unavailable

depends_on: ["EPIC-001", "EPIC-008"]

### EPIC-015 -- Design Improvement: Token Budget Accounting
Roles: architect, engineer
Objective: Implement systematic token budget tracking and enforcement

#### Definition of Done
- [ ] Token budget calculator for agent launch
- [ ] Per-component budget allocation (system prompt, MCP tools, skills, memory)
- [ ] Warning when budget exceeds 80% of context window
- [ ] Hard block when budget exceeds 95%
- [ ] Dashboard visualization of token budgets per room
- [ ] Historical tracking for budget optimization

#### Acceptance Criteria
- [ ] Agent launch logs estimated token budget
- [ ] Over-budget agents get truncated skills or reduced MCP access
- [ ] Dashboard shows token budget per room
- [ ] No agent hits context limit silently

depends_on: ["EPIC-005", "EPIC-006"]

### EPIC-016 -- Operations Runbook
Roles: technical-writer, sre-lead
Objective: Create production operations documentation

#### Definition of Done
- [ ] Debugging guide for stuck rooms
- [ ] MCP server failure recovery procedures
- [ ] Memory system maintenance (cleanup, re-index, backup)
- [ ] Knowledge namespace management (retention, backup, migration)
- [ ] Health check aggregation endpoint documented
- [ ] Monitoring dashboard key metrics documented
- [ ] Incident response playbook for common failures

#### Acceptance Criteria
- [ ] Operator can debug a stuck room by following the runbook
- [ ] Operator can recover from MCP server crash
- [ ] Operator can migrate a knowledge namespace to new embedding model
- [ ] All health check endpoints documented

depends_on: ["EPIC-006", "EPIC-007", "EPIC-008"]
