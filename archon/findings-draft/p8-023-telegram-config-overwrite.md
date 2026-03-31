Phase: 8
Sequence: 023
Slug: telegram-config-overwrite
Verdict: VALID
Rationale: Unauthenticated endpoint allows any network client to overwrite Telegram notification configuration, redirecting all system alerts to an attacker-controlled bot and silencing legitimate monitoring.
Severity-Original: HIGH
PoC-Status: executed
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-B/debate.md

## Summary

The `POST /api/telegram/config` endpoint (system.py:152-157) allows any unauthenticated client to overwrite the Telegram bot configuration with attacker-controlled values. This redirects all system notifications to the attacker's Telegram bot and chat, silencing legitimate monitoring. The `POST /api/telegram/test` endpoint (system.py:159-164) is also unauthenticated, allowing arbitrary message sending via the configured bot.

## Location

- **Write endpoint**: `dashboard/routes/system.py:152-157` -- `save_telegram_config()` with no auth
- **Test endpoint**: `dashboard/routes/system.py:159-164` -- `test_telegram_connection()` with no auth
- **Config storage**: `telegram_bot.save_config()` writes to `telegram_config.json`

## Attacker Control

Full control over `bot_token` and `chat_id` fields. Pydantic validates types only (both are strings). No format validation, no ownership verification.

## Trust Boundary Crossed

Network boundary. Unauthenticated network client can modify persistent server configuration.

## Impact

- All system notifications redirected to attacker (real-time operational intelligence)
- Legitimate owner loses all alerting capability
- Attacker receives notifications about plans, rooms, errors, and agent activity
- Persistent: survives server restarts (written to config file)
- Combined with H-03: attacker first reads existing config, then overwrites

## Evidence

1. `system.py:152-157` -- POST endpoint with no auth decorator
2. `system.py:154` -- `telegram_bot.save_config(config.bot_token, config.chat_id)` -- direct overwrite
3. `system.py:159-164` -- test endpoint also unauthenticated
4. Probe PH-04 validated this path

## Reproduction Steps

1. Start the dashboard: `python api.py`
2. Read current config: `curl http://<host>:9000/api/telegram/config`
3. Overwrite with attacker values: `curl -X POST http://<host>:9000/api/telegram/config -H "Content-Type: application/json" -d '{"bot_token":"<attacker-bot-token>","chat_id":"<attacker-chat-id>"}'`
4. Trigger a notification event and verify it arrives at the attacker's Telegram chat
5. Verify the legitimate owner no longer receives notifications

## Cold Verification

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Unauthenticated POST /api/telegram/config overwrites persistent config; reproduced in live environment with auth confirmed working on adjacent endpoints.
Severity-Final: HIGH
PoC-Status: executed
```

**Independent code trace confirmed:** `system.py:152-157` defines `save_telegram_config()` with no `Depends(get_current_user)`. `telegram_bot.save_config()` writes directly to `telegram_config.json` with no validation. 7 other endpoints in the same file are protected. `POST /api/telegram/test` (lines 159-164) is also unprotected.

**Reproduction:** Server started at commit 4c06f66 with `OSTWIN_API_KEY` set. Unauthenticated POST with attacker values returned HTTP 200. Subsequent GET confirmed the config was overwritten with attacker values. The change persists to disk.

**Full review:** `security/adversarial-reviews/telegram-config-overwrite-review.md`
