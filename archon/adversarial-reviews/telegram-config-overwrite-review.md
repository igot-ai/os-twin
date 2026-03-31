# Adversarial Review: telegram-config-overwrite (p8-023)

## Step 1 -- Restate and Decompose

**Restated claim:** The application allows any unauthenticated network client to replace the Telegram notification configuration (bot token and chat ID) via a POST request, persisting the change to disk. This redirects all future system notifications to an attacker-controlled Telegram bot and silences legitimate monitoring. A second unauthenticated endpoint also allows sending arbitrary messages through the configured bot.

**Sub-claims:**

- **Sub-claim A:** Any network client can issue POST /api/telegram/config without authentication.
- **Sub-claim B:** The endpoint writes attacker-supplied bot_token and chat_id to telegram_config.json, overwriting legitimate values.
- **Sub-claim C:** All subsequent notifications use the overwritten config, redirecting alerts to the attacker.

All sub-claims are coherent and testable.

## Step 2 -- Independent Code Path Trace

Traced from source at commit 4c06f66:

1. `system.py:152-157` defines `POST /api/telegram/config` with signature `async def save_telegram_config(config: TelegramConfigRequest)` -- **no** `Depends(get_current_user)`.
2. The function calls `telegram_bot.save_config(config.bot_token, config.chat_id)`.
3. `telegram_bot.py:26-32` -- `save_config()` writes `{"bot_token": bot_token, "chat_id": chat_id}` directly to `telegram_config.json` with no validation beyond Pydantic string type checking.
4. `telegram_bot.py:35-60` -- `send_message()` reads from the same config file, so any future notification uses the overwritten values.
5. `system.py:159-164` defines `POST /api/telegram/test` also without auth, allowing arbitrary message sending.

**Validation on path:** Pydantic `TelegramConfigRequest` validates types only (both fields are strings). No format validation on bot_token, no ownership verification.

## Step 3 -- Protection Surface Search

| Layer | Control Found | Blocks Attack? |
|-------|--------------|---------------|
| Framework | `Depends(get_current_user)` auth dependency | NOT applied to POST endpoints |
| Framework | Pydantic model validation | Type check only (string) -- does not block |
| Middleware | CORS `allow_origins=["*"]` | Permits cross-origin POST -- amplifies |
| Application | No rate limiting, no ownership verification | None |
| Persistence | Config written to disk file | Survives restarts -- amplifies impact |

No protection blocks the attack.

## Step 4 -- Real-Environment Reproduction

- **Environment:** macOS Darwin 25.3.0, Python3 with FastAPI/uvicorn, commit 4c06f66
- **Healthcheck:** `GET /api/status` returns 401 without auth (auth system working)
- **Attempt 1:** `curl -X POST http://127.0.0.1:19022/api/telegram/config -H "Content-Type: application/json" -d '{"bot_token":"ATTACKER_TOKEN_123","chat_id":"ATTACKER_CHAT_456"}'` -- HTTP 200, `{"status":"success"}`
- **Verification:** Subsequent GET returned the attacker values, confirming persistent overwrite.
- **Result:** REPRODUCED on first attempt.

Evidence stored at: `security/real-env-evidence/telegram-config-overwrite/reproduction.txt`

## Step 5 -- Prosecution and Defense Briefs

### Prosecution Brief

The vulnerability is genuine and trivially exploitable. `system.py:152-157` accepts unauthenticated POST requests that directly overwrite persistent configuration via `telegram_bot.save_config()`. The overwrite is permanent (survives restarts). The same router file protects 7 other endpoints with `Depends(get_current_user)`, proving this is an omission. Reproduction confirmed: unauthenticated POST successfully replaced the bot configuration. The `/api/telegram/test` endpoint (lines 159-164) is also unprotected, allowing message injection through the configured (or attacker-supplied) bot.

### Defense Brief

The impact requires that: (1) the application actually sends Telegram notifications (feature must be in use), and (2) the attacker can reach port 9000. This is a developer/operations tool likely used on trusted networks. However, the 0.0.0.0 binding and CORS wildcard suggest internet exposure was anticipated. The inconsistent auth pattern (protected vs unprotected endpoints in the same file) is strong evidence of oversight, not design.

## Step 6 -- Severity Challenge

Starting at MEDIUM:
- Remotely triggerable: YES (unauthenticated POST, network accessible)
- Trust boundary crossing: YES (network client modifies persistent server config)
- Significant preconditions: Telegram notifications must be in use (reasonable for users of this feature)
- Impact: Notification hijacking + monitoring blindness (not RCE, not data exfil of user data)

Upgrade to HIGH: Justified. Unauthenticated persistent configuration overwrite affecting operational monitoring integrity.

Severity-Original (HIGH) matches challenged severity.

## Step 7 -- Verdict

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Unauthenticated POST /api/telegram/config overwrites persistent config; reproduced in live environment with auth confirmed working on adjacent endpoints.
Severity-Final: HIGH
PoC-Status: executed
```
