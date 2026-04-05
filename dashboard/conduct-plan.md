# Plan: Ideas-to-Plan Ideation Flow



> Created: 2026-04-05T19:00:00+07:00

> Status: draft

> Project: agent-os/dashboard



## Config



working_dir: ./dashboard



---



## Goal



Build the first end-to-end **ideation flow**: user types an idea on the Home page → gets redirected to `/ideas/{thread_id}` → has a multi-turn AI brainstorming conversation (powered by deepagents) → clicks "Create Plan" to promote the idea into a real plan on disk.



Most of the implementation already exists on the `feat/home-page` branch (25+ untracked files, 16+ modified files vs `main`). This plan covers fixing the remaining issues, filling gaps, verifying the full flow, and getting it committed.



---



## EPIC-001 — Fix & Harden Backend: Store, Routes, Shared Helper



Roles: engineer, qa

Objective: Fix the duplicated plan-creation logic in the promote endpoint, harden the auto-title check, and verify all backend pieces work together end-to-end.



### Description



The backend is substantially built across 4 files:

- `dashboard/planning_thread_store.py` — PlanningThread/PlanningMessage models + filesystem CRUD (untracked)

- `dashboard/routes/threads.py` — 7 API endpoints for thread lifecycle (untracked)

- `dashboard/plan_agent.py` — `BRAINSTORM_SYSTEM_PROMPT`, `create_brainstorm_agent()`, `brainstorm_stream()` (modified)

- `dashboard/api.py` — threads router registered + `resolve_frontend_file()` catch-all (modified)



**Three issues to fix:**



1. **Promote endpoint duplicates plan creation logic.** Lines 192-238 of `threads.py` copy-paste the disk-write logic from `routes/plans.py` lines 485-528 (plan.md + meta.json + roles.json). Extract a shared `create_plan_on_disk(title, content, working_dir, thread_id=None) -> dict` helper in `routes/plans.py` and call it from both the `/api/plans/create` endpoint and the `/api/plans/threads/{id}/promote` endpoint.



2. **Auto-title race condition.** In `threads.py` line 148, `thread.message_count` is read from the object fetched *before* the user message was appended to the store. By the time the check runs post-streaming, the count is stale. Replace with `len(db_messages)` check or re-read the thread after streaming completes.



3. **Backend import chain verification.** `api.py` now imports `command` (formerly `files`) and `threads` — both are untracked files. Verify the full import chain works: `python -c "from dashboard.api import app"`.



### Definition of Done



- [ ] Shared `create_plan_on_disk()` helper extracted into `routes/plans.py`

- [ ] `routes/threads.py` promote endpoint calls the shared helper (no duplicated logic)

- [ ] `routes/plans.py` `create_plan()` endpoint refactored to use the same helper

- [ ] Auto-title fires correctly after the first exchange (uses `len(db_messages)` check, not stale `thread.message_count`)

- [ ] `python -c "from dashboard.api import app"` succeeds with no import errors

- [ ] `pytest dashboard/tests/test_planning_thread_store.py` passes

- [ ] `pytest dashboard/tests/test_threads_api.py` passes



### Acceptance Criteria



- [ ] Promoting a thread creates `{plan_id}.md`, `{plan_id}.meta.json`, and `{plan_id}.roles.json` on disk under `PLANS_DIR`

- [ ] `meta.json` includes `thread_id` linking back to the source thread

- [ ] Thread status changes to `promoted` with `plan_id` set

- [ ] Auto-title generates a 4-8 word title after the first AI response

- [ ] No duplicated plan-creation code between `routes/plans.py` and `routes/threads.py`

- [ ] SSE streaming delivers tokens and ends with `{"done": true}`



depends_on: []



---



## EPIC-002 — Fix & Complete Frontend: Ideas Page, Stubs, Build



Roles: engineer, qa

Objective: Fix the stub `ideas/page.tsx`, clean up `generateStaticParams`, verify markdown rendering in IdeaChat, and ensure the frontend builds without errors.



### Description



The frontend is substantially built across these files:

- `dashboard/fe/src/components/ideas/IdeaChat.tsx` — full chat component with streaming, images, promote (untracked)

- `dashboard/fe/src/hooks/use-planning-thread.ts` — SSE streaming + SWR + optimistic UI (untracked)

