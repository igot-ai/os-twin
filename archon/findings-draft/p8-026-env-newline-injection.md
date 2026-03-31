Phase: 8
Sequence: 026
Slug: env-newline-injection
Verdict: VALID
Rationale: Newline injection in env file serialization allows an authenticated attacker to persistently disable all authentication on the next server restart; while auth is required and restart is needed, the impact is a complete permanent auth bypass that survives indefinitely.
Severity-Original: HIGH
PoC-Status: pending
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-B/debate.md

## Summary

The `_serialize_env()` function (system.py:52-68) does not sanitize newline characters in key or value fields when writing to `~/.ostwin/.env`. An authenticated attacker can inject `OSTWIN_API_KEY=DEBUG` into the .env file via `POST /api/env` by embedding a newline in a value field. On the next server restart, `load_dotenv(override=False)` (api.py:18) loads the injected variable, and `auth.py:79` activates the DEBUG bypass that disables ALL authentication permanently.

## Location

- **Serializer**: `dashboard/routes/system.py:52-68` -- `_serialize_env()` with no newline filtering
- **Injection point**: `dashboard/routes/system.py:65` -- `lines.append(f"{key}={value}")`
- **Write endpoint**: `dashboard/routes/system.py:254-270` -- `save_env()` with `Depends(get_current_user)`
- **Load on restart**: `dashboard/api.py:14-18` -- `load_dotenv(_env_file, override=False)`
- **DEBUG bypass**: `dashboard/auth.py:78-81` -- `if _API_KEY == "DEBUG": return {"username": ...}`

## Attacker Control

Attacker controls the `value` field in env entries. By injecting `x\nOSTWIN_API_KEY=DEBUG`, a new line is written to the .env file that sets the DEBUG bypass.

## Trust Boundary Crossed

Authenticated user to permanent unauthenticated access. The attack persists across restarts and affects all future sessions.

## Impact

- Complete, permanent authentication bypass after next restart
- All endpoints (including /api/shell RCE) become unauthenticated
- Survives log rotation, container restarts, and updates
- Identity spoofing via X-User header in DEBUG mode
- Escalation path: auth user -> permanent full admin -> RCE

## Evidence

1. `system.py:65` -- `f"{key}={value}"` with no newline sanitization
2. `system.py:254` -- `Depends(get_current_user)` present (auth required)
3. `api.py:18` -- `load_dotenv(_env_file, override=False)` loads .env on startup
4. `auth.py:79` -- `if _API_KEY == "DEBUG":` disables all auth
5. Probe PH-07/PH-08 validated this chain

## Reproduction Steps

1. Start dashboard with a valid API key: `OSTWIN_API_KEY=real-key python api.py`
2. Authenticate and send injection payload:
   ```
   curl -X POST http://localhost:9000/api/env \
     -H "X-API-Key: real-key" \
     -H "Content-Type: application/json" \
     -d '{"entries": [{"type":"var","key":"SAFE_VAR","value":"safe\nOSTWIN_API_KEY=DEBUG","enabled":true}]}'
   ```
3. Verify injection: `cat ~/.ostwin/.env` -- should show `OSTWIN_API_KEY=DEBUG` on a separate line
4. Restart the server (without OSTWIN_API_KEY in process env): `python api.py`
5. Confirm all endpoints are now unauthenticated: `curl http://localhost:9000/api/env`
6. Confirm identity spoofing: `curl -H "X-User: admin" http://localhost:9000/api/auth/me`
