# H4 — Telegram Config Overwrite

| Field | Value |
|---|---|
| ID | H4 |
| Severity | HIGH |
| CWE | CWE-306: Missing Authentication for Critical Function |
| Phase | 8 |
| Draft | security/findings-draft/p8-023-telegram-config-overwrite.md |
| PoC-Status | executed |
| Affected File | dashboard/routes/system.py:152-157, 159-164 |

## Description

The `POST /api/telegram/config` endpoint allows any unauthenticated client to overwrite the Telegram bot token and chat ID with arbitrary values. The write goes directly to `telegram_config.json` on disk (via `telegram_bot.save_config()`), persisting across server restarts. The `POST /api/telegram/test` endpoint (lines 159-164) is also unauthenticated, allowing an attacker to trigger message delivery through whatever bot is currently configured.

```python
# system.py:152-157 — no auth
@router.post("/telegram/config")
async def save_telegram_config(config: TelegramConfigRequest):
    success = telegram_bot.save_config(config.bot_token, config.chat_id)
    ...

# system.py:159-164 — no auth
@router.post("/telegram/test")
async def test_telegram_connection():
    success = await telegram_bot.send_message("Test message from OS Twin!")
```

## Attacker Starting Position

No authentication required. Any network client or cross-origin web page.

## Impact

- All system notifications permanently re-routed to attacker's Telegram chat
- Legitimate operator loses all alerting (monitoring blackout)
- Attacker receives real-time operational intelligence: plan events, war-room status changes, errors, agent activity
- Persistent: change survives server restarts
- Chain with H3: read the existing token, then overwrite — full notification hijack in two unauthenticated requests

## Reproduction Steps

1. Read current config (H3):
   ```
   curl http://<host>:9000/api/telegram/config
   ```
2. Overwrite with attacker bot:
   ```
   curl -X POST http://<host>:9000/api/telegram/config \
     -H "Content-Type: application/json" \
     -d '{"bot_token":"<attacker-token>","chat_id":"<attacker-chat-id>"}'
   ```
3. Confirm overwrite persisted (read back config — returns attacker values).
4. All subsequent Telegram notifications are delivered to the attacker.

## Evidence

- `system.py:152-157`: no `Depends(get_current_user)` on `save_telegram_config`
- `system.py:154`: `telegram_bot.save_config(config.bot_token, config.chat_id)` — direct overwrite, no ownership validation
- Cold verification: unauthenticated POST returned HTTP 200; subsequent GET confirmed config was overwritten with supplied values
- `system.py:159-164`: `test_telegram_connection` also unauthenticated (can trigger message sending without auth)

## Remediation

1. Add `user: dict = Depends(get_current_user)` to `save_telegram_config` and `test_telegram_connection`.
2. Consider a write-once configuration model: require current token verification before overwrite.
3. Log all configuration changes with timestamp and source IP.
4. Batch-fix all three Telegram endpoints in the same PR (H3 + H4).
