# Evidence Harvest: dashboard-backend
# All Rounds (Round 1 + Round 2 + Round 3)

---

## Evidence for PH-01: Unauthenticated RCE via /api/shell

- Status: VALIDATED
- Fragility: Robust
- Primary evidence: `dashboard/routes/system.py:166-169`
  ```python
  @router.post("/shell")
  async def shell_command(command: str):
      result = subprocess.run(command, shell=True, capture_output=True, text=True)
      return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
  ```
- No `Depends(get_current_user)` in function signature
- `command: str` is a FastAPI query parameter (non-body param in POST handler)
- `subprocess.run(command, shell=True)` — confirmed shell injection
- Supporting: `dashboard/api.py:108-113` — no global auth middleware; auth is opt-in per route
- Attack: `POST http://host:9000/api/shell?command=id` — no credentials required

---

## Evidence for PH-02: Drive-by RCE via CORS + /api/shell

- Status: VALIDATED
- Fragility: Robust
- Primary evidence: `dashboard/api.py:108-113`
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- `allow_credentials` NOT set (defaults to False) — but unauthenticated endpoints don't need credentials
- `POST /api/shell` requires no cookies or auth headers → CORS wildcard allows any origin to POST
- Browser WILL allow reading response (`Access-Control-Allow-Origin: *` is set)
- Attack: Malicious page JavaScript `fetch("http://localhost:9000/api/shell?command=...", {method:"POST"})` executes from victim's machine

---

## Evidence for PH-03: Telegram Bot Token Theft

- Status: VALIDATED
- Fragility: Robust
- Primary evidence: `dashboard/routes/system.py:148-150`
  ```python
  @router.get("/telegram/config")
  async def get_telegram_config():
      return telegram_bot.get_config()
  ```
- No `Depends(get_current_user)` — confirmed unauthenticated
- Compare: adjacent endpoints `get_status` (line 70), `get_config` (line 140) all have `user: dict = Depends(get_current_user)` — this endpoint clearly omits it

---

## Evidence for PH-04: Telegram Config Overwrite

- Status: VALIDATED
- Fragility: Robust
- Primary evidence: `dashboard/routes/system.py:152-157`
  ```python
  @router.post("/telegram/config")
  async def save_telegram_config(config: TelegramConfigRequest):
      success = telegram_bot.save_config(config.bot_token, config.chat_id)
  ```
- No auth. `TelegramConfigRequest` model: only validates types (str, str) — no format validation of bot_token

---

## Evidence for PH-05: Unauthenticated Subprocess via /api/run_pytest_auth

- Status: VALIDATED
- Fragility: Robust
- Primary evidence: `dashboard/routes/system.py:171-185`
  ```python
  @router.get("/run_pytest_auth")
  async def run_pytest_auth():
      cmd = ["python3", "-m", "pytest", str(PROJECT_ROOT / "test_auth.py"), "-v"]
      process = await asyncio.create_subprocess_exec(*cmd, ...)
  ```
- No auth. Command args are fixed (not injectable), but execution can be triggered by any network-accessible client.
- stdout/stderr returned — test output may contain sensitive values

---

## Evidence for PH-06: DEBUG Auth Bypass

- Status: VALIDATED
- Fragility: Fragile (config-dependent: OSTWIN_API_KEY=DEBUG required)
- Primary evidence: `dashboard/auth.py:79-81`
  ```python
  if _API_KEY == "DEBUG":
      username = request.headers.get("x-user", "debug-user")
      return {"username": username}
  ```
- `_API_KEY` read from `os.environ.get("OSTWIN_API_KEY", "")` at module import (line 23)
- Comment in code: "DEBUG mode: skip auth entirely when OSTWIN_API_KEY=DEBUG" — intentional but dangerous
- Supporting: `dashboard/routes/auth.py:8` — separate module also reads `_API_KEY = os.environ.get("OSTWIN_API_KEY", "")` independently

---

## Evidence for PH-07: Env File Write to Persist DEBUG

- Status: VALIDATED (mechanism confirmed; fragile activation)
- Fragility: Fragile — requires valid auth + server restart + key not in system env
- Primary evidence: `dashboard/routes/system.py:254-270`
  ```python
  @router.post("/env")
  async def save_env(request: dict, user: dict = Depends(get_current_user)):
      entries = request.get("entries", [])
      content = _serialize_env(entries)
      _ENV_FILE.write_text(content)
  ```
- Auth required (`get_current_user`), but no validation of entry content
- `dashboard/api.py:18` — `load_dotenv(_env_file, override=False)` on startup
- If `OSTWIN_API_KEY` not already set in environment, dotenv loads it from file → DEBUG activates

---

## Evidence for PH-08: Newline Injection in _serialize_env

- Status: VALIDATED
- Fragility: Fragile — requires auth + restart + key not in system env
- Primary evidence: `dashboard/routes/system.py:62-65`
  ```python
  elif t == "var":
      key = e.get("key", "")
      value = e.get("value", "")
      if e.get("enabled", True):
          lines.append(f"{key}={value}")
  ```
