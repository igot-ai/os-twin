# PLAN: Design — Dashboard Bug Fixes & UX Refactoring Wave

## Goal

Address 8 reported bugs and UX issues across the OS Twin Dashboard plan detail UI. Consolidate the sidebar navigation, fix save/load/progress data flows, surface DAG-driven role information on plan cards, improve editor UX, and lay the groundwork for asset change tracking.

---

### EPIC-001 — Plan Card Role Badges from DAG.json

**Objective**: Display the assigned role for each epic on plan cards (both Dashboard list and Kanban cards) using `DAG.json` node data.

**Root Cause**: `EpicCard.tsx` renders `epic.role` but the synthesized epics from `PlanWorkspace.tsx` already read `dagNode.role` correctly. The **Dashboard plan list cards** (main `/` page) don't fetch or show per-epic roles at all — they only show epic count and progress.

**Definition of Done**:
- [x] Kanban `EpicCard` shows role badge sourced from DAG node data
- [ ] Dashboard plan list cards show role distribution (e.g., "2× engineer, 1× architect")
- [ ] Role badges use `roleColorMap` consistently across DAG, Kanban, and Dashboard

**Tasks**:
- [ ] TASK-001: Enrich `/api/plans` response with `role_distribution` extracted from each plan's `DAG.json`
- [ ] TASK-002: Update Dashboard `PlanCard` component to display role distribution chips
- [ ] TASK-003: Ensure `PlanWorkspace.epics` synthesizer consistently populates `role` from DAG fallback

**Acceptance Criteria**:
- [ ] Plan cards on Dashboard show role badges (e.g., colored circles with initials)
- [ ] Roles sourced from `DAG.json` nodes, not hardcoded

depends_on: []

---

### EPIC-002 — Fix Save Plan API

**Objective**: Fix the save plan functionality so plans can be persisted.

**Root Cause**: `PlanWorkspace.savePlan()` calls `apiPost('/plans/${planId}/save', { content: planContent })` — the backend `SavePlanRequest` model expects `content: str` and optionally `change_source: str`. The API client sends `Content-Type: application/json`. The issue is likely:
1. The `api-client.ts` `BASE_URL` defaults to `/api`, but `apiPost` prepends it, so the actual URL becomes `/api/plans/{id}/save` — which is the correct route `@router.post("/api/plans/{plan_id}/save")`.
2. The backend route at line 402 has duplicate definition — first at L475 (`get_plan_roles`) and then overridden at L833. Need to check for route conflicts.
3. The `get_plan_roles` endpoint is defined **twice** (L475 and L833) — the second one overwrites the first, which changes the behavior.

**Definition of Done**:
- [ ] Save plan button successfully persists content to disk
- [ ] Save triggers zvec re-index
- [ ] Error toast shows meaningful message on failure
- [ ] No duplicate route definitions

**Tasks**:
- [ ] TASK-001: Audit and remove duplicate `/api/plans/{plan_id}/roles` route definition (L475 vs L833)
- [ ] TASK-002: Add error handling and user feedback in `PlanSidebar.savePlan()` (toast notification)
- [ ] TASK-003: Write integration test to verify save roundtrip (save → re-fetch → content matches)

**Acceptance Criteria**:
- [ ] Click "Save Plan" → content persisted to `{plan_id}.md`
- [ ] Error shown if save fails
- [ ] No 500/422 errors in server log

depends_on: []

---

### EPIC-003 — Physical File ↔ zvec Store Sync & Diff

**Objective**: Detect when plan `.md` files are modified externally (e.g., by git pull, manual edit) and show diff rather than blindly overwriting.

**Root Cause**: `zvec_store` calls `upsert()` which writes the latest version. When a plan file is modified on disk (physically), the FE loads from zvec (stale) and the physical file is newer. The `save_plan` endpoint reads old content, snapshots it via `store.save_plan_version()`, then overwrites — but there's no mechanism to detect external changes before the FE loads.

**Definition of Done**:
- [ ] Backend detects file-modified-since-last-index via `mtime` comparison
- [ ] FE shows "File changed on disk" warning with option to reload or merge
- [ ] zvec always stays in sync with physical file as source of truth