- `dashboard/fe/src/hooks/use-planning-threads.ts` — thread listing (untracked)

- `dashboard/fe/src/app/ideas/[threadId]/page.tsx` — dynamic route page (untracked)

- `dashboard/fe/src/app/page.tsx` — refactored Home with thread creation + redirect (modified)

- `dashboard/fe/src/components/layout/Sidebar.tsx` — "Recent Ideas" section (modified)

- `dashboard/fe/src/components/ui/CommandPrompt.tsx` + `BrandIcon.tsx` (untracked)



**Four issues to fix:**



1. **`ideas/page.tsx` is a stub** — currently renders `<div>Loading ideas...</div>`. Should redirect to Home (`/`) since the Home page is the entry point for new ideas, or render a simple thread list using `usePlanningThreads()`.



2. **`generateStaticParams` hardcodes `pt-001`** — in `[threadId]/page.tsx` line 11. Only `{ threadId: 'template' }` is needed. Remove the extra entry to avoid unnecessary build artifacts.



3. **Verify markdown rendering** — IdeaChat must properly render assistant responses as markdown (code blocks, lists, bold). Verify that `react-markdown` or equivalent is used in the assistant message bubbles.



4. **Build check** — `cd dashboard/fe && npm run build` must succeed with zero errors related to the new files.



### Definition of Done



- [ ] `ideas/page.tsx` either redirects to `/` or shows a thread list (not a stub)

- [ ] `generateStaticParams` returns only `[{ threadId: 'template' }]`

- [ ] Assistant messages render markdown correctly (code blocks, lists, headers)

- [ ] `cd dashboard/fe && npm run build` succeeds with zero errors

- [ ] All untracked frontend files (hooks, components, pages) are consistent and import cleanly



### Acceptance Criteria



- [ ] Navigating to `/ideas` shows either a redirect or a thread list (not "Loading ideas...")

- [ ] Navigating to `/ideas/{thread_id}` loads the full IdeaChat with message history

- [ ] Typing a message streams AI response with proper markdown rendering

- [ ] Image paste/upload works in the chat composer

- [ ] "Create Plan" button calls promote and navigates to `/plans/{plan_id}`

- [ ] Sidebar shows recent ideas with active highlighting

- [ ] Home page creates a thread on submit and redirects to `/ideas/{id}`



depends_on: [EPIC-001]



---



## EPIC-003 — End-to-End Verification & Testing



Roles: qa, engineer

Objective: Run the full happy path end-to-end, verify persistence across server restarts, run all test suites, and confirm the feature is ready to commit.



### Description



This EPIC covers the verification plan from the original proposal. All code from EPICs 001-002 should be complete. Now we validate the full flow.



**Automated tests:**

```bash

pytest dashboard/tests/test_planning_thread_store.py -v

pytest dashboard/tests/test_threads_api.py -v

pytest dashboard/tests/test_frontend_fallback.py -v

```



**Manual E2E flow:**

1. Start dashboard: `python dashboard/api.py`

2. Open Home page → type "Build a task tracker with React and Node.js"

3. Verify redirect to `/ideas/{thread_id}`

4. Send 2-3 follow-up messages → verify SSE streaming works

5. Verify auto-title appears in sidebar after first exchange

6. Click "Create Plan" → verify redirect to `/plans/{plan_id}`

7. Verify plan files on disk: `ls ~/.ostwin/.agents/plans/{plan_id}.*`

8. Stop server → restart → navigate to `/ideas/{thread_id}` → verify messages persist



**Build verification:**

```bash

cd dashboard/fe && npm run build  # zero errors

python -c "from dashboard.api import app"  # no import errors

```



**Regression check:**

- Existing plan routes still work (`GET /api/plans`, `POST /api/plans/create`)

- WebSocket still works for real-time broadcasting

- Sidebar navigation items all still route correctly



### Definition of Done



- [ ] All 3 test suites pass (`test_planning_thread_store`, `test_threads_api`, `test_frontend_fallback`)

- [ ] Frontend builds with zero errors

- [ ] Backend starts with no import errors

- [ ] Full E2E flow works: Home → idea → brainstorm → Create Plan → plan on disk

- [ ] Thread data survives server restart

