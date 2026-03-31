# Cross-Model Seeds: dashboard-backend

---

## CROSS-01: API Key Disclosure Enables Cross-Origin Authenticated Env Injection

Source-A: PH-07 from backward-reasoner (round-1-hypotheses.md) — Env file injection to persist DEBUG bypass (requires valid API key)
Source-B: PH-13 from contradiction-reasoner (round-2-hypotheses.md) — API key returned in login response body (enables key theft via XSS or logging)
Connection: PH-07 requires a valid API key to POST /api/env. PH-13 provides the mechanism to steal that key. When combined: attacker steals API key from login response body (via XSS, logging, or devtools observation), then uses it cross-origin (CORS wildcard + X-API-Key header allowed by allow_headers=["*"]) to inject OSTWIN_API_KEY=DEBUG into ~/.ostwin/.env. On next restart, all auth is bypassed permanently.
Combined hypothesis: A two-step attack where Step 1 uses stored XSS (via unauthenticated plan content that renders in frontend) to capture the API key from /api/auth/token response, and Step 2 uses that key cross-origin to write a DEBUG-enabling .env entry. This requires no network-level access to the server itself — just an XSS payload in a plan.
Test direction for causal-verifier: Verify that (1) the login response body contains the raw API key, (2) CORS allow_headers includes X-API-Key, and (3) _serialize_env does not sanitize newlines in key/value fields. Confirm the startup dotenv loading picks up a new OSTWIN_API_KEY value when override=False.

---

## CROSS-02: SSE Reconnaissance Enables Targeted Plan-ID-Based Second-Order Injection

Source-A: PH-10 from backward-reasoner (round-1-hypotheses.md) — Second-order LLM injection via plan create (attacker needs plan_id for step 2)
Source-B: PH-22 from contradiction-reasoner (round-2-hypotheses.md) — SSE event stream leaks plan/room IDs to unauthenticated clients
Connection: PH-10 Step 2 (POST /api/plans/refine with plan_id) requires the attacker to know the plan_id generated in Step 1. The plan_id is derived from SHA256(path+timestamp)[:12] — not predictable. However, PH-22 shows that after Step 1 creates a plan, the plan_id is broadcast via the SSE stream (broadcaster.broadcast() is called in many places). The attacker can subscribe to SSE before Step 1, execute Step 1 (plan create), observe the plan_id in the event stream, then execute Step 2 (refine with that plan_id).
Combined hypothesis: Attacker subscribes to /api/events (unauthenticated), creates a malicious plan via /api/plans/create (unauthenticated), observes the plan_id in the event stream, then calls /api/plans/refine with that plan_id (unauthenticated) to execute the LLM injection. All three steps require zero authentication.
Test direction for causal-verifier: Confirm that plan creation events include plan_id in the SSE broadcast payload. Verify that the refine endpoint does NOT require auth and accepts plan_id to load plan content. Verify that plan content is passed to the LLM without sanitization.

---

## CROSS-03: Working Dir Injection + SSE Room Discovery Enables read_room Subprocess Trigger

Source-A: PH-21 from contradiction-reasoner (round-2-hypotheses.md) — read_room subprocess side-effect via run_pytest_now file
Source-B: PH-20 from contradiction-reasoner (round-2-hypotheses.md) — working_dir injection in plan meta causes room lookups to scan attacker-specified path
Connection: PH-21 requires read_room() to be called on an attacker-controlled directory. PH-20 provides the mechanism: by setting working_dir in an unauthenticated plan create to a path the attacker controls (e.g., /tmp/attack-rooms), the warrooms_dir in meta.json points to /tmp/attack-rooms/.war-rooms. Any authenticated request that calls resolve_plan_warrooms_dir() for that plan then scans /tmp/attack-rooms/.war-rooms/room-*/. If the attacker creates a directory /tmp/attack-rooms/.war-rooms/room-evil/ with a run_pytest_now file, the read_room() function will trigger subprocess execution of debug_test.ps1.
Combined hypothesis: Unauthenticated plan create with malicious working_dir, combined with attacker's ability to write files to the target directory (via PH-03/PH-01 or system access), triggers the run_pytest_now subprocess side-effect when an authenticated user lists rooms for that plan.
Test direction for causal-verifier: Verify that working_dir in CreatePlanRequest is stored verbatim in meta.json. Verify that resolve_plan_warrooms_dir() uses the stored warrooms_dir without validation. Verify that read_room() actually checks for run_pytest_now and executes subprocess. Confirm AGENTS_DIR/debug_test.ps1 exists and what it does.

