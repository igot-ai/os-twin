# H1 — DEBUG Auth Bypass (OSTWIN_API_KEY=DEBUG)

| Field | Value |
|---|---|
| ID | H1 |
| Severity | HIGH |
| CWE | CWE-288: Authentication Bypass Using an Alternate Path or Channel |
| Phase | 8 |
| Draft | security/findings-draft/p8-003-debug-auth-bypass.md |
| PoC-Status | theoretical (code-confirmed; execution requires DEBUG env config) |
| Affected File | dashboard/auth.py:78-81 |

## Description

When the environment variable `OSTWIN_API_KEY` is set to the literal string `"DEBUG"`, the `get_current_user` FastAPI dependency returns immediately without checking any credential. The function is the sole authentication guard for every protected endpoint in the application. Additionally, the `X-User` request header is accepted verbatim as the authenticated identity, allowing complete identity spoofing.

```python
# dashboard/auth.py:78-81
if _API_KEY == "DEBUG":
    username = request.headers.get("x-user", "debug-user")
    return {"username": username}
```

There is no logging, rate limiting, IP restriction, or secondary check in this branch.

## Attacker Starting Position

Network access to the dashboard on port 9000 while the server is running with `OSTWIN_API_KEY=DEBUG`. This can be a deliberate operator misconfiguration or can be injected via the env-file newline injection finding (p8-005).

## Impact

- Every authenticated endpoint becomes unauthenticated (GET /api/config, GET /api/env, GET /api/fs/browse, POST /api/run, POST /api/shell, etc.)
- Identity spoofing to any username including "admin" via the `X-User` header
- Combined with the unauthenticated `/api/shell` endpoint (p8-001), provides complete OS command execution without any credential

## Reproduction Steps

1. Start the dashboard with `OSTWIN_API_KEY=DEBUG python dashboard/api.py`
2. Access any protected endpoint with no credentials:
   ```
   curl http://localhost:9000/api/config
   curl http://localhost:9000/api/env
   ```
3. Spoof identity:
   ```
   curl -H "X-User: admin" http://localhost:9000/api/status
   ```
4. All requests return HTTP 200 with full response bodies.

## Evidence

- Code path: `dashboard/auth.py:23` reads `OSTWIN_API_KEY`; `auth.py:79` compares to `"DEBUG"` with no further checks
- 28+ route handlers use `Depends(get_current_user)` — all bypassed simultaneously
- Cold verification (commit 4c06f66) confirmed: `GET /api/engagement/test123` and `GET /api/plans` return 200 with no credentials when DEBUG is active; same endpoints return 401 with a real key

## Remediation

1. **Remove the DEBUG bypass entirely** — delete lines 78-81 from `dashboard/auth.py`.
2. If a no-auth development mode is genuinely needed, gate it on `DEBUG=true AND environment != production` with an explicit startup warning.
3. Add a startup assertion that rejects `OSTWIN_API_KEY=DEBUG` when `ENVIRONMENT=production`.
4. Remove the `X-User` identity spoofing capability from the DEBUG branch (it also exists in the authenticated branch at line 97 — restrict to localhost-only requests).
