# Round 2 Hypotheses — contradiction-reasoner-01
# Dashboard Backend — Contradiction / TRIZ / Abductive Analysis

---

## PH-13: Contradiction — Cookie httponly=True But Raw Key Also in JSON Response Body

- Reasoning-Model: Contradiction
- Target: `dashboard/routes/auth.py:43` — `login_for_access_token`
- Contradiction: The cookie is set with `httponly=True` (meaning JavaScript CANNOT read the cookie value — this is the protection), BUT the same raw API key is simultaneously returned in the JSON response body as `"access_token": _API_KEY`. JavaScript CAN read the JSON body. The httponly protection is completely negated.
- Attack precondition: Attacker can observe the login response (e.g., XSS on the frontend, browser extension, network intercept, logging middleware).
- Attack input: `POST /api/auth/token` with `{"key": "<valid_key>"}` — observe response body
- Code path: `auth.py:43-44 JSONResponse(content={"access_token": _API_KEY})` → `_API_KEY` transmitted to browser JS context
- Sanitizers on path: None. `secrets.compare_digest` protects the login check but not the response.
- Security consequence: Any XSS vulnerability in the frontend (including stored XSS via attacker-created plan content) can steal the API key from a `fetch('/api/auth/token')` response or from any response that includes the key. Key also appears in browser devtools, server logs, and proxy logs. No session rotation is possible since the "session token" is the permanent API key.
- Severity estimate: HIGH
- Confidence: HIGH

---

## PH-14: Contradiction — Cookie "secure" Missing — Cookie Transmitted Over HTTP in Plaintext

- Reasoning-Model: Contradiction
- Target: `dashboard/routes/auth.py:48` — `login_for_access_token` cookie setting
- Contradiction: Cookie has `httponly=True` (protection against JS theft) and `samesite="lax"` (CSRF protection), but is missing `secure=True`. The cookie is sent over HTTP connections in plaintext, destroying confidentiality while maintaining the illusion of security.
- Attack precondition: Attacker is on the same network (LAN, coffee shop Wi-Fi). Dashboard accessed over HTTP (no TLS — typical for local deployment).
- Attack input: Passive network interception of any HTTP request from browser to dashboard
- Code path: Browser sends `Cookie: ostwin_auth_key=<raw_api_key>` in HTTP headers → network-visible
- Sanitizers on path: None. `samesite=lax` only prevents cross-site POST requests, not network interception.
- Security consequence: MITM attacker on LAN can capture the raw API key from any authenticated HTTP request. Since the key never rotates and has a 30-day max_age, capture provides 30-day persistent access.
- Severity estimate: MEDIUM
- Confidence: HIGH

---

## PH-15: Contradiction — CORS Wildcard With Cookie-Based Auth Creates Mixed Security Model

- Reasoning-Model: Contradiction
- Target: `dashboard/api.py:108` — CORS middleware
- Contradiction: The auth system uses cookies (`samesite=lax`) which normally provides CSRF protection. However, `allow_origins=["*"]` with no `allow_credentials=True` means cross-origin requests CAN be made but WITHOUT cookies. Simultaneously, `allow_headers=["*"]` means the API key can be sent via `X-API-Key` header cross-origin. For unauthenticated endpoints, CORS provides zero protection. For authenticated endpoints, a cross-origin attacker CAN send the X-API-Key header if they obtained the key (e.g., via PH-13).
- Attack precondition: Attacker knows the API key (obtained via PH-13 XSS, network intercept, or DEBUG mode).
- Attack input: Cross-origin JS: `fetch("http://localhost:9000/api/env", {method:"POST", headers:{"X-API-Key":"<stolen_key>", "Content-Type":"application/json"}, body: JSON.stringify({entries: [{type:"var",key:"OSTWIN_API_KEY",value:"DEBUG",enabled:true}]})})`
- Code path: CORS middleware allows request → `auth.py:55 api_key = request.headers.get("x-api-key")` → key valid → auth passes
- Sanitizers on path: `allow_credentials` defaults to False (browsers block cookies cross-origin) but X-API-Key header is explicitly allowed by `allow_headers=["*"]`
- Security consequence: If attacker has the API key via any prior disclosure, they can use it cross-origin from a malicious page to perform authenticated operations (write .env, browse filesystem, etc.).
- Severity estimate: HIGH
- Confidence: MEDIUM

---

## PH-16: Contradiction — WebSocket "Ping/Pong Only" Claim vs. Full Internal Event Broadcast

