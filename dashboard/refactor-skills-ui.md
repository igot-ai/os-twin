# Plan: Refactor Skills UI & War-Room Messaging

> Created: 2026-03-13T16:01:47Z
> Status: draft
> Project: /Users/paulaan/PycharmProjects/agent-os/dashboard

---

## Goal

Enhance the dashboard to provide full visibility into **skills management** (assign, view, edit per role) and **war-room channel messages** (per-room message exploration, per-plan scoped views). These two features are the final pieces needed for a complete operational dashboard.

## Config

working_dir: /Users/paulaan/PycharmProjects/agent-os/dashboard

---

# Epics

## EPIC-001 — Refactor the Skills Management UI

Roles: engineer
Working_dir: /Users/paulaan/PycharmProjects/agent-os/dashboard

#### Objective

Build a comprehensive Skills panel in the Next.js dashboard that lets users browse, search, assign, and inspect skills across roles and plans.

### Context

The backend already has full skill support:
- `GET /api/skills` — list skills (filter by role, tags)
- `GET /api/skills/search?q=...&role=...` — semantic search
- `GET /api/skills/{name}` — get skill details (content, tags, trust_level)
- `POST /api/skills/install` — install from filesystem path
- `POST /api/skills/sync` — sync vector DB with on-disk SKILL.md files
- `GET /api/skills/tags` — list all unique tags
- Skill model: `{ name, description, tags, trust_level, source, path, relative_path, content }`
- Skills are stored in: `.agents/skills/roles/*/`, `.agents/skills/global/`, `~/.deepagents/agent/skills/`
- Skills are resolved per-room by the Manager Loop via `Resolve-RoomSkills()` before spawning workers

What's missing is the **frontend UI** to interact with this data.

### Definition of Done

- [ ] Skills panel/page in the Next.js dashboard listing all available skills
- [ ] Users can filter skills by role (engineer, qa, architect, etc.) and tags
- [ ] Users can search skills semantically via the search endpoint
- [ ] Skill detail view showing: name, description, tags, trust_level, source, relative_path, and full SKILL.md content (rendered markdown)
- [ ] Users can see which skills are assigned to each role in a specific plan (via `/api/plans/{id}/roles`)
- [ ] Users can trigger a skill sync (`POST /api/skills/sync`) and see the result (added/updated/removed counts)
- [ ] UI shows skill trust_level with visual indicators (experimental = yellow, stable = green)
- [ ] Responsive design that works in the existing dashboard layout

### Acceptance Criteria

- [ ] Skills panel loads without errors on a fresh dashboard start
- [ ] Filtering by role returns role-relevant skills only (matching backend behavior)
- [ ] Clicking a skill name shows its full SKILL.md content rendered as markdown
- [ ] Sync button triggers the API and shows a toast/notification with results
- [ ] No regressions in existing dashboard panels (WarRoomGrid, PlanEditor, etc.)
- [ ] No critical or high-severity bugs

### Tasks

- [ ] TASK-001 — Review the current Skill data model (`models.py:Skill`) and backend routes (`routes/skills.py`, `api_utils.py:build_skills_list`) to understand all available data fields
- [ ] TASK-002 — Create a `SkillsPanel` component (`nextjs/src/components/panels/SkillsPanel.tsx`) with:
  - Skills list view (name, description, tags, trust level badge)
  - Role filter dropdown (populated from registry.json roles)
  - Tag filter chips
  - Search input wired to `/api/skills/search`
- [ ] TASK-003 — Create a `SkillDetailModal` component showing full SKILL.md content, metadata, and the skill's filesystem path
- [ ] TASK-004 — Create a `SkillSyncButton` component that calls `POST /api/skills/sync` and displays the result
- [ ] TASK-005 — Wire into the plan detail view: show "Skills" tab in plan editor that maps roles → resolved skills (data from `/api/plans/{id}/roles`)
- [ ] TASK-006 — Add route/navigation entry for `/skills` in the Next.js app

depends_on: []

---

## EPIC-002 — War-Room Channel Message Explorer

Roles: engineer
Working_dir: /Users/paulaan/PycharmProjects/agent-os/dashboard

#### Objective

Build a message explorer that lets users view, filter, and search channel messages for any specific war-room — both globally and scoped to a plan.

#### Context

The backend already supports:
- `GET /api/rooms/{room_id}/channel` — all messages for a room (searches global + plan-specific dirs)
- `GET /api/plans/{plan_id}/rooms/{room_id}/channel` — plan-scoped room channel
- `GET /api/search?q=...&room_id=...&type=...` — semantic vector search across all indexed messages
- `GET /api/rooms/{room_id}/context?q=...` — semantic search scoped to one room
- Messages stored in `channel.jsonl` (JSONL format, one record per line)
- Message schema: `{ v, id, ts, from, to, type, ref, body }`
- 18 message types: task, done, review, pass, fail, fix, error, signoff, release, plan-review, plan-approve, plan-reject, plan-update, escalate, design-review, design-guidance, redesign-done, subcommand-redesigned
- Real-time updates: `poll_war_rooms()` detects new messages every 1s and broadcasts via WebSocket (`room_updated` event) and SSE (`/api/events`)

