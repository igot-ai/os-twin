# Commit Archaeology Report

**Repository**: os-twin (`git@github.com / origin/main`)
**Commit range**: all history (single commit) — HEAD `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
**Branches searched**: main (origin/main)
**Languages detected**: Python (88 files), TypeScript (32 files), JavaScript (20 files)
**Project security vocabulary discovered**:
- `PROJECT_VOCAB_VALIDATORS`: `escapeHtml`, `compare_digest`, `secrets.compare_digest`, `MAX_BODY_BYTES`, `VALID_TYPES`, `VALID_ROLES`
- `PROJECT_VOCAB_AUTH`: `get_current_user`, `_API_KEY`, `OSTWIN_API_KEY`, `AUTH_COOKIE_NAME`, `Depends(get_current_user)`
- `PROJECT_VOCAB_CONFIG`: `CORSMiddleware`, `allow_origins`, `OSTWIN_VAULT_KEY`, `httponly`, `samesite`
**Scan date**: 2026-03-30T00:00:00Z
**Total commits in repo**: 1

> NOTE: This repository has only a single initial commit. There is no multi-commit history to mine with git pickaxe techniques. All findings below are based on static analysis of the current HEAD snapshot — they represent security issues present at first commit, not regressions introduced over time. They are equally valid for Phase 2 deep-probe targeting.

---

## Summary Statistics

| Category | Findings | HIGH | MEDIUM | LOW |
|----------|----------|------|--------|-----|
| 1. Dangerous Pattern Introductions | 5 | 3 | 1 | 1 |
| 2. Security Control Weakening | 4 | 2 | 2 | 0 |
| 3. Silent Security Fixes | 0 | 0 | 0 | 0 |
| 4. Reverted Security Fixes | 0 | 0 | 0 | 0 |
| 5. Secret Archaeology | 2 | 1 | 1 | 0 |
| 6. CI/CD Pipeline Changes | 0 | 0 | 0 | 0 |
| 7. Suspicious Patterns | 1 | 0 | 1 | 0 |
| **Total (deduplicated)** | **12** | **6** | **5** | **1** |

---

## Priority Commits (top findings, ordered by risk)

Since the repository contains only one commit, entries reference the sole commit SHA `4c06f66` and the specific file/line where the issue exists.

| # | SHA | Category | Risk | File | Description | Recommended Phase |
|---|-----|----------|------|------|-------------|-------------------|
| 1 | 4c06f66 | 1 | HIGH | `dashboard/routes/system.py:167-169` | Unauthenticated arbitrary shell command execution via `POST /api/shell` | Phase 2 + Phase 5 |
| 2 | 4c06f66 | 2 | HIGH | `dashboard/routes/system.py:149-164` | Telegram config read/write/test with no auth (`get_current_user` absent) | Phase 2 + Phase 5 |
| 3 | 4c06f66 | 1 | HIGH | `dashboard/routes/system.py:171-185` | Unauthenticated pytest/test-script execution (`/api/run_pytest_auth`, `/api/test_ws`) | Phase 2 + Phase 5 |
| 4 | 4c06f66 | 2 | HIGH | `dashboard/api.py:109-113` | Wildcard CORS (`allow_origins=["*"]`) with cookie-based auth enables cross-origin credential theft | Phase 2 + Phase 5 |
| 5 | 4c06f66 | 1 | HIGH | `dashboard/routes/plans.py:461-502` | `POST /api/plans/create` has no authentication; creates files and sets `working_dir` on the host | Phase 2 + Phase 5 |
| 6 | 4c06f66 | 5 | HIGH | `dashboard/telegram_config.json` | Telegram bot token committed in-repo as `"test_token"` placeholder — stored in plaintext JSON on disk | Phase 2 |
| 7 | 4c06f66 | 1 | MEDIUM | `.agents/mcp/vault.py:117` | Hardcoded fallback encryption key `ostwin-default-insecure-key-32ch` used when `OSTWIN_VAULT_KEY` not set | Phase 5 |
| 8 | 4c06f66 | 2 | MEDIUM | `dashboard/routes/rooms.py:159,183,197,210,228` | Five room/event routes (`/api/events`, `/api/search`, `/api/rooms/{id}/context`, `/api/rooms/{id}/state`, `/api/rooms/{id}/action`) have no `get_current_user` dependency | Phase 5 |
| 9 | 4c06f66 | 1 | MEDIUM | `dashboard/routes/system.py:110-115` | `GET /api/run_tests_direct` hardcodes an absolute path to a developer machine (`/Users/paulaan/...`) and executes it | Phase 5 |
| 10 | 4c06f66 | 2 | MEDIUM | `dashboard/routes/plans.py:1108,1128,1188,1205,1212` | Five plan routes (`/api/goals`, `/api/plans/refine`, `/api/plans/refine/stream`, `/api/plans/{id}/epics`, `/api/search/*`) are unauthenticated | Phase 5 |
| 11 | 4c06f66 | 5 | MEDIUM | `dashboard/routes/auth.py:43-45` | Login success response echoes back `access_token: _API_KEY` (the raw secret) in the JSON body | Phase 5 |
| 12 | 4c06f66 | 7 | MEDIUM | `dashboard/api.py:86-105` | WebSocket endpoint `/api/ws` has no authentication; any client can subscribe | Phase 5 |

---

## Category 1: Dangerous Pattern Introductions

### [4c06f66-SYS-SHELL] Unauthenticated Arbitrary Shell Command Execution

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **File**: `dashboard/routes/system.py` lines 166–169
- **Pattern**: `subprocess.run(command, shell=True, ...)` where `command` is a raw query parameter
- **Discovery source**: generic baseline (shell=True + user-supplied input)
- **Risk**: HIGH
- **FP assessment**: The function signature `async def shell_command(command: str)` takes `command` directly from the HTTP POST body as a string. There is no authentication dependency (`get_current_user` is absent), no input sanitization, no allowlist, and `shell=True` enables full shell metacharacter expansion. Any unauthenticated HTTP client can execute arbitrary OS commands as the dashboard process owner. This is a textbook Remote Code Execution (RCE) vulnerability.
- **Downstream**: Phase 2 (`type: undisclosed-fix`) + Phase 5 (deep-probe)

```python
# dashboard/routes/system.py:166-169
@router.post("/api/shell")
async def shell_command(command: str):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
```

---

### [4c06f66-SYS-TESTS] Unauthenticated Test Script Execution Endpoints

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **Files**: `dashboard/routes/system.py` lines 110–115, 171–185, 187–196
- **Pattern**: `subprocess.run` / `asyncio.create_subprocess_exec` called from unauthenticated HTTP GET handlers
- **Discovery source**: generic baseline (subprocess + missing auth)
- **Risk**: HIGH
- **FP assessment**: Three endpoints — `GET /api/run_tests_direct`, `GET /api/run_pytest_auth`, `GET /api/test_ws` — invoke Python subprocesses without any `Depends(get_current_user)` guard. `run_tests_direct` also hardcodes an absolute path to a developer machine (`/Users/paulaan/PycharmProjects/...`), confirming this is leftover developer debugging code inadvertently shipped to production. Any unauthenticated caller can trigger these subprocess launches.
- **Downstream**: Phase 2 + Phase 5

---

### [4c06f66-PLANS-CREATE] Unauthenticated Plan Creation with Host Filesystem Write

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **File**: `dashboard/routes/plans.py` lines 461–502
- **Pattern**: `@router.post("/api/plans/create")` with no `Depends(get_current_user)`, accepts `working_dir` from request body, writes files to disk
- **Discovery source**: project-vocab discovery (`get_current_user` absent)
- **Risk**: HIGH
- **FP assessment**: The `create_plan` handler has no authentication dependency. It writes arbitrary plan content to the plans directory and uses the caller-supplied `working_dir` / `path` as filesystem references. While it does not directly traverse paths, an unauthenticated actor can create plans and influence the `meta.json` `working_dir` field, which is later used by the authenticated `launch` endpoint to call `subprocess.Popen([run_sh, plan_path])`. This creates a two-step pre-auth write → post-auth exec chain.
- **Downstream**: Phase 2 + Phase 5

---

### [4c06f66-VAULT-KEY] Hardcoded Fallback Encryption Key in Vault

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **File**: `.agents/mcp/vault.py` line 117
- **Pattern**: Hardcoded default encryption key string used as fallback when `OSTWIN_VAULT_KEY` env var is absent
- **Discovery source**: generic baseline (hardcoded key)
- **Risk**: MEDIUM
- **FP assessment**: `EncryptedFileVault._get_encryption_key()` falls back to `b"ostwin-default-insecure-key-32ch"` when no environment variable is configured. The in-code comment even acknowledges this: `# Default key (insecure, but better than plaintext if cryptography is available)`. Any attacker with read access to the vault file (`~/.ostwin/mcp/.vault.enc`) can decrypt it using this published key.
- **Downstream**: Phase 5

---

### [4c06f66-DEVPATH] Developer Machine Absolute Path Hardcoded in Production Endpoint

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **File**: `dashboard/routes/system.py` line 114
- **Pattern**: `subprocess.run(["python3", "/Users/paulaan/PycharmProjects/agent-os/..."], ...)`
- **Discovery source**: generic baseline (hardcoded path in subprocess call)
- **Risk**: LOW
- **FP assessment**: This path refers to a specific developer's machine and will silently fail (or worse, succeed if a file at that path exists on a deployment server with a matching username). The endpoint is shipped in production code with no auth guard.
- **Downstream**: Phase 5

---

## Category 2: Security Control Weakening

### [4c06f66-CORS-WILDCARD] Wildcard CORS with Cookie-Based Authentication

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **File**: `dashboard/api.py` lines 108–113
- **Pattern**: `allow_origins=["*"]` combined with `allow_credentials` not explicitly set, but httponly cookies used for auth
- **Discovery source**: project-vocab discovery (`CORSMiddleware`, `allow_origins`)
- **Risk**: HIGH
- **FP assessment**: The application uses `httponly=True` cookies for auth (`AUTH_COOKIE_NAME`). The CORS middleware uses `allow_origins=["*"]` which, per the Fetch specification, means the browser will NOT send cookies for cross-origin requests (wildcard and `allow_credentials=True` cannot coexist). However, the wildcard still allows cross-origin reads of JSON responses for unauthenticated endpoints. Additionally, any future addition of `allow_credentials=True` would create a full CSRF/cross-origin exfiltration scenario. The current config is at best one line away from a critical vulnerability and exposes all unauthenticated API responses to any origin.
- **Downstream**: Phase 2 + Phase 5

---

### [4c06f66-TELEGRAM-NOAUTH] Telegram Config Endpoints Missing Authentication

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **File**: `dashboard/routes/system.py` lines 148–164
- **Pattern**: Three endpoints (`GET /api/telegram/config`, `POST /api/telegram/config`, `POST /api/telegram/test`) have no `Depends(get_current_user)`
- **Discovery source**: project-vocab discovery (`get_current_user` absent on sensitive routes)
- **Risk**: HIGH
- **FP assessment**: The Telegram config endpoints read and write `telegram_config.json` (which contains `bot_token` and `chat_id`) without any authentication. An unauthenticated attacker can: (1) read the bot token via `GET /api/telegram/config`, (2) replace it with their own token to intercept agent notifications, or (3) send arbitrary messages to the configured chat via `POST /api/telegram/test`.
- **Downstream**: Phase 2 + Phase 5

---

### [4c06f66-ROOMS-NOAUTH] Multiple Room/Event Endpoints Without Authentication

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **File**: `dashboard/routes/rooms.py` lines 159, 183, 197, 210, 228
- **Pattern**: `GET /api/events`, `GET /api/search`, `GET /api/rooms/{id}/context`, `GET /api/rooms/{id}/state`, `POST /api/rooms/{id}/action` — no `Depends(get_current_user)`
- **Discovery source**: project-vocab discovery (`get_current_user` absent)
- **Risk**: MEDIUM
- **FP assessment**: Five endpoints that expose real-time event streams, semantic search results, room state, and room control actions (stop/pause/resume) are accessible without authentication. The `POST /api/rooms/{room_id}/action` endpoint in particular allows unauthenticated state mutation — any caller can stop or pause any war-room.
- **Downstream**: Phase 5

---

### [4c06f66-PLANS-NOAUTH] Multiple Plan/Refine/Search Endpoints Without Authentication

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **File**: `dashboard/routes/plans.py` lines 1108, 1128, 1154, 1188, 1205, 1212, 768
- **Pattern**: `GET /api/goals`, `POST /api/plans/refine`, `POST /api/plans/refine/stream`, `GET /api/plans/{id}/epics`, `GET /api/search/plans`, `GET /api/search/epics`, `POST /api/plans/{id}/status` — no auth dependency
- **Discovery source**: project-vocab discovery (`get_current_user` absent)
- **Risk**: MEDIUM
- **FP assessment**: These endpoints expose plan content, goals, epics, and search results to unauthenticated callers. `POST /api/plans/refine` and its streaming variant invoke the AI plan refinement agent without auth. `POST /api/plans/{plan_id}/status` allows unauthenticated status mutation of any plan.
- **Downstream**: Phase 5

---

## Category 3: Silent Security Fixes

No silent security fix commits found — the repository contains only a single commit, so no pre-fix/post-fix diff pairs exist in history.

---

## Category 4: Reverted Security Fixes

No reverted commits found — single-commit repository has no revert history.

---

## Category 5: Secret Archaeology

### [4c06f66-TELEGRAM-TOKEN] Telegram Bot Token Committed to Repository in Plaintext

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **File**: `dashboard/telegram_config.json`
- **Content**: `{"bot_token": "test_token", "chat_id": "test_chat"}`
- **Pattern**: Credentials stored in a JSON config file checked into git
- **Discovery source**: generic baseline (credential file committed)
- **Risk**: HIGH
- **FP assessment**: While `"test_token"` is not a real Telegram token, the config file `telegram_config.json` is committed to the repository rather than being gitignored. This file is written to by `save_config()` with real credentials at runtime. The `.gitignore` does not exclude this file (no `.gitignore` was found at the project root). Any real token written to this file would be committed on the next `git add .` or `git commit -a`. The file should be gitignored and replaced with an env-var-based configuration.
- **Downstream**: Phase 2

---

### [4c06f66-AUTH-TOKEN-LEAK] Login Endpoint Returns Raw API Key as `access_token`

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **File**: `dashboard/routes/auth.py` lines 43–45
- **Pattern**: `"access_token": _API_KEY` returned verbatim in JSON response body
- **Discovery source**: project-vocab discovery (`_API_KEY` echoed in response)
- **Risk**: MEDIUM
- **FP assessment**: The `POST /api/auth/token` endpoint, on successful authentication, returns `{"access_token": _API_KEY, ...}` where `_API_KEY` is the raw `OSTWIN_API_KEY` environment variable value. This exposes the master API key in the response body. Any JavaScript code (e.g., from a CORS-permitted origin) or a logged HTTP response can capture the raw secret. Tokens should be derived/scoped (e.g., a short-lived JWT) rather than returning the root credential.
- **Downstream**: Phase 5

---

## Category 6: CI/CD Pipeline Changes

No CI/CD configuration files found (`.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, etc.) in the repository. No findings in this category.

---

## Category 7: Suspicious Patterns

### [4c06f66-WS-NOAUTH] Unauthenticated WebSocket Endpoint

- **Commit**: `4c06f66d61b60bbc082a67ffd517c6d5776a7c3a`
- **File**: `dashboard/api.py` lines 86–105
- **Pattern**: `@app.websocket("/api/ws")` with no token/cookie validation before `manager.connect(websocket)`
- **Discovery source**: generic baseline (unauthenticated persistent connection endpoint)
- **Risk**: MEDIUM
- **FP assessment**: The WebSocket endpoint accepts any connection without verifying the `ostwin_auth_key` cookie or an `Authorization` header. Once connected, the client receives real-time system events broadcast by `global_state.broadcaster`. This enables unauthenticated subscription to internal agent activity feeds. The HTTP REST SSE endpoint (`/api/events`) has the same gap.
- **Downstream**: Phase 5

---

## Appendix: Project Security Vocabulary (for Phase 3 KB Builder)

### Validators / Sanitizers
- `escapeHtml()` — frontend HTML escaper in `markdown-renderer.tsx` (correctly used)
- `secrets.compare_digest()` — timing-safe comparison in `auth.py` (correctly used)
- `MAX_BODY_BYTES` — body size cap in MCP channel server
- `VALID_TYPES`, `VALID_ROLES` — allowlists in MCP channel server

### Auth Constructs
- `get_current_user` (FastAPI Depends) — central auth guard in `dashboard/auth.py`
- `_API_KEY` / `OSTWIN_API_KEY` — single shared API key model
- `AUTH_COOKIE_NAME = "ostwin_auth_key"` — httponly cookie name
- `OSTWIN_VAULT_KEY` — env var for vault encryption key

### Security Config
- `CORSMiddleware` / `allow_origins` — in `dashboard/api.py`
- `httponly=True`, `samesite="lax"` — cookie flags in `auth.py`
- `EncryptedFileVault` / `MacOSKeychainVault` — dual vault backends in `vault.py`

### Critical Security Gaps Identified (for Phase 3 KB)
1. No CSRF protection (no CSRF tokens, `samesite="lax"` partially mitigates but is not sufficient alone)
2. No rate limiting on auth endpoint (`POST /api/auth/token`) — brute-force possible
3. No input validation on `working_dir` / `path` parameters (plan creation, filesystem browse)
4. `telegram_config.json` not gitignored — credential leakage risk on every commit
5. `shell=True` with user input — textbook RCE vector

---

## Phase 2 Candidate SHAs for `patch-bypass-checker`

Since the repository has a single commit, the following findings represent undisclosed vulnerabilities present at `4c06f66` that require patches, not bypasses of existing patches:

| Finding ID | File | Type | Priority |
|-----------|------|------|----------|
| 4c06f66-SYS-SHELL | `dashboard/routes/system.py:167` | RCE via shell=True | CRITICAL |
| 4c06f66-TELEGRAM-NOAUTH | `dashboard/routes/system.py:148` | Missing auth | HIGH |
| 4c06f66-SYS-TESTS | `dashboard/routes/system.py:171,187` | Unauth subprocess | HIGH |
| 4c06f66-PLANS-CREATE | `dashboard/routes/plans.py:461` | Unauth file write | HIGH |
| 4c06f66-CORS-WILDCARD | `dashboard/api.py:110` | CORS misconfiguration | HIGH |

## Phase 5 Deep-Probe Target Files

- `dashboard/routes/system.py` — RCE, missing auth, hardcoded paths
- `dashboard/routes/plans.py` — Missing auth on create/refine/status/search endpoints
- `dashboard/routes/rooms.py` — Missing auth on action/state/events endpoints
- `dashboard/api.py` — CORS wildcard, unauth WebSocket
- `.agents/mcp/vault.py` — Hardcoded fallback encryption key
- `dashboard/routes/auth.py` — Token leakage in login response
- `dashboard/telegram_config.json` — Credentials file not gitignored
