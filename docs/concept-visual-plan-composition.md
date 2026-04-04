# OS Twin — Visual Plan Composition

> Plans are the first-class object. Markdown is storage. The UI is the experience.

## The Problem

Today, plans in OS Twin are markdown files. Users write raw text with `## Epic:` headers, then the manager agent parses them. There's no visual understanding of what a plan contains, how EPICs relate, or what the overall shape of work looks like.

This creates three gaps:

1. **Composition gap**: Writing a good plan requires understanding markdown conventions and EPIC structure. No visual feedback during creation.
2. **Comprehension gap**: Reading a 200-line markdown plan doesn't give you an instant picture of the work. You have to mentally parse structure, dependencies, and scope.
3. **Monitoring gap**: Once a plan launches, there's no visual connection between the plan you wrote and the war rooms executing it.

## The Architecture: Three Layers

```
┌─────────────────────────────────────────────────────┐
│  PRESENTATION LAYER  (what user sees & interacts)   │
│  Visual EPIC cards, dependency arrows, live status   │
├─────────────────────────────────────────────────────┤
│  ABSTRACTION LAYER   (structured plan model)        │
│  Plan object → EPICs → tasks, criteria, agents      │
├─────────────────────────────────────────────────────┤
│  PHYSICAL LAYER      (storage format)               │
│  Markdown files, YAML metadata, JSONL channels      │
└─────────────────────────────────────────────────────┘
```

### Physical Layer (Already Exists)

Markdown files in `.agents/plans/` with metadata in `.meta.json` and `.roles.json`. This layer stays — it's portable, git-trackable, and human-readable as a fallback.

### Abstraction Layer (The Structured Plan Model)

The plan isn't just text — it's a structured object:

```
Plan
├── id, title, status, created_at
│
├── EPIC-001
│   ├── title, objective
│   ├── tasks[] (parsed from epic body)
│   ├── acceptance_criteria[]
│   ├── dependencies[] (other EPIC ids)
│   ├── assigned_agent
│   ├── estimated_complexity (S/M/L/XL)
│   ├── status (draft | queued | in-progress | review | done | blocked)
│   ├── room_id (linked war room, once launched)
│   └── progress (tasks done / total)
│
├── EPIC-002
│   ├── ...
│   └── dependencies: [EPIC-001]
│
└── metadata
    ├── total_epics, completed_epics
    ├── dependency_graph (DAG)
    ├── critical_path (longest dependency chain)
    └── agent_assignments
```

This model is **derived from** the markdown (physical layer) but provides structure that the presentation layer can render. Changes in either direction sync:
- Edit markdown → abstraction model updates
- Edit in UI → markdown regenerates

### Presentation Layer (The Visual Experience)

The UI renders plans as interactive visual objects — not text.

---

## UX Flow: Compose → Visualize → Refine → Launch → Monitor

### Step 1: Compose — Two Entry Points

#### A. From Scratch (Manual Visual Composition)

User builds a plan directly in the visual editor.

**Flow:**
1. User clicks "New Plan" → selects "Blank Plan"
2. Empty canvas with "Add EPIC" button
3. User creates EPIC cards one by one
4. For each EPIC: title, objective, tasks (as a checklist), acceptance criteria
5. Draw dependency arrows between EPICs by dragging
6. Assign agents to EPICs
7. Markdown is generated automatically in the background

#### C. From AI (Goal-Driven Generation)

User describes what they want to achieve. AI composes the plan.

**Flow:**
1. User clicks "New Plan" → selects "Describe Goal"
2. Text input: "Build an OAuth2 authentication system for our Express API"
3. AI analyzes the codebase (if available) and generates a plan with EPICs
4. Plan appears in the visual editor for review and refinement
5. User adjusts EPICs, adds/removes tasks, changes assignments

All three entry points converge into the same visual editor.

---

### Step 2: Visualize — The Plan View

The plan is displayed as a canvas of EPIC cards with connections:

