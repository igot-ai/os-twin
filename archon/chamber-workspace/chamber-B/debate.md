# Review Chamber: chamber-B

Cluster: Data/Credential Exposure
DFD Slices: DFD-5, DFD-7, DFD-8
NNN Range: 020-039
Started: 2026-03-30T10:00:00Z
Status: CLOSED

---

## Round 1 -- Ideation

### [IDEATOR] Hypotheses -- 2026-03-30T10:01:00Z

Based on the threat cluster scope (credential theft, information disclosure, crypto weaknesses) and pre-validated deep probe results, the following hypotheses are generated. Pre-seeded hypotheses from deep probes are marked with their source.

#### H-01: Vault Decryption via Hardcoded Default Key (from PH-04/PH-20, SAST-005)
- **Target**: `.agents/mcp/vault.py:117` -- hardcoded `ostwin-default-insecure-key-32ch`
- **Attack**: On non-macOS systems, read `~/.ostwin/mcp/.vault.enc` (world-readable, default umask) and decrypt with the publicly known key using `Fernet(base64.urlsafe_b64encode(b"ostwin-default-insecure-key-32ch"))`
- **Impact**: All stored MCP API keys and service credentials exposed to any local user
- **Severity estimate**: HIGH (CWE-321)

#### H-02: Vault Plaintext Fallback When cryptography Absent (from PH-05)
- **Target**: `.agents/mcp/vault.py:131-132,143-145` -- plaintext JSON read/write path
- **Attack**: On systems where `cryptography` is not installed (it is NOT in requirements.txt), vault is stored/read as plaintext JSON at `~/.ostwin/mcp/.vault.enc`
- **Impact**: Zero cryptographic barrier; any process with file read access obtains all secrets
- **Severity estimate**: HIGH (CWE-312)

#### H-03: Telegram Bot Token Theft via Unauthenticated GET /api/telegram/config (from PH-03, SAST-008)
- **Target**: `dashboard/routes/system.py:148-150` -- no auth decorator on `get_telegram_config`
- **Attack**: `GET /api/telegram/config` returns `bot_token` and `chat_id` without authentication
- **Impact**: Bot token theft enables Telegram bot impersonation, reading chat history, sending messages
- **Severity estimate**: HIGH (CWE-306)

#### H-04: Telegram Config Overwrite -- Notification Hijacking (from PH-04, SAST-008)
- **Target**: `dashboard/routes/system.py:152-157` -- no auth on `save_telegram_config`
- **Attack**: `POST /api/telegram/config` with attacker-controlled `bot_token` and `chat_id`
- **Impact**: All system notifications redirected to attacker; legitimate monitoring disabled
- **Severity estimate**: HIGH (CWE-306)

#### H-05: Raw API Key Returned in Login JSON Response (from PH-13, SAST-009)
- **Target**: `dashboard/routes/auth.py:43-44` -- `JSONResponse(content={"access_token": _API_KEY, ...})`
- **Attack**: Observe login response in browser devtools, proxy logs, or server logs; XSS chain (CV-11) can fetch and exfiltrate the response
- **Impact**: Permanent API key exposed in transport/logs; never rotates; 30-day session
- **Severity estimate**: HIGH (CWE-200)

#### H-06: fe_catch_all Path Traversal -- Arbitrary File Read (from PH-17, SAST-014a)
- **Target**: `dashboard/api.py:147-151` -- `FE_OUT_DIR / path` with no containment check
- **Attack**: `GET /../../dashboard/auth.py` when FE_OUT_DIR exists (production)
- **Impact**: Read any file the server process can access: source code, .env, /etc/passwd
- **Severity estimate**: HIGH (CWE-22) -- conditional on production deployment with built frontend

#### H-07: Env File Newline Injection to Persist DEBUG Auth Bypass (from PH-07/PH-08)
- **Target**: `dashboard/routes/system.py:65` -- `_serialize_env` has no newline sanitization
- **Attack**: Authenticated `POST /api/env` with `{"entries": [{"type":"var","key":"SAFE","value":"x\nOSTWIN_API_KEY=DEBUG","enabled":true}]}`
- **Impact**: On next restart, `OSTWIN_API_KEY=DEBUG` activates, disabling all authentication permanently
- **Severity estimate**: HIGH (CWE-93) -- requires initial auth or DEBUG mode

---

## Round 2 -- Tracing

