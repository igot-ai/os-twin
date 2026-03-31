# Review Chamber: chamber-A

Cluster: RCE + Auth Bypass
DFD Slices: DFD-1 (/api/shell RCE), DFD-4 (AUTH DEBUG bypass), Drive-by RCE via CORS, Unauthenticated subprocess endpoints, Env file injection, Plan create → subprocess chain
NNN Range: p8-001 to p8-019
Started: 2026-03-30T10:00:00Z
Status: CLOSED

---

## Pre-Seeded Hypotheses from Deep Probe

### H-01: Unauthenticated OS Command Execution via POST /api/shell (from PH-01)
- **Source**: Deep Probe PH-01 (VALIDATED, CRITICAL)
- **Target**: `dashboard/routes/system.py:166-168`
- **Attack**: `POST /api/shell?command=id` — no auth required
- **Path**: query param `command` → `subprocess.run(command, shell=True)` — zero sanitization
- **Impact**: Full RCE as server process user

### H-02: Drive-by RCE via CORS Wildcard + /api/shell (from PH-02)
- **Source**: Deep Probe PH-02 (VALIDATED, CRITICAL)
- **Target**: `dashboard/api.py:108-112` CORS + `system.py:166-168` shell
- **Attack**: Malicious webpage sends `fetch("http://localhost:9000/api/shell?command=...")`
- **Path**: CORS allow_origins=["*"] permits cross-origin POST → shell_command fires
- **Impact**: Drive-by RCE — victim visits malicious page while dashboard runs

### H-03: OSTWIN_API_KEY=DEBUG Disables All Authentication (from PH-06)
- **Source**: Deep Probe PH-06 (VALIDATED, CRITICAL)
- **Target**: `dashboard/auth.py:79-81`
- **Attack**: When env has OSTWIN_API_KEY=DEBUG, any request passes auth; X-User header spoofs identity
- **Path**: `_API_KEY == "DEBUG"` → return user dict with attacker-controlled username
- **Impact**: All authenticated endpoints become fully open; identity spoofable

### H-04: Unauthenticated Subprocess via /api/run_pytest_auth and /api/test_ws (from PH-05)
- **Source**: Deep Probe PH-05 (VALIDATED, HIGH)
- **Target**: `dashboard/routes/system.py:171-196`
- **Attack**: `GET /api/run_pytest_auth` or `GET /api/test_ws` — no auth, no params
- **Path**: Fixed subprocess commands (not injectable), but unauthenticated
- **Impact**: DoS (CPU/disk), test output leaks sensitive values

### H-05: Env File Newline Injection Persists DEBUG Bypass (from PH-07/PH-08)
- **Source**: Deep Probe PH-07/PH-08 (VALIDATED, HIGH)
- **Target**: `dashboard/routes/system.py:52-68` (_serialize_env) + `dashboard/routes/system.py:254` (save_env)
- **Attack**: `POST /api/env` with value containing `\nOSTWIN_API_KEY=DEBUG`
- **Path**: No newline sanitization in _serialize_env → injected line written to .env → load_dotenv on restart
- **Impact**: Persistent auth bypass surviving restarts (requires auth or DEBUG to trigger initially)

### H-06: Unauthenticated Plan Create → LLM Prompt Injection (from PH-10)
- **Source**: Deep Probe PH-10 (VALIDATED, HIGH)
- **Target**: `dashboard/routes/plans.py:461` (create) → `plans.py:1128` (refine)
- **Attack**: POST /api/plans/create with malicious content → POST /api/plans/refine with plan_id
- **Path**: plan_file.write_text(request.content) (no auth) → refine reads content → LLM processes injection
- **Impact**: LLM data exfiltration, misleading responses, context extraction

---

## Round 1 -- Ideation

### [IDEATOR] Additional Hypothesis -- 2026-03-30T10:05:00Z

H-01 through H-06 are pre-seeded and accepted. One additional chain hypothesis:

### H-07: Unauthenticated Plan Create → Authenticated Launch Executes Attacker-Controlled working_dir Subprocess
- **Type**: Attack chain (H-06 plan create + subprocess launch)
- **Target**: `plans.py:461` (unauthenticated create with working_dir) → `plans.py:623-764` (authenticated run_plan reads working_dir from plan content → spawns subprocess with attacker-influenced cwd)
- **Attack**: Step 1: Attacker creates plan via unauthenticated POST /api/plans/create with `working_dir=/tmp/attacker-controlled`. Step 2: Legitimate user launches the plan via POST /api/run. Step 3: `subprocess.Popen([run_sh, plan_path], cwd=PROJECT_ROOT)` spawns with PROJECT_ROOT cwd (safe), BUT working_dir from meta is used for git operations and room directory resolution throughout plans.py, which could lead to subprocess execution in attacker-controlled directories.
- **Path**: create_plan writes working_dir to meta.json → run_plan reads working_dir from plan content (line 679) → git subprocess calls at line 902-944 use `cwd=working_dir` → attacker controls git operations directory
- **Impact**: Git operations (status, log) executed in attacker-controlled directory. If directory contains malicious .git/hooks or .gitconfig, secondary code execution possible. Requires social engineering (user must launch the planted plan).
- **Severity estimate**: MEDIUM (requires authenticated user action, indirect RCE via git hooks)

---

## Round 2 -- Tracing

### [TRACER] Evidence for H-01 -- 2026-03-30T10:10:00Z

**Code path confirmed**:
1. `dashboard/routes/system.py:166` — `@router.post("/shell")`
2. `dashboard/routes/system.py:167` — `async def shell_command(command: str):` — FastAPI query parameter, no `Depends(get_current_user)`
3. `dashboard/routes/system.py:168` — `result = subprocess.run(command, shell=True, capture_output=True, text=True)`
4. Router mounted at `dashboard/api.py:121` — `app.include_router(system.router)` with no prefix override; system.py defines `router = APIRouter(prefix="/api")`

