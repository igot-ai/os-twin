# Static Analysis Results

> Phase 4 SAST | Date: 2026-03-30 | Repo: os-twin
> Tools: CodeQL 2.24.2, Semgrep 1.144.0, Manual taint analysis

---

## Tooling Summary

| Tool | Version | Targets | Rules/Queries | Findings |
|------|---------|---------|---------------|---------|
| CodeQL | 2.24.2 | Python (88 files), JS/TS (144 files) | python-security-and-quality.qls, javascript-security-and-quality.qls | 268 Python, 13 JS |
| Semgrep | 1.144.0 | Python, JS | p/python, p/security-audit, p/owasp-top-ten, p/javascript, p/nodejs | 5 baseline |
| Semgrep Custom | 1.144.0 | Python, JS | 7 custom rulesets (19 rules) | 80 |
| Manual Taint | N/A | All components | DFD/CFD-driven | Confirmed all KB targets |

**CodeQL Databases**:
- Python: `security/codeql-artifacts/db/python-db/` (88 files, 1.79 MiB)
- JavaScript: `security/codeql-artifacts/db/js-db/` (144 files, 6.14 MiB)

**Semgrep Pro**: Not available (no Pro license). Standard Semgrep used for all passes. Documented fallback reason: Semgrep returned authentication error for --pro flag; standard mode covers all required patterns.

---

## Sub-step 4.1 — Structural Extraction Results

- **Entry points identified**: 22 (see `security/codeql-artifacts/entry-points.json`)
- **Sinks identified**: 12 (see `security/codeql-artifacts/sinks.json`)
- **Call-graph slices**: 6 high-risk DFD slices (see `security/codeql-artifacts/call-graph-slices.json`)
- **Flow paths**: `security/codeql-artifacts/flow-paths-all-severities.md`

**Unauthenticated endpoints confirmed by structural extraction**: 20 of 22 entry points have no auth dependency. Two authenticated entry points are EP-021 (Discord guild membership) and EP-022 (process env).

---

## CRITICAL Findings

### SAST-001 — Unauthenticated RCE: subprocess.run(shell=True)
**Rule**: `py/command-line-injection` (CodeQL), `subprocess-shell-true-user-input` (Semgrep custom), `subprocess-shell-true-unauthenticated-route` (Semgrep custom)
**File**: `dashboard/routes/system.py:166-169`
**CWE**: CWE-78 (OS Command Injection), CWE-306 (Missing Authentication)
**Severity**: CRITICAL

```python
@router.post("/shell")
async def shell_command(command: str):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
```

The HTTP POST body parameter `command` flows directly into `subprocess.run(..., shell=True)` with no authentication dependency and no input sanitization. Any network-reachable attacker can execute arbitrary OS commands as the server user. Combined with `allow_origins=["*"]` CORS, any website visited by a LAN user can trigger this via JavaScript.

**Evidence**: CodeQL confirmed data flow from HTTP request parameter to shell sink. Semgrep confirmed missing auth and shell=True patterns.

---

### SAST-002 — DEBUG Authentication Bypass
**Rule**: `debug-auth-bypass-key` (Semgrep custom), manual analysis
**File**: `dashboard/auth.py:79`
**CWE**: CWE-287 (Improper Authentication)
**Severity**: CRITICAL

```python
if _API_KEY == "DEBUG":
    username = request.headers.get("x-user", "debug-user")
    return {"username": username}
```

When `OSTWIN_API_KEY=DEBUG`, all authentication is bypassed for every endpoint that uses `Depends(get_current_user)`. An attacker can additionally impersonate any user via the `X-User` header. This is a critical risk in any development or demo deployment.

---

### SAST-003 — CORS Wildcard Origin with Cookie Auth
**Rule**: `wildcard-cors` (Semgrep baseline), `cors-allow-all-origins` (Semgrep custom), manual analysis
**File**: `dashboard/api.py:108-113`
**CWE**: CWE-346 (Origin Validation Error)
**Severity**: HIGH

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Wildcard CORS combined with cookie-based authentication enables cross-origin requests from any website. Any site visited by a logged-in user can exfiltrate data or execute actions on their behalf. Particularly dangerous combined with SAST-001 (drive-by RCE).

