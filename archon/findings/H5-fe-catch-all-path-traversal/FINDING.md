# H5 — Path Traversal in fe_catch_all

| Field | Value |
|---|---|
| ID | H5 |
| Severity | HIGH |
| CWE | CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal') |
| Phase | 8 |
| Draft | security/findings-draft/p8-025-fe-catch-all-path-traversal.md |
| PoC-Status | executed |
| Affected File | dashboard/api.py:146-151 |

## Description

The `fe_catch_all` handler serves static files by constructing `FE_OUT_DIR / path` from the URL-supplied `path` parameter with no containment check:

```python
# api.py:147-151
@app.api_route("/{path:path}", methods=["GET", "HEAD"])
async def fe_catch_all(path: str):
    exact = FE_OUT_DIR / path          # No is_relative_to() / resolve() check
    if exact.is_file():
        return FileResponse(str(exact))
```

Starlette normalizes literal `..` segments, but URL-encoded dots (`%2e%2e`) bypass this normalization and are passed verbatim to `pathlib.Path.__truediv__`, which resolves them at OS level. The handler is active only when `USE_FE=True` (production deployment with a built frontend).

The correct attack vector (confirmed in cold verification): `GET /%2e%2e/%2e%2e/.../%2e%2e/etc/passwd`

## Attacker Starting Position

No authentication required. Any client reachable to port 9000. Requires production deployment with `USE_FE=True` and the frontend build directory present.

## Impact

- Arbitrary file read from any path the server process can access
- Direct targets: `dashboard/auth.py` (reveals DEBUG bypass), `~/.ostwin/.env` (AI API keys, OSTWIN_API_KEY), SSH private keys, `/etc/shadow`
- No authentication required — fully pre-auth exploitation
- Cross-platform: works on any OS where Python's pathlib resolves `%2e%2e` at the OS level

## Reproduction Steps

1. Build the frontend: `cd dashboard/fe && npm run build`
2. Start the dashboard: `python dashboard/api.py`
3. Send URL-encoded traversal:
   ```
   curl "http://localhost:9000/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd"
   ```
4. Confirm `/etc/passwd` contents in the response body (HTTP 200).
5. For raw socket proof (bypasses curl normalization):
   ```
   printf "GET /%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd HTTP/1.1\r\nHost: localhost\r\n\r\n" \
     | nc localhost 9000
   ```

## Evidence

- `api.py:149`: `exact = FE_OUT_DIR / path` — no `is_relative_to()` call
- `api.py:150`: `exact.is_file()` resolves the path at OS level, following `..` after `%2e%2e` decoding
- Unlike `StaticFiles` (which has path containment), this is a custom handler with no security controls
- Cold verification: end-to-end reproduction confirmed via Starlette TestClient — `/etc/passwd` contents returned with HTTP 200 using `%2e%2e` encoding

## Remediation

1. Add a path containment check immediately after path construction:
   ```python
   exact = (FE_OUT_DIR / path).resolve()
   if not exact.is_relative_to(FE_OUT_DIR.resolve()):
       raise HTTPException(status_code=404)
   ```
2. Apply the same fix to the `html_file` and `index_file` path constructions on lines 153-158.
3. Alternatively, replace the custom handler with FastAPI's `StaticFiles` mount, which performs containment internally.
4. Add a test that attempts traversal and asserts HTTP 404.