**Tasks**:
- [ ] TASK-001: Add `file_mtime` field to the zvec plans collection schema (or use a separate cache file)
- [ ] TASK-002: Add `/api/plans/{plan_id}/sync-status` endpoint returning `{in_sync: bool, disk_mtime, zvec_mtime}`
- [ ] TASK-003: `usePlan` hook checks sync status on mount; shows banner when out of sync
- [ ] TASK-004: Add "Reload from Disk" action that re-reads `.md` file and re-indexes zvec

**Acceptance Criteria**:
- [ ] Modify plan file via editor → dashboard shows "out of sync" warning
- [ ] "Reload" button pulls latest from disk

depends_on: []

---

### EPIC-004 — Consolidate Plan Settings / Roles / Skills Sidebar

**Objective**: Eliminate duplication between "Roles & Models", "Skills", and "Plan Settings" tabs in the sidebar. Expose roles directly on the Plan Detail UI even before launch, using the markdown plan file `Roles:` metadata per EPIC.

**Root Cause**: `PlanSidebar.tsx` has 9 tabs including both "Roles & Models" and "Plan Settings" — the latter is essentially a subset of the former (role model overrides). There's also a separate "Skills" tab. These should be unified into a single "Roles & Config" tab.

**Definition of Done**:
- [ ] Remove `plan-settings` tab from sidebar
- [ ] Merge role override functionality into the `roles` tab
- [ ] Parse `Roles:` annotations from plan markdown per-EPIC and display them
- [ ] Sidebar has max 7 clean navigation items

**Tasks**:
- [ ] TASK-001: Merge `PlanSettingsTab` content into `RolesTab` as a collapsible "Model Overrides" section
- [ ] TASK-002: Remove `plan-settings` from `PlanSidebar.tabs` and `WorkspaceTabs`
- [ ] TASK-003: Parse plan markdown for `Roles:` lines per EPIC section and expose in roles tab
- [ ] TASK-004: Clean up sidebar: combine "Settings" into contextual gear icon or merge with remaining config

**Acceptance Criteria**:
- [ ] No duplicate settings experience
- [ ] Roles tab shows per-epic role assignments from plan file + model overrides
- [ ] Clean sidebar with ≤7 items

depends_on: []

---

### EPIC-005 — Move AI Assistant Button to Top-Right Header

**Objective**: Relocate the AI Architect toggle button from the bottom of the sidebar to the top-right header area for better discoverability.

**Root Cause**: Currently the AI Architect button is at the very bottom of `PlanSidebar.tsx` action buttons section. Users expect AI assistance in the header like ChatGPT/Copilot patterns.

**Definition of Done**:
- [ ] AI Architect button is in the top-right of the PlanWorkspace header (near breadcrumb)
- [ ] Button shows active/inactive state with animation
- [ ] Sidebar bottom section simplified (only Save + Launch)

**Tasks**:
- [ ] TASK-001: Move AI toggle button to `PlanBreadcrumb.tsx` header right side
- [ ] TASK-002: Add pulse/glow animation when AI is generating
- [ ] TASK-003: Remove AI button from `PlanSidebar` action section

**Acceptance Criteria**:
- [ ] AI button visible in header without scrolling
- [ ] Click opens/closes AI chat panel on the right

depends_on: []

---

### EPIC-006 — Editor-Preview Toggle Mode

**Objective**: Replace separate "Editor" and "Preview" sidebar tabs with a single "Editor" tab that has a built-in preview toggle (split/preview mode).

