# Evidence Report — discord-agent
> Produced by: evidence-harvester-02
> Hypotheses files: round-1-hypotheses.md, round-2-hypotheses.md, round-3-hypotheses.md
> Component source paths: discord-bot/src/, .agents/mcp/, .agents/bin/

---

## Evidence Methodology

For each hypothesis, the harvester locates the exact code lines confirming or denying the claimed attack path. Fragility scores assess how robust the vulnerability is to minor code changes that might inadvertently fix it.

Fragility: **Solid** = requires deliberate code change to fix; **Fragile** = a minor refactor might accidentally resolve it; **Structural** = architectural issue requiring design change.

---

## PH-01: Direct Prompt Injection via Discord @mention

**Status**: VALIDATED
**Evidence**:
- `discord-bot/src/client.js:107` — `message.content.replace(new RegExp('<@!?' + client.user.id + '>', 'g'), '').trim()` — only strips @mention, no further sanitization
- `discord-bot/src/agent-bridge.js:121` — `` { text: `${systemPrompt}\n\n---\n\n${contextBlock}\n\n---\n\n**User question:** ${question}` } `` — raw string concatenation, question appears verbatim
- `discord-bot/src/agent-bridge.js:116` — `genAI.getGenerativeModel({ model: geminiModel })` — no `systemInstruction` field
- No length cap on `question` before `askAgent()` call
**Fragility**: Solid — the vulnerable pattern (string concatenation into user-role message) requires deliberate architectural change (use of systemInstruction API) to fix.
**Confidence**: HIGH

---

## PH-02: Second-Order Prompt Injection via Attacker-Planted Plan Content

**Status**: VALIDATED
**Evidence**:
- `discord-bot/src/agent-bridge.js:70` — `` `[${r.room_id || 'global'}] ${r.from || '?'} → ${r.type || '?'}: ${(r.body || '').slice(0, 200)}` `` — search result body (up to 200 chars) injected into prompt
- `discord-bot/src/agent-bridge.js:111` — `## Relevant Messages (semantic search for "${question}")\n${search}` — search string (containing attacker body content) placed in context block
- KB confirms: `POST /api/plans/create` (plans.py:461) unauthenticated AND content indexed in zvec vector store
- KB confirms: `GET /api/search` (rooms.py:184) is unauthenticated and returns search results
**Fragility**: Solid — requires sanitizing search result content AND restricting plan creation.
**Confidence**: HIGH

---

## PH-03: API Key Exfiltration via DASHBOARD_URL Poisoning

**Status**: VALIDATED
**Evidence**:
- `discord-bot/src/agent-bridge.js:10` — `const DASHBOARD_URL = process.env.DASHBOARD_URL || 'http://localhost:9000'` — no validation
- `discord-bot/src/agent-bridge.js:14-15` — `const headers = {}; if (OSTWIN_API_KEY) headers['X-API-Key'] = OSTWIN_API_KEY;` — header set once at module load
- `discord-bot/src/agent-bridge.js:21` — `` const res = await fetch(`${DASHBOARD_URL}${path}`, { headers }); `` — DASHBOARD_URL prepended to all paths without host validation
- No scheme validation, no hostname allowlist, no check against expected host before attaching API key
**Fragility**: Solid — requires adding explicit URL validation before requests.
**Confidence**: HIGH

---

## PH-04: Vault Decryption via Known Hardcoded Key (Non-macOS)

**Status**: VALIDATED
**Evidence**:
- `.agents/mcp/vault.py:107` — `env_key = os.environ.get("OSTWIN_VAULT_KEY")`
- `.agents/mcp/vault.py:117` — `return base64.urlsafe_b64encode(b"ostwin-default-insecure-key-32ch")` — literal hardcoded key in source
- `.agents/mcp/vault.py:168-173` — `get_vault()` returns `EncryptedFileVault` on non-macOS
- `.agents/mcp/vault.py:172` — path: `Path.home() / ".ostwin" / "mcp" / ".vault.enc"` — known path
- The key `b"ostwin-default-insecure-key-32ch"` is exactly 32 bytes; base64url-encoded = valid Fernet key
**Fragility**: Solid — hardcoded key in source requires deliberate removal; not accidentally fixed by refactoring.
**Confidence**: HIGH

---

## PH-05: Vault Plaintext Fallback When `cryptography` Absent

