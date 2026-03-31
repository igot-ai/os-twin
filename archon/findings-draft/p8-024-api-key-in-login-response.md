Phase: 8
Sequence: 024
Slug: api-key-in-login-response
Verdict: VALID
Rationale: The permanent API key is returned in the login JSON response body, exposing it in browser DevTools, proxy logs, and to XSS attacks, negating the httponly cookie protection; requires network observation or XSS chain to exploit.
Severity-Original: MEDIUM
PoC-Status: pending
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-B/debate.md

## Summary

The `POST /api/auth/token` login endpoint (auth.py:42-47) returns the raw, permanent `OSTWIN_API_KEY` in the JSON response body as `access_token`. While the same value is also set as an httponly cookie (auth.py:48-55), including it in the response body negates the httponly protection entirely. The key never rotates and provides 30-day session access. It is exposed in browser DevTools, server/proxy access logs, and is extractable via XSS chains.

## Location

- **Response body**: `dashboard/routes/auth.py:43-44` -- `JSONResponse(content={"access_token": _API_KEY, ...})`
- **Cookie (httponly)**: `dashboard/routes/auth.py:48-55` -- `response.set_cookie(..., httponly=True)`
- **Key source**: `dashboard/routes/auth.py:8` -- `_API_KEY = os.environ.get("OSTWIN_API_KEY", "")`

## Attacker Control

The attacker does not inject data. Exposure vectors:
1. Browser DevTools Network tab (any user who logs in)
2. Server access logs with response body logging
3. Proxy/CDN logs that capture response bodies
4. XSS chain (CV-11 javascript: URI) can fetch the login endpoint and exfiltrate the key

## Trust Boundary Crossed

Application-to-user boundary. The permanent server secret crosses into the client response, where multiple observation channels exist.

## Impact

- Permanent API key exposed (no rotation mechanism)
- 30-day persistent session access via the key
- Negates the deliberate httponly cookie protection
- Enables full API access if key is intercepted

## Evidence

1. `auth.py:43-44` -- `"access_token": _API_KEY` in JSON response
2. `auth.py:48-55` -- httponly cookie set with same value (contradictory protection)
3. `auth.py:8` -- key is static from environment, never rotates
4. Probe PH-13 validated this finding

## Reproduction Steps

1. Start the dashboard with `OSTWIN_API_KEY=test-key-123`
2. Send login request: `curl -X POST http://localhost:9000/api/auth/token -H "Content-Type: application/json" -d '{"key":"test-key-123"}'`
3. Observe response contains `{"access_token": "test-key-123", "token_type": "bearer", "username": "api-key-user"}`
4. Confirm the raw API key is present in the response body
5. Use the extracted key for authenticated API calls: `curl -H "X-API-Key: test-key-123" http://localhost:9000/api/env`
