# Attack Surface Map: dashboard-backend

## Entry Points

- `dashboard/routes/system.py:167` — `shell_command` — POST /api/shell; accepts `command: str` query param; no auth
- `dashboard/routes/system.py:171` — `run_pytest_auth` — GET /api/run_pytest_auth; no auth; spawns pytest subprocess
- `dashboard/routes/system.py:187` — `run_ws_test` — GET /api/test_ws; no auth; spawns test_ws.py subprocess
- `dashboard/routes/system.py:148` — `get_telegram_config` — GET /api/telegram/config; no auth; returns bot token + chat ID
- `dashboard/routes/system.py:152` — `save_telegram_config` — POST /api/telegram/config; no auth; accepts bot_token, chat_id
- `dashboard/routes/system.py:159` — `test_telegram_connection` — POST /api/telegram/test; no auth; sends Telegram message
- `dashboard/routes/system.py:254` — `save_env` — POST /api/env; authenticated; writes ~/.ostwin/.env with attacker-supplied entries dict
- `dashboard/routes/system.py:273` — `browse_filesystem` — GET /api/fs/browse?path=; authenticated; accepts arbitrary path string
- `dashboard/routes/plans.py:461` — `create_plan` — POST /api/plans/create; no auth; accepts title, content, path, working_dir; writes files to disk
- `dashboard/routes/plans.py:768` — `update_plan_status` — POST /api/plans/{plan_id}/status; no auth; accepts status dict
- `dashboard/routes/plans.py:1129` — `refine_plan` (via refine route) — POST /api/plans/refine; no auth; passes message to LLM
- `dashboard/routes/plans.py:1155` — `refine_stream` — POST /api/plans/refine/stream; no auth; streams LLM response
- `dashboard/routes/plans.py:1109` — `get_goals` — GET /api/goals; no auth; aggregates plan data
- `dashboard/routes/plans.py:1189` — `get_epics` — GET /api/plans/{id}/epics; no auth; lists epics
- `dashboard/routes/plans.py:1206` — `search_plans` — GET /api/search/plans?q=; no auth; min_length=1 only
- `dashboard/routes/plans.py:1213` — `search_epics` — GET /api/search/epics?q=; no auth; min_length=1 only
- `dashboard/routes/rooms.py:159` — `sse_events` — GET /api/events; no auth; streams all internal agent events
- `dashboard/routes/rooms.py:183` — `search_messages` — GET /api/search?q=; no auth; semantic vector search
- `dashboard/routes/rooms.py:197` — `search_room_context` — GET /api/rooms/{id}/context?q=; no auth; room-scoped vector search
- `dashboard/routes/rooms.py:210` — `get_room_state` — GET /api/rooms/{id}/state; no auth; room metadata
- `dashboard/routes/rooms.py:228` — `room_action` — POST /api/rooms/{id}/action?action=; no auth; writes status file; only allowlist enforced is ["stop","pause","resume","start"]
- `dashboard/api.py:86` — `websocket_endpoint` — WS /api/ws; no auth; broadcasts all internal events to any connected client
- `dashboard/routes/auth.py:12` — `login_for_access_token` — POST /api/auth/token; accepts JSON {key}; returns raw API key in response body
- `dashboard/auth.py:72` — `get_current_user` — dependency used by all auth-gated routes; DEBUG bypass at line 79
- `dashboard/api.py:146` — `fe_catch_all` — GET /{path:path}; static file serving with path-based resolution; no jail check against FE_OUT_DIR

## Trust Boundary Crossings