### [TRACER] Evidence for H-01 through H-07 -- 2026-03-30T10:10:00Z

#### H-01 Trace: Vault Hardcoded Key

**Entry point**: `.agents/mcp/vault.py:106-117` -- `_get_encryption_key()`

**Code path**:
1. `vault.py:168-173` -- `get_vault()`: on non-macOS (`sys.platform != "darwin"`), returns `EncryptedFileVault(Path.home() / ".ostwin" / "mcp" / ".vault.enc")`
2. `vault.py:103` -- `self.key = self._get_encryption_key()`
3. `vault.py:107` -- checks `OSTWIN_VAULT_KEY` env var. If absent (default), falls through to line 117
4. `vault.py:117` -- `return base64.urlsafe_b64encode(b"ostwin-default-insecure-key-32ch")` -- HARDCODED, PUBLIC
5. `vault.py:136-142` -- `_save_data()`: `self.fernet.encrypt(json_data)` then `f.write(encrypted_data)` -- NO chmod, NO umask override
6. Default umask on most Linux = 0022 => file created 0644 (world-readable)

**Attacker control**: Attacker needs only local file read access (any OS user). Key is embedded in public source code.

**Data confirmed in vault**: MCP server API keys/tokens (GitHub, Slack, other service credentials) stored via `vault.set(server, key, value)`.

**Verdict**: REACHABLE. Path confirmed from vault creation through hardcoded key to world-readable file.

---

#### H-02 Trace: Vault Plaintext Fallback

**Entry point**: `.agents/mcp/vault.py:10-16` -- conditional import

**Code path**:
1. `vault.py:10-16` -- `try: from cryptography.fernet import Fernet ... except ImportError: CRYPTOGRAPHY_AVAILABLE = False`
2. `vault.py:104` -- `self.fernet = Fernet(self.key) if CRYPTOGRAPHY_AVAILABLE else None`
3. `vault.py:143-145` -- `_save_data()`: when `self.fernet` is None, writes `f.write(json_data)` (raw JSON)
4. `vault.py:131-132` -- `_load_data()`: when fernet is None, `json.loads(encrypted_data)` (reads raw JSON)

**Dependency check**: `.agents/mcp/requirements.txt` does NOT list `cryptography`. It may be a transitive dependency but is not guaranteed.

**Verdict**: REACHABLE. When cryptography is absent, vault is stored as plaintext JSON. Combined with default umask, any local user reads all secrets in clear.

---

#### H-03 Trace: Telegram Config Unauthenticated Read

**Entry point**: `dashboard/routes/system.py:148-150`

**Code path**:
1. `system.py:148` -- `@router.get("/telegram/config")` -- NO `Depends(get_current_user)` in signature
2. `system.py:149` -- `async def get_telegram_config():` -- no auth parameter
3. `system.py:150` -- `return telegram_bot.get_config()` -- returns full config including bot_token and chat_id

**Compare with authenticated endpoints**: `get_status()` at line 71 has `user: dict = Depends(get_current_user)`. Telegram endpoints at lines 148-164 do NOT.

**Network reachability**: Dashboard binds to `0.0.0.0:9000` (api.py:230). CORS wildcard allows cross-origin requests.

**Verdict**: REACHABLE. Unauthenticated, network-accessible, returns credentials.

---

#### H-04 Trace: Telegram Config Overwrite

**Entry point**: `dashboard/routes/system.py:152-157`

**Code path**:
1. `system.py:152` -- `@router.post("/telegram/config")` -- NO auth
2. `system.py:153` -- `async def save_telegram_config(config: TelegramConfigRequest):` -- Pydantic validates types only (str, str)
3. `system.py:154` -- `telegram_bot.save_config(config.bot_token, config.chat_id)` -- overwrites config

**Additional**: `system.py:159-164` -- `POST /api/telegram/test` also unauthenticated, allows arbitrary message send via the bot.

**Verdict**: REACHABLE. Unauthenticated write to credential config.

---

#### H-05 Trace: API Key in Login Response

**Entry point**: `dashboard/routes/auth.py:42-47`

**Code path**:
1. `auth.py:43-47` -- After successful `secrets.compare_digest`, returns `JSONResponse(content={"access_token": _API_KEY, "token_type": "bearer", "username": "api-key-user"})`
2. `_API_KEY` is the raw, permanent OSTWIN API key from environment
3. `auth.py:48-55` -- Cookie also set with `value=_API_KEY` (httponly=True) -- but JSON body fully negates httponly protection

