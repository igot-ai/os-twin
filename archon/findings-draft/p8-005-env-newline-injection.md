Phase: 8
Sequence: 005
Slug: env-newline-injection
Verdict: VALID
Rationale: Authenticated env file newline injection enables persistent escalation to full auth bypass; the persistence across restarts and the resulting CRITICAL bypass (p8-003) warrant HIGH severity.
Severity-Original: HIGH
PoC-Status: pending
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-A/debate.md

## Summary

The `_serialize_env` function in system.py constructs `.env` file content using f-string formatting (`f"{key}={value}"`) without sanitizing newline characters in keys or values. An authenticated attacker can inject arbitrary environment variable definitions (e.g., `OSTWIN_API_KEY=DEBUG`) that persist in the `.env` file and take effect on the next server restart, permanently activating the auth bypass described in p8-003.

## Location

- `dashboard/routes/system.py:52-68` — `_serialize_env` function (no newline sanitization)
- `dashboard/routes/system.py:254-270` — `save_env` endpoint (auth required, writes to .env)

## Attacker Control

The attacker controls the `value` field in env entries sent to POST /api/env. Newline characters in the value cause additional lines to be written to the .env file. The attacker can inject any `KEY=VALUE` pair.

## Trust Boundary Crossed

Authenticated user with env-write access → permanent auth bypass for all users. This is a privilege escalation from "authenticated user" to "persistent backdoor installer" that survives server restarts.

## Impact

- Persistent activation of OSTWIN_API_KEY=DEBUG auth bypass (p8-003)
- Survives server restarts, log rotation, and container recreation
- Once injected, all users/attackers benefit from the bypass without needing credentials
- Can inject other dangerous env vars (API keys, URLs for SSRF, etc.)

## Evidence

```python
# dashboard/routes/system.py:52-68
def _serialize_env(entries: list[dict]) -> str:
    lines = []
    for e in entries:
        t = e.get("type", "comment")
        # ...
        elif t == "var":
            key = e.get("key", "")
            value = e.get("value", "")
            if e.get("enabled", True):
                lines.append(f"{key}={value}")  # NO newline sanitization
    return "\n".join(lines) + "\n"
```

## Reproduction Steps

1. Authenticate with a valid API key
2. Send: `curl -X POST http://localhost:9000/api/env -H "X-API-Key: <key>" -H "Content-Type: application/json" -d '{"entries": [{"type": "var", "key": "SAFE_KEY", "value": "safe\nOSTWIN_API_KEY=DEBUG", "enabled": true}]}'`
3. Read the .env file — observe two lines: `SAFE_KEY=safe` and `OSTWIN_API_KEY=DEBUG`
4. Restart the server
5. Access any authenticated endpoint without credentials — auth is now bypassed

## Cold Verification

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Newline injection in _serialize_env is technically real and code-level testing confirms injection output, but severity is downgraded because authentication is required, restart is needed, and the same effect is achievable without injection via the intended env editing capability.
Severity-Final: MEDIUM
PoC-Status: theoretical
```

### Independent Code Path Trace

Traced from `POST /api/env` (system.py:254) through `_serialize_env` (system.py:52-68) to `.env` file write (system.py:269), then through startup loading (api.py:14-31) to auth bypass check (auth.py:79). The path is confirmed: no sanitization exists on newlines in key or value fields.

### Key Observations

1. **The newline injection is real but redundant**: The `save_env` endpoint replaces the entire `.env` file with whatever entries the attacker provides. An authenticated attacker can simply include `{"type": "var", "key": "OSTWIN_API_KEY", "value": "DEBUG", "enabled": true}` as a direct entry without needing newline injection at all. The injection adds stealth but not capability.

2. **Authentication is required**: The endpoint uses `Depends(get_current_user)`, meaning the attacker must already possess a valid API key.

3. **Restart is required**: The injected values only take effect after the server process restarts and re-reads the `.env` file.

4. **`load_dotenv(override=False)`**: If `OSTWIN_API_KEY` is already present in the process environment (e.g., set by a launcher script), the injected value from `.env` will be ignored.

5. **Broader context**: `POST /api/shell` (system.py:166-169) exists without authentication and provides arbitrary command execution, making this finding relatively academic in the context of overall application security.

### Severity Downgrade Rationale

Downgraded from HIGH to MEDIUM because:
- Authentication precondition prevents classification as remotely triggerable without credentials
- Server restart precondition adds a second gate
- The env editor endpoint is designed to write arbitrary env vars, making this partially by-design behavior
- The same end result is achievable without the specific injection technique

### Full Review

See: `security/adversarial-reviews/env-newline-injection-review.md`