What's missing is a dedicated **channel message viewer** in the frontend.

### Definition of Done

- [ ] Channel message panel/drawer that shows all messages for a selected war-room
- [ ] Messages displayed in chronological order with: timestamp, from → to, type badge, ref, body
- [ ] Message type badges color-coded (task=blue, done=green, pass=green, fail=red, fix=yellow, error=red, etc.)
- [ ] Filter controls: by message type (multi-select), by sender role, by time range
- [ ] Semantic search within a room's messages (via `/api/rooms/{id}/context`)
- [ ] Real-time updates: new messages appear automatically via WebSocket/SSE without refresh
- [ ] Plan-scoped mode: when viewing a plan, channel uses `/api/plans/{pid}/rooms/{rid}/channel`
- [ ] Message body rendered with basic markdown support (code blocks, bold, lists)
- [ ] Click on room card → opens channel viewer for that room

### Acceptance Criteria

- [ ] Selecting a room from the WarRoomGrid opens the channel viewer with all messages
- [ ] Message type filter correctly narrows the message list
- [ ] New messages from an active room appear in real-time (< 2s delay)
- [ ] Semantic search returns relevant results with highlighted matches
- [ ] Works for both global rooms (`/api/rooms/{id}/channel`) and plan-scoped rooms
- [ ] Performance: loads 500+ messages without UI freezing
- [ ] No regressions in existing dashboard functionality

### Tasks

- [ ] TASK-001 — Review the existing message rendering in the dashboard (if any) and the WarRoomGrid click handler (`onSelectRoom`)
- [ ] TASK-002 — Create a `ChannelViewer` component (`nextjs/src/components/warroom/ChannelViewer.tsx`) with:
  - Chronological message list with badges and role avatars
  - Auto-scroll to latest message
  - Visual grouping by type (task assignments, QA feedback, etc.)
- [ ] TASK-003 — Create a `MessageCard` component for rendering individual messages with:
  - Color-coded type badge
  - From → To header with role icons
  - Timestamp formatting (relative + absolute)
  - Markdown-rendered body
- [ ] TASK-004 — Add filter controls: message type multi-select, sender role dropdown, search input
- [ ] TASK-005 — Integrate real-time updates via WebSocket: subscribe to `room_updated` events and append new messages
- [ ] TASK-006 — Wire the ChannelViewer into the existing WarRoomGrid: clicking a RoomCard opens the channel panel/drawer
- [ ] TASK-007 — Add plan-scoped channel support: detect if viewing a plan context and use `/api/plans/{pid}/rooms/{rid}/channel` endpoint

depends_on: []

---

## EPIC-003 — Extended Room State Panel

Roles: engineer
Working_dir: /Users/paulaan/PycharmProjects/agent-os/dashboard

#### Objective

Enhance the RoomCard and room detail view to show the full room metadata now available through the `read_room(include_metadata=True)` endpoint.

#### Context

The `read_room()` function with `include_metadata=True` returns rich data:
- `config` — full `config.json` (assignment, goals, constraints)
- `roles` — list of per-role instance files (`{role}_{id}.json`)
- `state_changed_at` — last state transition timestamp
- `artifact_files` — list of artifact filenames
- `audit_tail` — last 20 lines of audit.log

The `/api/plans/{id}/rooms` endpoint already calls `read_room(include_metadata=True)` but the frontend only displays basic fields.

### Definition of Done

- [ ] Room detail view shows: assignment details (assigned_role, candidate_roles, type)
- [ ] Goal contract displayed: DoD items, AC items, quality requirements (test_coverage_min, lint_clean)
- [ ] Constraints shown: max_retries, timeout_seconds, budget_tokens_max
- [ ] Role instances listed with: role, instance_id, model, status
- [ ] Artifact files listed with download/view links
- [ ] Audit log tail visible in a collapsible section
- [ ] State transition timeline visualization

### Acceptance Criteria

- [ ] All metadata fields from `read_room(include_metadata=True)` are displayed
- [ ] Goal completion (DoD/AC) shows checkmark status
- [ ] Clicking an artifact filename opens/downloads the file
- [ ] Audit log is readable with timestamps and state transitions
- [ ] No performance regression when loading large rooms

### Tasks

- [ ] TASK-001 — Extend the `RoomCard` component to show role badges, artifact count, and state_changed_at
- [ ] TASK-002 — Create a `RoomDetailPanel` component with tabs: Overview, Goals, Roles, Artifacts, Audit
- [ ] TASK-003 — Create a `GoalContract` sub-component showing DoD and AC items as checklists
- [ ] TASK-004 — Create an `AuditTimeline` sub-component parsing audit.log into a visual timeline
- [ ] TASK-005 — Wire into plan room view: clicking a room opens the detail panel

depends_on: []