**Exposure vectors**:
- Browser DevTools Network tab (any user who logs in can copy the key)
- Server access logs if request/response logging is enabled
- Proxy/CDN logs
- XSS chain via CV-11 javascript: URI can `fetch('/api/auth/token', {method:'POST', body:...}).then(r=>r.json())` to extract

**Verdict**: REACHABLE. Raw permanent credential in response body.

---

#### H-06 Trace: fe_catch_all Path Traversal

**Entry point**: `dashboard/api.py:146-151`

**Code path**:
1. `api.py:146` -- `@app.api_route("/{path:path}", methods=["GET", "HEAD"])` -- FastAPI `{path:path}` converter passes `..` segments verbatim
2. `api.py:149` -- `exact = FE_OUT_DIR / path` -- Python `Path.__truediv__` does NOT normalize `..`
3. `api.py:150` -- `if exact.is_file(): return FileResponse(str(exact))` -- OS resolves `..` during stat/open
4. No containment check (e.g., `exact.resolve().is_relative_to(FE_OUT_DIR)`)

**Precondition**: `USE_FE` must be True (FE_OUT_DIR must exist). This is the production deployment path.

**Confirmed**: uvicorn does NOT normalize `..` in URL paths. Probe PH-17 verified this.

**Verdict**: REACHABLE (conditional on production deployment with built frontend). Path traversal confirmed.

---

#### H-07 Trace: Env File Newline Injection

**Entry point**: `dashboard/routes/system.py:254-270`

**Code path**:
1. `system.py:254` -- `@router.post("/env")` with `Depends(get_current_user)` -- REQUIRES AUTH
2. `system.py:261` -- `entries = request.get("entries", [])` -- accepts arbitrary entry dicts
3. `system.py:268` -- `content = _serialize_env(entries)` calls `_serialize_env`
4. `system.py:65` -- `lines.append(f"{key}={value}")` -- NO newline sanitization on key or value
5. `system.py:269` -- `_ENV_FILE.write_text(content)` -- writes to `~/.ostwin/.env`
6. On restart: `api.py:14-18` -- `load_dotenv(_env_file, override=False)` -- loads injected `OSTWIN_API_KEY=DEBUG`
7. `auth.py:79` -- `if _API_KEY == "DEBUG":` -- all auth bypassed

**Precondition**: Attacker must have valid API key (or exploit DEBUG mode already active).

**Verdict**: REACHABLE. Auth-gated but enables privilege escalation from authenticated user to permanent full auth bypass.

---

## Round 3 -- Challenge

### [ADVOCATE] Defense Briefs -- 2026-03-30T10:20:00Z

#### H-01 Defense: Vault Hardcoded Key

**Layer 1 -- Framework protection**: No relevant framework protection. Fernet is used correctly in mechanics but the key is hardcoded.

**Layer 2 -- Application-level check**: The code checks `OSTWIN_VAULT_KEY` env var first (vault.py:107-113). If set, the hardcoded key is NOT used.

**Layer 3 -- OS/platform protection**: On macOS (`sys.platform == "darwin"`), `MacOSKeychainVault` is used instead, which stores secrets in the system keychain. The hardcoded key path only applies on non-macOS.

**Layer 4 -- Network isolation**: This is a LOCAL privilege escalation. Requires file system access on the host.

**Layer 5 -- Configuration mitigation**: Users CAN set `OSTWIN_VAULT_KEY` to use a strong key.

**FP assessment**: NOT a false positive. The hardcoded key IS the default. Users who do not set `OSTWIN_VAULT_KEY` on non-macOS systems are vulnerable. The code comment at line 115 acknowledges it is "insecure". macOS users are protected by Keychain. Non-macOS users with default config are fully exposed.

**Blocking protection found**: PARTIAL -- macOS users protected; non-macOS with OSTWIN_VAULT_KEY set protected. Default non-macOS users are NOT protected.

---

#### H-02 Defense: Vault Plaintext Fallback

**Layer 1 -- Framework**: No protection.

**Layer 2 -- Application**: The code logs "NOT RECOMMENDED" in a comment (vault.py:131) but does NOT warn the user at runtime, does NOT refuse to start, and does NOT require explicit opt-in.