```
┌─ Plan: "Game MVP" ── DRAFT ─────────────────────────────┐
│                                                          │
│  ┌─ EPIC-001 ─────────┐    ┌─ EPIC-002 ─────────┐      │
│  │ Character System    │───→│ Combat Mechanics    │      │
│  │                     │    │                     │      │
│  │ 📋 3 tasks          │    │ 📋 4 tasks          │      │
│  │ 👤 Engineer-01      │    │ 👤 unassigned       │      │
│  │ ✅ 2 criteria       │    │ ✅ 3 criteria       │      │
│  │ 📏 Medium           │    │ 📏 Large            │      │
│  └─────────────────────┘    └──────────┬──────────┘      │
│                                        │                 │
│  ┌─ EPIC-003 ─────────┐    ┌─ EPIC-004─▼─────────┐      │
│  │ Level Design        │    │ UI/UX Polish        │      │
│  │                     │    │                     │      │
│  │ 📋 5 tasks          │    │ 📋 3 tasks          │      │
│  │ 👤 unassigned       │    │ 👤 unassigned       │      │
│  │ ✅ 2 criteria       │    │ depends: 001, 002   │      │
│  │ 📏 Large            │    │ 📏 Small            │      │
│  └─────────────────────┘    └─────────────────────┘      │
│                                                          │
│  ── 4 EPICs ── 15 tasks ── 1/4 assigned ── Est: L ──    │
└──────────────────────────────────────────────────────────┘
```

**What each EPIC card shows:**
- Title & objective (summarized)
- Task count (from the epic body)
- Agent assignment (or "unassigned")
- Acceptance criteria count
- Complexity estimate
- Dependencies (visual arrows to other EPICs)
- Status indicator

**Plan-level summary bar:**
- Total EPICs and tasks
- Assignment coverage
- Critical path highlighting
- Overall complexity estimate

---

### Step 3: Refine — Interactive Editing

Users interact with the visual plan, not markdown:

**Card interactions:**
- Click EPIC card → expand detail panel (tasks, criteria, full objective)
- Drag cards → reorder priority
- Draw arrows → set dependencies
- Right-click → duplicate, split, merge, delete

**AI-assisted refinement:**
- Chat panel alongside the plan view (existing PlanEditor AI chat)
- "Split this EPIC into frontend and backend"
- "Add error handling tasks to EPIC-002"
- "What am I missing for a production-ready auth system?"
- AI modifies the plan model → visual updates instantly → markdown syncs

**Validation:**
- Circular dependency detection (visual warning on arrows)
- Unassigned EPICs highlighted
- Missing acceptance criteria flagged
- Complexity imbalance warning (one EPIC is XL, others are S)

All visual edits automatically sync to the markdown physical layer.

---

### Step 4: Launch — Plan Becomes Active

User clicks "Launch Plan" → confirmation showing what will happen:

```
Launching "Game MVP":
  → 4 War Rooms will be created
  → EPIC-001, EPIC-003 start immediately (no dependencies)
  → EPIC-002 starts after EPIC-001 completes
  → EPIC-004 starts after EPIC-001 + EPIC-002 complete
  → 1 EPIC has no agent assigned (will use default)

  [Cancel]  [Launch]
```

The system respects the dependency graph:
- EPICs with no dependencies → war rooms start immediately
- EPICs with unmet dependencies → queued, auto-start when dependencies complete
- Blocked EPICs → visually locked, show which dependency is holding them

---

### Step 5: Monitor — Same View, Live Data

After launch, the plan view transforms from an editor into a live dashboard. No context switching — the same visual you composed with now shows execution state:

