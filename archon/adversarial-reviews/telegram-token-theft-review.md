# Adversarial Review: telegram-token-theft (p8-022)

## Step 1 -- Restate and Decompose

**Restated claim:** The application exposes an HTTP endpoint that returns Telegram bot credentials (token and chat ID) to any caller without requiring authentication, while other endpoints on the same router do enforce authentication. Combined with a wildcard CORS policy and binding to all network interfaces, this makes the credentials accessible to any network client or cross-origin web page.

**Sub-claims:**

- **Sub-claim A:** Any network client can reach `GET /api/telegram/config` without authentication.
- **Sub-claim B:** The endpoint returns the raw bot_token and chat_id from the configuration file.
- **Sub-claim C:** Possession of the bot token allows full impersonation of the Telegram bot.

All sub-claims are coherent and testable.

## Step 2 -- Independent Code Path Trace

Traced from source at commit 4c06f66:

1. `dashboard/api.py:121` includes `system.router` into the FastAPI app.
2. `dashboard/routes/system.py:21` defines `router = APIRouter(prefix="/api")`.
3. `system.py:148-150` defines `GET /api/telegram/config` -- the function signature is `async def get_telegram_config()` with **no** `Depends(get_current_user)` parameter.
4. The function calls `telegram_bot.get_config()` which reads `telegram_config.json` and returns `{"bot_token": "...", "chat_id": "..."}` verbatim.
5. Compare with `system.py:71` (`get_status`) which has `user: dict = Depends(get_current_user)` -- proving the auth mechanism exists and works.

**Validation/sanitization on path:** None. No auth check, no rate limit, no IP filter.

**Framework protections:** FastAPI's `Depends(get_current_user)` is the auth mechanism, but it is simply not applied to this endpoint.

## Step 3 -- Protection Surface Search

| Layer | Control Found | Blocks Attack? |
|-------|--------------|---------------|
| Framework | `Depends(get_current_user)` auth dependency | NOT applied to this endpoint |
| Middleware | CORS `allow_origins=["*"]` | Permits cross-origin access -- amplifies rather than blocks |
| Application | No rate limiting, no IP allowlist | None |
| Network | `host="0.0.0.0"` binding | Exposes to all interfaces -- amplifies |
| Documentation | No SECURITY.md addressing this | N/A |

No protection blocks the attack.

## Step 4 -- Real-Environment Reproduction

- **Environment:** macOS Darwin 25.3.0, Python3 with FastAPI/uvicorn, commit 4c06f66
- **Healthcheck:** `GET /api/status` returns 401 without auth (auth system working)
- **Attempt 1:** `curl http://127.0.0.1:19022/api/telegram/config` -- HTTP 200, returned `{"bot_token":"test_token","chat_id":"test_chat"}`
- **Result:** REPRODUCED on first attempt.

Evidence stored at: `security/real-env-evidence/telegram-token-theft/reproduction.txt`

## Step 5 -- Prosecution and Defense Briefs

### Prosecution Brief

The vulnerability is genuine and trivially exploitable. The code at `system.py:148-150` defines an endpoint with no authentication dependency. The same file contains multiple endpoints (lines 71, 87, 111, 117, 132, 140) that DO use `Depends(get_current_user)`, proving this is an omission not a design choice. The `telegram_bot.get_config()` function at `telegram_bot.py:16-24` returns the raw bot token without redaction. CORS wildcard at `api.py:108-113` allows any web page to exfiltrate the token. Reproduction confirmed: unauthenticated GET returns the full token.

### Defense Brief

The severity depends on whether the Telegram bot token is configured. If `telegram_config.json` does not exist, the endpoint returns empty strings. Additionally, this is a developer/operations dashboard (OS Twin), likely intended for trusted network use. The default bind to 0.0.0.0 could be considered an intentional convenience for LAN access. However, no documentation marks this as an accepted risk, and the inconsistent auth application (some endpoints protected, some not) indicates an oversight rather than design.

## Step 6 -- Severity Challenge

Starting at MEDIUM:
- Remotely triggerable: YES (network accessible, no auth required)
- Trust boundary crossing: YES (network to credential disclosure)
- Significant preconditions: Telegram must be configured (reasonable assumption for users of this feature)
- Not RCE/full auth bypass, but credential theft of an external service

Upgrade to HIGH: Justified. Remotely triggerable credential disclosure with no preconditions beyond feature configuration.

Severity-Original (HIGH) matches challenged severity.

## Step 7 -- Verdict

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Unauthenticated GET /api/telegram/config returns raw bot token; reproduced in live environment with auth working on other endpoints.
Severity-Final: HIGH
PoC-Status: executed
```