**Attacker control**: Complete. The `command` parameter is taken directly from the HTTP query string with zero transformation.

**Sanitizers on path**: NONE. No input validation, no allowlist, no escaping, no sandboxing.

**Auth check**: NONE. The function signature has no `Depends(get_current_user)`.

**Evidence**: REACHABLE — trivially exploitable via `curl -X POST "http://target:9000/api/shell?command=id"`

### [TRACER] Evidence for H-02 -- 2026-03-30T10:11:00Z

**Code path confirmed**:
1. `dashboard/api.py:108-113` — CORSMiddleware configured with `allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`
2. This means any webpage can make cross-origin requests to the API
3. `allow_credentials` not set (defaults to False), but irrelevant since /api/shell requires no cookies/auth
4. Browser CORS preflight: POST with simple content-type will be allowed. Even with preflight, `allow_methods=["*"]` and `allow_headers=["*"]` means the preflight OPTIONS response grants permission.
5. Chain: attacker page → `fetch("http://localhost:9000/api/shell?command=reverse_shell_payload")` → browser sends POST → server executes

**Attacker control**: Complete. Attacker crafts the malicious webpage and controls the command parameter.

**Evidence**: REACHABLE — requires only that victim visits a webpage while the dashboard is running on localhost.

### [TRACER] Evidence for H-03 -- 2026-03-30T10:12:00Z

**Code path confirmed**:
1. `dashboard/auth.py:23` — `_API_KEY = os.environ.get("OSTWIN_API_KEY", "")` — read at module load
2. `dashboard/auth.py:78-81` — `if _API_KEY == "DEBUG": username = request.headers.get("x-user", "debug-user"); return {"username": username}`
3. This is in `get_current_user()`, the sole auth dependency used across all protected endpoints
4. When `OSTWIN_API_KEY=DEBUG` is set in the environment, ALL requests pass auth with no credential check

**Attacker control**: Conditional. Attacker cannot directly set env vars, BUT:
- If deployed with DEBUG (misconfiguration), all auth is bypassed
- Combined with H-05 (env injection), an authenticated attacker can persist this
- The `.env` file at `~/.ostwin/.env` is loaded via `load_dotenv` on startup

**Evidence**: REACHABLE (conditional on configuration). The code path is unambiguous — a string equality check with no additional guards.

### [TRACER] Evidence for H-04 -- 2026-03-30T10:13:00Z

**Code path confirmed**:
1. `dashboard/routes/system.py:171` — `@router.get("/run_pytest_auth")` — no auth
2. `system.py:174-185` — spawns `python3 -m pytest test_auth.py -v` and returns stdout/stderr
3. `dashboard/routes/system.py:187` — `@router.get("/test_ws")` — no auth
4. `system.py:190-196` — spawns `python3 test_ws.py` and returns stdout/stderr

**Attacker control**: Limited. Commands are hardcoded (not injectable). Attacker can trigger execution but not modify the command.

**Impact verification**: Test outputs returned to caller may contain assertion values, file paths, configuration details. Repeated invocation causes CPU/memory consumption (DoS).

**Evidence**: REACHABLE — unauthenticated, but impact limited to DoS and information disclosure from test output.

### [TRACER] Evidence for H-05 -- 2026-03-30T10:14:00Z

**Code path confirmed**:
1. `dashboard/routes/system.py:254-270` — `save_env` requires `Depends(get_current_user)` — auth required
2. `system.py:262` — receives entries from request body
3. `system.py:52-68` — `_serialize_env` builds `.env` content: `lines.append(f"{key}={value}")` — NO newline sanitization
4. If `value = "safe_value\nOSTWIN_API_KEY=DEBUG"`, the output will contain two lines:
   ```
   SAFE_KEY=safe_value
   OSTWIN_API_KEY=DEBUG
   ```
5. `system.py:269` — `_ENV_FILE.write_text(content)` writes the injected content
6. On next server restart, `load_dotenv` parses the file and `OSTWIN_API_KEY=DEBUG` takes effect

**Attacker control**: Requires authentication to POST /api/env. But once executed, the DEBUG bypass persists across all future restarts.

**Evidence**: REACHABLE — authenticated attacker can permanently backdoor the auth system via newline injection in env values.

### [TRACER] Evidence for H-06 -- 2026-03-30T10:15:00Z

**Code path confirmed**:
1. `dashboard/routes/plans.py:461` — `@router.post("/api/plans/create")` — no `Depends(get_current_user)`
2. `plans.py:471-472` — `if request.content: plan_file.write_text(request.content)` — writes attacker content to disk
3. `plans.py:1128` — `@router.post("/api/plans/refine")` — no `Depends(get_current_user)`
4. `plans.py:1134-1138` — reads plan content from file, passes to `refine_plan()` which sends to LLM

**Attacker control**: Complete for plan content. Plan ID returned in create response, used in refine request.

**Evidence**: REACHABLE — two-step unauthenticated attack. Attacker writes payload, then triggers LLM processing.

### [TRACER] Evidence for H-07 -- 2026-03-30T10:16:00Z

**Code path confirmed**:
1. `plans.py:461-479` — unauthenticated create_plan writes `working_dir` to meta.json (line 478)
2. `plans.py:623-624` — `run_plan` requires auth (`Depends(get_current_user)`)
3. `plans.py:677-683` — run_plan extracts `working_dir` from plan content (regex match), not from meta
4. `plans.py:759-764` — subprocess.Popen uses `cwd=str(PROJECT_ROOT)` (fixed), NOT working_dir
5. `plans.py:899-944` — git operations in `get_plan_changes` use `cwd=working_dir` from meta
6. `plans.py:880-887` — working_dir read from meta.json (which was set by unauthenticated create)

