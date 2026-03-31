# Phase 7 Enrichment Report

> Phase 7 Enrichment Filter | Date: 2026-03-30 | Analyst: Claude (Sonnet 4.6)
> Input: 32 SAST candidates from Phase 4
> Output: enriched-findings.json

---

## Summary

| Metric | Count |
|--------|-------|
| Total candidates evaluated | 32 |
| Passed to Phase 8 Chamber | 29 |
| Dropped | 3 |
| CRITICAL findings passed | 2 |
| HIGH findings passed | 11 |
| MEDIUM findings passed | 16 |
| LOW findings dropped (mandatory) | 1 |
| Environment/admin-only dropped | 2 |

---

## Verdict Table

| Finding | Severity | Classification | Attacker Control | Trust Boundary Crossed | CodeQL Reachability | Verdict |
|---------|----------|---------------|-----------------|----------------------|-------------------|---------|
| SAST-001 | CRITICAL | security | HTTP POST body `command` param (unauthenticated) | Network → OS shell (RCE) | reachable (CGS-001, SK-001 tainted) | PASS_TO_CHAMBER |
| SAST-002 | CRITICAL | security | Any HTTP request with `OSTWIN_API_KEY=DEBUG` set | Unauthenticated → all authenticated endpoints | reachable (CGS-005) | PASS_TO_CHAMBER |
| SAST-003 | HIGH | security | Browser cross-origin request from any domain | Cross-origin → cookie-authenticated API | reachable (SK-002 in sinks.json, EP-020 and all auth'd routes) | PASS_TO_CHAMBER |
| SAST-004 | HIGH | security | HTTP POST body to unauthenticated route | Network → filesystem write | reachable (CGS-003, SK-008 tainted) | PASS_TO_CHAMBER |
| SAST-005 | HIGH | security | Vault file access (escalates via path traversal or post-exploitation) | File access → full secret decryption | reachable (CGS-004) | PASS_TO_CHAMBER |
| SAST-006 | HIGH | security | Discord guild member (any user who can @mention the bot) | Discord user input → LLM prompt context | reachable (CGS-002, SK-009 tainted) | PASS_TO_CHAMBER |
| SAST-007a | HIGH | security | HTTP GET to unauthenticated route | Network → subprocess spawn + stdout disclosure | reachable (EP-002 auth=false) | PASS_TO_CHAMBER |
| SAST-007b | HIGH | security | HTTP GET to unauthenticated route | Network → subprocess spawn | reachable (EP-003 auth=false) | PASS_TO_CHAMBER |
| SAST-008a | HIGH | security | HTTP GET to unauthenticated route | Network → Telegram bot token disclosure | reachable (EP-004 auth=false) | PASS_TO_CHAMBER |
| SAST-008b | HIGH | security | HTTP POST to unauthenticated route | Network → Telegram credential overwrite | reachable (EP-005 auth=false) | PASS_TO_CHAMBER |
| SAST-008c | HIGH | security | HTTP POST to unauthenticated route | Network → arbitrary Telegram message send | reachable (EP-006 auth=false) | PASS_TO_CHAMBER |
| SAST-009 | HIGH | security | Any caller who authenticates (login endpoint open) | Login response → raw API key in JSON body | reachable (SK-004 in sinks.json) | PASS_TO_CHAMBER |
| SAST-010 | MEDIUM | environment | Requires control of `process.env` on the Discord bot host | Env var → SSRF to arbitrary host | not reachable from network (requires admin/deployment access) | DROP |
| SAST-011 | MEDIUM | security | Any HTTP client that triggers login over plain HTTP | HTTP network → cookie interception | reachable (CGS-006, SK-003) | PASS_TO_CHAMBER |
| SAST-012 | MEDIUM | security | Any unauthenticated HTTP client | Network → real-time agent event stream | reachable (EP-020 auth=false) | PASS_TO_CHAMBER |
| SAST-013a | MEDIUM | security | Any unauthenticated HTTP client | Network → plan state mutation | reachable (EP-008 auth=false) | PASS_TO_CHAMBER |
| SAST-013b | MEDIUM | security | Any unauthenticated HTTP client | Network → unauthenticated LLM invocation / prompt injection | reachable (EP-010 auth=false) | PASS_TO_CHAMBER |
| SAST-013c | MEDIUM | security | Any unauthenticated HTTP client | Network → internal agent event disclosure (SSE) | reachable (EP-015 auth=false) | PASS_TO_CHAMBER |
| SAST-013d | MEDIUM | security | Any unauthenticated HTTP client | Network → room state mutation (stop/pause/resume) | reachable (EP-019 auth=false) | PASS_TO_CHAMBER |
| SAST-014a | MEDIUM | security | HTTP query parameter `path` (unauthenticated /api/fs/browse) | Network → arbitrary filesystem read via traversal | reachable (SK-011 tainted=true) | PASS_TO_CHAMBER |
| SAST-014b | MEDIUM | security | HTTP path parameter `plan_id`/`room_id` (unauthenticated endpoints) | Network → filesystem path traversal via api_utils | reachable (SK-008/SK-012 tainted=true, unauthenticated EPs) | PASS_TO_CHAMBER |
| SAST-014c | MEDIUM | security | HTTP path parameter `room_id` (unauthenticated room endpoints) | Network → room directory traversal | reachable (EP-017/018/019 auth=false) | PASS_TO_CHAMBER |
| SAST-014d | MEDIUM | security | HTTP path parameter `plan_id` (unauthenticated /api/plans/{id}/epics) | Network → plan directory traversal | reachable (EP-012 auth=false) | PASS_TO_CHAMBER |
| SAST-015 | MEDIUM | security | HTTP query parameter `q` on unauthenticated search endpoints | Network → ReDoS / regex injection on server | reachable (EP-013/014 auth=false) | PASS_TO_CHAMBER |
| SAST-016a | MEDIUM | security | HTTP request body to skills validate endpoint (auth bypassable via SAST-002) | Network → server-side CPU exhaustion (DoS) | reachable (auth bypassable; cross-user DoS impact on shared server) | PASS_TO_CHAMBER |
| SAST-016b | MEDIUM | security | HTTP request body to skills validate endpoint (auth bypassable via SAST-002) | Network → server-side CPU exhaustion (DoS) | reachable (same as SAST-016a) | PASS_TO_CHAMBER |
| SAST-017a | MEDIUM | security | Any caller who triggers an exception on mcp.py endpoints | Network → internal path/module structure disclosure in error response | reachable (mcp.py endpoints accessible) | PASS_TO_CHAMBER |
| SAST-017b | MEDIUM | security | Any caller who triggers an exception on mcp.py endpoints | Network → internal path/module structure disclosure | reachable (same as SAST-017a) | PASS_TO_CHAMBER |
| SAST-017c | MEDIUM | security | Any caller who triggers an exception on unauthenticated plans endpoints | Network → stack trace disclosure | reachable (multiple auth=false plan EPs) | PASS_TO_CHAMBER |
| SAST-017d | MEDIUM | security | Any caller who triggers an exception on roles endpoints | Network → stack trace disclosure (auth bypassable via SAST-002) | reachable (auth bypassable) | PASS_TO_CHAMBER |
| SAST-018 | MEDIUM | environment | Requires read access to log files on the host | Admin log access → secret exposure in log | not reachable from network (admin/host-only position) | DROP |
| SAST-019 | LOW | correctness | N/A — function not currently invoked in active auth path | None — dormant code | not reachable (dormant; SK-007 tainted=false) | DROP |

---

## Dropped Findings

### SAST-010 — SSRF via DASHBOARD_URL env var (MEDIUM, environment)

**Drop reason**: The source of the SSRF taint is `process.env.DASHBOARD_URL`. For an attacker to redirect API calls to an arbitrary host, they must control the environment variables of the Discord bot process. This requires a privileged position equivalent to local code execution on the deployment host. There is no network-facing entry point through which an external attacker can set this value. The finding is classified `environment` (admin/deployment-only trigger) and does not cross an attacker-accessible trust boundary.

**CodeQL note**: SK-010 is marked `tainted=true` in sinks.json, confirming the data flow exists. However, taint tracing starts at `process.env`, which is only controllable by a privileged operator, not a remote attacker. The reachability label is therefore `false` for the external attacker threat model.

### SAST-018 — Clear-text logging of sensitive data (MEDIUM, environment)

**Drop reason**: The logged secret exists in `.agents/mcp/config_resolver.py`. Exploitation requires read access to the application's log files on the host filesystem. This is an admin-equivalent position. No network-facing entry point exposes log contents. The finding is classified `environment` per the Phase 7 drop criteria for "admin safety" and "local tooling behavior where the attacker already has equivalent code execution."

### SAST-019 — verify_password() always returns True (LOW, correctness)

**Drop reason**: Mandatory LOW severity drop per Phase 7 rules. Additionally, `verify_password()` is dormant — it is not currently invoked in the active authentication code path. SK-007 is `tainted=false` in sinks.json, confirming no active taint flow. This is a future-risk correctness issue, not a presently exploitable vulnerability.

---

## CodeQL Reachability Cross-Reference Notes

### Pre-computed slices coverage

| Slice | Maps to SAST finding(s) | Reachability |
|-------|------------------------|-------------|
| CGS-001 | SAST-001 | reachable |
| CGS-002 | SAST-006 | reachable |
| CGS-003 | SAST-004 | reachable |
| CGS-004 | SAST-005 | reachable |
| CGS-005 | SAST-002 | reachable |
| CGS-006 | SAST-011 | reachable |

### Findings without pre-computed slices

The following 23 findings (SAST-003, 007a, 007b, 008a-c, 009, 010, 012, 013a-d, 014a-d, 015, 016a-b, 017a-d, 018) lack a dedicated CGS slice. Reachability was assessed via:
1. Direct cross-reference against `entry-points.json` (22 entries with `auth` flags)
2. Direct cross-reference against `sinks.json` (12 sinks with `tainted` flags)
3. Structural analysis of FastAPI route definitions confirming absence of `Depends(get_current_user)` on flagged routes

All 21 findings passed to the chamber were assessed as reachable via at least one of the above methods.

---

## Entry Point Coverage Notes

All 22 entry points from `entry-points.json` are accounted for in the enriched findings. The following entry points from `entry-points.json` do **not** appear in the 6 pre-computed DFD slices in `call-graph-slices.json`, representing unmodeled flows that Phase 8 should note:

- EP-002 (GET /api/run_pytest_auth) — subprocess spawn, no slice
- EP-003 (GET /api/test_ws) — subprocess spawn, no slice
- EP-004 (GET /api/telegram/config) — token disclosure, no slice
- EP-005 (POST /api/telegram/config) — credential overwrite, no slice
- EP-006 (POST /api/telegram/test) — arbitrary Telegram send, no slice
- EP-008 (POST /api/plans/{id}/status) — state mutation, no slice
- EP-009 (GET /api/goals) — info disclosure, no slice (not in SAST candidates)
- EP-010 (POST /api/plans/refine) — unauthenticated LLM, no slice
- EP-011 (POST /api/plans/refine/stream) — streaming LLM, no slice (not in SAST candidates)
- EP-012 through EP-019 — various plan/room info disclosure and mutation endpoints, no slices
- EP-020 (WS /api/ws) — WebSocket event broadcast, no slice
- EP-022 (DASHBOARD_URL) — SSRF env var, no slice

**Recommendation for Phase 8**: The call-graph-slices coverage is sparse (6 of 22 entry points). Reviewers should treat the entry-points.json list as the authoritative surface and not assume non-sliced paths are lower risk.

---

## Sinks Not Fully Modeled in DFD

| Sink | CWE | Mapped to DFD? | Notes |
|------|-----|---------------|-------|
| SK-001 subprocess.run(shell=True) | CWE-78 | Yes (DFD-1) | Covered by CGS-001 |
| SK-002 CORSMiddleware wildcard | CWE-346 | No | No DFD slice; SAST-003 covers it |
| SK-003 set_cookie missing secure | CWE-614 | Yes (DFD-6) | Covered by CGS-006 |
| SK-004 JSONResponse(access_token=_API_KEY) | CWE-200 | No | No DFD slice; SAST-009 covers it |
| SK-005 hardcoded vault key | CWE-321 | Yes (DFD-4) | Covered by CGS-004 |
| SK-006 DEBUG auth bypass | CWE-287 | Yes (DFD-5) | Covered by CGS-005 |
| SK-007 verify_password always True | CWE-798 | No | Dormant; SAST-019 dropped |
| SK-008 plan_file.write_text | CWE-22 | Yes (DFD-3) | Covered by CGS-003 |
| SK-009 generateContent prompt | CWE-74 | Yes (DFD-2) | Covered by CGS-002 |
| SK-010 fetch(DASHBOARD_URL) | CWE-918 | No | No DFD slice; SAST-010 dropped (environment) |
| SK-011 Path(path).expanduser().resolve() | CWE-22 | No | No DFD slice; SAST-014a covers it |
| SK-012 subprocess with plan content | CWE-78 | No | No DFD slice; partially covered by SAST-014b |

**Unmodeled high-risk sinks for Phase 8 attention**: SK-002 (CORS), SK-004 (key exposure), SK-011 (path traversal), SK-012 (subprocess with plan content). These sinks have confirmed taint flows but no pre-computed DFD slices — reviewers should treat them as first-class findings.

---

## Phase 7 Enrichment Notes

The following notes are appended to the knowledge base for downstream phases.

### Entry Points Without Phase 3 DFD Slice Coverage

Sixteen of the 22 entry points in `entry-points.json` have no corresponding slice in the Phase 3 DFD or the 6 CodeQL call-graph slices. This is a significant coverage gap. The most critical unsliced entries are:

1. **EP-002/EP-003** — unauthenticated subprocess endpoints. Subprocess stdout/stderr is returned to the caller, constituting information disclosure in addition to the process-spawn itself.
2. **EP-004/EP-005/EP-006** — unauthenticated Telegram configuration cluster. EP-004 discloses the bot token; EP-005 allows credential replacement enabling bot hijacking; EP-006 allows message impersonation.
3. **EP-010/EP-011** — unauthenticated LLM refine endpoints. These accept free-form text piped to the LLM, enabling prompt injection from the HTTP layer without requiring Discord membership.
4. **EP-020** — unauthenticated WebSocket. Broadcasts all real-time agent events including plan contents, room states, and potential credential fragments.

### Auth Bypass Amplifier (SAST-002)

The DEBUG auth bypass (SAST-002, CGS-005) amplifies every other missing-auth finding. When `OSTWIN_API_KEY=DEBUG`, any caller can impersonate any user on any otherwise-authenticated endpoint. This means:
- SAST-016a/b (ReDoS on skills endpoints that require auth) are fully reachable via the DEBUG bypass.
- SAST-017d (stack trace on roles.py, which requires auth) is fully reachable via the DEBUG bypass.
- Any future endpoint that adds `Depends(get_current_user)` remains bypassed if the DEBUG key is set.

Phase 8 reviewers should treat SAST-002 as a multiplier that makes the effective authentication posture of the entire application equivalent to "no authentication."

### Path Traversal Cluster (SAST-014a-d)

The four path traversal findings form a cluster that, when combined with the unauthenticated file write in SAST-004 (CGS-003), creates a potential write-what-where primitive:
- SAST-014a allows reading arbitrary filesystem paths via `/api/fs/browse`
- SAST-014b/c/d allow traversal in plan/room ID parameters
- SAST-004 allows writing arbitrary content to `~/.ostwin/plans/{plan_id}.md`

If `plan_id` is not sanitized before path construction and the write endpoint is also accessible, an attacker may be able to write files outside the intended plans directory. Phase 8 should assess whether CGS-003 + SAST-014b constitute a chained write-primitive.
