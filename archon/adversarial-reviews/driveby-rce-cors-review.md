# Adversarial Review: driveby-rce-cors

## Step 1 -- Restate and Decompose

**Claim**: The dashboard exposes an unauthenticated POST endpoint at `/api/shell` that executes arbitrary OS commands via `subprocess.run(shell=True)`. Combined with CORS wildcard (`allow_origins=["*"]`), any webpage on the internet can trigger command execution on a victim's machine by sending cross-origin fetch requests to the dashboard.

**Sub-claim A**: Attacker controls the `command` query parameter via a cross-origin HTTP POST request.
- SUPPORTED. The `command` parameter is a bare `str` with no validation.

**Sub-claim B**: CORS wildcard allows the cross-origin request to succeed and the response to be read.
- SUPPORTED. `CORSMiddleware` at `api.py:108-113` sets `allow_origins=["*"]`. Since `command` is a query parameter, the POST is a "simple request" (no custom headers, no JSON body) and does not even require preflight. Even if preflight is triggered, it succeeds.

**Sub-claim C**: The `/api/shell` endpoint executes the command without authentication.
- SUPPORTED. `system.py:166-169` has no `Depends(get_current_user)` unlike neighboring endpoints (lines 71, 87, 111, 118, etc.).

All sub-claims supported.

## Step 2 -- Independent Code Path Trace

1. Cross-origin POST arrives at `http://localhost:9000/api/shell?command=<payload>`
2. `CORSMiddleware` processes the request, adds `Access-Control-Allow-Origin: *` header
3. FastAPI routes to `system.router` (prefix `/api`) -> `POST /shell`
4. `shell_command(command: str)` receives the attacker-controlled string
5. `subprocess.run(command, shell=True, capture_output=True, text=True)` executes it
6. Output returned as JSON: `{"stdout": ..., "stderr": ..., "returncode": ...}`

**Validations on path**: ZERO. No auth middleware, no input sanitization, no rate limiting.
**Framework protections**: None applicable. CORS is misconfigured to permit all origins.

## Step 3 -- Protection Surface Search

| Layer | Control | Blocks Attack? |
|-------|---------|---------------|
| Language | Python type hints (`str`) | No -- not a security control |
| Framework | FastAPI `Depends(get_current_user)` | NOT applied to `/shell` endpoint |
| Framework | CORSMiddleware | Configured to ALLOW all origins -- enables rather than blocks |
| Middleware | No WAF, no rate limiting | No protection |
| Application | No allowlist, no command sanitization | No protection |
| Network | Default bind is `0.0.0.0:9000` | Worsens exposure -- accessible beyond localhost |
| Documentation | No SECURITY.md or known-risk acknowledgment found | Not accepted risk |

No protection blocks this attack at any layer.

## Step 4 -- Real-Environment Reproduction

- **Environment**: Local macOS, FastAPI 0.135.1, commit 4c06f66
- **Healthcheck**: Server started, direct curl to `/api/shell?command=echo+test` returned `{"stdout":"test\n",...}` -- server operational
- **Attempt 1**: Direct POST `echo PWNED` -- returned stdout with "PWNED" (SUCCESS)
- **Attempt 2**: OPTIONS preflight from `Origin: http://evil.attacker.com` -- returned `access-control-allow-origin: *` (SUCCESS)
- **Attempt 3**: POST `whoami` with `Origin: http://evil.attacker.com` -- returned username with CORS allow header (SUCCESS)

All three attempts succeeded. Full evidence in `security/real-env-evidence/driveby-rce-cors/`.

## Step 5 -- Prosecution Brief

The `/api/shell` endpoint at `dashboard/routes/system.py:166-169` executes arbitrary commands via `subprocess.run(command, shell=True)` with zero authentication. This is confirmed by inspecting the function signature which lacks the `Depends(get_current_user)` dependency that protects 10+ other endpoints in the same file.

The CORS configuration at `dashboard/api.py:108-113` uses `allow_origins=["*"]`, which instructs browsers to permit cross-origin requests from any webpage. Since the `command` parameter is passed as a query string, the POST request qualifies as a "simple request" under CORS rules, meaning no preflight is even necessary -- the browser will send the request immediately.

Reproduction confirmed all three aspects: unauthenticated command execution, permissive CORS headers on preflight, and successful cross-origin command execution with readable response.

The attack requires only that a victim visits a malicious webpage while the dashboard is running. No user interaction beyond page load is needed. The default bind address of `0.0.0.0` means this is also exploitable from other machines on the network, not just localhost.

## Defense Brief

The defense must argue that some protection blocks exploitation. Examining every layer:

1. **Authentication**: The endpoint genuinely lacks auth. This is not a case of auth being applied at a different layer.
2. **CORS**: The wildcard is real and there is no `allow_credentials=True` complication (irrelevant since no auth is needed).
3. **Network isolation**: The dashboard binds to `0.0.0.0` by default, so network-level isolation does not apply.
4. **Intended behavior**: One could argue this is a developer tool intended for local use. However, (a) there is no documentation stating this is accepted risk, (b) many other endpoints in the same file ARE authenticated, suggesting auth was intended, and (c) the CORS wildcard specifically enables remote exploitation that transcends "local tool" assumptions.
5. **Deployment context**: This is a dashboard meant to be run on developer machines. While it might not be internet-facing, the cross-origin attack vector means any webpage the developer visits can exploit it -- this is the exact threat model that makes this CRITICAL rather than theoretical.

The defense has no viable argument. No protection exists at any layer.

## Step 6 -- Severity Challenge

Starting at MEDIUM:
- **Remotely triggerable**: YES -- via cross-origin request from any webpage (drive-by)
- **Trust boundary crossing**: YES -- cross-origin to localhost, then localhost to OS commands
- **No significant preconditions**: Dashboard must be running (its normal state during use)
- Upgrade to HIGH: all criteria met

Further evaluation for CRITICAL:
- **RCE**: YES -- `subprocess.run(shell=True)` with attacker-controlled input
- **Unauthenticated**: YES -- no auth on the endpoint
- **Internet-facing attack surface**: YES via CORS -- any webpage triggers it

Upgrade to CRITICAL. Matches the original severity assessment.

## Step 7 -- Verdict

The prosecution brief survives the defense with no blocking protection found at any layer. Real-environment reproduction succeeded on all three test attempts.

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Unauthenticated /api/shell endpoint with subprocess.run(shell=True) combined with CORS allow_origins=["*"] enables drive-by RCE from any webpage, confirmed by successful cross-origin reproduction.
Severity-Final: CRITICAL
PoC-Status: executed
```
