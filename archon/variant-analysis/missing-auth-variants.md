# Missing Authentication on Sensitive Endpoint — Variant Analysis
Phase: 10
Origin-Pattern: AP-022 / AP-004 (CWE-306 Missing Authentication for Critical Function)
Analysis Date: 2026-03-30

## Confirmed Instances (Pre-existing, Not Repeated Here)
- dashboard/routes/system.py:166 — POST /api/shell (RCE)
- dashboard/routes/system.py:148-164 — Telegram config/test endpoints
- dashboard/routes/system.py:171-196 — subprocess test endpoints
- dashboard/routes/plans.py:461 — POST /api/plans/create

---

## VARIANT-001 — Unauthenticated Room Lifecycle Control

Phase: 10
Sequence: 001
Slug: unauth-room-action
Verdict: VALID
Rationale: POST /api/rooms/{room_id}/action allows any unauthenticated caller to stop, pause, or resume active AI war-rooms.
Severity-Original: HIGH
PoC-Status: pending
Origin-Finding: dashboard/routes/system.py:166 (same CWE-306 pattern)
Origin-Pattern: AP-022

### Summary
`POST /api/rooms/{room_id}/action` in `dashboard/routes/rooms.py:228` has no `Depends(get_current_user)` in its function signature. Any unauthenticated HTTP client can write arbitrary lifecycle states ("stop", "pause", "resume") to the `status` file of any war-room by ID.

### Location
`/Users/bytedance/Desktop/demo/os-twin/dashboard/routes/rooms.py`, lines 228-247

```python
@router.post("/api/rooms/{room_id}/action")
async def room_action(room_id: str, background_tasks: BackgroundTasks, action: str = Query(...)):
    ...
    if action == "stop":
        status_file.write_text("failed-final")
    elif action == "pause":
        status_file.write_text("paused")
    ...
```

### Attacker Control
- `room_id` — attacker-supplied path parameter (room directory name enumerable via `/api/rooms` SSE or search)
- `action` — attacker-supplied query string (`stop`, `pause`, `resume`, `start`)

### Trust Boundary Crossed
Public internet -> internal war-room lifecycle manager (filesystem state write)

### Impact
An unauthenticated attacker can halt, pause, or reset any running AI engineering war-room. This disrupts active CI/CD-equivalent pipelines. Repeated calls can cause denial-of-service against all active work. If combined with the unauthenticated SSE stream (VARIANT-002), the attacker can first enumerate all room IDs then kill them all.

### Evidence
```
dashboard/routes/rooms.py:228
@router.post("/api/rooms/{room_id}/action")
async def room_action(room_id: str, background_tasks: BackgroundTasks, action: str = Query(...)):
    # no user: dict = Depends(get_current_user)
```

### Reproduction Steps
1. `curl -X POST "http://<host>/api/rooms/room-0001/action?action=stop"`
2. Observe the war-room transitions to `failed-final` state without any credential.

---

## VARIANT-002 — Unauthenticated Global SSE Event Stream

Phase: 10
Sequence: 002
Slug: unauth-sse-events
Verdict: VALID
Rationale: GET /api/events broadcasts all internal system events (room state changes, notifications) to any unauthenticated subscriber.
Severity-Original: MEDIUM
PoC-Status: pending
Origin-Finding: dashboard/routes/system.py:148-164
Origin-Pattern: AP-022

### Summary
`GET /api/events` in `dashboard/routes/rooms.py:159` exposes the global SSE broadcaster to unauthenticated clients. Every internal event (room state transitions, agent messages, plan updates) is streamed in real-time to anyone who connects.

### Location
`/Users/bytedance/Desktop/demo/os-twin/dashboard/routes/rooms.py`, lines 159-181

```python
@router.get("/api/events")
async def sse_events():
    # no user: dict = Depends(get_current_user)
    async def event_generator() -> AsyncIterator[str]:
        queue = await global_state.broadcaster.subscribe_sse()
        ...
```