---

## HIGH Findings

### SAST-004 — Unauthenticated Plan File Write
**Rule**: `fastapi-route-missing-auth-dependency` (Semgrep custom)
**File**: `dashboard/routes/plans.py:461-502`
**CWE**: CWE-306 (Missing Authentication), CWE-22 (Path Traversal potential)
**Severity**: HIGH

```python
@router.post("/api/plans/create")
async def create_plan(request: CreatePlanRequest):
```

No `Depends(get_current_user)`. Unauthenticated attackers can write arbitrary content to `~/.ostwin/plans/{plan_id}.md`. Files are later indexed in the vector store and returned in semantic search results that feed into the Gemini LLM prompt, enabling second-order prompt injection via planted plan content.

---

### SAST-005 — Hardcoded Vault Encryption Key
**Rule**: `hardcoded-fernet-encryption-key` (Semgrep custom), `hardcoded-secret-fallback` (Semgrep custom)
**File**: `.agents/mcp/vault.py:115-117`
**CWE**: CWE-321 (Use of Hard-coded Cryptographic Key)
**Severity**: HIGH

```python
# Default key (insecure, but better than plaintext if cryptography is available)
return base64.urlsafe_b64encode(b"ostwin-default-insecure-key-32ch")
```

When `OSTWIN_VAULT_KEY` is not set (default), the Fernet encryption key is the publicly-known literal `ostwin-default-insecure-key-32ch`. Any attacker with access to `~/.ostwin/mcp/.vault.enc` can decrypt all stored secrets. Additionally, if the `cryptography` package is not installed, the vault falls back to plaintext JSON storage (vault.py:143-145).

---

### SAST-006 — Discord Prompt Injection via LLM Concatenation
**Rule**: `prompt-injection-discord-mention-gemini` (Semgrep custom), manual taint analysis
**File**: `discord-bot/src/agent-bridge.js:110,121`
**CWE**: CWE-74 (Improper Neutralization of Special Elements in Output)
**Severity**: HIGH

```javascript
// Line 110 — injected into context block
`## Relevant Messages (semantic search for "${question}")`

// Line 121 — injected into final prompt
{ role: 'user', parts: [{ text: `${systemPrompt}\n\n---\n\n${contextBlock}\n\n---\n\n**User question:** ${question}` }] }
```

Discord `message.content` (stripped of @mention) flows unsanitized into the Gemini `generateContent` call. An attacker can:
1. Override system instructions to produce harmful/misleading output
2. Exfiltrate all plan/room/stats context from the LLM prompt
3. Plant content in plans (via SAST-004) to create second-order injection via search results

---

### SAST-007 — Multiple Unauthenticated Subprocess Endpoints
**Rule**: `fastapi-route-missing-auth-dependency`, `fastapi-route-missing-auth-subprocess` (Semgrep custom)
**File**: `dashboard/routes/system.py:171,187`
**CWE**: CWE-306, CWE-78
**Severity**: HIGH

```python
@router.get("/run_pytest_auth")
async def run_pytest_auth():  # No Depends(get_current_user)
    # Spawns: python3 -m pytest test_auth.py

@router.get("/test_ws")
async def run_ws_test():  # No Depends(get_current_user)
    # Spawns: python3 test_ws.py
