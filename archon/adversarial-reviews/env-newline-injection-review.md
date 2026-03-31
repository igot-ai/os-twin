# Adversarial Review: env-newline-injection (p8-005)

## Restated Claim

An authenticated user can inject newline characters into environment variable values via `POST /api/env`, causing the `_serialize_env` function to write additional arbitrary KEY=VALUE pairs into the `.env` file. After a server restart, the injected `OSTWIN_API_KEY=DEBUG` would activate a debug auth bypass mode, allowing unauthenticated access to all endpoints.

## Sub-claims

- **Sub-claim A**: Attacker controls the `value` field in entries sent to `POST /api/env` -- CONFIRMED. The endpoint accepts arbitrary JSON entries (system.py:255-261). Authentication is required via `Depends(get_current_user)`.
- **Sub-claim B**: The value reaches `_serialize_env` without newline sanitization -- CONFIRMED. No sanitization exists anywhere on the path from `request.get("entries")` to `f"{key}={value}"` (system.py:65).
- **Sub-claim C**: The injected `OSTWIN_API_KEY=DEBUG` persists and causes auth bypass on restart -- CONFIRMED with conditions. The `.env` is loaded by `api.py:14-31` on startup, and `auth.py:79` bypasses auth when `_API_KEY == "DEBUG"`. However, `load_dotenv(override=False)` means pre-existing env vars are not overridden.

## Independent Code Path Trace

1. `POST /api/env` (system.py:254) -- requires `get_current_user` auth
2. `request.get("entries", [])` (system.py:261) -- attacker-controlled list
3. No validation on entry keys, values, or types
4. `_serialize_env(entries)` (system.py:268) -- uses `f"{key}={value}"` at line 65
5. `_ENV_FILE.write_text(content)` (system.py:269) -- writes to `~/.ostwin/.env`
6. On restart: `load_dotenv(_env_file, override=False)` or manual parser (api.py:15-31)
7. `auth.py:23`: `_API_KEY = os.environ.get("OSTWIN_API_KEY", "")`
8. `auth.py:79`: `if _API_KEY == "DEBUG"` -- bypasses all auth

**Critical observation**: The attacker does not need newline injection at all. Since `save_env` replaces the entire `.env` file with the provided entries, the attacker can simply include `{"type": "var", "key": "OSTWIN_API_KEY", "value": "DEBUG", "enabled": true}` as a direct entry. The newline injection is a stealth variant of a broader design issue.

## Protection Surface

| Layer | Protection Found | Blocks Attack? |
|-------|-----------------|----------------|
| Application | `Depends(get_current_user)` on `save_env` | Partially -- requires valid API key |
| Application | `load_dotenv(override=False)` | Partially -- won't override pre-existing env vars |
| Application | No input validation on keys/values | No |
| Framework | No CSRF protection relevant (API key auth) | N/A |
| Middleware | None found | No |

## Reproduction Evidence

Code-level reproduction confirmed:

```
>>> _serialize_env([{'type': 'var', 'key': 'SAFE_KEY', 'value': 'safe\nOSTWIN_API_KEY=DEBUG', 'enabled': True}])
'SAFE_KEY=safe\nOSTWIN_API_KEY=DEBUG\n'
```

The manual env parser from api.py would parse both lines and set both variables. Full server reproduction not attempted due to environment constraints.

## Prosecution Brief

The newline injection in `_serialize_env` is technically real. The function at system.py:65 uses `f"{key}={value}"` without stripping newlines, and the output is written directly to `~/.ostwin/.env`. On server restart, the injected `OSTWIN_API_KEY=DEBUG` line would be parsed and loaded into the environment, activating the auth bypass at auth.py:79. Code-level testing confirms the injection produces the expected multi-line output.

## Defense Brief

1. **Authentication required**: Exploiting this requires a valid `OSTWIN_API_KEY`, significantly limiting the attack surface.
2. **Restart required**: The injection only takes effect after a server restart. The attacker may not be able to trigger this.
3. **Designed behavior**: The `POST /api/env` endpoint is explicitly an env file editor. An authenticated user directly setting `OSTWIN_API_KEY=DEBUG` as a regular entry achieves the same result without any injection. The newline injection adds stealth but not capability.
4. **`override=False`**: If `OSTWIN_API_KEY` is already set in the process environment (common in production), the injected value is ignored.
5. **Self-hosted tool**: This is a developer tool where env editing is a core feature. The authenticated user likely already has broad system access.
6. **Unauthenticated shell endpoint**: `POST /api/shell` (system.py:166-169) exists without any auth and provides arbitrary command execution, making this finding relatively academic.

## Severity Challenge

Starting at MEDIUM:
- Requires authentication (significant precondition) -- blocks upgrade to HIGH
- Requires server restart -- additional precondition
- The env editor endpoint is designed to write env vars -- partially by design
- The same result is achievable without the injection technique
- Unauthenticated shell endpoint makes this moot in practice

**Challenged severity: MEDIUM** (downgraded from HIGH)

## Verdict

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Newline injection in _serialize_env is technically real and code-level testing confirms injection output, but severity is downgraded because authentication is required, restart is needed, and the same effect is achievable without injection via the intended env editing capability.
Severity-Final: MEDIUM
PoC-Status: theoretical
```

The vulnerability is real at the code level but the original HIGH severity is not justified given the authentication precondition, restart requirement, and the fact that the endpoint is designed to write arbitrary env vars (making the newline injection a stealth variant of intended functionality).
