Phase: 8
Sequence: 003
Slug: debug-auth-bypass
Verdict: VALID
Rationale: The DEBUG bypass is an intentional backdoor that completely eliminates all authentication when OSTWIN_API_KEY=DEBUG; while requiring explicit configuration, no guardrails prevent production use and it can be injected via env file newline injection (p8-005).
Severity-Original: CRITICAL
PoC-Status: theoretical
Pre-FP-Flag: check-4-ambiguous (requires DEBUG config or chained injection)
Debate: security/chamber-workspace/chamber-A/debate.md

## Summary

When the environment variable OSTWIN_API_KEY is set to the literal string "DEBUG", the `get_current_user` auth dependency returns immediately without checking any credentials. The attacker can additionally spoof their identity to any username via the X-User header. This affects every authenticated endpoint in the application.

## Location

- `dashboard/auth.py:23` — `_API_KEY = os.environ.get("OSTWIN_API_KEY", "")`
- `dashboard/auth.py:78-81` — DEBUG bypass branch in `get_current_user`

## Attacker Control

When DEBUG is active: complete. Any request passes auth. The X-User header value becomes the authenticated username with no validation. When DEBUG is not active: requires chaining with p8-005 (env newline injection) to activate.

## Trust Boundary Crossed

Unauthenticated request → full authenticated access to all protected endpoints (POST /api/env, GET /api/fs/browse, POST /api/run, GET /api/config, etc.). Identity boundary also crossed via X-User spoofing.

## Impact

- All authenticated endpoints become unauthenticated
- Identity spoofing to any username (including "admin")
- Enables access to POST /api/env (read/write secrets), GET /api/fs/browse (filesystem enumeration), POST /api/run (plan execution with subprocess spawn)
- Combined with p8-001 (/api/shell), provides complete system access without any credentials

## Evidence

```python
# dashboard/auth.py:78-81
if _API_KEY == "DEBUG":
    username = request.headers.get("x-user", "debug-user")
    return {"username": username}
```

No additional checks, no logging, no rate limiting when DEBUG mode is active.

## Reproduction Steps

1. Set environment variable: `OSTWIN_API_KEY=DEBUG`
2. Start the dashboard
3. Access any authenticated endpoint without credentials: `curl http://localhost:9000/api/env`
4. Spoof identity: `curl -H "X-User: admin" http://localhost:9000/api/env`
5. Both requests succeed — all auth is bypassed

## Cold Verification

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Real-environment reproduction confirms complete auth bypass when OSTWIN_API_KEY=DEBUG; hardcoded backdoor with zero guardrails in dashboard/auth.py:78-81, downgraded from CRITICAL to HIGH due to non-default configuration precondition.
Severity-Final: HIGH
PoC-Status: executed
```

### Verification Details

**Reviewer**: Cold Verifier (independent, zero prior context)
**Date**: 2026-03-30
**Commit**: 4c06f66

**Code trace confirmed**: `dashboard/auth.py:78-81` unconditionally bypasses all authentication when `_API_KEY == "DEBUG"`. No logging, no IP restriction, no secondary check. The function is used as a FastAPI `Depends()` guard on endpoints across `plans.py`, `engagement.py`, and other route modules.

**Reproduction**: Fully executed on local FastAPI instance.
- With `OSTWIN_API_KEY=DEBUG`: `GET /api/engagement/test123` returned 200 with zero credentials. `GET /api/plans` returned 200 with zero credentials. `X-User: admin` header accepted for identity spoofing.
- Control (`OSTWIN_API_KEY=real_key_here`): Same endpoints returned 401.
- Evidence stored at: `security/real-env-evidence/debug-auth-bypass/reproduction-log.txt`

**Severity downgrade from CRITICAL to HIGH**: The bypass requires the operator to explicitly set `OSTWIN_API_KEY=DEBUG`, which is a non-default configuration. The install script generates a cryptographically random key. No `.env.example` or documentation suggests "DEBUG" as a value. While the backdoor is dangerous and unguarded, the non-default precondition prevents a CRITICAL rating.

**Full review**: `security/adversarial-reviews/debug-auth-bypass-review.md`
