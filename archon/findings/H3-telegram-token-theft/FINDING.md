# H3 — Telegram Bot Token Theft

| Field | Value |
|---|---|
| ID | H3 |
| Severity | HIGH |
| CWE | CWE-306: Missing Authentication for Critical Function |
| Phase | 8 |
| Draft | security/findings-draft/p8-022-telegram-token-theft.md |
| PoC-Status | executed |
| Affected File | dashboard/routes/system.py:148-150 |

## Description

The `GET /api/telegram/config` endpoint returns the Telegram bot token and chat ID without any authentication check. The endpoint definition contains no `Depends(get_current_user)` decorator, unlike seven neighboring endpoints in the same file that are properly protected.

```python
# system.py:148-150 — no auth
@router.get("/telegram/config")
async def get_telegram_config():
    return telegram_bot.get_config()

# system.py:71 — protected (contrast)
@router.get("/status")
async def get_status(user: dict = Depends(get_current_user)):
    ...
```

The dashboard binds to `0.0.0.0:9000` and CORS is configured as `allow_origins=["*"]`, making the token reachable from any network client or cross-origin web page.

## Attacker Starting Position

No authentication required. Any client with network access to port 9000.

## Impact

- Telegram bot token exfiltrated without credentials
- Full bot impersonation: attacker can send messages as the bot, read chat history, and intercept all notifications via the Telegram Bot API
- Social engineering: attacker can send phishing content from the trusted bot identity to all subscribers
- Combined with H4 (config overwrite), enables complete notification system takeover

## Reproduction Steps

1. Start the dashboard: `python dashboard/api.py`
2. From any host on the network:
   ```
   curl http://<host>:9000/api/telegram/config
   ```
3. Response contains `{"bot_token": "<token>", "chat_id": "<id>"}`.
4. Verify bot access:
   ```
   curl https://api.telegram.org/bot<token>/getMe
   ```

## Evidence

- `system.py:148-150`: no `Depends(get_current_user)` on `get_telegram_config`
- Cold verification (commit 4c06f66): `GET /api/status` returned 401 (auth working); `GET /api/telegram/config` returned 200 with full credentials — same server, same key configuration
- `api.py:108-113`: `allow_origins=["*"]` enables cross-origin token theft from a malicious web page

## Remediation

1. Add `user: dict = Depends(get_current_user)` to `get_telegram_config`.
2. Redact the `bot_token` in the response — return only the last 4 characters for display purposes.
3. Store the bot token in the server-side environment only; never return it to the client API.
4. Audit all `/api/telegram/*` endpoints — `POST /api/telegram/config` and `POST /api/telegram/test` are also unauthenticated (H4).