**Layer 3 -- Transitive dependency**: `cryptography` MAY be installed as a transitive dependency of `mcp[cli]` or other packages. However, it is NOT listed in requirements.txt.

**Layer 4 -- Local access required**: Same as H-01.

**Layer 5 -- Configuration**: No configuration option to force encryption or refuse plaintext.

**FP assessment**: NOT a false positive. The plaintext fallback is explicit production code, not a test path. The dependency gap is real.

**Blocking protection found**: NONE

---

#### H-03 Defense: Telegram Config Read

**Layer 1 -- Framework**: FastAPI `Depends()` is the auth mechanism. It is NOT applied to this endpoint.

**Layer 2 -- Application**: No auth check in the function body.

**Layer 3 -- Network**: Dashboard binds to `0.0.0.0:9000`. CORS `allow_origins=["*"]`. No WAF or reverse proxy assumed.

**Layer 4 -- Telegram-level**: Bot tokens can be revoked via @BotFather, but that is a recovery step, not a preventive control.

**Layer 5 -- Configuration**: No option to disable these endpoints.

**FP assessment**: NOT a false positive. Clear missing auth on credential-returning endpoint.

**Blocking protection found**: NONE

---

#### H-04 Defense: Telegram Config Overwrite

**Layer 1-5**: Same analysis as H-03. No auth, no validation beyond Pydantic type checking.

**Additional**: The overwrite is persistent (writes to JSON file). Recovery requires manual re-configuration.

**FP assessment**: NOT a false positive.

**Blocking protection found**: NONE

---

#### H-05 Defense: API Key in Login Response

**Layer 1 -- Framework**: FastAPI JSONResponse does not redact fields.

**Layer 2 -- Application**: `httponly=True` on cookie prevents JavaScript cookie access, BUT the same value is in the JSON body, fully negating that protection.

**Layer 3 -- Network**: If HTTPS is used, transport encryption protects the response body in transit. However, the key is still exposed in browser DevTools, server logs, and any client-side JavaScript.

**Layer 4 -- Key rotation**: The key DOES NOT rotate. It is static from environment load.

**Layer 5 -- Short-lived token alternative**: The code does NOT issue short-lived tokens. The raw permanent key IS the token.

**FP assessment**: NOT a false positive. The httponly cookie is deliberately set, suggesting the developer intended to protect the key from scripts. Returning it in JSON contradicts that intent.

**Blocking protection found**: NONE that blocks the exposure. httponly cookie is a PARTIAL mitigation that is negated by the JSON body.

---

#### H-06 Defense: fe_catch_all Path Traversal

**Layer 1 -- Framework**: FastAPI/Starlette does NOT normalize path parameters containing `..`. StaticFiles does have path containment, but fe_catch_all is a custom handler, not StaticFiles.

**Layer 2 -- Application**: No `is_relative_to()` or equivalent check.

**Layer 3 -- Uvicorn**: Does NOT normalize `..` in URL paths (confirmed by probe).

**Layer 4 -- Deployment**: Requires `USE_FE=True` (FE_OUT_DIR must exist). This is the production deployment scenario.

**Layer 5 -- Reverse proxy**: If behind nginx/caddy with path normalization, `..` may be stripped. However, this is an assumed external control, not an application-level protection.

**FP assessment**: NOT a false positive, but CONDITIONAL. The vulnerability is latent in development (FE_OUT_DIR does not exist) but active in production deployments.

**Blocking protection found**: NONE in application code. Potential external mitigation via reverse proxy (not guaranteed).

---

#### H-07 Defense: Env File Newline Injection

**Layer 1 -- Framework**: FastAPI parses JSON body correctly; no framework-level newline sanitization.

**Layer 2 -- Application**: `_serialize_env()` at system.py:52-68 has NO newline sanitization. Direct string formatting.

**Layer 3 -- Auth**: `Depends(get_current_user)` IS present on `POST /api/env`. Attacker needs valid API key.

**Layer 4 -- Restart required**: The injected value only takes effect on next server restart (`load_dotenv(override=False)` only sets vars not already in env).

**Layer 5 -- `override=False`**: If `OSTWIN_API_KEY` is already set in the process environment (e.g., via systemd, Docker), `load_dotenv(override=False)` will NOT override it. This is a significant mitigating factor for containerized deployments.

**FP assessment**: NOT a false positive, but with significant preconditions: (1) valid API key required, (2) server restart required, (3) OSTWIN_API_KEY must not be set via other env mechanism.