**Root Cause**: `PlanSidebar.tsx` has separate "Editor" (`edit_document` icon) and "Preview" (`visibility` icon) tabs — they both work with `planContent` state. A toggle within the editor tab is more natural (like GitHub's editor).

**Definition of Done**:
- [ ] Single "Editor" tab in sidebar
- [ ] Editor view has toolbar with "Edit | Preview | Split" toggle
- [ ] Remove "Preview" tab from sidebar and WorkspaceTabs

**Tasks**:
- [ ] TASK-001: Add mode toggle toolbar to `PlanEditorTab` (edit / preview / split)
- [ ] TASK-002: Implement split view rendering (editor left, preview right)
- [ ] TASK-003: Remove `preview` from `PlanSidebar.tabs` and `WorkspaceTabs`
- [ ] TASK-004: Move `PlanPreviewTab` rendering logic into `PlanEditorTab` as embedded preview mode

**Acceptance Criteria**:
- [ ] Editor tab shows "Edit | Preview | Split" toggle
- [ ] Content syncs between edit and preview in real-time
- [ ] No separate Preview tab in sidebar

depends_on: []

---

### EPIC-007 — Progress Bar Alignment with /progress Endpoint

**Objective**: Ensure `ProgressFooter` and the sidebar progress bar both read from the `/api/plans/{plan_id}/progress` endpoint consistently.

**Root Cause**: `ProgressFooter.tsx` already reads from `useWarRoomProgress()` hook and falls back to `plan.pct_complete`. The sidebar in `PlanSidebar.tsx` only reads `plan.pct_complete`, which is enriched from `progress.json` in the list endpoint but may be stale. The footer's `critical_path` parsing splits a string "N/M" format — this may mismatch what the list endpoint provides (object `{completed, total}`).

**Definition of Done**:
- [ ] Both sidebar and footer use the same progress data source (`useWarRoomProgress`)
- [ ] Progress ring, percentage, and critical path are consistent across all UI locations
- [ ] Fallback handles missing progress.json gracefully

**Tasks**:
- [ ] TASK-001: Expose `progress` from `PlanContext` so sidebar can use it
- [ ] TASK-002: Update `PlanSidebar` to use `progress.pct_complete` from context instead of `plan.pct_complete`
- [ ] TASK-003: Normalize `critical_path` field — backend should return object `{completed, total}` not string
- [ ] TASK-004: Add loading skeleton for progress data

**Acceptance Criteria**:
- [ ] Progress bar shows same value in sidebar and footer
- [ ] Values match `/api/plans/{plan_id}/progress` response
- [ ] No NaN or undefined shown when progress.json missing

depends_on: []

---

### EPIC-008 — Plan History & Asset Change Tracking Foundation

**Objective**: Design a mechanism to track changes to plan assets (code files, PDFs, config) over time, integrated with git-like semantics.

**Root Cause**: `PlanHistoryTab` shows plan version history from `zvec_store.save_plan_version()`, but this only tracks `.md` content changes. There's no mechanism to track changes to non-plan assets (code files, reports, generated artifacts in war-room folders). Users want to see a timeline of all asset mutations.

**Definition of Done**:
- [ ] Plan History tab shows a unified timeline of plan content versions + asset changes
- [ ] Asset changes detected via git diff or file watcher
- [ ] Each history entry has: timestamp, change type, file path, diff preview

**Tasks**:
- [ ] TASK-001: Design `ChangeEvent` schema: `{id, plan_id, timestamp, change_type, file_path, diff_summary, source}`
- [ ] TASK-002: Add `/api/plans/{plan_id}/changes` endpoint that reads git log for the plan's `working_dir`
- [ ] TASK-003: Enhance `PlanHistoryTab` to show both plan versions and file changes in a unified timeline
- [ ] TASK-004: Add "View Diff" modal for individual change entries

**Acceptance Criteria**:
- [ ] History tab shows plan version history + git-based file changes
- [ ] Clicking a change shows diff preview
- [ ] Works for plans with and without git repos

depends_on: [EPIC-003]

---

## Verification Plan

### Automated Tests
- **Existing**: `cd fe && bun run test` — runs `vitest` tests in `__tests__/api-client.test.ts`
- **New tests to add**:
  - Test for save plan roundtrip (EPIC-002): mock fetch → call savePlan → verify POST body
  - Test for progress data normalization (EPIC-007): verify critical_path parsing for string vs object formats
  - Test for duplicate route detection (EPIC-002): verify no duplicate FastAPI routes

### Browser Verification
- Launch dev server: `cd fe && bun run dev` (port 3000) + backend on port 9001
- Verify plan cards show role badges (EPIC-001)
- Test Save Plan button works (EPIC-002)
- Check sidebar has no duplicate tabs (EPIC-004)
- Verify AI button in header (EPIC-005)
- Test editor toggle mode (EPIC-006)
- Compare progress footer values with `/api/plans/{id}/progress` response (EPIC-007)

### Manual Verification
- Modify a plan `.md` file on disk → verify dashboard detects the change (EPIC-003)
- Check History tab shows timeline entries (EPIC-008)