- Reasoning-Model: Contradiction
- Target: `dashboard/api.py:86` — `websocket_endpoint`
- Contradiction: The WebSocket handler appears to only process `ping` messages from clients, implying limited functionality. But the `manager` object is the same `ConnectionManager` used by `global_state.broadcaster` — ALL internal agent events (plan launches, room state changes, notifications) are broadcast to ALL connected WebSocket clients, including unauthenticated ones.
- Attack precondition: Network access to port 9000. WebSocket connection capability.
- Attack input: `ws://localhost:9000/api/ws` — connect and listen
- Code path: `api.py:87 await manager.connect(websocket)` [no auth] → `global_state.py:29 await manager.broadcast(event_dict)` called on every internal event → all connected clients receive all events
- Sanitizers on path: JSON parsing only for incoming client messages. No filtering of broadcast events per client.
- Security consequence: Any unauthenticated client receives real-time feed of: plan IDs and status, room state transitions, agent action notifications, error messages (which may include stack traces with sensitive paths), any data included in broadcast payloads. Persistent connection provides ongoing surveillance of internal system activity.
- Severity estimate: MEDIUM
- Confidence: HIGH

---

## PH-17: Contradiction — fe_catch_all "Static File Server" Has No Path Jail

- Reasoning-Model: Contradiction
- Target: `dashboard/api.py:147` — `fe_catch_all`
- Contradiction: The catch-all handler is described as serving static frontend files from FE_OUT_DIR. But `Path.__truediv__` in Python does NOT prevent `..` traversal. The `exact.is_file()` check only verifies the target exists — it does NOT verify the target is within FE_OUT_DIR.
- Attack precondition: FE_OUT_DIR exists and has a known relative depth. Must know or guess a target file path.
- Attack input: `GET /../../dashboard/auth.py` or `GET /../../../../etc/passwd`
- Code path: `api.py:149 exact = FE_OUT_DIR / path` — e.g., FE_OUT_DIR="/app/dashboard/fe/out", path="../../dashboard/auth.py" → `exact = Path("/app/dashboard/fe/out/../../dashboard/auth.py")` = `/app/dashboard/auth.py` → `api.py:150 if exact.is_file(): return FileResponse(str(exact))`
- Sanitizers on path: NONE. `exact.is_file()` is a presence check, not a containment check.
- Assumed protection broken: FastAPI's `StaticFiles` mount (for `/_next`) does have path sanitization, but the catch-all route does NOT use StaticFiles — it manually constructs paths.
- Security consequence: Attacker can read any file on the filesystem that the server process can access, if they can determine the relative depth. Source code files (auth.py, plans.py — containing logic and possibly hardcoded values), .env files, configuration files, and system files are all accessible.
- Severity estimate: HIGH
- Confidence: MEDIUM (depends on depth guessing; `..` URL encoding may be normalized by FastAPI before path param extraction)

---

## PH-18: Contradiction — Post-Auth X-User Identity Spoofing

- Reasoning-Model: Contradiction
- Target: `dashboard/auth.py:96` — `get_current_user` (post-auth section)
- Contradiction: The auth module correctly validates the API key (constant-time compare), establishing identity. But then it OVERWRITES the identity with whatever the `X-User` request header says. The validation was correct but the identity assignment is broken.
- Attack precondition: Valid API key. (Or DEBUG mode where no key is needed.)
- Attack input: Any authenticated request to any endpoint with `X-User: admin` or `X-User: system` header
- Code path: `auth.py:83 provided_key = _extract_api_key(request)` → `auth.py:90 secrets.compare_digest(...)` → match → `auth.py:97 username = request.headers.get("x-user", "api-key-user")` → `{"username": "admin"}` returned
- Sanitizers on path: None on X-User header
- Security consequence: Any authenticated user can impersonate any other identity by sending X-User header. If the application makes authorization decisions based on username (e.g., admin-only features, audit logs attributing actions to users), those decisions are fully bypassed. This becomes critical in DEBUG mode where even the key check is bypassed — unauthenticated attacker can be "admin".
- Severity estimate: MEDIUM (requires valid key or DEBUG)
- Confidence: HIGH

---

## PH-19: Contradiction — verify_password Always Returns True — Dormant Full Auth Bypass

