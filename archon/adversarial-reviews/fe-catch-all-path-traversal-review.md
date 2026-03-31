# Adversarial Review: fe-catch-all-path-traversal

## Step 1 -- Restate and Decompose

**Vulnerability claim (restated):** The FastAPI catch-all route at `dashboard/api.py:146-151` constructs a filesystem path by joining a user-controlled URL path parameter with the static files base directory (`FE_OUT_DIR`). No containment check prevents `..` traversal. When the frontend build directory exists (`USE_FE=True`), an unauthenticated attacker can read arbitrary files the server process can access.

**Sub-claims:**

- **A: Attacker controls input** -- The `{path:path}` route parameter is fully attacker-controlled via the URL. SUPPORTED.
- **B: Input reaches sink without sanitization** -- `FE_OUT_DIR / path` at line 149 has no `is_relative_to()`, `resolve()` containment, or other sanitization. SUPPORTED.
- **C: File read outside FE_OUT_DIR** -- `pathlib.Path` follows `..` segments, and `is_file()` returns True for traversed paths. SUPPORTED.
- **D: Server framework does not normalize** -- Partially correct. Starlette DOES normalize literal `..` segments. However, URL-encoded dots (`%2e%2e`) bypass this normalization and arrive at the handler as `..`. SUPPORTED with correction.

## Step 2 -- Independent Code Path Trace

Entry point: `dashboard/api.py:146` -- `@app.api_route("/{path:path}", methods=["GET", "HEAD"])`

1. Request arrives at uvicorn/Starlette
2. Starlette's router matches `/{path:path}` -- the `path` converter captures the full remaining URL path
3. For literal `..`, Starlette normalizes the URL before routing (tested: `/../etc/passwd` yields `path="etc/passwd"`)
4. For URL-encoded `%2e%2e`, Starlette decodes to `..` AFTER path normalization, so `..` passes through (tested: `/%2e%2e/etc/passwd` yields `path="../etc/passwd"`)
5. Handler at line 149: `exact = FE_OUT_DIR / path` -- pathlib joins with `..` segments
6. Line 150: `exact.is_file()` -- OS resolves the `..`, checks the traversed path
7. Line 151: `FileResponse(str(exact))` -- serves the traversed file

**Validation/sanitization on path: NONE.**
- No `resolve()` + `is_relative_to()` check
- No allowlist of characters
- No path length limit
- No authentication dependency

**Discrepancy from draft:** The draft's reproduction steps suggest literal `../../` in URLs and raw HTTP via `nc`. In practice, literal `..` IS normalized by Starlette. The correct attack vector uses `%2e%2e` encoding. The core vulnerability claim remains valid.

## Step 3 -- Protection Surface Search

| Layer | Protection | Blocks Attack? |
|-------|-----------|---------------|
| Language | Python pathlib type -- no containment enforcement | No |
| Framework | Starlette URL normalization for literal `..` | Partial -- bypassed via `%2e%2e` encoding |
| Framework | No CSRF middleware needed (GET request) | N/A |
| Middleware | Only CORSMiddleware configured (allows all origins) | No |
| Application | `USE_FE` gate -- only active when frontend is built | Precondition, not protection |
| Application | No authentication on catch-all route | No |
| Application | No `is_relative_to()` or resolve-based containment | No |
| Documentation | No SECURITY.md found acknowledging this risk | N/A |

**Verdict on protections:** Starlette's literal `..` normalization is the only partial control, and it is bypassed via URL encoding.

## Step 4 -- Real-Environment Reproduction

**Environment:** Starlette TestClient with exact replication of the catch-all handler logic.

**Healthcheck:** TestClient created successfully, fallback response working.

**Attempt 1 -- Literal `..` in URL:**
- URL: `/../../../etc/passwd`
- Result: Starlette normalized to `path="etc/passwd"` -- traversal blocked
- Outcome: BLOCKED by framework normalization

**Attempt 2 -- URL-encoded dots (`%2e%2e`):**
- URL: `/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd`
- Result: Status 200, full `/etc/passwd` contents returned
- Outcome: EXPLOITED

**Attempt 3 -- Mixed encoding (`%2e%2e` with literal `/`):**
- URL: `/%2e%2e/etc/passwd`
- Result: Status 200 (with sufficient depth), file contents returned
- Outcome: EXPLOITED

Evidence stored at: `security/real-env-evidence/fe-catch-all-path-traversal/poc-output.txt`

## Step 5 -- Prosecution and Defense Briefs

### Prosecution Brief

The vulnerability is genuine and exploitable. The code at `dashboard/api.py:149-151` joins an attacker-controlled path with `FE_OUT_DIR` and serves the result via `FileResponse` with zero containment checks. URL-encoded `..` segments (`%2e%2e`) bypass Starlette's path normalization and reach the handler as literal `..`, which pathlib resolves during `is_file()`. End-to-end reproduction confirms `/etc/passwd` is readable.

The attack is:
- Unauthenticated (no `Depends()` or auth middleware on the catch-all route)
- Remotely triggerable (standard HTTP GET request)
- Crosses a trust boundary (network to filesystem)
- Conditional only on `USE_FE=True` (frontend build exists), which is the expected production deployment state

The only framework-level protection (Starlette literal `..` normalization) is trivially bypassed with `%2e%2e` encoding.

### Defense Brief

The vulnerability has the following limiting factors:

1. **Precondition:** `USE_FE` must be True, meaning the frontend must be built. Development setups may not have this.
2. **Read-only impact:** The vulnerability allows file reads only, not writes or code execution.
3. **Draft inaccuracy:** The reproduction steps in the finding are partially incorrect -- literal `..` in URLs does NOT work due to Starlette normalization. Only URL-encoded variants succeed.
4. **Process permissions:** Impact is limited to files readable by the server process user.

However, none of these factors negate the vulnerability. The precondition is met in production. URL-encoded bypass is trivial. Read-only access to `.env` files containing API keys is a significant impact.

## Step 6 -- Severity Challenge

Starting at MEDIUM:

- Remotely triggerable: YES (HTTP GET) -> upgrade signal
- Trust boundary crossing: YES (network to filesystem) -> upgrade signal
- No significant preconditions: MOSTLY (requires `USE_FE=True`, which is the production default) -> slight precondition but expected in deployment
- Unauthenticated: YES -> upgrade signal
- Impact: Arbitrary file read including secrets (`.env` with API keys) -> significant but not RCE

Upgrade to HIGH. Does not reach CRITICAL because it is file-read only, not RCE/full auth bypass.

`Severity-Original: HIGH` matches the challenged severity.

## Step 7 -- Verdict

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: End-to-end reproduction succeeded via URL-encoded dot traversal (%2e%2e), returning /etc/passwd contents through the unprotected catch-all handler at api.py:149-151.
Severity-Final: HIGH
PoC-Status: executed
```
