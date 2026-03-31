# Code Anatomy: discord-agent

> Produced by: code-anatomist-02
> Source files analyzed:
> - discord-bot/src/index.js
> - discord-bot/src/client.js
> - discord-bot/src/agent-bridge.js
> - discord-bot/src/commands/join.js
> - discord-bot/src/commands/leave.js
> - discord-bot/src/commands/ping.js
> - .agents/mcp/vault.py
> - .agents/mcp/config_resolver.py
> - .agents/mcp/warroom-server.py
> - .agents/mcp/channel-server.py
> - .agents/mcp/memory-server.py
> - .agents/mcp/memory-core.py
> - .agents/bin/cli.py

---

## discord-bot/src/index.js

**Role**: Bot entry point. Validates `DISCORD_TOKEN` and calls `client.login()`.

**Functions**:
- _(module level)_ — checks `process.env.DISCORD_TOKEN`; calls `client.login()` with bot token from env; exits on failure. No additional logic.

**Sensitive operations**: Reads `DISCORD_TOKEN` from environment. If absent, process exits cleanly. No injection risk here.

---

## discord-bot/src/client.js

**Role**: Discord client initialization, message handling, slash command dispatch, message logging, voice session auto-cleanup.

**Functions**:

| Function / Handler | Line | Input | Output | Notes |
|---|---|---|---|---|
| `messageCreate` handler | 75 | Discord `Message` object | triggers `askAgent()`, writes log file | Central untrusted-input entry point |
| @mention extractor | 106-108 | `message.content` | `question` string | Only strips `<@!?{userId}>` prefix; no further sanitization |
| `askAgent()` call | 117 | `question` (raw user text) | Discord reply | No sanitization before passing to agent-bridge |
| `interactionCreate` handler | 42 | `Interaction` object | dispatches to command | Only checks `isChatInputCommand()`; no extra auth |
| log file write | 98 | `JSON.stringify(entry)` appended to JSONL | disk file | Includes verbatim `message.content`; path derived from `channelName` + `channelId` |
| `voiceStateUpdate` handler | 134 | `VoiceState` objects | calls `cleanupSession()` | No security-relevant input processing |

**State**:
- `messageBuffer`: in-memory ring buffer (last 100 messages); exported as `module.exports.messageBuffer`
- Log files: `../logs/{channelName}-{channelId}.jsonl` — path components derived from Discord-provided `channelName` (could contain path separators if channel names are crafted, but Discord normalizes channel names)

**Critical data flows**:
```
Discord Gateway
  → message.content (up to 2000 chars, attacker-controlled)
  → strip @mention (line 107)
  → question string
  → askAgent(question)          [agent-bridge.js]
  → Gemini prompt injection
```

---

## discord-bot/src/agent-bridge.js

**Role**: Gathers context from FastAPI backend, builds Gemini prompt, calls Gemini API, returns answer.

**Module-level constants** (line 10-15):
- `DASHBOARD_URL` = `process.env.DASHBOARD_URL || 'http://localhost:9000'` — no validation
- `OSTWIN_API_KEY` = `process.env.OSTWIN_API_KEY || ''`
- `GOOGLE_API_KEY` = `process.env.GOOGLE_API_KEY || ''`
- `headers` = `{ 'X-API-Key': OSTWIN_API_KEY }` (set once at module load, sent to ALL fetchJSON targets)

**Functions**:

| Function | Line | Input | Output | Security Notes |
|---|---|---|---|---|
| `fetchJSON(path)` | 19 | `path` string | JSON object | Base URL = `DASHBOARD_URL` (unvalidated); `X-API-Key` header attached to all requests regardless of destination |
| `getPlans()` | 35 | none | string (plan list) | Calls `fetchJSON('/api/plans')`; returns plan titles/IDs from unauthenticated endpoint |
| `getRooms()` | 45 | none | string (room list) | Calls `fetchJSON('/api/rooms')`; returns room IDs/status |
| `getStats()` | 54 | none | string (stats) | Calls `fetchJSON('/api/stats')` |
| `semanticSearch(query)` | 65 | `query` (user-controlled) | string (search results) | `encodeURIComponent(query)` applied to param only; DASHBOARD_URL base unvalidated; results injected verbatim into prompt |
| `askAgent(question)` | 81 | `question` (user-controlled, up to ~2000 chars) | string answer | Central vulnerability: question appears at line 110 (inside context block) and line 121 (appended to prompt); both as raw string concatenation |

**Prompt construction** (lines 95-121):
```
systemPrompt (line 95-99)     — hardcoded instructions
contextBlock (line 101-111)   — includes: plans, rooms, stats, AND semanticSearch(question)
                                          ↑ second injection point: line 110 "${question}"
final contents[0] (line 121)  — "${systemPrompt}\n\n---\n\n${contextBlock}\n\n---\n\n**User question:** ${question}"
                                                                                                                 ↑ primary injection point
```

Both injection sites are in the same `user` role message. Gemini's `systemInstruction` API field is NOT used. There is no structural separation between instructions and user data.