- TB-1: Internet/LAN → FastAPI (0.0.0.0:9000) — any network-reachable host can reach all endpoints; CORS wildcard means any origin is accepted including cross-origin JS
- TB-5: FastAPI → OS Shell — `POST /api/shell` passes attacker-controlled `command` string directly to `subprocess.run(shell=True)` without any auth or validation check
- TB-4: FastAPI → Filesystem (plans) — `POST /api/plans/create` writes attacker-controlled `content` to ~/.ostwin/plans/{plan_id}.md and associated .meta.json / .roles.json
- TB-4: FastAPI → Filesystem (env) — `POST /api/env` writes attacker-controlled entries to ~/.ostwin/.env; environment controls all API keys and auth
- TB-4: FastAPI → Filesystem (telegram) — `POST /api/telegram/config` writes attacker-controlled bot_token/chat_id to telegram_config.json
- TB-4: FastAPI → Filesystem (room status) — `POST /api/rooms/{id}/action` writes to {room_dir}/status file with allowed values only
- TB-5: FastAPI → OS Shell (subprocess) — `GET /api/run_pytest_auth` and `GET /api/test_ws` spawn subprocesses without auth
- TB-1 cross-origin: CORS `allow_origins=["*"]` + unauthenticated endpoints enables drive-by exploitation from any malicious webpage (TA2)

## Auth / AuthZ Decision Points

- `dashboard/auth.py:72` — `get_current_user` — the single auth gate; DEBUG bypass at line 79 skips all validation when OSTWIN_API_KEY=="DEBUG"; used as Depends() on individual routes only
- `dashboard/auth.py:79-81` — DEBUG bypass — when `_API_KEY == "DEBUG"`, any X-User header value becomes the authenticated username; no key check at all
- `dashboard/auth.py:90` — `secrets.compare_digest` — correct constant-time comparison when not in DEBUG mode
- `dashboard/routes/auth.py:29` — login guard — `if not key or not _API_KEY` rejects empty key login (sound)
- `dashboard/routes/auth.py:36` — `secrets.compare_digest(str(key), _API_KEY)` — correct comparison but raw _API_KEY returned in response body at line 44
- `dashboard/routes/auth.py:43-44` — `"access_token": _API_KEY` — raw secret returned in login response body (info disclosure)
- `dashboard/auth.py:96-97` — post-auth X-User header — even when properly authenticated, `X-User` header overrides username; allows identity spoofing by any valid-key holder

## Validation / Sanitization Functions

- `dashboard/routes/rooms.py:185,186` — `q: str = Query(..., min_length=1)` — search query: only minimum length enforced; no sanitization, no injection prevention
- `dashboard/routes/plans.py` — `CreatePlanRequest` Pydantic model — validates field types only; no content sanitization, no path traversal prevention on `path` field
- `dashboard/routes/system.py:167` — `command: str` query param in `shell_command` — NO validation whatsoever
- `dashboard/routes/system.py:273` — `path: str = Query(None)` in `browse_filesystem` — uses `.expanduser().resolve()` then `is_dir()` but no jail check against a safe base directory; can browse entire filesystem
- `dashboard/routes/system.py:52` — `_serialize_env` — no key/value sanitization; entries accepted as raw dict from request body; key injection (e.g., injecting newlines) possible
- `dashboard/auth.py:55` — `_extract_api_key` — checks header/bearer/cookie in order; no timing-safe check until compare_digest in line 90

## Layer Trust Chain

For each layer transition in this component:

| From Layer | To Layer | Trust Assumption | Holds for ALL paths? | Alternate Paths that Skip This Layer? |
|-----------|---------|-----------------|:---:|---|
| Internet/LAN (TB-1) | FastAPI Router | Request is from authenticated user | NO | 18+ endpoints have no auth at all; CORS wildcard allows cross-origin |
| CORS Middleware | Route Handler | Preflight has been validated | NO | CORS `allow_origins=["*"]` — all origins accepted; no cookies blocked |
| Route Handler | `get_current_user` | All routes enforce Depends(get_current_user) | NO | system.py:167,171,187,148,152,159; plans.py:461,768,1109,1129,1155,1189,1206,1213; rooms.py:159,183,197,210,228; api.py:86 all skip |
| `get_current_user` | Auth logic | API key is real (not DEBUG) | NO | `_API_KEY == "DEBUG"` path at auth.py:79 skips all key validation |
| Auth Layer | Handler logic | Authenticated user is who they claim to be | NO | auth.py:96-97: X-User header overrides identity even after valid auth |
| Handler | subprocess.run | Command input is safe/allowlisted | NO | system.py:167: no allowlist, no sanitization, shell=True |
| Handler | Filesystem (plans) | Written content is safe | NO | plans.py:461: attacker-controlled content written verbatim; later consumed by LLM, frontend, search |
| Handler | Filesystem (env) | Env entries are validated | NO | system.py:254: raw dict from request body; no key/value sanitization |
| Handler | Filesystem (browse) | Path is within safe base directory | NO | system.py:273: resolve() used but no jail check; entire filesystem accessible |
| Authenticated Handler | WebSocket /api/ws | Only authenticated clients connect | NO | api.py:86: WS upgrade has no auth check; broadcasts to all connected clients |
| Service | LLM (refine) | User message is safe for LLM context | NO | plans.py refine endpoints: unauthenticated; user message passed to LLM without sanitization |

## Trust Chain Gaps (rows where "Alternate Paths" column is NOT empty)

- **GAP-1 (CRITICAL): Missing auth on 18+ route handlers** — The opt-in `Depends(get_current_user)` model means any route that omits the dependency is fully unauthenticated. Affects: `POST /api/shell` (RCE), `GET /api/run_pytest_auth`, `GET /api/test_ws`, `GET|POST /api/telegram/config`, `POST /api/telegram/test`, `POST /api/plans/create`, `POST /api/plans/{id}/status`, and all read endpoints in rooms.py and plans.py.
- **GAP-2 (CRITICAL): DEBUG auth bypass** — When `OSTWIN_API_KEY=DEBUG`, `get_current_user` skips all validation. Any route using `Depends(get_current_user)` becomes unauthenticated. X-User header allows identity spoofing. Affects ALL routes.
- **GAP-3 (CRITICAL): shell=True with no input validation** — `POST /api/shell` passes the raw `command` query parameter to `subprocess.run(shell=True)`. No auth, no allowlist, no sanitization. Trivial RCE.
- **GAP-4 (HIGH): CORS wildcard** — `allow_origins=["*"]` allows any website to make cross-origin requests. Combined with unauthenticated endpoints, enables drive-by RCE from malicious webpages (victim visits page, JS POSTs to http://localhost:9000/api/shell).
- **GAP-5 (HIGH): WebSocket /api/ws has no auth** — Any client can connect to the WebSocket and receive all internal agent events broadcast to connected clients.
- **GAP-6 (HIGH): Filesystem browse without jail** — `GET /api/fs/browse?path=` resolves the path but does not verify it stays within a safe base directory. Authenticated users can enumerate the entire filesystem.
- **GAP-7 (HIGH): Env file write without sanitization** — `POST /api/env` writes attacker-controlled key=value pairs to ~/.ostwin/.env. Injecting `OSTWIN_API_KEY=DEBUG` into the env file would cause the DEBUG bypass to activate on next restart.
- **GAP-8 (MEDIUM): Post-auth identity spoofing via X-User header** — Even authenticated requests can use X-User to override their username in the returned user dict.
- **GAP-9 (MEDIUM): Unauthenticated plan create → second-order injection** — Attacker-controlled content in plan files is later consumed by the LLM refine endpoint, the Discord search, and potentially rendered by the frontend (stored XSS).
- **GAP-10 (MEDIUM): Room action without target_state validation** — `POST /api/rooms/{id}/action` validates action against ["stop","pause","resume","start"] but `POST /api/rooms/{id}/advance` writes arbitrary `target_state` values to the status file (auth-gated but target_state is unvalidated).
- **GAP-11 (MEDIUM): Static file catch-all without path jail** — `fe_catch_all` in api.py resolves paths under FE_OUT_DIR but the resolution logic iterates directories without verifying the final served file is within FE_OUT_DIR.