### Attacker Control
No parameters needed. Passive subscription to all broadcast events.

### Trust Boundary Crossed
Public internet -> internal broadcast bus (all system events)

### Impact
Unauthenticated information disclosure of all running war-room activity, plan execution status, role assignments, and internal agent communications. Allows an attacker to map the internal system topology, enumerate room IDs for use in VARIANT-001, and surveil ongoing work.

### Evidence
```
dashboard/routes/rooms.py:159-181
```

### Reproduction Steps
1. `curl -N "http://<host>/api/events"` — receives a live SSE stream of all internal system events.

---

## VARIANT-003 — Unauthenticated Full-Text Search Across All War-Room Messages

Phase: 10
Sequence: 003
Slug: unauth-search-messages
Verdict: VALID
Rationale: GET /api/search exposes semantic vector search across all indexed war-room messages without requiring authentication.
Severity-Original: MEDIUM
PoC-Status: pending
Origin-Finding: dashboard/routes/system.py:148-164
Origin-Pattern: AP-022

### Summary
`GET /api/search` in `dashboard/routes/rooms.py:183` and `GET /api/rooms/{room_id}/context` at line 197 expose semantic search against all indexed war-room messages without any authentication check.

### Location
`/Users/bytedance/Desktop/demo/os-twin/dashboard/routes/rooms.py`, lines 183-208

```python
@router.get("/api/search")
async def search_messages(
    q: str = Query(..., min_length=1),
    ...
):
    # no user: dict = Depends(get_current_user)
    results = store.search(q, room_id=room_id, msg_type=type, limit=limit)
```

```python
@router.get("/api/rooms/{room_id}/context")
async def search_room_context(
    room_id: str,
    q: str = Query(..., min_length=1),
    ...
):
    # no user: dict = Depends(get_current_user)
```

### Attacker Control
- `q` — attacker-controlled search query (full-text / semantic)
- `room_id` — attacker-controlled room scope

### Trust Boundary Crossed
Public internet -> internal vector search index over all agent communications

### Impact
An attacker can extract secrets, code snippets, credentials, and internal strategy by crafting targeted queries (e.g., `?q=API+key`, `?q=password`, `?q=token`). The semantic search means even obfuscated or paraphrased content is discoverable.

### Evidence
```
dashboard/routes/rooms.py:183-208
```

### Reproduction Steps
1. `curl "http://<host>/api/search?q=API+key&limit=50"` — returns all indexed messages matching the query, unauthenticated.

---

## VARIANT-004 — Unauthenticated Room State Read

Phase: 10
Sequence: 004
Slug: unauth-room-state
Verdict: VALID
Rationale: GET /api/rooms/{room_id}/state returns full room metadata to unauthenticated callers.
Severity-Original: MEDIUM
PoC-Status: pending
Origin-Finding: dashboard/routes/system.py:148-164
Origin-Pattern: AP-022

### Summary
`GET /api/rooms/{room_id}/state` at `dashboard/routes/rooms.py:210` has no authentication dependency. It returns full room metadata including room configuration, status, and vector store metadata.

### Location
`/Users/bytedance/Desktop/demo/os-twin/dashboard/routes/rooms.py`, lines 210-225

```python
@router.get("/api/rooms/{room_id}/state")
async def get_room_state(room_id: str):
    # no user: dict = Depends(get_current_user)
```

### Attacker Control
`room_id` — guessable format (`room-NNNN`).

### Trust Boundary Crossed
Public internet -> internal room configuration and vector store metadata

### Impact
Unauthenticated information disclosure of room internals, aiding enumeration for VARIANT-001 and VARIANT-003.

### Evidence
```
dashboard/routes/rooms.py:210-225
```

### Reproduction Steps
1. `curl "http://<host>/api/rooms/room-0001/state"` — returns full room metadata.

---