**Response handling** (line 129-131):
- LLM response truncated at 1900 chars and sent back to Discord via `message.reply(answer)`
- No output sanitization: `@everyone`, `@here`, arbitrary markdown, fake bot messages all pass through

---

## discord-bot/src/commands/join.js

**Role**: `/join` slash command — joins voice channel, records audio to PCM files.

**Functions**:
- `cleanupSession(guildId)` — closes streams, disconnects voice, saves files
- `execute(interaction)` — joins voice channel, starts opus decoding pipeline

**Sensitive operations**:
- `filePath = path.join(RECORDINGS_DIR, '${username}-${timestamp}.pcm')` — `username` comes from `interaction.client.users.cache.get(userId).username`; Discord enforces username character restrictions, so path traversal is low risk but the username appears in a path component.
- Audio data written verbatim to disk; no content analysis.

---

## .agents/mcp/vault.py

**Role**: Abstract secret store with two backends: macOS Keychain and Fernet-encrypted file.

**Classes**:

| Class | Backend | Auth |
|---|---|---|
| `MacOSKeychainVault` | macOS `security` CLI subprocess | macOS user session |
| `EncryptedFileVault` | Fernet-encrypted JSON file | Encryption key |

**`EncryptedFileVault._get_encryption_key()`** (line 106-117):
```python
env_key = os.environ.get("OSTWIN_VAULT_KEY")
if env_key:
    return base64.urlsafe_b64encode(env_key.encode().ljust(32)[:32])
# FALLBACK:
return base64.urlsafe_b64encode(b"ostwin-default-insecure-key-32ch")
```
- If `OSTWIN_VAULT_KEY` is absent: uses public hardcoded key
- If `OSTWIN_VAULT_KEY` is present but short: left-padded with null bytes (weak key extension)
- If `cryptography` not installed (`CRYPTOGRAPHY_AVAILABLE = False`): `self.fernet = None`; vault stores and reads **plaintext JSON**

**`EncryptedFileVault._load_data()`** (line 119-134):
- Reads `~/.ostwin/mcp/.vault.enc`
- If `self.fernet` is None: `json.loads(encrypted_data)` — plaintext read
- Exception on decrypt failure: silently returns `{}`

**`EncryptedFileVault._save_data()`** (line 136-145):
- If `self.fernet` is None: writes plaintext JSON
- No file permissions hardening (uses default umask)

**`get_vault()`** (line 168-173):
- On macOS: returns `MacOSKeychainVault()` (secure)
- On non-macOS: returns `EncryptedFileVault(Path.home() / '.ostwin' / 'mcp' / '.vault.enc')` with potentially hardcoded key

**`MacOSKeychainVault.set()`/`get()`** (lines 42-66):
- Constructs service name as `ostwin-mcp/{server}/{key}` — `/` separator is used in Keychain service name
- `subprocess.run(["security", ...])` — arguments are passed as list (safe from shell injection)
- BUT: `server` and `key` are caller-controlled; malformed values could confuse the `security` CLI

---

## .agents/mcp/config_resolver.py

**Role**: Resolves `${vault:server/key}` references in MCP config dictionaries by looking them up in the vault.

**Key function: `_resolve_recursive()`** (line 27-41):
- Regex: `r"\$\{vault:([^/]+)/([^}]+)\}"`
- Extracts `server` and `key` from config strings
- Calls `self.vault.get(server, key)`
- Replaces the reference with the secret value
- If secret is `None`: raises `ValueError`

**`compile_config()`** (line 70-106):
- Merges home config + builtin config
- Replaces vault refs with `${MCP_{SERVER}_{KEY}}` env var placeholders
- If vault lookup returns `None`: leaves ref partially resolved (line 93-95 — sets `env_vars[env_name] = secret or ""` — empty string for missing secrets)

**Attack surface**: If an attacker can write a JSON config file with `${vault:server/key}` patterns, they can enumerate which vault keys exist (missing raises ValueError; found returns the secret value). This is a vault key oracle.

---

## .agents/mcp/warroom-server.py

**Role**: MCP server (stdio transport) exposing war-room file operations as tools.

**Tools**:

| Tool | Line | Critical Input | Validation | File Write |
|---|---|---|---|---|
| `update_status()` | 43 | `room_dir` (arbitrary path), `status` | status: allowlist check; room_dir: NONE | Writes `status`, `state_changed_at`, `audit.log` under `room_dir` |
| `list_artifacts()` | 88 | `room_dir` (arbitrary path) | NONE | None (read-only) |
| `report_progress()` | 120 | `room_dir` (arbitrary path), `message` (free text) | percent: clamped; others: NONE | Writes `progress.json` under `room_dir` |

**Path traversal risk**: `room_dir` accepts any string including `../../../` sequences. `os.makedirs(room_dir, exist_ok=True)` will create directories anywhere the process user can write. Files written at attacker-controlled paths.

---

## .agents/mcp/channel-server.py

**Role**: MCP server (stdio transport) for war-room message channel (JSONL append log).