```
┌─ Plan: "Game MVP" ── LIVE ──────────────────────────────┐
│                                                          │
│  ┌─ EPIC-001 ─────────┐    ┌─ EPIC-002 ─────────┐      │
│  │ Character System    │───→│ Combat Mechanics    │      │
│  │ ██████████░░ 80%    │    │ ████░░░░░░░░ 30%   │      │
│  │ 🟢 engineering      │    │ 🔵 review        │      │
│  │ 👤 Engineer-01      │    │ 👤 Engineer-02      │      │
│  │ Room: room-042      │    │ Room: room-043      │      │
│  │ ⏱ 23 min active     │    │ ⏱ 12 min active     │      │
│  └─────────────────────┘    └─────────────────────┘      │
│                                                          │
│  ┌─ EPIC-003 ─────────┐    ┌─ EPIC-004 ─────────┐      │
│  │ Level Design        │    │ UI/UX Polish        │      │
│  │ ██████████████ 100% │    │ 🔒 blocked          │      │
│  │ ✅ passed            │    │ waiting: 001, 002   │      │
│  │ 👤 Engineer-03      │    │                     │      │
│  │ Room: room-044      │    │                     │      │
│  └─────────────────────┘    └─────────────────────┘      │
│                                                          │
│  ── 1/4 done ── 2 active ── 1 blocked ── Cost: $1.23 ── │
└──────────────────────────────────────────────────────────┘
```

**Live updates via WebSocket:**
- Progress bars fill as tasks complete within war rooms
- Status changes animate (engineering → review → passed)
- Blocked EPICs auto-unlock when dependencies complete
- Cost accumulates in real-time

**Click-through:**
- Click an active EPIC card → opens the war room channel feed
- See agent messages, QA reviews, and current activity
- Jump back to plan view for the big picture

---

## The EPIC as the Core Concept

In Paperclip, the first-class object is the **Issue** (a unit of work assigned to an agent).

In OS Twin, the first-class object is the **EPIC** (a goal-oriented chunk of a plan, executed by agents in a war room).

### Why EPICs, Not Issues

| Issue (Paperclip) | EPIC (OS Twin) |
|---|---|
| Standalone task | Part of a plan |
| One action | Multiple tasks toward a goal |
| Assigned to one agent | Executed by agent team in a war room |
| Status: open/closed | Status: draft → engineering → qa → done |
| No dependency model | Dependencies between EPICs |
| Created individually | Created as part of plan composition |

EPICs are bigger than tasks but smaller than projects. They represent a **meaningful chunk of progress** — something that, when completed, moves the plan forward in a visible way.

### EPIC Lifecycle

```
DRAFT ──→ QUEUED ──→ IN-PROGRESS ──→ QA-REVIEW ──→ DONE
  │                      │               │
  │                      ▼               ▼
  │                   FIXING ←──── FAILED (retry)
  │
  └──→ CANCELLED
```

- **Draft**: EPIC exists in plan but plan hasn't launched
- **Queued**: Plan launched, waiting for dependencies to complete
- **In-Progress**: War room active, agents working
- **QA-Review**: Engineer done, QA agent reviewing
- **Fixing**: QA found issues, engineer fixing
- **Done**: QA passed, EPIC complete
- **Cancelled**: Removed from plan during execution

This lifecycle maps directly to the existing war room status machine — no new concepts needed at the execution layer.

---

## Bi-Directional Sync: Visual ↔ Markdown

The visual editor and markdown are always in sync:

**Visual → Markdown:**
- User adds EPIC card → `## Epic: {title}` appended to plan.md
- User draws dependency arrow → `depends_on: [EPIC-XXX]` added to epic header
- User assigns agent → `assigned: engineer-01` added to epic metadata
- User reorders → markdown sections reordered

**Markdown → Visual:**
- User edits plan.md directly (in IDE or text editor)
- File watcher detects change
- Parser re-extracts plan model
- Visual updates to match

**Conflict handling:**
- If both change simultaneously, visual edit wins (user is actively working)
- Markdown changes from external tools trigger a visual refresh notification
- All changes are git-trackable — conflicts resolvable via standard git

---

## Integration with Existing OS Twin Architecture

| Existing Component | Visual Plan Integration |
|---|---|
| **Plan files** (.agents/plans/) | Physical layer — generated/updated by visual editor |
| **Manager agent** | Reads plan model to spawn war rooms respecting dependency order |
| **War Rooms** | 1:1 mapped to EPICs — EPIC card links directly to room |
| **Channel feed** | Click-through from EPIC card to room's message stream |
| **PlanEditor + AI chat** | Enhanced with visual context — AI sees the plan structure, not just text |
| **Dashboard** | Plan progress shown as summary cards on main dashboard |
| **WebSocket** | Existing real-time updates power live EPIC status changes |