- [ ] No regression on existing plan/epic/sidebar functionality



### Acceptance Criteria



- [ ] A developer can complete the full ideation flow from Home to plan creation without errors

- [ ] Thread messages persist in `.agents/conversations/plans/` as JSONL

- [ ] Promoted plans appear in the plans list (`GET /api/plans`)

- [ ] Sidebar shows the thread with correct status badge (lightbulb for active, checkmark for promoted)

- [ ] No broken imports or dead code remain

- [ ] All existing tests still pass (no regression)



depends_on: [EPIC-001, EPIC-002]



---



## EPIC-004 — Commit & PR



Roles: engineer

Objective: Stage all changes, create a clean commit (or series of commits), and prepare for PR to `main`.



### Description



The `feat/home-page` branch has 25+ untracked files and 16+ modified files. All changes need to be committed cleanly.



**Commit strategy options:**

- **Option A: Single feature commit** — one commit covering the full ideation flow. Simpler, but large diff.

- **Option B: Per-EPIC commits** — 3-4 commits matching the EPIC structure. Cleaner history, easier to review.



**Files to stage (summary):**



Backend (new):

- `dashboard/planning_thread_store.py`

- `dashboard/routes/threads.py`

- `dashboard/routes/command.py`

- `dashboard/frontend_fallback.py`

- `dashboard/command_dispatcher.py`

- `dashboard/tests/test_planning_thread_store.py`

- `dashboard/tests/test_threads_api.py`

- `dashboard/tests/test_frontend_fallback.py`



Backend (modified):

- `dashboard/plan_agent.py`

- `dashboard/global_state.py`

- `dashboard/tasks.py`

- `dashboard/api.py`

- `dashboard/api_utils.py`

- `dashboard/routes/plans.py`



Frontend (new):

- `dashboard/fe/src/hooks/use-planning-thread.ts`

- `dashboard/fe/src/hooks/use-planning-threads.ts`

- `dashboard/fe/src/app/ideas/[threadId]/page.tsx`

- `dashboard/fe/src/app/ideas/page.tsx`

- `dashboard/fe/src/components/ideas/IdeaChat.tsx`

- `dashboard/fe/src/components/ui/CommandPrompt.tsx`

- `dashboard/fe/src/components/ui/BrandIcon.tsx`

- `dashboard/fe/src/components/chat/ActivityFeed.tsx`

- `dashboard/fe/src/hooks/use-home-data.ts`

- `dashboard/fe/src/hooks/use-websocket.ts`



Frontend (modified):

- `dashboard/fe/src/app/page.tsx`

- `dashboard/fe/src/components/layout/Sidebar.tsx`

- `dashboard/fe/src/types/index.ts`



**Exclude from commit:**

- `.coverage`, `debug_test_output.txt`, `test_pid*.txt`, `security.zip` (already in .gitignore or irrelevant)

- `sample/` directory (test data)

- `PLAN-MCP-CONNECTOR.md`, `dashboard/implementation_plan.md` (planning docs, not code)



### Definition of Done



- [ ] All code changes committed to `feat/home-page` branch

- [ ] Commit message(s) clearly describe the ideation flow feature

- [ ] No sensitive files (.env, credentials) included

- [ ] Branch is ready for PR review



### Acceptance Criteria



- [ ] `git status` shows clean working directory (for the feature files)

- [ ] `git log` shows clear, descriptive commit(s)

- [ ] Branch can be PR'd to `main` with no conflicts



depends_on: [EPIC-003]



---



## Files Touched — Summary



| Action | File | EPIC |

|--------|------|------|

| MODIFY | `dashboard/routes/plans.py` (extract helper) | 001 |

| MODIFY | `dashboard/routes/threads.py` (use shared helper, fix auto-title) | 001 |

| FIX | `dashboard/fe/src/app/ideas/page.tsx` (replace stub) | 002 |

| FIX | `dashboard/fe/src/app/ideas/[threadId]/page.tsx` (clean generateStaticParams) | 002 |

| VERIFY | `dashboard/fe/src/components/ideas/IdeaChat.tsx` (markdown rendering) | 002 |

| VERIFY | All test suites | 003 |

| VERIFY | Frontend build | 003 |

| COMMIT | All 40+ files | 004 |


