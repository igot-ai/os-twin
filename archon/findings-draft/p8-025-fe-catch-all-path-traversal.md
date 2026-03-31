Phase: 8
Sequence: 025
Slug: fe-catch-all-path-traversal
Verdict: VALID
Rationale: Path traversal in the static file catch-all handler allows unauthenticated reading of arbitrary server files in production deployments; no application-level path containment exists, and the vulnerability is confirmed reachable through uvicorn's lack of path normalization.
Severity-Original: HIGH
PoC-Status: executed
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-B/debate.md

## Summary

The `fe_catch_all` handler (api.py:147-151) serves static files by constructing `FE_OUT_DIR / path` from the URL path parameter without any containment check. FastAPI's `{path:path}` converter passes `..` segments verbatim, and uvicorn does NOT normalize them. When the frontend is built (production deployment with `USE_FE=True`), an attacker can read any file the server process can access by sending requests like `GET /../../etc/passwd`.

## Location

- **Handler**: `dashboard/api.py:146-151` -- `fe_catch_all(path: str)`
- **Path construction**: `dashboard/api.py:149` -- `exact = FE_OUT_DIR / path` (no normalization)
- **File serve**: `dashboard/api.py:150-151` -- `if exact.is_file(): return FileResponse(str(exact))`
- **Gate**: `dashboard/api.py:134` -- `if USE_FE:` (only active when frontend is built)

## Attacker Control

Full control over the `path` parameter via the URL. `..` segments traverse out of `FE_OUT_DIR` to any location on the filesystem.

## Trust Boundary Crossed

Network-to-filesystem boundary. Unauthenticated remote attacker reads arbitrary files from the server.

## Impact

- Read source code: `dashboard/auth.py` (reveals DEBUG condition and API key logic)
- Read environment: `~/.ostwin/.env` (contains API keys for AI providers)
- Read system files: `/etc/passwd`, SSH keys, etc.
- No authentication required
- Conditional on production deployment (FE_OUT_DIR must exist)

## Evidence

1. `api.py:149` -- `exact = FE_OUT_DIR / path` with no `is_relative_to()` check
2. `api.py:146` -- `{path:path}` converter does not strip `..`
3. Probe PH-17 confirmed uvicorn passes `..` without normalization
4. `api.py:150` -- `exact.is_file()` uses OS path resolution which follows `..`
5. No StaticFiles (which has containment) -- this is a custom handler

## Reproduction Steps

1. Build the frontend: `cd dashboard/fe && npm run build` (creates FE_OUT_DIR)
2. Start the dashboard: `python api.py`
3. Send traversal request: `curl http://localhost:9000/../../etc/passwd`
4. If blocked by curl URL normalization, use raw HTTP: `printf "GET /../../etc/passwd HTTP/1.1\r\nHost: localhost\r\n\r\n" | nc localhost 9000`
5. Confirm file contents are returned in the response
6. Read sensitive files: `GET /../../dashboard/auth.py`, `GET /../../../../home/<user>/.ostwin/.env`

## Cold Verification

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: End-to-end reproduction succeeded via URL-encoded dot traversal (%2e%2e), returning /etc/passwd contents through the unprotected catch-all handler at api.py:149-151.
Severity-Final: HIGH
PoC-Status: executed
```

### Verification Notes

**Important correction to reproduction steps:** Starlette (v0.50.0) normalizes literal `..` segments in URL paths before routing. The attack vector `GET /../../etc/passwd` with literal dots will NOT work -- Starlette collapses the `..` segments during URL normalization.

The correct attack uses URL-encoded dots (`%2e%2e` instead of `..`), which bypass Starlette's normalization:

```
GET /%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd HTTP/1.1
Host: localhost:9000
```

This was independently confirmed via end-to-end reproduction using Starlette's TestClient, which returned the full contents of `/etc/passwd` with HTTP 200.

**Protections evaluated:**
- Starlette literal `..` normalization: present but bypassed via `%2e%2e` encoding
- Authentication: none on the catch-all route
- Path containment (`is_relative_to`, `resolve()`): absent
- Application-level input validation: absent

Full review: `security/adversarial-reviews/fe-catch-all-path-traversal-review.md`
Evidence: `security/real-env-evidence/fe-catch-all-path-traversal/poc-output.txt`