**Blocking protection found**: PARTIAL -- auth required + override=False behavior limits exploitation scenarios.

---

## Round 4 -- Synthesis

### [SYNTHESIZER] Verdicts -- 2026-03-30T10:30:00Z

---

### [SYNTHESIZER] Verdict for H-01 -- 2026-03-30T10:30:00Z

**Prosecution summary**: On non-macOS systems, `EncryptedFileVault` uses a hardcoded key `ostwin-default-insecure-key-32ch` (vault.py:117) when `OSTWIN_VAULT_KEY` is not set. The vault file at `~/.ostwin/mcp/.vault.enc` is created with default umask (world-readable). Any local user can read and decrypt all stored MCP credentials with the publicly known key.

**Defense summary**: macOS users are protected via Keychain. Users who set `OSTWIN_VAULT_KEY` are protected. However, the default non-macOS path is vulnerable, and the code comment acknowledges the insecurity.

**Pre-FP Gate**:
- Attacker control verified: Yes -- key is in public source code, file is world-readable
- Framework protection searched: Yes -- all 5 layers, none blocking
- Trust boundary crossing: Yes -- crosses user-to-user boundary on shared systems
- Normal attacker position: Yes -- any local OS user (not admin)
- Ships to production: Yes -- vault.py is production code

All checks passed.

**Verdict: VALID**
**Severity: HIGH**
**Rationale**: Hardcoded cryptographic key in production vault code with world-readable file permissions allows any local user to decrypt all stored MCP service credentials on non-macOS systems; macOS Keychain provides protection only for that platform.

**Finding draft written to**: security/findings-draft/p8-020-vault-hardcoded-key.md
**Registry updated**: AP-020 Hardcoded Cryptographic Key

---

### [SYNTHESIZER] Verdict for H-02 -- 2026-03-30T10:31:00Z

**Prosecution summary**: When `cryptography` package is not installed, vault falls back to plaintext JSON storage (vault.py:143-145). `cryptography` is NOT listed in `.agents/mcp/requirements.txt`, making plaintext the default for minimal installations.

**Defense summary**: No blocking protection found. The fallback is explicit code, not a test path. No runtime warning is emitted.

**Pre-FP Gate**: All checks passed.

**Verdict: VALID**
**Severity: HIGH**
**Rationale**: Vault stores credentials as plaintext JSON when cryptography package is absent, which is the default state per requirements.txt; combined with world-readable file permissions, any local process can read all stored secrets without any cryptographic barrier.

**Finding draft written to**: security/findings-draft/p8-021-vault-plaintext-fallback.md
**Registry updated**: AP-021 Silent Crypto Downgrade to Plaintext

---

### [SYNTHESIZER] Verdict for H-03 -- 2026-03-30T10:32:00Z

**Prosecution summary**: `GET /api/telegram/config` (system.py:148-150) has no authentication. Returns bot_token and chat_id. Dashboard binds to 0.0.0.0:9000 with CORS wildcard.

**Defense summary**: No blocking protection at any layer. Token revocation is a recovery action, not a preventive control.

**Pre-FP Gate**: All checks passed.

**Verdict: VALID**
**Severity: HIGH**
**Rationale**: Unauthenticated network-accessible endpoint returns Telegram bot token, enabling full bot impersonation; no authentication, no rate limiting, no access control at any layer.

**Finding draft written to**: security/findings-draft/p8-022-telegram-token-theft.md
**Registry updated**: AP-022 Missing Auth on Credential-Returning Endpoint

---

### [SYNTHESIZER] Verdict for H-04 -- 2026-03-30T10:33:00Z

**Prosecution summary**: `POST /api/telegram/config` (system.py:152-157) has no authentication. Overwrites bot_token and chat_id with attacker values. Persistent (written to JSON file).

**Defense summary**: No blocking protection found. Pydantic only validates types (str, str), not content.

**Pre-FP Gate**: All checks passed.

**Verdict: VALID**
**Severity: HIGH**
**Rationale**: Unauthenticated endpoint allows any network client to overwrite Telegram notification configuration, redirecting all system alerts to an attacker-controlled bot and silencing legitimate monitoring.

**Finding draft written to**: security/findings-draft/p8-023-telegram-config-overwrite.md
**Registry updated**: no new pattern (same as AP-022)

