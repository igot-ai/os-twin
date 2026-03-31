# Bypass Analysis: Unauthenticated RCE Endpoints in system.py

**Cluster ID**: `unauth-rce-system-routes`
**Bypass verdict**: **bypassable** — three endpoints completely lack authentication
**Undisclosed tag**: [undisclosed]

---

## Patch Summary

There is no patch — the vulnerability is live on `main`. The `system.py` router defines
four subprocess-executing endpoints. Only one (`/api/run_tests_direct`, line 110) uses
`Depends(get_current_user)`. The other three are fully unauthenticated:

| Endpoint | Auth | Risk |
|---|---|---|
| `POST /api/shell` (L167) | **NONE** | Critical — arbitrary command execution via `shell=True` |
| `GET /api/run_pytest_auth` (L171) | **NONE** | High — runs pytest, leaks stdout/stderr |
| `GET /api/test_ws` (L187) | **NONE** | High — runs arbitrary script |
| `GET /api/run_tests_direct` (L110) | `get_current_user` | Medium — hardcoded path, but auth-gated |

## Findings

### 1. No global auth middleware

`dashboard/api.py` does **not** apply any global authentication middleware. Auth is
opt-in via `Depends(get_current_user)` on individual route handlers. Any route that
omits this dependency is publicly accessible. There is no nginx config, IP allowlist,
or any other network-level protection in the repository.

### 2. POST /api/shell — unrestricted OS command injection

```python
@router.post("/shell")
async def shell_command(command: str):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
```

- **No authentication** — no `Depends(get_current_user)`.
- **No input validation** — no allowlist, no WAF, no sanitization.
- **`shell=True`** — the `command` parameter is passed directly to the system shell.
- Any network-reachable attacker can execute arbitrary OS commands as the server process user.

### 3. CORS `allow_origins=["*"]` enables cross-origin exploitation

`api.py` line 108-113 configures:

```python
CORSMiddleware(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```

Combined with the unauthenticated `/api/shell` endpoint, this means:
- Any website visited by a user on the same network can issue a `POST /api/shell`
  request to `http://localhost:9000/api/shell` from JavaScript.
- The wildcard CORS policy will return `Access-Control-Allow-Origin: *`, so the
  browser will not block the response.
- **This is a drive-by RCE vector**: visiting a malicious webpage is sufficient to
  execute commands on any machine running the dashboard.

### 4. DEBUG auth bypass

`auth.py` line 79: if `OSTWIN_API_KEY=DEBUG`, all auth checks are skipped and every
request is treated as authenticated. Even the endpoints that *do* use
`Depends(get_current_user)` become unauthenticated in this mode. This is a config-gated
bypass that may be active in development/demo deployments.

### 5. Additional unauthenticated endpoints (non-RCE)

The following routes in `system.py` also lack `Depends(get_current_user)`:

- `GET /api/telegram/config` (L148) — leaks telegram bot token and chat ID
- `POST /api/telegram/config` (L152) — allows overwriting telegram config
- `POST /api/telegram/test` (L159) — sends arbitrary telegram messages

### 6. POST /api/plans/create — unauthenticated file write

`plans.py` line 461:

```python
@router.post("/api/plans/create")
async def create_plan(request: CreatePlanRequest):
```

No `Depends(get_current_user)`. An unauthenticated attacker can create plan files with
arbitrary `content` written to disk. While this is not direct code execution, it writes
attacker-controlled content to a predictable path under the plans directory, which could
be chained with other vulnerabilities (e.g., if plan content is later evaluated or
included).

### 7. WebSocket endpoint — unauthenticated

`api.py` line 86: the `/api/ws` WebSocket endpoint has no authentication check. Any
client can connect and receive real-time events from the dashboard.

## Evidence Summary

The three unauthenticated subprocess endpoints have:
- No authentication dependency
- No global auth middleware
- No network-level protection (no nginx, no IP allowlist)
- No input validation on `/api/shell`
- Wildcard CORS enabling cross-origin exploitation
- Default bind to `0.0.0.0` (all interfaces)

## Recommendation

1. Add `user: dict = Depends(get_current_user)` to all subprocess endpoints immediately.
2. Remove `POST /api/shell` entirely — it is an intentional backdoor API with no safe use case in production.
3. Replace `allow_origins=["*"]` with an explicit origin allowlist.
4. Remove the `DEBUG` auth bypass or gate it behind a compile-time flag.
5. Audit all routes across all router modules for missing auth dependencies.