- No sanitization of `\n` in key or value strings
- Payload: `{"entries": [{"type": "var", "key": "X", "value": "y\nOSTWIN_API_KEY=DEBUG", "enabled": true}]}` → writes `X=y\nOSTWIN_API_KEY=DEBUG` to .env file

---

## Evidence for PH-09: Filesystem Browse Without Jail

- Status: VALIDATED
- Fragility: Robust (auth required, but path is unrestricted)
- Primary evidence: `dashboard/routes/system.py:273-295`
  ```python
  target = Path(path).expanduser().resolve()
  if not target.exists() or not target.is_dir():
      raise HTTPException(status_code=400, detail="Not a valid directory")
  # NO jail check
  for entry in sorted(target.iterdir()):
  ```
- `Path(path).expanduser().resolve()` normalizes but does NOT restrict to any base dir
- `GET /api/fs/browse?path=/etc` returns listing of /etc
- Dotfile filtering is cosmetic (output filtering only), not a security control

---

## Evidence for PH-10: Second-Order LLM Injection

- Status: VALIDATED
- Fragility: Robust — both endpoints unauthenticated, plan_id returned in create response
- Primary evidence (Step 1): `dashboard/routes/plans.py:461-502`
  - No `Depends(get_current_user)` in `create_plan`
  - `plan_file.write_text(request.content)` at line 472 — verbatim write
  - Returns `{"plan_id": plan_id, ...}` in response
- Primary evidence (Step 2): `dashboard/routes/plans.py:1128-1152`
  - No `Depends(get_current_user)` in `refine_plan_endpoint`
  - Lines 1134-1138: reads plan content from disk using plan_id, passes to `refine_plan()`
- No content sanitization at either step

---

## Evidence for PH-12: Unauthenticated Plan Status Mutation

- Status: VALIDATED
- Fragility: Robust
- Primary evidence: `dashboard/routes/plans.py:768-790`
  ```python
  @router.post("/api/plans/{plan_id}/status")
  async def update_plan_status(plan_id: str, request: dict):
      meta["status"] = request.get("status", meta["status"])
      meta_file.write_text(json.dumps(meta, indent=2) + "\n")
  ```
- No auth. Status value unvalidated (any string accepted).

---

## Evidence for PH-13: API Key in Login Response Body

- Status: VALIDATED
- Fragility: Robust
- Primary evidence: `dashboard/routes/auth.py:43-44`
  ```python
  response = JSONResponse(content={
      "access_token": _API_KEY,
  ```
- Cookie is set (httponly=True) but the raw key is ALSO in the JSON body
- `_API_KEY` is the permanent secret (no rotation, no session tokens)

---

## Evidence for PH-14: Cookie Missing secure=True

- Status: VALIDATED
- Fragility: Robust (affects all HTTP deployments)
- Primary evidence: `dashboard/routes/auth.py:48-55`
  ```python
  response.set_cookie(
      key=AUTH_COOKIE_NAME,
      value=_API_KEY,
      httponly=True,
      samesite="lax",
      max_age=60 * 60 * 24 * 30,
      path="/",
  )
  ```
- No `secure=True` parameter — cookie transmitted over HTTP in plaintext

---

## Evidence for PH-16: WebSocket No Auth + Full Broadcast

- Status: VALIDATED
- Fragility: Robust
- Primary evidence: `dashboard/api.py:86-88`
  ```python
  @app.websocket("/api/ws")
  async def websocket_endpoint(websocket: WebSocket):
      await manager.connect(websocket)  # NO AUTH CHECK
  ```
- `global_state.py:29` — `manager.broadcast(event_dict)` called for all internal events
- `ws_router.py:20-28` — `ConnectionManager.broadcast()` sends to ALL active connections

---

## Evidence for PH-17: fe_catch_all Path Traversal

- Status: NEEDS_DEEPER
- Fragility: Fragile (depends on FastAPI/Starlette URL normalization)
- Primary evidence: `dashboard/api.py:146-160`
  ```python
  @app.api_route("/{path:path}", methods=["GET", "HEAD"])
  async def fe_catch_all(path: str):
      exact = FE_OUT_DIR / path
      if exact.is_file():
          return FileResponse(str(exact))
  ```
- Python `Path / ".."` does NOT strip `..` before OS resolution
- `FileResponse(str(exact))` uses raw path string
- NEEDS_DEEPER: FastAPI may normalize `..` in URL before route handler; requires live testing

---

## Evidence for PH-18: Post-Auth X-User Identity Spoofing

- Status: VALIDATED
- Fragility: Robust (always active for authenticated users)
- Primary evidence: `dashboard/auth.py:96-98`
  ```python
  # Allow X-User header for identity if API key is valid (for testing/dev)
  username = request.headers.get("x-user", "api-key-user")
  return {"username": username}
  ```
- X-User overrides identity even after successful key validation
- No validation of X-User format or allowlist

---

## Evidence for PH-19: verify_password Always Returns True

- Status: VALIDATED (dormant)
- Fragility: Fragile (dormant — only activates if called)
- Primary evidence: `dashboard/auth.py:29-30`
  ```python
  def verify_password(plain_password: str, hashed_password: str) -> bool:
      return True
  ```
