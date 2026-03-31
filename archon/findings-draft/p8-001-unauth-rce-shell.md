Phase: 8
Sequence: 001
Slug: unauth-rce-shell
Verdict: VALID
Rationale: Unauthenticated arbitrary OS command execution with zero protections — the most severe class of web vulnerability, trivially exploitable by any network-adjacent attacker.
Severity-Original: CRITICAL
PoC-Status: executed
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-A/debate.md

## Summary

POST /api/shell accepts a `command` query parameter and passes it directly to `subprocess.run(command, shell=True)` with no authentication, no input validation, and no sandboxing. Any network-adjacent attacker can execute arbitrary OS commands as the server process user.

## Location

- `dashboard/routes/system.py:166-168` — `shell_command` endpoint
- `dashboard/api.py:121` — router registration (no auth middleware)

## Attacker Control

Complete. The `command` query parameter is passed verbatim to `subprocess.run(shell=True)`. No transformation, sanitization, or validation occurs between HTTP input and OS command execution.

## Trust Boundary Crossed

Unauthenticated HTTP request → OS-level command execution as server process user. This is a direct network-to-host trust boundary violation.

## Impact

- **Confidentiality**: Read any file accessible to the server process (API keys in ~/.ostwin/.env, /etc/passwd, source code, secrets)
- **Integrity**: Write/modify any file, install backdoors, modify application code
- **Availability**: Kill processes, consume resources, wipe data
- **Lateral movement**: Establish reverse shells, pivot to internal network, access cloud metadata endpoints

## Evidence

```python
# dashboard/routes/system.py:166-168
@router.post("/shell")
async def shell_command(command: str):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
```

No `Depends(get_current_user)` in function signature. No input validation. Direct shell=True execution.

## Reproduction Steps

1. Start the dashboard server: `python -m uvicorn dashboard.api:app --host 0.0.0.0 --port 9000`
2. Execute: `curl -X POST "http://localhost:9000/api/shell?command=id"`
3. Observe the response contains the output of the `id` command
4. Escalate: `curl -X POST "http://localhost:9000/api/shell?command=cat+~/.ostwin/.env"` to read secrets

## Cold Verification

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Unauthenticated POST /api/shell executes attacker-supplied commands via subprocess.run(shell=True) with zero protections; confirmed via live reproduction returning OS command output.
Severity-Final: CRITICAL
PoC-Status: executed
```

### Independent Code Trace

Independently verified the full code path:
1. `dashboard/routes/system.py:21` -- `router = APIRouter(prefix="/api")`
2. `dashboard/routes/system.py:166-168` -- `@router.post("/shell")` with `command: str` parameter, no `Depends(get_current_user)`
3. `subprocess.run(command, shell=True, ...)` -- direct execution, zero sanitization
4. `dashboard/api.py:121` -- `app.include_router(system.router)` with no global auth middleware
5. `dashboard/api.py:108-113` -- Only middleware is CORS with `allow_origins=["*"]`

### Protection Surface

No blocking protection found at any layer. The `get_current_user` auth dependency is imported and used on ~10 other endpoints in the same file but is absent from `shell_command`. No WAF, rate limiting, input validation, or sandboxing exists.

### Reproduction Result

- **Environment**: macOS Darwin 25.3.0, Python 3.14, commit 4c06f66
- **Healthcheck**: `GET /api/status` returned HTTP 200 (with auth key)
- **Exploit**: `POST /api/shell?command=id` returned `uid=501(bytedance)` with **no authentication headers**
- **Second confirm**: `POST /api/shell?command=whoami` returned `bytedance` with no authentication

Full review: `security/adversarial-reviews/unauth-rce-shell-review.md`
Evidence: `security/real-env-evidence/unauth-rce-shell/`