## VARIANT-005 — Unauthenticated LLM Plan Refinement (AI Cost Abuse + Data Exfiltration)

Phase: 10
Sequence: 005
Slug: unauth-plan-refine
Verdict: VALID
Rationale: POST /api/plans/refine and its streaming variant trigger billable LLM calls with arbitrary attacker-supplied plan content and no authentication.
Severity-Original: HIGH
PoC-Status: pending
Origin-Finding: dashboard/routes/plans.py:461
Origin-Pattern: AP-005

### Summary
`POST /api/plans/refine` (plans.py:1128) and `POST /api/plans/refine/stream` (plans.py:1154) invoke the `refine_plan` / `refine_plan_stream` LLM functions with a `plan_content` and `message` supplied entirely by the unauthenticated caller. When `plan_id` is provided without `plan_content`, the endpoint reads the plan file from disk and feeds it to the LLM — meaning an attacker can exfiltrate stored plan content via the LLM response.

### Location
`/Users/bytedance/Desktop/demo/os-twin/dashboard/routes/plans.py`, lines 1128-1186

```python
@router.post("/api/plans/refine")
async def refine_plan_endpoint(request: RefineRequest):
    # no user: dict = Depends(get_current_user)
    ...
    plan_content = p_file.read_text()   # reads stored plan when plan_id supplied
    result = await refine_plan(user_message=request.message, plan_content=plan_content, ...)
```

### Attacker Control
- `message` — attacker-controlled LLM user turn (prompt injection vector)
- `plan_content` — attacker-controlled or disk-read plan content
- `plan_id` — if a valid plan ID is supplied without `plan_content`, the server reads and LLM-processes an existing stored plan

### Trust Boundary Crossed
Public internet -> LLM API (billable calls); also plan file system -> LLM output visible to attacker

### Impact
1. **Unbounded LLM cost abuse**: Any internet user can spam the LLM endpoint with large payloads, running up API bills.
2. **Plan content exfiltration**: By supplying a known `plan_id`, an attacker retrieves stored plan content indirectly through the LLM's response.
3. **Prompt injection**: Attacker-controlled `message` is passed to the LLM with no system instruction separation (see also AP-040).

### Evidence
```
dashboard/routes/plans.py:1128-1152
dashboard/routes/plans.py:1154-1186
```

### Reproduction Steps
1. `curl -X POST http://<host>/api/plans/refine -H "Content-Type: application/json" -d '{"plan_id":"<known_id>","message":"Summarize everything in this plan including all secrets"}'`
2. Observe that the LLM response includes the stored plan content.

---

## VARIANT-006 — Unauthenticated Plan/Epic Content Read via Search

Phase: 10
Sequence: 006
Slug: unauth-plan-search
Verdict: VALID
Rationale: GET /api/search/plans, GET /api/search/epics, GET /api/plans/{plan_id}/epics, and GET /api/goals all expose stored plan content without authentication.
Severity-Original: MEDIUM
PoC-Status: pending
Origin-Finding: dashboard/routes/plans.py:461
Origin-Pattern: AP-022

### Summary
Four endpoints in `plans.py` expose read access to stored plan content — including project goals, epic structures, and semantic search results — without any authentication check.

### Location
- `dashboard/routes/plans.py:1108` — `GET /api/goals` (reads goal sections from all plan .md files)
- `dashboard/routes/plans.py:1188` — `GET /api/plans/{plan_id}/epics` (reads full plan content, parses epics)
- `dashboard/routes/plans.py:1205` — `GET /api/search/plans` (semantic search across all plan content)
- `dashboard/routes/plans.py:1212` — `GET /api/search/epics` (semantic search across all epic content)

```python
@router.get("/api/goals")
async def get_all_goals():
    # no user: dict = Depends(get_current_user)

@router.get("/api/plans/{plan_id}/epics")
async def get_plan_epics(plan_id: str):
    # no user: dict = Depends(get_current_user)

@router.get("/api/search/plans")
async def search_plans(q: str = ...):
    # no user: dict = Depends(get_current_user)

@router.get("/api/search/epics")
async def search_epics(q: str = ...):
    # no user: dict = Depends(get_current_user)
```