**Status**: VALIDATED
**Evidence**:
- `.agents/mcp/vault.py:9-16` — `try: from cryptography.fernet import Fernet; CRYPTOGRAPHY_AVAILABLE = True; except ImportError: CRYPTOGRAPHY_AVAILABLE = False`
- `.agents/mcp/vault.py:104` — `self.fernet = Fernet(self.key) if CRYPTOGRAPHY_AVAILABLE else None`
- `.agents/mcp/vault.py:143-145` — `else: with open(self.path, "wb") as f: f.write(json_data)` — plaintext write when fernet is None
- `.agents/mcp/vault.py:130-133` — `else: return json.loads(encrypted_data)` — plaintext read when fernet is None
- Comment at line 131: "# Fallback to plaintext if cryptography is missing (NOT RECOMMENDED)"
**Fragility**: Solid — the plaintext branch requires explicit code change to remove; the conditional exists deliberately.
**Confidence**: HIGH

---

## PH-06: MCP room_dir Path Traversal — Arbitrary File Write

**Status**: VALIDATED
**Evidence**:
- `.agents/mcp/warroom-server.py:61` — `os.makedirs(room_dir, exist_ok=True)` — no path validation before makedirs
- `.agents/mcp/warroom-server.py:63` — `status_file = os.path.join(room_dir, "status")` — path join with unvalidated base
- `.agents/mcp/warroom-server.py:71-82` — writes to `status_file`, `state_changed_at`, `audit.log` — all under unvalidated `room_dir`
- `.agents/mcp/warroom-server.py:130-141` — `report_progress()` also writes to `os.path.join(room_dir, "progress.json")` — same issue
- `.agents/mcp/channel-server.py:79` — `channel_file = os.path.join(room_dir, "channel.jsonl")` — same pattern in channel server
- No call to `os.path.realpath()`, `os.path.abspath()`, or any prefix-restriction check in any MCP server
**Fragility**: Solid — requires adding path validation; unlikely to be accidentally fixed.
**Confidence**: HIGH

---

## PH-07: channel-server from_role Manager Impersonation

**Status**: VALIDATED
**Evidence**:
- `.agents/mcp/channel-server.py:38` — `VALID_ROLES = {"manager", "engineer", "qa", "architect", ...}` — defined but unused
- `.agents/mcp/channel-server.py:71` — `if msg_type not in VALID_TYPES:` — VALID_TYPES IS checked
- NO corresponding `if from_role not in VALID_ROLES:` check anywhere in `post_message()`
- `.agents/mcp/channel-server.py:87` — `"from": from_role,` — written verbatim to JSONL
- `.agents/mcp/channel-server.py:151-153` — `if from_role is not None and msg.get("from") != from_role: continue` — read path trusts the stored from value
**Fragility**: Fragile — a developer adding `if from_role not in VALID_ROLES: return error` would fix the validation gap, though not the underlying trust model issue. The pattern is already present for msg_type; from_role validation may be added in a routine code review.
**Confidence**: HIGH

---

## PH-08: Unsanitized LLM Output — @everyone/@here Injection

**Status**: VALIDATED
**Evidence**:
- `discord-bot/src/client.js:119` — `message.reply(answer)` — LLM response passed directly to Discord reply API
- No string replacement, regex filter, or sanitization applied to `answer` before `reply()`
- Discord API: `message.reply()` will render @mentions if the bot has permission; `@here` mentions online members
- `askAgent()` returns raw `result.response?.text?.()` with only length truncation (line 129-131)
**Fragility**: Fragile — a developer adding `answer.replace(/@(everyone|here)/g, '@\u200beveryone')` would defuse the most obvious variant. The underlying LLM output trust issue remains.
**Confidence**: HIGH

---

## PH-09: Weak Vault Key Derivation — Null-Byte Padding

**Status**: VALIDATED
**Evidence**:
- `.agents/mcp/vault.py:111` — `return base64.urlsafe_b64encode(env_key.encode().ljust(32)[:32])`
- Python `bytes.ljust(width)` documentation: "The sequence is left-justified in a sequence of length width. Padding is done using the specified fill sequence (default is an ASCII space, which is `b' '` for bytes)"
- CORRECTION: `bytes.ljust()` pads with `b'\x20'` (space), NOT null bytes, by default
- Re-evaluation: `env_key.encode().ljust(32)[:32]` — if `env_key = "short"` → `b"short\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20"` (space padding, not null)
- The padding character (space `\x20`) is slightly less predictable than null bytes, but still deterministic
- The key entropy is still limited to the entropy of the original short key
- An attacker who knows the ljust-with-space convention can still brute-force short keys
**Fragility**: Fragile — if the code used a proper KDF (PBKDF2HMAC, which IS imported at line 13 but not used for env var keys), this would be fixed. The KDF infrastructure exists but is not applied.
**Confidence**: MEDIUM — the padding is space not null, slightly changes the attack but the low-entropy finding holds for short keys.

