# Adversarial Review: unauth-rce-shell

## Step 1 -- Restate and Decompose

**Restated claim**: The `/api/shell` endpoint accepts a user-supplied `command` parameter and executes it via `subprocess.run` with `shell=True`. The endpoint has no authentication dependency, allowing any network-reachable client to execute arbitrary OS commands.

**Sub-claims**:
- **A**: Attacker controls the `command` parameter via HTTP POST query string -- **SUPPORTED** (FastAPI auto-binds query param `command: str`)
- **B**: The `command` value reaches `subprocess.run(command, shell=True)` with no auth or sanitization -- **SUPPORTED** (no `Depends(get_current_user)` in signature, no input filtering)
- **C**: This results in arbitrary OS command execution as the server process user -- **SUPPORTED** (confirmed via reproduction)

## Step 2 -- Independent Code Path Trace

1. **Entry**: `dashboard/routes/system.py:166` -- `@router.post("/shell")` on `router = APIRouter(prefix="/api")`, yielding `POST /api/shell`
2. **Parameter binding**: `command: str` -- FastAPI binds from query parameter, no dependency injection for auth
3. **Execution**: Line 168 -- `subprocess.run(command, shell=True, capture_output=True, text=True)` -- direct pass-through, zero transformations
4. **Response**: stdout, stderr, returncode returned to caller as JSON
5. **Router registration**: `dashboard/api.py:121` -- `app.include_router(system.router)` with no global auth middleware

**Discrepancies with finding draft**: None. The code path matches exactly.

## Step 3 -- Protection Surface Search

| Layer | Protection | Blocks Attack? |
|-------|-----------|----------------|
| Language | Python -- no type safety preventing string-to-shell | No |
| Framework | FastAPI -- no global auth middleware applied | No |
| Framework | CORS set to `allow_origins=["*"]` | No (allows any origin) |
| Application | `get_current_user` exists and is used on ~10 other endpoints in system.py | **Missing on this endpoint** |
| Application | No input validation, allowlist, or sanitization | No |
| Middleware | No WAF, rate limiting, or proxy normalization evident | No |
| Documentation | No SECURITY.md or known-risk documentation found | N/A |

**Key observation**: The `get_current_user` auth dependency is imported in `system.py` line 19 and applied to most other endpoints (lines 71, 87, 111, 118, 133, 141, 203, 245, 255, 274) but is **absent** from the `shell_command` endpoint at line 166. This is either an oversight or an intentionally unprotected debug endpoint -- either way, it is exploitable.

## Step 4 -- Real-Environment Reproduction

- **Environment**: macOS Darwin 25.3.0, Python 3.14, uvicorn, commit 4c06f66
- **Server start**: `OSTWIN_API_KEY=testkey123 python -m uvicorn dashboard.api:app --host 127.0.0.1 --port 9876`
- **Healthcheck**: `GET /api/status` with `X-API-Key: testkey123` returned HTTP 200 -- server operational

**Attempt 1** (exact reproduction steps):
```
curl -s -X POST "http://127.0.0.1:9876/api/shell?command=id"
```
Result: HTTP 200, response body contained full `id` output including `uid=501(bytedance)`. **Successful unauthenticated RCE.**

**Attempt 2** (variation):
```
curl -s -X POST "http://127.0.0.1:9876/api/shell?command=whoami"
```
Result: HTTP 200, response body `{"stdout":"bytedance\n","stderr":"","returncode":0}`. **Confirmed.**

No authentication headers were sent in either request. The server had `OSTWIN_API_KEY` configured, proving that auth is enforced on other endpoints but not on `/api/shell`.

## Step 5 -- Prosecution and Defense Briefs

### Prosecution Brief

The vulnerability is trivially exploitable and fully confirmed:

1. The endpoint `POST /api/shell` at `dashboard/routes/system.py:166-168` accepts arbitrary commands and executes them via `subprocess.run(command, shell=True)`.
2. Authentication is provably absent: the function signature `async def shell_command(command: str)` has no `Depends(get_current_user)` -- compare with every other state-modifying endpoint in the same file which does include it.
3. No global auth middleware exists -- `dashboard/api.py` only adds CORS middleware with `allow_origins=["*"]`.
4. Live reproduction succeeded on first attempt with zero authentication.
5. The response returns stdout, stderr, and return code -- providing full interactive shell capabilities to the attacker.
6. Impact is maximal: the attacker runs commands as the server process user, can read secrets from `~/.ostwin/.env`, establish reverse shells, and pivot laterally.

### Defense Brief

1. The endpoint might be intended as a debug/development feature. However, it ships in the main branch with no conditional guard (no `if DEBUG:` check, no environment variable gate).
2. The server might only be bound to localhost in production. However, the reproduction steps in the codebase suggest `--host 0.0.0.0`, and even localhost binding allows exploitation from other processes on the same machine or via SSRF.
3. One could argue this requires network access. However, the server is a web dashboard intended to be network-accessible, and CORS is set to `*`, explicitly allowing cross-origin requests.

The defense has no blocking protection to cite. The endpoint is unguarded by any mechanism.

## Step 6 -- Severity Challenge

Starting at MEDIUM:
- **Upgrade to HIGH**: Remotely triggerable (yes, HTTP endpoint), meaningful trust boundary crossing (network to OS command execution), no significant preconditions (just network reachability). -> HIGH
- **Upgrade to CRITICAL**: RCE (yes), unauthenticated (yes), internet-facing by design (dashboard with `0.0.0.0` binding and `CORS *`). -> **CRITICAL**

No downgrade signals apply: no local access required, no admin privileges needed, no non-default config, reproduction succeeded.

**Challenged severity: CRITICAL** -- matches the original finding.

## Step 7 -- Verdict

**Adversarial-Verdict: CONFIRMED**

Both conditions met:
1. Prosecution brief survives defense -- no blocking protection found at any layer
2. Real-environment reproduction succeeded on first attempt

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Unauthenticated POST /api/shell executes attacker-supplied commands via subprocess.run(shell=True) with zero protections; confirmed via live reproduction returning OS command output.
Severity-Final: CRITICAL
PoC-Status: executed
```