- Reasoning-Model: Contradiction
- Target: `dashboard/auth.py:29` — `verify_password`
- Contradiction: The function is named `verify_password` (implying validation), but its body is `return True` regardless of inputs. It is currently unused in the auth flow. But it is exported and available for any code — present or future — that imports it.
- Attack precondition: Any code path (plugin, test, future feature) that calls `verify_password(user_supplied_password, stored_hash)`.
- Attack input: Any string for either argument to verify_password
- Code path: `auth.py:29-30 def verify_password(plain_password, hashed_password): return True`
- Sanitizers on path: None
- Security consequence: If `verify_password` is ever called in a real auth decision, any password is accepted. Currently dormant but represents a time-bomb. Risk escalates if: (a) someone adds a password-based auth flow and calls this function thinking it works, (b) an LLM-generated code completion suggests using this function, (c) a future feature adds login by username+password.
- Severity estimate: MEDIUM (dormant) → HIGH if activated
- Confidence: HIGH (current state: dormant)

---

## PH-20: Contradiction — Working Dir Injection in Plan Meta Affects Room Path Resolution

- Reasoning-Model: Abductive
- Target: `dashboard/routes/plans.py:461` — `create_plan` (meta.json write) → `dashboard/api_utils.py` — `resolve_plan_warrooms_dir`
- Contradiction: The `working_dir` field from an unauthenticated plan creation request is stored verbatim in meta.json as `warrooms_dir`. This value is later used to construct filesystem paths for room directory lookups. The system assumes working_dir is a legitimate project directory, but it is attacker-controlled.
- Attack precondition: Network access to port 9000. Attacker creates plan with malicious working_dir.
- Attack input: Step 1: `POST /api/plans/create` with `{"path": "/tmp/x", "title": "test", "working_dir": "/etc"}` → meta.json written with `"warrooms_dir": "/etc/.war-rooms"`. Step 2: Any authenticated endpoint that calls `resolve_plan_warrooms_dir(plan_id)` for the attacker's plan.
- Code path: `plans.py:478 meta = {"warrooms_dir": str(Path(working_dir) / ".war-rooms"), ...}` → stored in meta.json → `api_utils.resolve_plan_warrooms_dir()` reads warrooms_dir from meta → uses it to construct room paths → room lookups scan attacker-specified base dir
- Sanitizers on path: None on working_dir field in CreatePlanRequest model
- Security consequence: An attacker can cause the dashboard to read room data from arbitrary filesystem paths. If `/etc/.war-rooms` or another attacker-chosen path contains `room-*` subdirectories, those are treated as war-rooms and their contents are read and returned to authenticated users. This enables reading attacker-planted data into the UI or triggering the `run_pytest_now` side-effect in `read_room()` if such a file is placed in the target directory.
- Severity estimate: MEDIUM
- Confidence: MEDIUM

---

## PH-21: Abductive — read_room Subprocess Side-Effect via Filesystem Plant

- Reasoning-Model: Abductive
- Target: `dashboard/api_utils.py:75` — `read_room`
- Contradiction: The `read_room` function, which is called when listing rooms, contains a subprocess execution triggered purely by file presence: `if (room_dir / "run_pytest_now").exists()`. This creates an implicit code execution path triggered by filesystem state.
- Attack precondition: Attacker can write a file named `run_pytest_now` to a directory that will be passed to `read_room`. This requires: either writing to a real war-room directory (needs room action endpoint or RCE) OR combining with PH-20 (working_dir injection pointing to attacker-writable directory).
- Attack input: If attacker controls /tmp/evil-room/: create files `run_pytest_now`, `status`, `task-ref` in /tmp/evil-room/. Then trigger a plan with working_dir="/tmp" → warrooms_dir="/tmp/.war-rooms". If /tmp/.war-rooms/evil-room/ exists, read_room is called on it → subprocess runs `pwsh -File <AGENTS_DIR>/debug_test.ps1`
- Code path: `api_utils.py:75 if (room_dir / "run_pytest_now").exists():` → `api_utils.py:77 command = ["pwsh", "-File", str(AGENTS_DIR / "debug_test.ps1")]` → `api_utils.py:78 result = subprocess.run(command, ...)`
- Sanitizers on path: Command is fixed (debug_test.ps1 from AGENTS_DIR) — not directly injectable. But the script path depends on AGENTS_DIR which could be modified via env injection.
- Security consequence: Indirect subprocess execution triggered by filesystem state. While the command itself is fixed, execution of the PowerShell script may have side effects. More critically, this demonstrates an implicit execution path that bypasses explicit auth checks — it's triggered by reading rooms, not by a dedicated endpoint.
- Severity estimate: MEDIUM
- Confidence: LOW (complex chain, multiple preconditions)