---

## PH-10: config_resolver Vault Key Oracle

**Status**: NEEDS-DEEPER
**Evidence**:
- `.agents/mcp/config_resolver.py:36-41` — `_resolve_recursive()` raises `ValueError` for missing vault keys
- `.agents/mcp/config_resolver.py:93-100` — `compile_config()` silently sets empty string for missing vault keys
- The oracle behavior depends on HOW `config_resolver.py` is invoked and whether attacker can supply config input
- No evidence found that `config_resolver` processes untrusted config input directly; it appears to process the project's own `mcp-config.json`
**Fragility**: Fragile — depends on deployment context; not directly attacker-accessible without a separate file write primitive
**Confidence**: LOW (requires additional investigation of invocation paths)

---

## PH-11: Gemini user-role Conflation

**Status**: VALIDATED (overlaps with PH-01 / PH-C01)
**Evidence**: Same as PH-01 — `agent-bridge.js:116` confirms no `systemInstruction`; `agent-bridge.js:121` confirms single user-role message
**Fragility**: Solid
**Confidence**: HIGH

---

## PH-12: encodeURIComponent False Safety

**Status**: VALIDATED (overlaps with PH-02 / PH-C02)
**Evidence**:
- `agent-bridge.js:66` — `encodeURIComponent(query)` applied to URL param only
- `agent-bridge.js:70` — `r.body.slice(0, 200)` — result body inserted unescaped into prompt
**Fragility**: Solid
**Confidence**: HIGH

---

## PH-13: Guild Membership Auth — Zero Trust

**Status**: VALIDATED
**Evidence**:
- `client.js:77` — `if (message.author.bot) return` — only bot filter
- `client.js:79` — `if (!message.guild) return` — only DM filter
- No role check, no user allowlist, no permission verification beyond guild membership
**Fragility**: Structural — requires architectural change (Discord role-based permissions check, e.g., `message.member.roles.cache.has(allowedRoleId)`)
**Confidence**: HIGH

---

## PH-14: reply() Channel Scope Amplification

**Status**: VALIDATED
**Evidence**:
- `client.js:119` — `message.reply(answer)` — public channel reply
- Discord behavior: `message.reply()` posts a visible reply in the channel, visible to all members with access
- LLM output contains no sanitization of @mentions or URLs
**Fragility**: Fragile — adding `answer.replace(/(@everyone|@here)/gi, '[FILTERED]')` partially mitigates; full mitigation requires structured output from LLM
**Confidence**: HIGH

---

## PH-15: from_role Dead Code Validation

**Status**: VALIDATED (same as PH-07)
**Evidence**: Same as PH-07
**Fragility**: Fragile
**Confidence**: HIGH

---

## PH-16: Vault ljust() Padding Weak Key

**Status**: VALIDATED (see PH-09 correction — space padding, not null)
**Evidence**: `vault.py:111` — `ljust(32)` with space padding confirmed; entropy limited by original key length
**Fragility**: Fragile
**Confidence**: MEDIUM

---

## PH-17: Memory Ledger Poisoning via publish()

**Status**: VALIDATED
**Evidence**:
- `.agents/mcp/memory-server.py:44-66` — `publish()` accepts `kind`, `summary`, `tags`, `room_id`, `author_role`, `ref` — all user-supplied, no caller authentication
- `.agents/mcp/memory-core.py` — entries written to `ledger.jsonl` with caller-supplied `author_role`
- `memory-server.py:69-86` — `query()` returns entries with stored `author_role` values; no re-validation
- MCP stdio transport: no caller authentication possible at transport layer
**Fragility**: Structural — MCP stdio has no authentication mechanism; requires application-level signing or out-of-band verification
**Confidence**: HIGH

---

## PH-18: Bot Log File Path Traversal via channelName

**Status**: NEEDS-DEEPER
**Evidence**:
- `client.js:97` — `path.join(LOGS_DIR, '${entry.channelName}-${entry.channelId}.jsonl')`
- Discord enforces channel name restrictions: lowercase letters, numbers, hyphens only (no path separators)
- Risk is effectively blocked by Discord's channel name validation on the platform side
- However: `channelName` comes from the Discord API, not from user input; if Discord ever changes name restrictions or if the bot is used with a modified client, the risk surfaces
**Fragility**: Fragile — dependent on Discord platform guarantees, not local code validation
**Confidence**: LOW (Discord platform controls effectively prevent this)