- Currently unused in auth flow (confirmed: no calls to verify_password found in codebase)

---

## Evidence for PH-20: Working Dir Injection in Plan Meta

- Status: VALIDATED
- Fragility: Robust (mechanism confirmed; full chain requires write access to target dir)
- Primary evidence:
  - `dashboard/routes/plans.py:469,478` — `working_dir = request.working_dir or request.path` written verbatim to meta.json
  - `dashboard/api_utils.py:661-670` — `resolve_plan_warrooms_dir` reads `working_dir` from meta.json, constructs `wd / ".war-rooms"` with no validation of absolute paths
- Any plan lookup for an attacker-created plan uses attacker-controlled warrooms_dir

---

## Evidence for PH-22: SSE Leaks Internal Events

- Status: VALIDATED
- Fragility: Robust
- Primary evidence: `dashboard/routes/rooms.py:159-181`
  - No auth in `sse_events()`
  - All `broadcaster.broadcast()` calls deliver to all SSE subscribers
  - `dashboard/tasks.py:95,117,137` — room events include room details, status, IDs

---

## Evidence for PH-23: advance_room_state Writes Arbitrary target_state

- Status: VALIDATED
- Fragility: Robust (auth required but input unvalidated)
- Primary evidence: `dashboard/routes/rooms.py:250-296`
  ```python
  target_state = request.get("target_state")
  if not target_state:
      raise HTTPException(status_code=400, detail="target_state is required")
  status_file.write_text(target_state)  # NO ALLOWLIST
  ```
- Compare: unauthenticated `room_action` HAS an allowlist (stop/pause/resume/start); authenticated `advance_room_state` does NOT

---

## Evidence for CV-11: javascript: URI XSS in Markdown Renderer

- Status: VALIDATED
- Fragility: Fragile (requires user click)
- Primary evidence: `dashboard/fe/src/lib/markdown-renderer.tsx:83-94`
  ```tsx
  const match = subpart.match(/\[([^\]]+)\]\(([^)]+)\)/);
  if (match) {
    return <a key={Math.random()} href={match[2]} target="_blank" rel="noopener noreferrer" ...>
  ```
- `match[2]` is the URL — no scheme validation; `javascript:` URIs are set directly as href
- `escapeHtml` applied to text content only; URL in href is NOT escaped or validated
- `target="_blank"` with `rel="noopener noreferrer"` prevents window.opener abuse but does NOT prevent javascript: execution

---

## Summary Table

| ID | Hypothesis | Status | Fragility | Severity |
|----|-----------|--------|-----------|---------|
| PH-01 | Unauthenticated RCE via /api/shell | VALIDATED | Robust | CRITICAL |
| PH-02 | Drive-by RCE via CORS | VALIDATED | Robust | CRITICAL |
| PH-03 | Telegram token theft | VALIDATED | Robust | HIGH |
| PH-04 | Telegram config overwrite | VALIDATED | Robust | HIGH |
| PH-05 | Unauthenticated pytest subprocess | VALIDATED | Robust | HIGH |
| PH-06 | DEBUG auth bypass | VALIDATED | Fragile | CRITICAL |
| PH-07 | Env file DEBUG injection | VALIDATED | Fragile | HIGH |
| PH-08 | Newline injection in _serialize_env | VALIDATED | Fragile | HIGH |
| PH-09 | Filesystem browse without jail | VALIDATED | Robust | MEDIUM |
| PH-10 | Second-order LLM injection | VALIDATED | Robust | HIGH |
| PH-11 | Room ID path traversal | NEEDS_DEEPER | Fragile | MEDIUM |
| PH-12 | Unauthenticated plan status mutation | VALIDATED | Robust | MEDIUM |
| PH-13 | API key in login response body | VALIDATED | Robust | HIGH |
| PH-14 | Cookie missing secure flag | VALIDATED | Robust | MEDIUM |
| PH-15 | CORS+X-API-Key cross-origin | VALIDATED | Fragile | HIGH |
| PH-16 | WebSocket no auth + full broadcast | VALIDATED | Robust | MEDIUM |
| PH-17 | fe_catch_all path traversal | NEEDS_DEEPER | Fragile | HIGH |
| PH-18 | Post-auth X-User identity spoofing | VALIDATED | Robust | MEDIUM |
| PH-19 | verify_password always true (dormant) | VALIDATED | Fragile | MEDIUM |
| PH-20 | working_dir injection in plan meta | VALIDATED | Robust | MEDIUM |
| PH-21 | read_room subprocess side effect | NEEDS_DEEPER | Fragile | LOW |
| PH-22 | SSE leaks internal events | VALIDATED | Robust | MEDIUM |
| PH-23 | advance_room_state no allowlist | VALIDATED | Robust | MEDIUM |
| PH-24 | plan_id path traversal | NEEDS_DEEPER | Fragile | MEDIUM |
| CV-11 | javascript: URI XSS in markdown | VALIDATED | Fragile | MEDIUM |