```

Both endpoints execute subprocesses with no authentication. Attackers can trigger test execution, see stdout/stderr output including potential secrets, and cause resource exhaustion.

---

### SAST-008 — Unauthenticated Telegram Config Endpoints
**Rule**: `fastapi-route-missing-auth-dependency` (Semgrep custom)
**File**: `dashboard/routes/system.py:148-164`
**CWE**: CWE-306 (Missing Authentication)
**Severity**: HIGH

Three endpoints — `GET /api/telegram/config`, `POST /api/telegram/config`, `POST /api/telegram/test` — lack authentication. Attackers can read the Telegram bot token and chat ID, redirect notifications to an attacker-controlled bot, and send arbitrary Telegram messages.

---

### SAST-009 — API Key Exposed in Login Response Body
**Rule**: `py/clear-text-storage-sensitive-data` (CodeQL), manual analysis
**File**: `dashboard/routes/auth.py:43-44`
**CWE**: CWE-200 (Exposure of Sensitive Information), CWE-312 (Cleartext Storage)
**Severity**: HIGH

```python
response = JSONResponse(content={
    "access_token": _API_KEY,  # Raw API key returned in JSON body
```

The raw `OSTWIN_API_KEY` value is returned in the JSON response. It appears in browser developer tools network tab, any logging middleware, CDN/proxy access logs, and JavaScript memory. The cookie is also set, so this serves no legitimate purpose beyond creating additional exposure.

---

### SAST-010 — SSRF via Unvalidated DASHBOARD_URL Environment Variable
**Rule**: `ssrf-env-controlled-url` (Semgrep custom), manual analysis
**File**: `discord-bot/src/agent-bridge.js:10,21`
**CWE**: CWE-918 (Server-Side Request Forgery)
**Severity**: MEDIUM-HIGH

```javascript
const DASHBOARD_URL = process.env.DASHBOARD_URL || 'http://localhost:9000';
// ...
const res = await fetch(`${DASHBOARD_URL}${path}`, { headers });
```

No scheme or host validation on `DASHBOARD_URL`. If attackers control the environment (CI/CD injection, container misconfiguration, `.env` file write access), all fetch calls can be redirected to `http://169.254.169.254` (cloud metadata) or attacker-controlled servers. The `X-API-Key` header is included on every request, enabling API key exfiltration.

---

## MEDIUM Findings

### SAST-011 — Cookie Missing `secure=True` Flag
**Rule**: `cookie-missing-secure-flag` (Semgrep custom)
**File**: `dashboard/routes/auth.py:48-55`
**CWE**: CWE-614 (Sensitive Cookie in HTTPS Session Without 'Secure' Attribute)
**Severity**: MEDIUM

```python
response.set_cookie(
    key=AUTH_COOKIE_NAME,
    value=_API_KEY,
    httponly=True,
    samesite="lax",
    max_age=60 * 60 * 24 * 30,
    path="/",
    # Missing: secure=True
)
```

The session cookie (which contains the raw API key) is transmitted over HTTP without `secure=True`. On non-HTTPS connections, the cookie is visible in plaintext to any network observer.

---

### SAST-012 — Unauthenticated WebSocket Broadcasts Internal Events
**Rule**: `fastapi-route-missing-auth-dependency` (Semgrep custom), manual analysis
**File**: `dashboard/api.py:86-105`
**CWE**: CWE-306 (Missing Authentication), CWE-200 (Information Disclosure)
**Severity**: MEDIUM

The `/api/ws` WebSocket endpoint has no authentication check. Any client can connect and receive real-time agent events, plan updates, and system state broadcasts.

---

### SAST-013 — Multiple Unauthenticated Plans/Rooms Endpoints (Information Disclosure)
**Rule**: `fastapi-route-missing-auth-dependency` (Semgrep custom)
**Files**: `dashboard/routes/plans.py`, `dashboard/routes/rooms.py`
**CWE**: CWE-306, CWE-200
**Severity**: MEDIUM

18 endpoints across plans.py and rooms.py lack authentication. Endpoints for listing goals, epics, refining plans, searching, querying room state, and streaming LLM responses are all publicly accessible.

---

### SAST-014 — Path Traversal in File Serving and Room/Plan Lookups
**Rule**: `py/path-injection` (CodeQL), `path-traversal-user-input-pathlib` (Semgrep custom)
**Files**: `dashboard/api_utils.py` (30+ locations), `dashboard/routes/rooms.py`, `dashboard/routes/plans.py`, `dashboard/routes/system.py:277`
**CWE**: CWE-22 (Path Traversal)
**Severity**: MEDIUM

CodeQL identified 60+ data flow paths where user-supplied values (plan IDs, room IDs, query parameters) reach `Path()` construction and filesystem access without `.resolve()` + base directory bounds checking. The `GET /api/fs/browse?path=` endpoint (system.py:274) accepts an arbitrary path parameter and is auth-gated, but the path is only checked with `is_dir()` — no normalization against a root boundary.

---

### SAST-015 — Regex Injection via User Query Parameter
**Rule**: `py/regex-injection` (CodeQL)
**File**: `dashboard/routes/plans.py:1019`
**CWE**: CWE-730 (ReDoS / Regex Injection)
**Severity**: MEDIUM

User-provided search query is passed to `re.match()` without escaping, allowing injection of malicious regex patterns that can cause catastrophic backtracking (ReDoS) or match unintended data.

---

### SAST-016 — ReDoS in Skills Routes
**Rule**: `py/polynomial-redos` (CodeQL)
**File**: `dashboard/routes/skills.py:337,349`
**CWE**: CWE-1333 (Inefficient Regular Expression)
**Severity**: MEDIUM

Two regex patterns that incorporate user-supplied values can exhibit polynomial backtracking on crafted inputs, enabling denial of service.

---

### SAST-017 — Stack Trace Exposure in API Responses
**Rule**: `py/stack-trace-exposure` (CodeQL)
**Files**: `dashboard/routes/mcp.py:238,300`, `dashboard/routes/plans.py:1184`, `dashboard/routes/roles.py:492`
**CWE**: CWE-209 (Exposure of Sensitive Information via Error Messages)
**Severity**: MEDIUM

Exception stack traces flow to API response bodies in multiple error handlers, leaking internal file paths, module names, and code structure to attackers.

---

### SAST-018 — Sensitive Data Logged in Clear Text
**Rule**: `py/clear-text-logging-sensitive-data` (CodeQL)
**File**: `.agents/mcp/config_resolver.py:126`
**CWE**: CWE-312 (Cleartext Storage of Sensitive Information)
**Severity**: MEDIUM

A secret value is logged via the standard logging module. Log files may be readable by other processes, stored insecurely, or shipped to log aggregation services.

---

### SAST-019 — verify_password Always Returns True
**Rule**: Manual analysis
**File**: `dashboard/auth.py:29-30`
**CWE**: CWE-798 (Use of Hard-coded Credentials)
**Severity**: LOW (dormant)

```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return True
```

This function accepts any password. Not currently called in the authentication flow (API-key based), but any future code invoking it will accept any credentials.

---

## GitHub Actions Audit

**Workflow**: `.github/workflows/pester-tests.yml`
- Actions pinned to `actions/checkout@v4`, `actions/upload-artifact@v4`, `dorny/test-reporter@v1` — all using tag references (not SHA-pinned, minor risk)
- No secret interpolation in run steps
- No user-controlled input reaching shell commands
- `workflow_dispatch` available — no input parameters defined (safe)
- **Verdict**: No critical CI/CD vulnerabilities found

---

## Custom Artifacts Created

### Semgrep Rules (`security/semgrep-rules/`)
| File | Rules | Target |
|------|-------|--------|
| `fastapi-missing-auth.yaml` | 2 | CWE-306: FastAPI routes without auth dep |
| `subprocess-shell-injection.yaml` | 3 | CWE-78: subprocess + shell=True |
| `cors-wildcard.yaml` | 2 | CWE-346: CORS wildcard origin |
| `cookie-missing-secure.yaml` | 2 | CWE-614: Cookie without secure flag |
| `hardcoded-keys.yaml` | 3 | CWE-321/287: Hardcoded crypto keys, DEBUG bypass |
| `path-traversal.yaml` | 3 | CWE-22: Path traversal in file ops |
| `prompt-injection.yaml` | 4 | CWE-74/918: LLM prompt injection, SSRF |

### CodeQL Queries (`security/codeql-queries/`)
| File | Type | Target |
|------|------|--------|
| `fastapi-unauthenticated-subprocess.ql` | problem | CWE-78/306: Unauthed FastAPI subprocess |
| `hardcoded-vault-key.ql` | problem | CWE-321: Hardcoded Fernet keys |
| `prompt-injection-js.ql` | path-problem | CWE-74: Discord→Gemini taint path |

---

## DFD/CFD Slices Driving Targeted Analysis

| Slice | Description | Custom Rules Triggered |
|-------|-------------|----------------------|
| DFD-1 | Unauthenticated RCE via /api/shell | subprocess-shell-true-user-input, fastapi-route-missing-auth-subprocess, subprocess-shell-true-unauthenticated-route |
| DFD-2 | Discord → LLM Prompt Injection | prompt-injection-discord-mention-gemini, ssrf-env-controlled-url |
| DFD-3 | Unauthenticated Plan File Write | fastapi-route-missing-auth-dependency (plans.py:461) |
| DFD-4 | Vault Hardcoded Key | hardcoded-fernet-encryption-key, hardcoded-secret-fallback |
| DFD-5 | DEBUG Auth Bypass | debug-auth-bypass-key |
| DFD-6 | Cookie Missing Secure | cookie-missing-secure-flag |
| TB-1 | Wildcard CORS | cors-allow-all-origins |

---

## Consolidated Finding Summary

| ID | Severity | CWE | File | Line | Tool |
|----|----------|-----|------|------|------|
| SAST-001 | CRITICAL | CWE-78,306 | dashboard/routes/system.py | 168 | CodeQL+Semgrep |
| SAST-002 | CRITICAL | CWE-287 | dashboard/auth.py | 79 | Semgrep Custom |
| SAST-003 | HIGH | CWE-346 | dashboard/api.py | 110 | Semgrep |
| SAST-004 | HIGH | CWE-306,22 | dashboard/routes/plans.py | 461 | Semgrep Custom |
| SAST-005 | HIGH | CWE-321 | .agents/mcp/vault.py | 117 | Semgrep Custom |
| SAST-006 | HIGH | CWE-74 | discord-bot/src/agent-bridge.js | 121 | Semgrep Custom |
| SAST-007 | HIGH | CWE-306,78 | dashboard/routes/system.py | 171,187 | Semgrep Custom |
| SAST-008 | HIGH | CWE-306 | dashboard/routes/system.py | 148,152,159 | Semgrep Custom |
| SAST-009 | HIGH | CWE-200,312 | dashboard/routes/auth.py | 44 | CodeQL |
| SAST-010 | MEDIUM | CWE-918 | discord-bot/src/agent-bridge.js | 10,21 | Semgrep Custom |
| SAST-011 | MEDIUM | CWE-614 | dashboard/routes/auth.py | 48 | Semgrep Custom |
| SAST-012 | MEDIUM | CWE-306,200 | dashboard/api.py | 86 | Semgrep Custom |
| SAST-013 | MEDIUM | CWE-306,200 | dashboard/routes/plans.py,rooms.py | multiple | Semgrep Custom |
| SAST-014 | MEDIUM | CWE-22 | dashboard/api_utils.py,routes/ | multiple | CodeQL+Semgrep |
| SAST-015 | MEDIUM | CWE-730 | dashboard/routes/plans.py | 1019 | CodeQL |
| SAST-016 | MEDIUM | CWE-1333 | dashboard/routes/skills.py | 337,349 | CodeQL |
| SAST-017 | MEDIUM | CWE-209 | dashboard/routes/mcp.py,plans.py | multiple | CodeQL |
| SAST-018 | MEDIUM | CWE-312 | .agents/mcp/config_resolver.py | 126 | CodeQL |
| SAST-019 | LOW | CWE-798 | dashboard/auth.py | 30 | Manual |