---

## PH-22: Abductive — SSE Event Stream Leaks Plan/Room IDs to Any Subscriber

- Reasoning-Model: Abductive
- Target: `dashboard/routes/rooms.py:159` — `sse_events`
- Contradiction: The SSE endpoint is designed as a real-time notification stream for the frontend. It has no auth, no origin check, and no per-subscriber filtering. Any client anywhere can subscribe and receive ALL events.
- Attack precondition: Network access to port 9000. Can maintain long-lived HTTP connection.
- Attack input: `GET /api/events` with `Accept: text/event-stream`
- Code path: `rooms.py:160 async def sse_events()` [NO AUTH] → `rooms.py:163 queue = await global_state.broadcaster.subscribe_sse()` → every `broadcaster.broadcast()` call delivers to all queues → includes plan_id, room_id, action types, status values
- Sanitizers on path: None — all fields from broadcast events are included
- Security consequence: Attacker maintains persistent surveillance of all internal operations. Learns plan IDs (needed for PH-12 plan status mutation and PH-10 second-order injection), room IDs (needed for PH-11 room traversal and room action), and real-time operational status. Combined with other unauthenticated endpoints, SSE acts as a reconnaissance channel that eliminates guessing.
- Severity estimate: MEDIUM
- Confidence: HIGH

---

## PH-23: Contradiction — /api/rooms/{id}/advance Writes Arbitrary target_state (No Allowlist)

- Reasoning-Model: Contradiction
- Target: `dashboard/routes/rooms.py:250` — `advance_room_state`
- Contradiction: The unauthenticated `room_action` endpoint correctly allowlists action values. But the authenticated `advance_room_state` endpoint writes `target_state` directly to the status file without ANY allowlist: `status_file.write_text(target_state)`.
- Attack precondition: Valid API key (authenticated).
- Attack input: `POST /api/rooms/<room_id>/advance` with body `{"target_state": "<arbitrary_string>"}`
- Code path: `rooms.py:263-264 target_state = request.get("target_state")` → `rooms.py:268 status_file.write_text(target_state)`
- Sanitizers on path: Only presence check (`if not target_state: raise 400`). No allowlist. No max length. No character validation.
- Security consequence: Authenticated user can write arbitrary strings to `{room_dir}/status` file. The orchestration layer reads this file to determine room state — injecting an invalid state could cause the orchestration to enter an undefined state or crash. With sufficiently long input, this is also a disk-write DoS vector. If the status value is later used in a shell command or included in a template, injection is possible.
- Severity estimate: MEDIUM
- Confidence: HIGH

---

## PH-24: Contradiction — plan_id Not Validated for Path Traversal in Unauthenticated Endpoints

- Reasoning-Model: Contradiction
- Target: `dashboard/routes/plans.py:768` — `update_plan_status` and `dashboard/routes/plans.py:1188` — `get_plan_epics`
- Contradiction: `plan_id` is a URL path parameter that is used directly to construct filesystem paths: `plans_dir / f"{plan_id}.meta.json"`. The code assumes plan_id is a safe alphanumeric identifier (12-char hex), but FastAPI does not enforce this constraint. Path traversal characters in plan_id could escape PLANS_DIR.
- Attack precondition: Network access to port 9000.
- Attack input: `POST /api/plans/%2E%2E%2Fsome-target/status` with body `{"status": "injected"}` — URL-encoded `../some-target` → plan_id="../../some-target" → `plans_dir / "../../some-target.meta.json"` → if file exists, read/write outside plans_dir
- Code path: `plans.py:770 meta_file = plans_dir / f"{plan_id}.meta.json"` → `plans.py:772 meta = json.loads(meta_file.read_text())` → `plans.py:775 meta_file.write_text(...)`
- Sanitizers on path: NONE. No validation that plan_id matches expected format. `.meta.json` suffix limits target extension.
- Security consequence: Attacker can read or overwrite `.meta.json` files outside PLANS_DIR if such files exist. The `.meta.json` suffix restriction limits targets, but combined with knowledge of application structure (other components writing .meta.json files), this could be exploitable. Also applicable to other plan routes that use plan_id in file paths.
- Severity estimate: MEDIUM
- Confidence: MEDIUM (FastAPI may normalize `%2E%2E` but this requires verification)