**Attacker control**: Partial. Attacker controls working_dir in meta.json. Git operations use this as cwd. However:
- The main subprocess spawn (Popen) uses PROJECT_ROOT, not working_dir
- Git operations only triggered when user views plan changes (not during launch)
- Git hooks exploitation requires attacker to pre-place a .git directory at the controlled path

**Evidence**: PARTIAL — the working_dir propagates to git operations but the main RCE path (Popen) is not affected. The git hooks chain requires additional filesystem access preconditions.

---

## Round 3 -- Challenge

### [ADVOCATE] Defense Brief for H-01 -- 2026-03-30T10:20:00Z

**Protection search (5 layers)**:
1. **Network layer**: No firewall rules in codebase. Dashboard binds to 0.0.0.0 or localhost depending on deployment.
2. **Middleware/auth**: No auth middleware wrapping /api/shell. The router has no dependency injection for auth.
3. **Input validation**: No validation, sanitization, or allowlist on the `command` parameter.
4. **Framework protection**: FastAPI does not provide automatic command injection protection.
5. **Deployment constraints**: No evidence of reverse proxy, WAF, or network segmentation in the codebase.

**FP pattern check**: NOT a false positive. This is textbook CWE-78 OS command injection.

**Blocking protections found**: NONE.

**Conclusion**: No defense available. VALID.

### [ADVOCATE] Defense Brief for H-02 -- 2026-03-30T10:21:00Z

**Protection search (5 layers)**:
1. **CORS enforcement**: `allow_origins=["*"]` with `allow_methods=["*"]` and `allow_headers=["*"]` — maximally permissive.
2. **Browser same-origin**: Fully bypassed by the CORS configuration.
3. **CSRF tokens**: None configured.
4. **Preflight restrictions**: All methods and headers allowed — preflight passes.
5. **Auth requirement**: /api/shell has no auth — no cookies needed — `allow_credentials=False` is irrelevant.