---

## CROSS-04: fe_catch_all Path Traversal Exposes Source Files Including Auth Logic

Source-A: PH-06 from backward-reasoner (round-1-hypotheses.md) — DEBUG bypass enables full auth bypass (attacker seeks to confirm DEBUG is active)
Source-B: PH-17 from contradiction-reasoner (round-2-hypotheses.md) — fe_catch_all serves files without path jail
Connection: An attacker who suspects DEBUG mode is active (e.g., from error responses, headers, or public deployment patterns) can use PH-17 to read auth.py source code and confirm the DEBUG bypass condition. More broadly, PH-17 can serve dashboard/routes/system.py (revealing the /api/shell endpoint), plans.py (revealing all route structures), and ~/.ostwin/.env (revealing OSTWIN_API_KEY value directly). PH-17 thus acts as a reconnaissance accelerator for all other attacks.
Combined hypothesis: Attacker uses fe_catch_all path traversal to read /dashboard/auth.py and /dashboard/routes/system.py, discovering the DEBUG bypass code and the unauthenticated /api/shell endpoint. With knowledge of the exact OSTWIN_API_KEY from ~/.ostwin/.env (if reachable via traversal), they can authenticate directly. With DEBUG confirmed, they need no key at all.
Test direction for causal-verifier: Verify that FE_OUT_DIR / "../../dashboard/auth.py" resolves to the actual auth.py file. Verify that Path.__truediv__ with ".." does NOT normalize the path. Verify that FileResponse serves arbitrary files without containment check. Determine exact depth of FE_OUT_DIR from project root to calculate traversal path.

---

## CROSS-05: Unauthenticated Plan Create → Stored XSS → API Key Theft → Full Takeover

Source-A: PH-10 from backward-reasoner (round-1-hypotheses.md) — Unauthenticated plan create writes attacker content to disk
Source-B: PH-13 from contradiction-reasoner (round-2-hypotheses.md) — API key returned in login response body (XSS can steal it)
Connection: PH-10 establishes that plan content is written verbatim to disk. If the Next.js frontend renders plan content as HTML without sanitization (Markdown rendered to HTML), a plan with `<script>` tags or markdown XSS payloads (like `[x](javascript:...)`) constitutes stored XSS. Once any legitimate user views the plan in the frontend, their browser executes the attacker's JS, which can fetch `/api/auth/token` body (PH-13) if the user has recently logged in, or observe the API key in localStorage/cookies. This bridges from unauthenticated plan create to full account takeover without any direct auth bypass.
Combined hypothesis: Attacker plants XSS in plan content via unauthenticated create. When legitimate user views the plan, XSS fires, steals the API key from login response or storage, and POSTs it to attacker's server. This requires frontend rendering without sanitization (needs verification).
Test direction for causal-verifier: Verify whether the Next.js frontend renders plan content as raw HTML or sanitized markdown. Check for use of dangerouslySetInnerHTML or unsanitized markdown renderers in dashboard/fe/src. Verify that plan content from API is displayed to authenticated users in a browser context.

---

## CROSS-06: DEBUG Mode + X-User Spoofing Bypasses Any Future RBAC

Source-A: PH-06 from backward-reasoner (round-1-hypotheses.md) — DEBUG mode disables all auth
Source-B: PH-18 from contradiction-reasoner (round-2-hypotheses.md) — Post-auth X-User header spoofs identity even after valid auth
Connection: Both vulnerabilities interact with the identity returned by get_current_user. In normal mode, PH-18 requires a valid key. In DEBUG mode, PH-06 bypasses the key check, making PH-18 trivially usable by any unauthenticated attacker. The returned `{"username": <X-User value>}` dict is used for any RBAC decisions the application makes. If any endpoint uses `user["username"]` for access control (e.g., "only admin can do X"), both DEBUG and X-User spoofing individually bypass this.
Combined hypothesis: In DEBUG mode, any unauthenticated attacker can claim any identity. Even in normal mode, any authenticated user (including low-privilege users if multiple keys existed) can claim to be "admin" or "system". This completely undermines any future role-based access control additions.
Test direction for causal-verifier: Search all route handlers for uses of user["username"] in access control decisions. Verify that get_current_user returns X-User header value without validation in both DEBUG and normal modes. Confirm no username allowlist or format validation exists.