---

## PH-19: No Rate Limiting on @mention Context Fetch

**Status**: VALIDATED
**Evidence**:
- `client.js:75-128` — no rate limiting, debounce, or cooldown logic in messageCreate handler
- `agent-bridge.js:87-92` — `Promise.all()` fires on every invocation; no request throttling
- Every @mention triggers 4 FastAPI requests + 1 Gemini API call
- No `messageBuffer` rate check, no per-user timestamp tracking
**Fragility**: Fragile — a simple per-user cooldown Map would mitigate this
**Confidence**: HIGH

---

## PH-20: Vault File World-Readable

**Status**: VALIDATED
**Evidence**:
- `vault.py:136-145` — `_save_data()` uses standard `open()` with no `os.chmod()` call
- `vault.py:137` — `self.path.parent.mkdir(parents=True, exist_ok=True)` — no explicit mode
- On Linux with default umask `0o022`: file created as `0o644` (world-readable); directory as `0o755` (world-executable)
- On macOS: similar defaults
**Fragility**: Fragile — adding `os.chmod(self.path, 0o600)` after write would fix file permissions
**Confidence**: HIGH

---

## PH-C07: DASHBOARD_URL Fragment Injection Variant

**Status**: VALIDATED
**Evidence**:
- `agent-bridge.js:21` — `` fetch(`${DASHBOARD_URL}${path}`, { headers }) `` — literal string concatenation
- If DASHBOARD_URL ends with `#`, the path becomes a URL fragment not sent to server
- `X-API-Key` header still transmitted to DASHBOARD_URL host
**Fragility**: Solid — requires URL validation to fix
**Confidence**: HIGH

---

## PH-C08: Log Files Persist Injection Payloads

**Status**: VALIDATED
**Evidence**:
- `client.js:88` — `content: message.content` — verbatim Discord message stored in entry object
- `client.js:98` — `fsp.appendFile(logFile, JSON.stringify(entry) + EOL)` — full entry including raw content written to JSONL
- Log directory: `discord-bot/logs/` — no access restriction specified
- All adversarial @mention messages permanently logged to disk
**Fragility**: Solid (informational — logs are intentional; the security concern is disclosure of message content to anyone with file access)
**Confidence**: HIGH

---

## Consolidated Findings Table

| ID | Title | Status | Severity | Fragility |
|---|---|---|---|---|
| PH-01 | Direct Prompt Injection via @mention | VALIDATED | HIGH | Solid |
| PH-02 | Second-Order Injection via Planted Plans | VALIDATED | HIGH | Solid |
| PH-03 | API Key Exfiltration via DASHBOARD_URL | VALIDATED | HIGH | Solid |
| PH-04 | Vault Decryption via Hardcoded Key | VALIDATED | HIGH | Solid |
| PH-05 | Vault Plaintext Fallback | VALIDATED | HIGH | Solid |
| PH-06 | MCP room_dir Path Traversal | VALIDATED | HIGH | Solid |
| PH-07 / PH-15 | from_role Manager Impersonation | VALIDATED | MEDIUM-HIGH | Fragile |
| PH-08 / PH-14 | LLM Output @everyone/@here Injection | VALIDATED | MEDIUM | Fragile |
| PH-09 / PH-16 | Vault Short-Key Low Entropy (space padding) | VALIDATED | MEDIUM | Fragile |
| PH-10 | config_resolver Vault Oracle | NEEDS-DEEPER | MEDIUM | Fragile |
| PH-11 | Gemini user-role Conflation | VALIDATED | HIGH | Solid |
| PH-12 | encodeURIComponent False Safety | VALIDATED | HIGH | Solid |
| PH-13 | Guild Membership Auth Gap | VALIDATED | HIGH | Structural |
| PH-17 | Memory Ledger Poisoning | VALIDATED | MEDIUM-HIGH | Structural |
| PH-18 | Log File Path Traversal | NEEDS-DEEPER | LOW | Fragile |
| PH-19 | No Rate Limiting | VALIDATED | MEDIUM | Fragile |
| PH-20 | Vault File World-Readable | VALIDATED | MEDIUM | Fragile |
| PH-C07 | DASHBOARD_URL Fragment Injection | VALIDATED | HIGH | Solid |
| PH-C08 | Log Files Persist Injection Payloads | VALIDATED | MEDIUM | Solid |