**Potential mitigation**: If the dashboard only binds to `127.0.0.1`, the attack surface is limited to same-machine browser processes. However, CORS wildcard still permits cross-origin from any origin (including malicious sites loaded in the user's browser).

**Blocking protections found**: NONE that block the attack.

**Conclusion**: VALID. The CORS wildcard combined with an unauthenticated RCE endpoint creates a drive-by attack vector.

### [ADVOCATE] Defense Brief for H-03 -- 2026-03-30T10:22:00Z

**Protection search (5 layers)**:
1. **Configuration guard**: No startup warning or check that OSTWIN_API_KEY != "DEBUG".
2. **Deployment docs**: No evidence of documentation warning against DEBUG mode in production.
3. **Environment isolation**: `_API_KEY` is read once at module import from `os.environ`. No runtime re-check.
4. **Default value**: Default is empty string `""` (line 23), which would cause all requests to fail auth (line 90 — `not _API_KEY` is True). DEBUG must be explicitly set.
5. **Access control on .env**: No file permission enforcement on `~/.ostwin/.env`.

**Mitigating factor**: DEBUG must be explicitly configured — it is not the default. Empty string default results in auth denial, not bypass.

**Blocking protections found**: The default configuration does NOT enable DEBUG. This is a misconfiguration-dependent vulnerability.

**Conclusion**: VALID but conditional. Severity should reflect that DEBUG must be explicitly set (or injected via H-05).

### [ADVOCATE] Defense Brief for H-04 -- 2026-03-30T10:23:00Z

**Protection search (5 layers)**:
1. **Auth**: None on these endpoints.
2. **Rate limiting**: None configured.
3. **Command injection**: Commands are hardcoded — not injectable from user input.
4. **Output filtering**: Full stdout/stderr returned — no redaction.
5. **Network exposure**: Same as other endpoints — depends on binding.

**Mitigating factors**:
- Commands are fixed (`python3 -m pytest test_auth.py -v` and `python3 test_ws.py`) — no user input enters the command
- Impact is DoS and information disclosure, NOT RCE
- Test files may not exist in production deployments (would return error, not sensitive data)

**Blocking protections found**: Command hardcoding prevents RCE escalation.

**Conclusion**: VALID for DoS/info disclosure. Not RCE. Severity should be MEDIUM (downgraded from HIGH) given fixed commands and non-critical information in test output.

### [ADVOCATE] Defense Brief for H-05 -- 2026-03-30T10:24:00Z

**Protection search (5 layers)**:
1. **Auth on save_env**: YES — `Depends(get_current_user)` is present on POST /api/env.
2. **Input validation on env values**: NONE — no newline filtering in `_serialize_env`.
3. **load_dotenv behavior**: `override=False` means existing env vars are not overwritten. If `OSTWIN_API_KEY` is already set in the process environment, the injected line is ignored until the process restarts without it pre-set.
4. **File permissions**: No enforcement on .env file permissions.
5. **Restart mechanism**: Attacker needs a way to trigger server restart (POST /api/stop exists but requires auth).

**Mitigating factors**:
- Requires authentication for the initial injection
- Takes effect only after restart
- If OSTWIN_API_KEY is set via process environment (not .env), the injected value may be ignored by `override=False`

**Blocking protections found**: Auth requirement limits initial access. However, the lack of newline sanitization is a clear injection vulnerability.

**Conclusion**: VALID. Auth requirement reduces severity but does not eliminate the risk — an authenticated low-privilege user can escalate to full auth bypass.

### [ADVOCATE] Defense Brief for H-06 -- 2026-03-30T10:25:00Z

**Protection search (5 layers)**:
1. **Auth on create_plan**: NONE.
2. **Auth on refine**: NONE.
3. **Content sanitization**: NONE — raw content written to file and read back into LLM.
4. **LLM safety**: Depends on LLM provider's built-in safety filters (variable, not controlled by app).
5. **Output filtering**: Full LLM response returned to caller.

**Mitigating factors**:
- LLM injection impact depends on what context the LLM has access to
- No direct code execution from LLM response (LLM cannot call /api/shell)
- Impact limited to information disclosure and response manipulation

**Blocking protections found**: NONE in the application.

**Conclusion**: VALID. Unauthenticated two-step prompt injection with no application-layer defense.

### [ADVOCATE] Defense Brief for H-07 -- 2026-03-30T10:26:00Z

**Protection search**:
1. Main subprocess (Popen at line 759) uses `cwd=PROJECT_ROOT` — NOT attacker-controlled working_dir.
2. Git operations use working_dir as cwd, but this requires the user to navigate to the plan changes view.
3. Git hooks exploitation requires attacker to have write access to the target directory.
4. The `run_plan` endpoint requires authentication.

**Blocking protections found**:
- Main execution path (Popen) does not use attacker-controlled working_dir
- Auth required on run_plan
- Multiple preconditions (filesystem write access + social engineering + user navigation)

**Conclusion**: The main RCE chain is blocked. The git operations side-channel has too many preconditions for practical exploitation. Recommend DROP or INCONCLUSIVE.

---

## Round 4 -- Synthesis

### [SYNTHESIZER] Verdict for H-01 -- 2026-03-30T10:30:00Z

**Prosecution summary**: POST /api/shell passes user-controlled `command` query parameter directly to `subprocess.run(command, shell=True)` with zero authentication, zero sanitization, and zero sandboxing. Code at system.py:166-168. Trivially exploitable with a single curl command.

**Defense summary**: No blocking protections found at any layer. No auth, no input validation, no framework protection, no network restriction in code.

**Pre-FP Gate**: all checks passed
- Attacker control verified: YES (query param → shell=True)
- Framework protection searched: YES (none found)
- Trust boundary crossing: YES (unauthenticated network → OS command execution)
- Normal attacker position: YES (network access only)
- Ships to production: YES (main application code)

**Verdict: VALID**
**Severity: CRITICAL**
**Rationale**: Unauthenticated arbitrary OS command execution with zero protections — the most severe class of web vulnerability, trivially exploitable by any network-adjacent attacker.

**Finding draft written to**: security/findings-draft/p8-001-unauth-rce-shell.md
**Registry updated**: AP-001 Unauthenticated shell=True command injection

### [SYNTHESIZER] Verdict for H-02 -- 2026-03-30T10:31:00Z

**Prosecution summary**: CORS wildcard (`allow_origins=["*"]`) at api.py:108-113 permits any webpage to make cross-origin POST requests to /api/shell, enabling drive-by RCE when a user visits a malicious page while the dashboard runs.

**Defense summary**: No blocking protections. allow_credentials=False is irrelevant since /api/shell requires no auth. Dashboard likely binds to localhost but browser still processes cross-origin from malicious pages.

**Pre-FP Gate**: all checks passed
- Attacker control verified: YES (attacker controls webpage content and command parameter)
- Framework protection searched: YES (CORS is maximally permissive)
- Trust boundary crossing: YES (cross-origin web page → local RCE)
- Normal attacker position: YES (host a webpage)
- Ships to production: YES

**Verdict: VALID**
**Severity: CRITICAL**
**Rationale**: CORS wildcard combined with unauthenticated RCE endpoint enables drive-by code execution requiring only that a victim visit a malicious webpage — no direct network access to the dashboard needed.

**Finding draft written to**: security/findings-draft/p8-002-driveby-rce-cors.md
**Registry updated**: AP-002 CORS wildcard enabling cross-origin RCE

### [SYNTHESIZER] Verdict for H-03 -- 2026-03-30T10:32:00Z

**Prosecution summary**: When OSTWIN_API_KEY=DEBUG, the auth.py:79-81 check returns a user dict with attacker-controlled username (via X-User header), completely bypassing all authentication across every protected endpoint.

**Defense summary**: DEBUG is not the default value (default is empty string, which denies all auth). Must be explicitly configured or injected via H-05.

**Pre-FP Gate**: all checks passed
- Attacker control verified: YES (identity spoofable via X-User header when DEBUG active)
- Framework protection searched: YES (no guards against DEBUG configuration)
- Trust boundary crossing: YES (unauthenticated → full authenticated access)
- Normal attacker position: check-4-ambiguous — requires DEBUG to be set (misconfiguration or chained via H-05)
- Ships to production: YES

**Verdict: VALID**
**Severity: CRITICAL**
**Rationale**: The DEBUG bypass is an intentional backdoor that, when active, completely eliminates all authentication; while it requires explicit configuration, there are no guardrails preventing its use in production and it can be injected via H-05.

**Finding draft written to**: security/findings-draft/p8-003-debug-auth-bypass.md
**Registry updated**: AP-003 DEBUG backdoor in auth flow

### [SYNTHESIZER] Verdict for H-04 -- 2026-03-30T10:33:00Z

**Prosecution summary**: GET /api/run_pytest_auth and GET /api/test_ws spawn subprocess commands without authentication. Any network-adjacent client can trigger CPU-intensive test execution and receive full stdout/stderr output.

**Defense summary**: Commands are hardcoded — no user input enters the command string. Impact limited to DoS and potential information disclosure from test output. Test files may not exist in production.

**Pre-FP Gate**: all checks passed
- Attacker control verified: YES (can trigger execution) / NO (cannot control command)
- Framework protection searched: YES (none for auth)
- Trust boundary crossing: YES (unauthenticated → subprocess execution)
- Normal attacker position: YES
- Ships to production: YES (but test files may not exist)

**Verdict: VALID**
**Severity: MEDIUM**
**Rationale**: Unauthenticated subprocess trigger enables DoS and information disclosure, but hardcoded commands prevent command injection, reducing severity from HIGH to MEDIUM.

**Finding draft written to**: security/findings-draft/p8-004-unauth-subprocess-test.md
**Registry updated**: no new pattern (covered by AP-001 missing auth variant)

### [SYNTHESIZER] Verdict for H-05 -- 2026-03-30T10:34:00Z

**Prosecution summary**: _serialize_env at system.py:52-68 performs no newline sanitization on key/value pairs, allowing an authenticated attacker to inject `OSTWIN_API_KEY=DEBUG` into the .env file via POST /api/env. On next restart, load_dotenv activates the DEBUG bypass (H-03), creating a persistent backdoor.

**Defense summary**: Requires authentication for the initial injection. Takes effect only after restart. If OSTWIN_API_KEY is set in process env (not .env), `override=False` in load_dotenv may ignore the injection.

**Pre-FP Gate**: all checks passed
- Attacker control verified: YES (newline injection confirmed in _serialize_env)
- Framework protection searched: YES (no sanitization found)
- Trust boundary crossing: YES (authenticated user → permanent auth bypass for all users)
- Normal attacker position: YES (authenticated user, possibly low-privilege)
- Ships to production: YES

**Verdict: VALID**
**Severity: HIGH**
**Rationale**: Authenticated env file newline injection enables persistent escalation to full auth bypass; while auth is required for the initial step, the persistence across restarts and the severity of the resulting bypass (CRITICAL H-03) warrant HIGH severity.

**Finding draft written to**: security/findings-draft/p8-005-env-newline-injection.md
**Registry updated**: AP-004 Newline injection in env file serialization

### [SYNTHESIZER] Verdict for H-06 -- 2026-03-30T10:35:00Z

**Prosecution summary**: Unauthenticated POST /api/plans/create writes attacker-controlled content to disk. Unauthenticated POST /api/plans/refine reads that content and passes it to the LLM, enabling second-order prompt injection.

**Defense summary**: No application-layer protections. LLM provider safety filters are external and not guaranteed. Impact limited to information disclosure and response manipulation (no direct code execution from LLM).

**Pre-FP Gate**: all checks passed
- Attacker control verified: YES (content fully controlled, plan_id returned)
- Framework protection searched: YES (none found)
- Trust boundary crossing: YES (unauthenticated input → LLM context poisoning)
- Normal attacker position: YES
- Ships to production: YES

**Verdict: VALID**
**Severity: HIGH**
**Rationale**: Unauthenticated two-step prompt injection with no application-layer defense allows data exfiltration from LLM context; severity is HIGH rather than CRITICAL because impact is limited to LLM manipulation, not direct system compromise.

**Finding draft written to**: security/findings-draft/p8-006-unauth-plan-llm-injection.md
**Registry updated**: AP-005 Unauthenticated stored LLM prompt injection

### [SYNTHESIZER] Verdict for H-07 -- 2026-03-30T10:36:00Z

**Prosecution summary**: Unauthenticated plan create writes attacker-controlled working_dir to meta.json. Git operations in get_plan_changes use this working_dir as cwd, potentially enabling git hooks code execution.

**Defense summary**: The main subprocess (Popen) uses PROJECT_ROOT, not working_dir. Auth required on run_plan. Git operations only triggered by user navigation. Git hooks exploitation requires prior filesystem write access. Multiple preconditions make practical exploitation unlikely.

**Pre-FP Gate**: failed on check-4 — requires attacker to have local filesystem write access to plant git hooks, which is not a normal attacker position for a network-based attack.

**Verdict: DROP**
**Severity: --**
**Rationale**: The main RCE path is not affected by the working_dir injection, and the git hooks side-channel requires local filesystem write access and social engineering — too many preconditions for practical exploitation.

**Finding draft written to**: --
**Registry updated**: no new pattern

---

## Chamber Summary

| Hypothesis | Verdict | Severity | Finding Draft |
|-----------|---------|----------|---------------|
| H-01 | VALID | CRITICAL | p8-001-unauth-rce-shell.md |
| H-02 | VALID | CRITICAL | p8-002-driveby-rce-cors.md |
| H-03 | VALID | CRITICAL | p8-003-debug-auth-bypass.md |
| H-04 | VALID | MEDIUM | p8-004-unauth-subprocess-test.md |
| H-05 | VALID | HIGH | p8-005-env-newline-injection.md |
| H-06 | VALID | HIGH | p8-006-unauth-plan-llm-injection.md |
| H-07 | DROP | -- | -- |

Findings written: 6
Patterns added to registry: 5
Variant candidates: 0

Chamber closed: 2026-03-30T10:40:00Z

---

## Tracer Verification Addendum -- 2026-03-30T18:10:00Z

> This section extends the Round 2 tracing with rigorous file:line evidence, sanitizer
> bypassability assessments, and CodeQL artifact cross-references per the Tracer protocol.
> Pre-traced Deep Probe evidence is extended and verified rather than re-traced from scratch.

### [TRACER] Evidence for H-01 -- 2026-03-30T18:10:00Z

**Reachability: REACHABLE**

Code path:
1. `dashboard/routes/system.py:166` -- `@router.post("/shell")` — no `Depends()` in decorator or function signature; the FastAPI router has no global auth middleware
2. `dashboard/routes/system.py:167` -- `async def shell_command(command: str):` — bare `str` function parameter on a POST handler is treated by FastAPI as a query parameter (not a body field); attack payload: `?command=<shell_expression>`
3. `dashboard/routes/system.py:168` -- `result = subprocess.run(command, shell=True, capture_output=True, text=True)` — the `command` string is passed to `/bin/sh -c <command>`; shell metacharacters (`;`, `|`, `$()`, `&&`, backtick) are fully interpreted
4. `dashboard/api.py:121` -- `app.include_router(system.router)` — the router is registered; `system.router` is declared with `prefix="/api"` at top of system.py, so the effective path is `/api/shell`
5. `dashboard/routes/system.py:169` -- `return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}` — full command output returned to caller confirming execution

Sanitizers on path:
- NONE. No authentication dependency, no input allowlist, no length limit, no subprocess argument list (which would prevent shell interpretation), no sandboxing.

CodeQL slice: call-graph-slices.json entry CGS-001, reachable: true. Entry EP-001 (entry-points.json), Sink SK-001 (sinks.json, `subprocess.run(shell=True)`, CWE-78).
On-demand query: none

**Assessment**: Fully confirmed via direct source reading of `dashboard/routes/system.py:166-169`. The endpoint is the textbook CWE-78 pattern: attacker-controlled string → `subprocess.run(shell=True)`. No wrapper, sanitizer, or framework-level protection exists on the path. Single HTTP request required.

---

### [TRACER] Evidence for H-02 -- 2026-03-30T18:11:00Z

**Reachability: REACHABLE**

Code path:
1. `dashboard/api.py:108-113` -- `app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])` — maximally permissive; `allow_credentials` is absent (defaults False)
2. Browser CORS preflight for `POST /api/shell` from any cross-origin page: `OPTIONS /api/shell` receives `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods: *`, `Access-Control-Allow-Headers: *` — browser grants permission
3. `dashboard/routes/system.py:166-168` — cross-origin POST request arrives; endpoint has no auth check; `subprocess.run(command, shell=True)` fires as in H-01
4. Browser receives the JSON response; `allow_credentials=False` does not block the response when no credentials are involved in the request

Sanitizers on path:
- `allow_credentials=False` (CORS default) — only prevents cookies/auth headers from being attached to cross-origin requests. The `/api/shell` endpoint requires no auth, so this provides zero barrier. **Bypassable: trivially — the endpoint does not require credentials.**
- Same-origin policy — structurally destroyed by `allow_origins=["*"]`. **Bypassable: not applicable once CORS wildcard is in place.**

CodeQL slice: CGS-001 (sink), SK-002 (sinks.json CORS config, CWE-346). No combined CGS slice for the two-component chain, but both components are independently confirmed.
On-demand query: none

**Assessment**: The combination of `allow_origins=["*"]` (confirmed at `api.py:110`) with the unauthenticated `/api/shell` endpoint creates a browser-mediated attack vector. A malicious page served from any origin can issue `fetch("http://localhost:9000/api/shell?command=...", {method:"POST"})` and receive the response. The `allow_credentials=False` default is commonly cited as a mitigation for CORS wildcard, but it is irrelevant here because the target endpoint requires no credentials.

---

### [TRACER] Evidence for H-03 -- 2026-03-30T18:12:00Z

**Reachability: REACHABLE (configuration-gated)**

Code path:
1. `dashboard/auth.py:23` -- `_API_KEY = os.environ.get("OSTWIN_API_KEY", "")` — module-level constant; value is fixed at process start; if `OSTWIN_API_KEY=DEBUG` in environment, `_API_KEY = "DEBUG"` for process lifetime
2. `dashboard/auth.py:72` -- `async def get_current_user(request: Request) -> dict:` — the single FastAPI dependency used by all protected routes
3. `dashboard/auth.py:79` -- `if _API_KEY == "DEBUG":` — plain string equality; evaluated before any credential extraction
4. `dashboard/auth.py:80` -- `username = request.headers.get("x-user", "debug-user")` — attacker-supplied `X-User` header value becomes the identity
5. `dashboard/auth.py:81` -- `return {"username": username}` — immediate return; the `secrets.compare_digest` comparison at line 90 is never reached

Sanitizers on path:
- `secrets.compare_digest` at `auth.py:90` — timing-safe comparison used in the normal auth path. **Bypassable: entirely unreachable when DEBUG condition fires at line 79.**
- `if not _API_KEY` at `auth.py:90` — raises 401 when API key is empty string. **Bypassable: unreachable when `_API_KEY == "DEBUG"` (the DEBUG check at line 79 fires first).**
- Default value `""` at `auth.py:23` — when `OSTWIN_API_KEY` is unset, `_API_KEY = ""`, which denies all auth at line 90 rather than granting it. This is correct behavior for the unset case only. **Not bypassable for the unset case; irrelevant when DEBUG is explicitly set.**

CodeQL slice: call-graph-slices.json entry CGS-005, reachable: true. Sink SK-006 (sinks.json, `_API_KEY == 'DEBUG'`, CWE-287).
On-demand query: none

**Assessment**: Confirmed at `dashboard/auth.py:79-81`. The bypass is a single string equality check with no guards. When `OSTWIN_API_KEY=DEBUG`, every `Depends(get_current_user)` route is fully open and identity is attacker-controlled via `X-User` header. Currently no RBAC decisions in the codebase use `user["username"]` (confirmed via probe summary CV-06), but the bypass enables access to all authenticated endpoints regardless.

---

### [TRACER] Evidence for H-04 -- 2026-03-30T18:13:00Z

**Reachability: REACHABLE (unauthenticated subprocess trigger; not command-injectable)**

Code path:
1. `dashboard/routes/system.py:171` -- `@router.get("/run_pytest_auth")` — no Depends() in signature
2. `dashboard/routes/system.py:174` -- `cmd = ["python3", "-m", "pytest", str(PROJECT_ROOT / "test_auth.py"), "-v"]` — command is fully hardcoded; no user input enters `cmd`
3. `dashboard/routes/system.py:175-179` -- `await asyncio.create_subprocess_exec(*cmd, ...)` — list-form invocation; shell injection not possible even if input were present
4. `dashboard/routes/system.py:180-184` -- full stdout and stderr returned in response body

Code path (test_ws):
5. `dashboard/routes/system.py:187` -- `@router.get("/test_ws")` — no Depends()
6. `dashboard/routes/system.py:190` -- `cmd = ["python3", str(PROJECT_ROOT / "test_ws.py")]` — hardcoded
7. `dashboard/routes/system.py:191` -- `subprocess.run(cmd, capture_output=True, text=True)` — list-form, not shell=True

Sanitizers on path:
- Hardcoded command list — prevents user input from reaching the command. **Bypassable for command injection: NO. Not bypassable for the unauthenticated trigger itself.**
- List-form subprocess invocation — even if input were present, list form prevents shell interpretation. Not relevant here since no input is used.

CodeQL slice: entry-points.json EP-002 (auth: false), EP-003 (auth: false). No CGS entry — CodeQL did not generate a dedicated slice for these (commands are hardcoded, no tainted flow).
On-demand query: none

**Assessment**: Both endpoints confirmed unauthenticated via direct source inspection. The impact is limited to (a) CPU/disk DoS via repeated invocation and (b) information disclosure from test output (stdout/stderr). The hardcoded command list prevents command injection. The probe summary assessment (PH-05) is confirmed.

---

### [TRACER] Evidence for H-05 -- 2026-03-30T18:14:00Z

**Reachability: REACHABLE (requires valid authentication)**

Code path:
1. `dashboard/routes/system.py:254` -- `@router.post("/env")` with `user: dict = Depends(get_current_user)` — authentication required
2. `dashboard/routes/system.py:261` -- `entries = request.get("entries", [])` — attacker-controlled list of dicts
3. `dashboard/routes/system.py:268` -- `content = _serialize_env(entries)` — delegates to serializer
4. `dashboard/routes/system.py:52-68` -- `_serialize_env()`:
   - Line 61: `key = e.get("key", "")` — raw string, no validation
   - Line 62: `value = e.get("value", "")` — raw string, no validation
   - Line 65: `lines.append(f"{key}={value}")` — if `value = "safe\nOSTWIN_API_KEY=DEBUG"`, this appends `"safe_key=safe\nOSTWIN_API_KEY=DEBUG"` — a string with an embedded newline
5. `dashboard/routes/system.py:68` -- `return "\n".join(lines) + "\n"` — the embedded newline from step 4 joins with the separator, producing a multi-line file with `OSTWIN_API_KEY=DEBUG` as a valid line
6. `dashboard/routes/system.py:269` -- `_ENV_FILE.write_text(content)` — injected content written to `~/.ostwin/.env`
7. `dashboard/api.py:18` -- `load_dotenv(_env_file, override=False)` at next server startup — `python-dotenv` parses the file and loads `OSTWIN_API_KEY=DEBUG` if not already in `os.environ`
8. `dashboard/auth.py:23` -- `_API_KEY = os.environ.get("OSTWIN_API_KEY", "")` — picks up the injected value; DEBUG bypass at line 79 activates for all subsequent requests

Sanitizers on path:
- `Depends(get_current_user)` at step 1 — requires valid authentication or existing DEBUG mode. **Bypassable: not bypassable on its own; requires prior auth or DEBUG activation.**
- `load_dotenv(override=False)` at step 7 — will not overwrite `OSTWIN_API_KEY` if it is already set in the process environment (e.g., exported in shell before starting uvicorn). **Bypassable: not bypassable if the env var is set at the OS level; bypassed if the server is started from a clean environment relying on the .env file.**

CodeQL slice: No dedicated CGS entry. Downstream sink is SK-006 (auth-bypass). This is a write-path → startup-read chain not captured in a single CodeQL data-flow query.
On-demand query: none

**Assessment**: Confirmed at `dashboard/routes/system.py:52-68` and `:254-270`. The `_serialize_env` function has zero newline sanitization. Injection payload: `{"entries": [{"type": "var", "key": "X", "value": "x\nOSTWIN_API_KEY=DEBUG", "enabled": true}]}`. This produces a valid `.env` file containing `OSTWIN_API_KEY=DEBUG`. On next startup without the var in the OS environment, the DEBUG bypass (H-03) activates persistently. Two preconditions: (1) valid auth at injection time, (2) server restart without `OSTWIN_API_KEY` pre-set in OS environment.

---

### [TRACER] Evidence for H-06 -- 2026-03-30T18:15:00Z

**Reachability: REACHABLE**

Code path (Step 1 — plant payload):
1. `dashboard/routes/plans.py:461` -- `@router.post("/api/plans/create")` — function signature: `async def create_plan(request: CreatePlanRequest)` — no `Depends()` parameter of any kind
2. `dashboard/routes/plans.py:464` -- `plan_id = hashlib.sha256(raw.encode()).hexdigest()[:12]` — deterministic 12-char hex ID
3. `dashboard/routes/plans.py:471-472` -- `if request.content: plan_file.write_text(request.content)` — attacker-controlled content written verbatim to disk at `~/.ostwin/plans/{plan_id}.md`
4. `dashboard/routes/plans.py:502` -- `return {"plan_id": plan_id, ...}` — the `plan_id` is returned in the HTTP 200 response body; attacker extracts it directly

Code path (Step 2 — trigger LLM processing):
5. `dashboard/routes/plans.py:1128` -- `@router.post("/api/plans/refine")` — function signature: `async def refine_plan_endpoint(request: RefineRequest)` — no `Depends()` parameter
6. `dashboard/routes/plans.py:1134-1137` -- `p_file = PLANS_DIR / f"{request.plan_id}.md"; plan_content = p_file.read_text()` — reads the attacker-planted file back from disk
7. `dashboard/routes/plans.py:1138` -- `result = await refine_plan(user_message=request.message, plan_content=plan_content, ...)` — attacker content is passed as `plan_content` to the LLM with no sanitization; it arrives as authoritative plan data in the LLM context

Sanitizers on path:
- `CreatePlanRequest` Pydantic model — enforces `str` type on `content`. No content validation, no length limit, no prompt injection detection. **Bypassable: trivially.**
- `RefineRequest` Pydantic model — enforces `str` types. No sanitization. **Bypassable: trivially.**
- LLM provider safety filters — external, not under application control, variable across models. **Bypassable: cannot be relied upon as a security boundary.**

CodeQL slice: call-graph-slices.json entry CGS-003 (SK-008 file-write sink, reachable: true). SK-012 (subprocess/LLM sink) also relevant for step 2. EP-007 and EP-010 both marked `auth: false` in entry-points.json.
On-demand query: none

**Assessment**: Two-step zero-authentication attack confirmed. Step 1 (`plans.py:461-502`) and Step 2 (`plans.py:1128-1138`) are both unauthenticated. The `plan_id` is in the HTTP 200 response from step 1 — no reconnaissance or SSE subscription needed (Deep Probe CV-12 confirmed this simplification). The LLM receives attacker-controlled content as authoritative input. Impact: extraction of LLM context (plans, roles, system structure), misleading LLM outputs sent to legitimate users.

---

### [TRACER] Evidence for H-07 (Dropped Hypothesis — Tracing for Record) -- 2026-03-30T18:16:00Z

**Reachability: PARTIAL (main RCE path blocked; git operations side-channel has high precondition bar)**

Code path:
1. `dashboard/routes/plans.py:461-479` -- `create_plan` (unauthenticated) writes `working_dir` to `meta["warrooms_dir"]` at line 478: `str(Path(working_dir) / ".war-rooms")` — attacker controls this value
2. `dashboard/routes/plans.py:504` -- `save_plan` requires auth (`Depends(get_current_user)`); this route is not the execution path
3. `dashboard/api_utils.py:661-670` -- `resolve_plan_warrooms_dir()` reads `working_dir` from `meta.json` and returns `Path(wd) / ".war-rooms"` — no path validation
4. `dashboard/routes/plans.py:759` -- `subprocess.Popen([run_sh, plan_path], cwd=str(PROJECT_ROOT))` — `cwd` is `PROJECT_ROOT`, NOT `working_dir`; the main subprocess is NOT influenced by attacker-controlled working_dir
5. `dashboard/routes/plans.py:880-944` -- `get_plan_changes()` reads `working_dir` from meta and uses it as `cwd` for git subprocess calls — this IS influenced by attacker-controlled working_dir

Sanitizers on path:
- `cwd=str(PROJECT_ROOT)` at `plans.py:759` — the main plan execution subprocess uses a fixed, safe cwd. **Effectively blocks the direct RCE chain.**
- Git hooks exploitation requires attacker to have pre-planted `.git/hooks/` at the attacker-controlled `working_dir` path before the git subprocess runs. **This requires local filesystem write access — not a network-only precondition.**

CodeQL slice: No CGS entry for this chain.
On-demand query: none

**Assessment**: The main subprocess execution path (`Popen`) uses `PROJECT_ROOT` as cwd — the attacker-controlled `working_dir` does not reach the primary RCE sink. The git operations side-channel (`get_plan_changes`) does use attacker-controlled working_dir as cwd, but exploiting this via git hooks requires the attacker to have prior write access to the target filesystem path, which is not achievable from a network-only position. The Synthesizer DROP verdict is supported by the tracing evidence.

---

### Tracer Findings Not Covered by Chamber Hypotheses

The following confirmed vulnerabilities from the Deep Probe and CodeQL artifacts fall within the RCE + Auth Bypass cluster scope and are noted for completeness.

**Finding T-01: Unauthenticated Telegram Config Exfiltration (EP-004, EP-005, EP-006)**

`dashboard/routes/system.py:148-164`: Three Telegram endpoints have no `Depends()`:
- `GET /api/telegram/config` (line 148) — returns `{bot_token, chat_id}` from `telegram_config.json`
- `POST /api/telegram/config` (line 152) — overwrites `telegram_config.json` with attacker-supplied values
- `POST /api/telegram/test` (line 159) — sends an arbitrary message via the configured bot

Adjacent endpoints on lines 141 and 132 (`/api/config`, `/api/release`) both use `Depends(get_current_user)`, confirming the omission is not intentional. Reachability: REACHABLE. Severity: HIGH.

**Finding T-02: verify_password Always Returns True (SK-007 — dormant)**

`dashboard/auth.py:29-30`: `def verify_password(plain_password, hashed_password): return True`. Not currently called in any reachable code path (confirmed via probe summary PH-19). Reachability: UNREACHABLE currently. Risk: dormant escalation if password-based auth is added.

**Finding T-03: Raw API Key in Login Response Body (SK-004)**

`dashboard/routes/auth.py:43-44`: `JSONResponse(content={"access_token": _API_KEY})` — the permanent server secret is returned in the JSON response body. The `httponly=True` cookie set at line 48 is negated by including the same value in the cleartext response. Confirmed by CodeQL finding #3 (py/clear-text-storage-sensitive-data) and SK-004 (sinks.json).

**Finding T-04: Cookie Missing secure=True (SK-003, CGS-006)**

`dashboard/routes/auth.py:48-55`: `response.set_cookie(key=AUTH_COOKIE_NAME, value=_API_KEY, httponly=True, samesite="lax")` — missing `secure=True`. Over HTTP, the raw API key is transmitted in plaintext in every authenticated request. Confirmed by CGS-006 (call-graph-slices.json) and SK-003 (sinks.json, CWE-614).

**Finding T-05: fe_catch_all Path Traversal (Latent)**

`dashboard/api.py:146-151`: `exact = FE_OUT_DIR / path; if exact.is_file(): return FileResponse(str(exact))` — no containment check. Python `Path.__truediv__` preserves `..` components; OS resolves them at open time. Route only active when `USE_FE = True` (FE_OUT_DIR built). Deep Probe assessed uvicorn does NOT normalize `..` in `{path:path}` parameters. Reachability: PARTIAL (latent; requires production deployment with built frontend). Severity: HIGH when deployed.

CodeQL: CodeQL finding #2 (py/path-injection) covers multiple files; `api.py` fe_catch_all is the most severe instance.

