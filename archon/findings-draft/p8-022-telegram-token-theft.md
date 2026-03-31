Phase: 8
Sequence: 022
Slug: telegram-token-theft
Verdict: VALID
Rationale: Unauthenticated network-accessible endpoint returns Telegram bot token, enabling full bot impersonation; no authentication, no rate limiting, no access control at any layer.
Severity-Original: HIGH
PoC-Status: executed
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-B/debate.md

## Summary

The `GET /api/telegram/config` endpoint (system.py:148-150) returns the Telegram bot token and chat ID without any authentication. The dashboard binds to `0.0.0.0:9000` with CORS `allow_origins=["*"]`, making this accessible from any network client or cross-origin web page. An attacker who obtains the bot token can fully impersonate the Telegram bot: read chat history, send messages to users, and receive all notifications.

## Location

- **Endpoint**: `dashboard/routes/system.py:148-150` -- `get_telegram_config()` with no auth
- **Compare**: `system.py:71` -- `get_status()` HAS `Depends(get_current_user)`
- **CORS**: `dashboard/api.py:108-113` -- `allow_origins=["*"]`
- **Binding**: `dashboard/api.py:230` -- `host="0.0.0.0"` (all interfaces)

## Attacker Control

No attacker input required beyond a simple GET request. The endpoint returns credentials unconditionally.

## Trust Boundary Crossed

Network boundary. Any client on the network (or any web page via CORS wildcard) can retrieve the bot token without authentication.

## Impact

- Full Telegram bot impersonation (send/receive messages as the bot)
- Access to chat history and notification content
- Social engineering vector (send phishing messages from trusted bot identity)
- Combined with H-04, enables complete notification system takeover

## Evidence

1. `system.py:148-150` -- endpoint definition with no `Depends(get_current_user)`
2. `system.py:71` -- nearby endpoint that DOES use auth (proves auth mechanism exists but was not applied)
3. `api.py:108-113` -- CORS wildcard configuration
4. Probe PH-03 validated this path end-to-end

## Reproduction Steps

1. Start the dashboard: `python api.py`
2. From any machine on the network: `curl http://<host>:9000/api/telegram/config`
3. Observe the response contains `{"bot_token": "...", "chat_id": "..."}`
4. Use the token with the Telegram Bot API: `curl https://api.telegram.org/bot<token>/getMe`
5. Confirm bot identity and access

## Cold Verification

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Unauthenticated GET /api/telegram/config returns raw bot token; reproduced in live environment with auth working on other endpoints.
Severity-Final: HIGH
PoC-Status: executed
```

**Independent code trace confirmed:** `system.py:148-150` defines `get_telegram_config()` with no `Depends(get_current_user)` while 7 other endpoints in the same file use it. `telegram_bot.get_config()` returns the raw bot_token without redaction. CORS wildcard and 0.0.0.0 binding amplify exposure.

**Reproduction:** Server started at commit 4c06f66 with `OSTWIN_API_KEY` set. `GET /api/status` correctly returned 401 (auth working). `GET /api/telegram/config` returned HTTP 200 with full credentials. No protection found at any layer.

**Full review:** `security/adversarial-reviews/telegram-token-theft-review.md`