**Tools**:

| Tool | Line | Critical Input | Validation | Notes |
|---|---|---|---|---|
| `post_message()` | 57 | `room_dir`, `from_role`, `to_role`, `msg_type`, `body` | msg_type: VALID_TYPES check; body: 65536 byte truncation; from_role: NOT validated | `from_role` written verbatim to JSONL; any string accepted |
| `read_messages()` | 107 | `room_dir`, filter params | NONE | Reads JSONL from `room_dir`; no path restriction |
| `get_latest()` | 168 | `room_dir`, `msg_type` | NONE | Reads JSONL from `room_dir` |

**`VALID_ROLES` constant** (line 38) is defined but never applied to `from_role` input in `post_message()`. This is a dead validation — the constant exists but is unused as a guard.

**`from_role` injection**: Written directly into JSONL: `"from": from_role`. Any consumer that trusts `from_role` to represent a legitimate role is deceived. Manager-role impersonation is possible.

---

## .agents/mcp/memory-server.py / memory-core.py

**Role**: Shared memory ledger for cross-room context. MCP wrapper around `memory-core.py`.

**Tools exposed**: `publish`, `query`, `search`, `get_context`, `list_memories`

**Key data**: `summary` (max 4KB), `detail` (max 16KB), `tags` — all attacker-controllable strings.

**Storage**: `{AGENT_OS_ROOT}/.agents/memory/ledger.jsonl` — JSONL with fcntl locking.

**`search()` function**: Tokenizes free-text query; scores entries by word overlap. If attacker controls memory entries, they can influence search ranking and which "memories" are surfaced to other agents.

**Security note**: Memory entries from all rooms are queryable by all agents. An attacker who can call `publish()` (via a compromised agent or prompt injection) can poison shared memory with false decisions, interfaces, or warnings that affect all subsequent agents.

---

## .agents/bin/cli.py

**Role**: Role-aware wrapper around `deepagents_cli`. Monkey-patches `Settings.get_project_agent_skills_dir` to read `AGENT_OS_SKILLS_DIR` env var.

**Key risk**: `AGENT_OS_SKILLS_DIR` env var points to the directory from which skill modules (Python files) are loaded. If an attacker controls this env var, they can redirect skill loading to an arbitrary directory — potentially loading malicious Python modules as "skills".

---

## Cross-Component Data Flows

### Flow A: Discord Message → Gemini Prompt (Primary Attack Path)
```
Discord User @mention
  → client.js:75 messageCreate
  → client.js:107 strip @mention → question
  → agent-bridge.js:81 askAgent(question)
    ├── semanticSearch(question) → fetchJSON('/api/search?q=...')
    │     → FastAPI (via DASHBOARD_URL)
    │     ← search results (may contain attacker-planted plan content)
    ├── getPlans() → fetchJSON('/api/plans')
    │     ← plan list (may contain attacker-planted content)
    └── prompt = systemPrompt + plans + rooms + stats + search(question) + question
         → Gemini generateContent (user role only, no systemInstruction separation)
         ← LLM response
  → client.js:119 message.reply(answer) [no output sanitization]
```

### Flow B: DASHBOARD_URL Compromise → API Key Exfiltration
```
Attacker controls DASHBOARD_URL (via env injection, .env write, etc.)
  → agent-bridge.js:14 headers = { 'X-API-Key': OSTWIN_API_KEY }
  → agent-bridge.js:21 fetch(`${DASHBOARD_URL}${path}`, { headers })
  → X-API-Key header sent to attacker-controlled host
  → API key exfiltrated
```

### Flow C: Unauthenticated Plan Create → Second-Order Prompt Injection
```
Attacker → POST /api/plans/create (no auth required)
  → Plan with attacker-controlled content written to ~/.ostwin/plans/
  → Plan indexed in vector store
  → Bot getPlans() or semanticSearch() retrieves this plan
  → Attacker content injected into Gemini prompt as "trusted" context
```

### Flow D: Vault Key Compromise → Secret Decryption
```
Non-macOS system, OSTWIN_VAULT_KEY unset
  → vault.py:117 hardcoded key = b"ostwin-default-insecure-key-32ch"
  → ~/.ostwin/mcp/.vault.enc readable by OS user
  → Attacker reads file, applies Fernet decryption with known key
  → All stored MCP secrets exposed
```

### Flow E: MCP room_dir Path Traversal → Arbitrary File Write
```
Compromised MCP client (or prompt-injected agent)
  → warroom-server.py:43 update_status(room_dir='../../../../tmp/evil', status='pending')
  → os.makedirs('../../../../tmp/evil', exist_ok=True) — creates dirs
  → writes status, state_changed_at, audit.log at arbitrary path
```

### Flow F: channel-server from_role Impersonation
```
Any MCP caller
  → channel-server.py:57 post_message(from_role='manager', ...)
  → from_role NOT validated against VALID_ROLES
  → "manager" message written to channel.jsonl
  → Other agents trust the "from" field and respond to fake manager instructions
```