---

### [SYNTHESIZER] Verdict for H-05 -- 2026-03-30T10:34:00Z

**Prosecution summary**: `POST /api/auth/token` response includes `{"access_token": _API_KEY, ...}` (auth.py:43-44). The raw, permanent API key is exposed in the JSON response body, negating the httponly cookie protection.

**Defense summary**: httponly cookie is set but negated by JSON body. HTTPS protects in-transit only. Key never rotates.

**Pre-FP Gate**: All checks passed.

**Verdict: VALID**
**Severity: MEDIUM**
**Rationale**: The permanent API key is returned in the login JSON response body, exposing it in browser DevTools, proxy logs, and to XSS attacks, negating the httponly cookie protection; however, the exposure requires either network observation or an XSS chain, which moderates severity from HIGH to MEDIUM.

**Finding draft written to**: security/findings-draft/p8-024-api-key-in-login-response.md
**Registry updated**: AP-024 Credential in Response Body

---

### [SYNTHESIZER] Verdict for H-06 -- 2026-03-30T10:35:00Z

**Prosecution summary**: `fe_catch_all` (api.py:147-151) constructs file paths from user input via `FE_OUT_DIR / path` with no containment check. `..` segments pass through FastAPI's `{path:path}` converter and uvicorn without normalization. When FE_OUT_DIR exists (production), any file readable by the server process is exposed.

**Defense summary**: Only active when FE_OUT_DIR exists (production with built frontend). A reverse proxy could normalize paths, but this is an external assumption. No application-level protection exists.

**Pre-FP Gate**: All checks passed. Conditional on production deployment but that IS the intended deployment model.

**Verdict: VALID**
**Severity: HIGH**
**Rationale**: Path traversal in the static file catch-all handler allows unauthenticated reading of arbitrary server files in production deployments; no application-level path containment exists, and the vulnerability is confirmed reachable through uvicorn's lack of path normalization.

**Finding draft written to**: security/findings-draft/p8-025-fe-catch-all-path-traversal.md
**Registry updated**: AP-025 Path Traversal in Custom Static File Handler

---

### [SYNTHESIZER] Verdict for H-07 -- 2026-03-30T10:36:00Z

**Prosecution summary**: `_serialize_env()` (system.py:65) has no newline sanitization. An authenticated attacker can inject `OSTWIN_API_KEY=DEBUG` into the .env file via `POST /api/env`. On restart, `load_dotenv(override=False)` loads the injected value, permanently disabling all authentication.

**Defense summary**: Requires valid API key (auth-gated). Requires server restart. `load_dotenv(override=False)` does not override existing env vars set via other mechanisms (Docker, systemd).

**Pre-FP Gate**:
- Attacker control verified: Yes -- newline injection confirmed
- Framework protection: None blocking
- Trust boundary crossing: Yes -- escalates from authenticated user to permanent auth bypass
- Normal attacker position: Requires auth (not unauthenticated), but this is privilege escalation
- Ships to production: Yes

All checks passed.

**Verdict: VALID**
**Severity: HIGH**
**Rationale**: Newline injection in env file serialization allows an authenticated attacker to persistently disable all authentication on the next server restart; while auth is required and restart is needed, the impact is a complete permanent auth bypass that survives indefinitely.

**Finding draft written to**: security/findings-draft/p8-026-env-newline-injection.md
**Registry updated**: AP-026 Newline Injection in Configuration Serialization

---

## Chamber Summary

| Hypothesis | Verdict | Severity | Finding Draft |
|-----------|---------|----------|---------------|
| H-01 | VALID | HIGH | p8-020-vault-hardcoded-key.md |
| H-02 | VALID | HIGH | p8-021-vault-plaintext-fallback.md |
| H-03 | VALID | HIGH | p8-022-telegram-token-theft.md |
| H-04 | VALID | HIGH | p8-023-telegram-config-overwrite.md |
| H-05 | VALID | MEDIUM | p8-024-api-key-in-login-response.md |
| H-06 | VALID | HIGH | p8-025-fe-catch-all-path-traversal.md |
| H-07 | VALID | HIGH | p8-026-env-newline-injection.md |

Findings written: 7
Patterns added to registry: 5 (AP-020, AP-021, AP-022, AP-024, AP-025, AP-026)
Variant candidates: see registry

Chamber closed: 2026-03-30T10:40:00Z