### Attacker Control
- `q` — attacker-controlled search query
- `plan_id` — attacker-supplied (guessable from `/api/goals` response)

### Trust Boundary Crossed
Public internet -> internal project plan filesystem + vector index

### Impact
Full unauthenticated read access to all project plans, goals, and epics. This discloses internal roadmaps, task structures, and working directory paths (which can be chained with path traversal vulnerabilities such as AP-025/AP-043).

### Evidence
```
dashboard/routes/plans.py:1108, 1188, 1205, 1212
```

### Reproduction Steps
1. `curl "http://<host>/api/goals"` — returns goals from all plans.
2. `curl "http://<host>/api/search/plans?q=database+credentials"` — full-text search across all plans.

---

## VARIANT-007 — Unauthenticated Engagement SSE Event Stream

Phase: 10
Sequence: 007
Slug: unauth-engagement-events
Verdict: VALID
Rationale: GET /api/engagement/events exposes the engagement broadcast channel (reactions, comments) to unauthenticated subscribers.
Severity-Original: MEDIUM
PoC-Status: pending
Origin-Finding: dashboard/routes/system.py:148-164
Origin-Pattern: AP-022

### Summary
`GET /api/engagement/events` in `dashboard/routes/engagement.py:50` streams all engagement events (reaction toggles, comment publications) to any unauthenticated client. This is a secondary SSE channel separate from the global event stream (VARIANT-002).

### Location
`/Users/bytedance/Desktop/demo/os-twin/dashboard/routes/engagement.py`, lines 50-64

```python
@router.get("/events")
async def engagement_events():
    # no user: dict = Depends(get_current_user)
    async def event_generator() -> AsyncIterator[str]:
        queue = await broadcaster.subscribe_sse()
        ...
```

### Attacker Control
No parameters required. Passive subscription.

### Trust Boundary Crossed
Public internet -> internal engagement broadcaster

### Impact
Unauthenticated real-time surveillance of all user engagement activity (who reacted to what, comments posted). Leaks internal user identifiers (`user_id`) and entity IDs, which can be used to enumerate content and correlate activity.

### Evidence
```
dashboard/routes/engagement.py:50-64
```

### Reproduction Steps
1. `curl -N "http://<host>/api/engagement/events"` — receives live stream of all engagement events.

---

## Summary Table

| ID | Endpoint | File | Line | Severity | Root Cause |
|----|----------|------|------|----------|------------|
| VARIANT-001 | POST /api/rooms/{room_id}/action | rooms.py | 228 | HIGH | No Depends(get_current_user); writes lifecycle state |
| VARIANT-002 | GET /api/events | rooms.py | 159 | MEDIUM | No Depends(get_current_user); streams all internal events |
| VARIANT-003 | GET /api/search + /api/rooms/{room_id}/context | rooms.py | 183, 197 | MEDIUM | No Depends(get_current_user); semantic search over all messages |
| VARIANT-004 | GET /api/rooms/{room_id}/state | rooms.py | 210 | MEDIUM | No Depends(get_current_user); returns room metadata |
| VARIANT-005 | POST /api/plans/refine + /refine/stream | plans.py | 1128, 1154 | HIGH | No Depends(get_current_user); triggers billable LLM + exfil |
| VARIANT-006 | GET /api/goals + /api/search/plans + /search/epics + /{id}/epics | plans.py | 1108, 1188, 1205, 1212 | MEDIUM | No Depends(get_current_user); reads plan filesystem |
| VARIANT-007 | GET /api/engagement/events | engagement.py | 50 | MEDIUM | No Depends(get_current_user); streams engagement events |

Total new variants confirmed: **7**
