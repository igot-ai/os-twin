# Adversarial Review: debug-auth-bypass (p8-003)

## Step 1 -- Restatement and Decomposition

**Vulnerability claim**: The application's authentication dependency `get_current_user` contains a hardcoded backdoor that disables all authentication when the environment variable `OSTWIN_API_KEY` equals the literal string "DEBUG". When active, any HTTP request passes authentication, and the `X-User` header is blindly trusted for identity.

**Sub-claims**:
- **A**: `OSTWIN_API_KEY` can be set to "DEBUG" (by operator or chained attack).
- **B**: When set, `get_current_user` returns immediately at line 79-81 without checking any credentials.
- **C**: This grants unauthenticated access to all protected endpoints and enables identity spoofing.

All sub-claims are coherent and testable. No sub-claim failures.

## Step 2 -- Independent Code Path Trace

Traced from `dashboard/auth.py`:

1. Line 23: `_API_KEY = os.environ.get("OSTWIN_API_KEY", "")` -- module-level variable, set once at import.
2. Line 72: `async def get_current_user(request: Request) -> dict:` -- the auth dependency.
3. Lines 78-81: `if _API_KEY == "DEBUG":` -- unconditional bypass. Returns `{"username": <X-User header or "debug-user">}`.
4. Lines 83-94: Normal auth path (only reached if `_API_KEY != "DEBUG"`).

The function is used as a FastAPI `Depends()` on numerous endpoints across `dashboard/routes/plans.py`, `dashboard/routes/engagement.py`, and others. When it returns a dict, auth is considered passed.

**Validations on the path**: Zero. No logging, no IP restriction, no rate limit, no warning output, no secondary check. The bypass is unconditional.

**Framework protections**: FastAPI provides no built-in guard against application-level auth bypass logic. The `Depends()` mechanism delegates entirely to the user-defined function.

**Discrepancies with finding**: None. The code matches exactly as described.

## Step 3 -- Protection Surface Search

| Layer | Protection | Blocks Attack? |
|-------|-----------|---------------|
| Language | Python string comparison | No |
| Framework | FastAPI Depends() | No -- delegates to user function |
| Middleware | None detected for auth override | No |
| Application | Install script generates real key (line 572 of install.sh) | Partial -- default config is safe |
| Application | No startup warning when DEBUG mode is active | No |
| Application | No allowlist restricting DEBUG to localhost | No |
| Documentation | No SECURITY.md mentioning this as known/accepted risk | No |

**Key mitigating factor**: The default installation generates a cryptographically random key via `secrets.token_urlsafe(32)`. The DEBUG value must be explicitly set by someone. This is a significant precondition -- the vulnerability is not exploitable in default configuration.

## Step 4 -- Real-Environment Reproduction

**Environment**: macOS Darwin 25.3.0, Python 3.14, FastAPI 0.135.1, commit 4c06f66.

**Healthcheck**: `GET /api/status` returned 200 on both test servers.

**Reproduction results**:
- With `OSTWIN_API_KEY=DEBUG`: All authenticated endpoints returned 200 with zero credentials. Identity spoofing via `X-User: admin` accepted.
- Control with `OSTWIN_API_KEY=real_key_here`: Same endpoints returned 401.

**PoC-Status**: executed. Full reproduction log at `security/real-env-evidence/debug-auth-bypass/reproduction-log.txt`.

## Step 5 -- Prosecution and Defense Briefs

### Prosecution Brief

The code at `dashboard/auth.py:78-81` is an unguarded authentication bypass. When `OSTWIN_API_KEY=DEBUG`:

1. Every endpoint protected by `Depends(get_current_user)` becomes fully unauthenticated.
2. The `X-User` header allows arbitrary identity spoofing with no validation.
3. No logging, warning, or rate limiting alerts operators to this state.
4. Protected endpoints include sensitive operations: plan management, engagement data, filesystem browsing, and potentially command execution (when combined with other endpoints).
5. Reproduction confirms trivial exploitability -- a single `curl` command with no headers accesses protected data.
6. The backdoor string "DEBUG" is a common, guessable value that developers might set casually during development and forget to change.
7. There are no runtime safeguards (e.g., "if DEBUG, only accept from localhost").

### Defense Brief

1. **Non-default configuration required**: The install script generates a secure random key. No `.env.example` or documentation suggests using "DEBUG". An operator must explicitly set `OSTWIN_API_KEY=DEBUG`.
2. **Intentional development feature**: The code comment `# DEBUG mode: skip auth entirely when OSTWIN_API_KEY=DEBUG` suggests this is an intentional developer convenience, not an accidental flaw.
3. **No remote injection path**: Without a chained vulnerability, a remote attacker cannot set environment variables. The finding's reference to p8-005 (env injection) is a separate finding and should be evaluated independently.
4. **Operator responsibility**: If an operator sets their API key to the literal string "DEBUG", they have effectively chosen to disable authentication, similar to setting an empty password.

## Step 6 -- Severity Challenge

Starting at MEDIUM.

**Upgrade signals**:
- When active, it is remotely triggerable (any HTTP request).
- Complete trust boundary crossing (unauth to full auth).
- Trivially exploitable (no special payload needed).

**Downgrade signals**:
- Requires non-default configuration (`OSTWIN_API_KEY=DEBUG` must be explicitly set).
- Not exploitable in default installation.
- Chained exploitation via p8-005 is a separate finding and not verified here.

The non-default configuration requirement is a significant precondition. However, the bypass is complete and unguarded when active, and "DEBUG" is a highly guessable/common developer value with no runtime warnings.

**Challenged severity: HIGH** (not CRITICAL, because it requires explicit non-default configuration).

The finding draft states Severity-Original: CRITICAL. The challenged severity HIGH is lower, so HIGH wins.

## Step 7 -- Verdict

**Adversarial-Verdict: CONFIRMED**

The prosecution brief survives the defense: while non-default configuration is required, the code unambiguously contains a complete authentication bypass triggered by a common, guessable string with zero guardrails. Real-environment reproduction succeeded on all attempts.

The defense's strongest point (non-default config) is a severity modifier, not a disproof. The code is undeniably a dangerous backdoor that should not exist in production-capable software.

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Real-environment reproduction confirms complete auth bypass when OSTWIN_API_KEY=DEBUG; hardcoded backdoor with zero guardrails in dashboard/auth.py:78-81, downgraded from CRITICAL to HIGH due to non-default configuration precondition.
Severity-Final: HIGH
PoC-Status: executed
```
