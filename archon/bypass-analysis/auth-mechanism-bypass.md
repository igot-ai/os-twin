# Authentication Mechanism Bypass Analysis

**Cluster ID**: auth-mechanism  
**Bypass verdict**: bypassable  
**Undisclosed tag**: [undisclosed]

---

## Finding 1: Empty API Key Means No Login Possible, But Unauthenticated Endpoints Still Exposed

**File**: `dashboard/auth.py:23`, `dashboard/routes/auth.py:8`

When `OSTWIN_API_KEY` is not set, `_API_KEY` defaults to `""`. The login endpoint (`/api/auth/token`) rejects all attempts (line 29: `if not key or not _API_KEY`), so no valid session can be created. However, this is not the default-open bypass initially suspected -- the empty string case is handled correctly for authenticated endpoints (line 90: `not _API_KEY` returns 401).

**Verdict**: sound for the empty-key case.

---

## Finding 2: DEBUG Bypass Disables All Authentication

**File**: `dashboard/auth.py:79`

```python
if _API_KEY == "DEBUG":
    username = request.headers.get("x-user", "debug-user")
    return {"username": username}
```

When `OSTWIN_API_KEY=DEBUG`, all authentication is skipped. An attacker who can set an `X-User` header can also impersonate any username. This is intentional for development but is a critical risk if deployed with this value.

**Risk**: If any deployment guide, docker-compose, or `.env.example` sets this value, production systems could be fully unauthenticated.

**Bypass verdict**: bypassable (conditional on configuration)

---

## Finding 3: API Key Leaked in Login Response Body

**File**: `dashboard/routes/auth.py:43-44`

```python
response = JSONResponse(content={
    "access_token": _API_KEY,
```

The raw API key is returned in the JSON response as `access_token`. This means:
- The key appears in browser devtools network tab, JS memory, and any logging middleware
- The key is also set as a cookie (line 49), so returning it in the body provides no additional functionality -- only additional exposure

**Bypass verdict**: relocated (secret exposure moved from server-only to client-visible)

---

## Finding 4: Cookie Missing `secure` Flag

**File**: `dashboard/routes/auth.py:48-55`

```python
response.set_cookie(
    key=AUTH_COOKIE_NAME,
    value=_API_KEY,
    httponly=True,
    samesite="lax",
    max_age=60 * 60 * 24 * 30,
    path="/",
)
```

The cookie has `httponly=True` and `samesite="lax"` (good), but is **missing `secure=True`**. Over HTTP, the raw API key cookie is transmitted in plaintext, enabling network-level interception.

**Bypass verdict**: bypassable (over HTTP connections)

---

## Finding 5: Cookie Value Is the Raw API Key (No Session Token)

The cookie value is the literal `_API_KEY`. There is no session management -- no rotation, no expiry-independent-of-cookie, no revocation mechanism. Compromise of the key means permanent access until the environment variable is changed and the process restarted. The 30-day `max_age` is irrelevant since the key itself never changes.

**Bypass verdict**: bypassable (no session revocation possible)

---

## Finding 6: Telegram Config Endpoints Have No Authentication

**File**: `dashboard/routes/system.py:148-164`

```python
@router.get("/telegram/config")
async def get_telegram_config():
    return telegram_bot.get_config()

@router.post("/telegram/config")
async def save_telegram_config(config: TelegramConfigRequest):

@router.post("/telegram/test")
async def test_telegram_connection():
```

All three Telegram endpoints lack `user: dict = Depends(get_current_user)`. Any unauthenticated request can:
- **Read** the bot token and chat ID via `GET /api/telegram/config`
- **Overwrite** the bot token via `POST /api/telegram/config` (redirect notifications to attacker-controlled bot)
- **Send arbitrary messages** via `POST /api/telegram/test`

Compare with other endpoints in the same file (e.g., `/api/status`, `/api/config`) which all use `Depends(get_current_user)`.

**Bypass verdict**: bypassable (no auth required)

---

## Finding 7: Unauthenticated Shell Command Execution

**File**: `dashboard/routes/system.py:166-169`

```python
@router.post("/shell")
async def shell_command(command: str):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
```

This endpoint has **no authentication** and executes arbitrary shell commands. This is a critical unauthenticated RCE.

**Bypass verdict**: bypassable (no auth, arbitrary command execution)

---

## Finding 8: Additional Unauthenticated Endpoints

**File**: `dashboard/routes/system.py:171-196`

`/api/run_pytest_auth` and `/api/test_ws` also lack `Depends(get_current_user)`.

**Bypass verdict**: bypassable

---

## Finding 9: Vault Hardcoded Encryption Key

**File**: `.agents/mcp/vault.py:117`

```python
return base64.urlsafe_b64encode(b"ostwin-default-insecure-key-32ch")
```

When `OSTWIN_VAULT_KEY` is not set (the default), the fallback key is deterministic and publicly known from source code. Any attacker with read access to `~/.ostwin/mcp/.vault.enc` can decrypt all stored secrets. On non-macOS systems (where `EncryptedFileVault` is used instead of macOS Keychain), this is the default path.

Additionally, when `cryptography` is not installed (`CRYPTOGRAPHY_AVAILABLE = False`), the vault falls back to **plaintext JSON** storage (lines 142-145).

**Bypass verdict**: bypassable (known key on non-macOS, plaintext fallback without cryptography package)

---

## Finding 10: `verify_password` Always Returns True

**File**: `dashboard/auth.py:29-30`

```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return True
```

While this function does not appear to be called in the current auth flow (API-key based), if any future code or plugin calls `verify_password`, it will accept any password.

**Bypass verdict**: bypassable (dormant, activates if called)

---

## Summary Table

| # | Issue | Severity | Verdict |
|---|-------|----------|---------|
| 1 | Empty API key handling | Low | sound |
| 2 | DEBUG bypass | Critical | bypassable |
| 3 | API key in response body | Medium | relocated |
| 4 | Cookie missing `secure` flag | Medium | bypassable |
| 5 | No session management | Medium | bypassable |
| 6 | Telegram endpoints unauthed | High | bypassable |
| 7 | Unauthenticated RCE via /shell | Critical | bypassable |
| 8 | Test endpoints unauthed | Low | bypassable |
| 9 | Vault hardcoded key | High | bypassable |
| 10 | verify_password always true | Low | bypassable (dormant) |
