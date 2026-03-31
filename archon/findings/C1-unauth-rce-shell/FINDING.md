# C1 — Unauthenticated Remote Code Execution via POST /api/shell

| Field            | Value                                              |
|------------------|----------------------------------------------------|
| ID               | C1                                                 |
| Severity         | CRITICAL                                           |
| CWE              | CWE-78 (OS Command Injection), CWE-306 (Missing Authentication for Critical Function) |
| CVSS v3.1 Base   | 10.0 (AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H)       |
| Affected File    | `dashboard/routes/system.py:166-169`               |
| Router Reg.      | `dashboard/api.py:121`                             |
| PoC-Status       | executed                                           |
| Evidence         | `security/real-env-evidence/unauth-rce-shell/`     |
| Commit           | 4c06f66                                            |

---

## Description

`POST /api/shell` accepts a `command` query parameter and executes it via
`subprocess.run(command, shell=True, ...)` with no authentication check, no
input validation, and no sandboxing. The endpoint is reachable by any
network-adjacent party — or any party on the internet if the server binds to
`0.0.0.0` (the default at `dashboard/api.py:215`).

```python
# dashboard/routes/system.py:166-169
@router.post("/shell")
async def shell_command(command: str):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
```

Every other sensitive endpoint in the same file is protected with
`Depends(get_current_user)`. The `shell_command` handler is the single
exception, and it is the most powerful endpoint in the application.

---

## Root Cause

Two independent defects compose to produce this vulnerability:

1. **Missing authentication dependency** — `shell_command` omits
   `Depends(get_current_user)` from its signature. FastAPI's dependency
   injection makes authentication opt-in; the omission is silently ignored.

2. **Unsafe subprocess invocation** — `shell=True` passes the attacker-supplied
   string directly to `/bin/sh -c`, enabling shell meta-character injection
   even if an allowlist were added at a higher layer (it is not).

---

## Impact

An unauthenticated attacker with network access to port 9000 can:

- **Read** any file accessible to the server process — API keys, `.env` secrets,
  SSH private keys, database credentials.
- **Write** arbitrary files — backdoors, cron jobs, SSH `authorized_keys`.
- **Execute** any binary — install reverse shells, lateral-movement tooling.
- **Deny service** — kill the application, fork-bomb the host, wipe data.
- **Pivot** — reach internal services, cloud metadata endpoints
  (`169.254.169.254`), or private network ranges inaccessible from the outside.

Because the dashboard binds to `0.0.0.0` by default, the attack surface is the
entire network the host is on, not just localhost.

---

## Reproduction

**Prerequisites**: os-twin dashboard running on port 9000.

```bash
# Step 1 — confirm RCE (no auth headers)
curl -X POST "http://localhost:9000/api/shell?command=id"
# {"stdout":"uid=501(bytedance) gid=20(staff)...","returncode":0}

# Step 2 — exfiltrate secrets
curl -X POST "http://localhost:9000/api/shell?command=cat+~/.ostwin/.env"

# Step 3 — full Python exploit (four stages)
python3 security/findings/C1-unauth-rce-shell/poc.py
```

Live output confirming execution with `uid=501(bytedance)` was captured at
`security/real-env-evidence/unauth-rce-shell/attempt1-id.json`.

---

## Code References

| File | Line(s) | Note |
|------|---------|------|
| `dashboard/routes/system.py` | 166 | `@router.post("/shell")` — no auth dependency |
| `dashboard/routes/system.py` | 167 | `async def shell_command(command: str)` — raw query param |
| `dashboard/routes/system.py` | 168 | `subprocess.run(command, shell=True, ...)` — direct execution |
| `dashboard/api.py` | 121 | `app.include_router(system.router)` — no auth middleware wrapper |
| `dashboard/api.py` | 215 | Default bind `0.0.0.0` — network-wide exposure |

---

## Remediation

**Fix 1 — Remove the endpoint entirely** (recommended).
There is no legitimate use case for an unauthenticated, unrestricted remote
shell in a production application. Delete `shell_command` and its route
registration.

**Fix 2 — Add authentication (if the endpoint must exist)**.
Add the existing auth dependency to the function signature:
```python
from dashboard.auth import get_current_user

@router.post("/shell")
async def shell_command(command: str, user=Depends(get_current_user)):
    ...
```

**Fix 3 — Replace `shell=True` with an explicit argument list**.
Never pass attacker-controlled input to a shell. If a command runner is
required internally, use `subprocess.run(shlex.split(command), shell=False)` and
validate the command against an allowlist before execution.

**Fix 4 — Restrict bind address**.
Change the default uvicorn bind from `0.0.0.0` to `127.0.0.1` so the dashboard
is not reachable from the network even if a future authentication bypass occurs.

---

## Adversarial Review

`security/adversarial-reviews/unauth-rce-shell-review.md`

> Adversarial-Verdict: CONFIRMED
> Severity-Final: CRITICAL
> Live reproduction returned `uid=501(bytedance)` with zero authentication headers.
