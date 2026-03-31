# Attack Surface Map: discord-agent

## Entry Points

- `discord-bot/src/client.js:75` — `messageCreate` handler — accepts full Discord message content from any guild member who can @mention the bot (up to 2000 chars); no length cap, no sanitization, no allow/deny list
- `discord-bot/src/client.js:42` — `interactionCreate` handler — accepts slash command interactions from Discord users; dispatches to command modules
- `discord-bot/src/client.js:98` — log file append — Discord message content written verbatim to per-channel JSONL files under `logs/`
- `discord-bot/src/agent-bridge.js:10` — `DASHBOARD_URL` env var — controls the base URL for all outbound HTTP calls; no scheme or host validation
- `discord-bot/src/agent-bridge.js:11` — `OSTWIN_API_KEY` env var — controls API key sent in X-API-Key header to DASHBOARD_URL
- `discord-bot/src/agent-bridge.js:65` — `semanticSearch(query)` — user question inserted into search URL via `encodeURIComponent`; the URL base itself is attacker-controllable via `DASHBOARD_URL`
- `discord-bot/src/agent-bridge.js:81` — `askAgent(question)` — primary injection sink: user message flows into Gemini prompt at lines 110 and 121 with no sanitization
- `.agents/mcp/vault.py:106` — `_get_encryption_key()` — reads `OSTWIN_VAULT_KEY` env var; falls back to hardcoded key `ostwin-default-insecure-key-32ch` if unset
- `.agents/mcp/vault.py:42` — `MacOSKeychainVault.set()` — invokes `security add-generic-password` subprocess with user-supplied `server` and `key` arguments
- `.agents/mcp/vault.py:55` — `MacOSKeychainVault.get()` — invokes `security find-generic-password` subprocess with user-supplied `server` and `key` arguments
- `.agents/mcp/config_resolver.py:33` — `_resolve_recursive()` — resolves `${vault:server/key}` references from config files; vault key controlled by config content
- `.agents/mcp/warroom-server.py:43` — `update_status()` MCP tool — accepts `room_dir` as an attacker-controlled absolute or relative path; writes `status`, `state_changed_at`, `audit.log` files at that path
- `.agents/mcp/warroom-server.py:88` — `list_artifacts()` MCP tool — accepts `room_dir`; walks the `artifacts/` subdirectory under the given path
- `.agents/mcp/warroom-server.py:120` — `report_progress()` MCP tool — accepts `room_dir` and free-text `message`; writes JSON to disk
- `.agents/mcp/channel-server.py:57` — `post_message()` MCP tool — accepts `room_dir`, `from_role`, `to_role`, `msg_type`, `ref`, `body`; writes JSONL to disk; `from_role` is NOT validated against `VALID_ROLES`
- `.agents/mcp/channel-server.py:107` — `read_messages()` MCP tool — reads channel JSONL; filter params are user-supplied
- `.agents/mcp/memory-server.py:44` — `publish()` MCP tool — accepts free-text `summary`, `tags`, `detail` from calling agent; no content filtering
- `.agents/bin/cli.py:37` — `_get_role_aware_skills_dir()` — reads `AGENT_OS_SKILLS_DIR` env var; used to load skill modules at runtime

## Trust Boundary Crossings

- **TB-2 → TB-3**: Discord message content (untrusted user input) crosses from Discord Gateway into the bot process via `messageCreate`, then flows — without transformation — into Gemini prompt construction and into HTTP requests to FastAPI (via semantic search). This is the primary injection path.
- **TB-3 DASHBOARD_URL**: The bot process trusts the `DASHBOARD_URL` env var to be the legitimate backend. If this var is tampered with, all API calls (including ones carrying `X-API-Key`) are redirected to an attacker-controlled host. No validation guards this crossing.
- **TB-6 Gemini**: User input crosses into a third-party LLM. The system prompt is constructed in the same `contents[0]` object as the user message (lines 119-122 of agent-bridge.js), so there is no structural separation between system instructions and user data.
- **TB-8 Vault → FS**: Vault keys derived from env var or hardcoded fallback; if the env var is absent, every vault operation uses the publicly known key. The vault file at `~/.ostwin/mcp/.vault.enc` is readable by any process running as the same OS user.
- **MCP stdio**: MCP servers (warroom, channel, memory) accept JSON-encoded tool calls over stdio. Any process that spawns these servers can pass arbitrary `room_dir` paths and message content. There is no caller authentication on the stdio channel.
- **config_resolver → vault**: `${vault:server/key}` patterns in JSON config files are resolved by calling `vault.get(server, key)`. If an attacker can write a config file with crafted vault references, they can probe or enumerate vault keys.

## Auth / AuthZ Decision Points

- `discord-bot/src/client.js:77` — `messageCreate` — checks `message.author.bot` (ignore bots) and `message.guild` (ignore DMs); NO authentication of user identity beyond Discord guild membership
- `discord-bot/src/client.js:104` — @mention check — only checks if the bot's user ID appears in `message.mentions`; any guild member can trigger the agent
- `discord-bot/src/agent-bridge.js:82` — `askAgent()` — checks `GOOGLE_API_KEY` is set; no user identity or permission check
- `.agents/mcp/vault.py:168` — `get_vault()` — selects vault backend based on `sys.platform`; on macOS uses Keychain (secure), on non-macOS uses `EncryptedFileVault` with potentially hardcoded key; no caller authentication
- `.agents/mcp/warroom-server.py:54` — `update_status()` — validates `status` against `StatusType` allowlist; does NOT validate `room_dir` is within any expected path; no caller authentication
- `.agents/mcp/channel-server.py:71` — `post_message()` — validates `msg_type` against `VALID_TYPES`; does NOT validate `from_role` against `VALID_ROLES` (validation constant exists but is never applied to input); no caller authentication

## Validation / Sanitization Functions

- `discord-bot/src/client.js:107` — `message.content.replace(regex, '').trim()` — strips the @mention prefix; does NOT sanitize or truncate the remaining content
- `discord-bot/src/agent-bridge.js:66` — `encodeURIComponent(query)` — URL-encodes the search parameter; only guards against URL injection in the query param, not the base URL
- `.agents/mcp/warroom-server.py:54-58` — `status not in valid` check — validates `status` against an allowlist; does NOT sanitize `room_dir` or `message` content
- `.agents/mcp/channel-server.py:71-76` — `msg_type not in VALID_TYPES` check + body truncation at 65536 bytes — validates message type; body is truncated but not sanitized; `from_role` is accepted without validation against `VALID_ROLES`
- `.agents/mcp/vault.py:108-113` — key derivation — left-pads/truncates `OSTWIN_VAULT_KEY` to 32 bytes; no validation that the key has adequate entropy

## Layer Trust Chain

For each layer transition in this component:

| From Layer | To Layer | Trust Assumption | Holds for ALL paths? | Alternate Paths that Skip This Layer? |
|---|---|---|:---:|---|
| Discord Gateway | client.js messageCreate | Input is from a legitimate, non-bot Discord user | Partial — bot filter only | No guild membership validation; any member can inject |
| client.js @mention check | agent-bridge.js askAgent | User is authorized to query the agent | NO | Any guild member who can send a message; no role/permission check |
| agent-bridge.js prompt builder | Gemini API generateContent | User content is separated from system instructions | NO | All content merged into single `user` role message at line 121; no delimiter enforcement |
| agent-bridge.js fetchJSON | FastAPI backend | DASHBOARD_URL points to the legitimate backend | NO | DASHBOARD_URL env var not validated; can be pointed to arbitrary host |
| DASHBOARD_URL → FastAPI | X-API-Key auth | Only authenticated callers receive API key header | NO | API key is attached to ALL requests regardless of destination host |
| FastAPI unauthenticated endpoints | agent-bridge.js context | Context data returned is non-attacker-controlled | NO | Plans/search results can contain attacker-planted content via unauthenticated POST /api/plans/create |
| MCP stdio | warroom-server tools | room_dir is a valid, expected war-room path | NO | room_dir is a free-form string; can be any filesystem path |
| MCP stdio | channel-server tools | from_role is a valid role | NO | from_role is NOT validated against VALID_ROLES; arbitrary values accepted |
| OSTWIN_VAULT_KEY env | EncryptedFileVault | Key has sufficient entropy | NO | Falls back to publicly known hardcoded key if env var is absent |
| vault.py EncryptedFileVault | ~/.ostwin/mcp/.vault.enc | Encrypted file is only readable by authorized processes | NO | Same OS user can read file; with known key, decryption is trivial |
| config_resolver vault refs | vault.get() | Config content is from trusted source | NO | Any process that writes a config file can enumerate vault keys |

## Trust Chain Gaps (rows where "Alternate Paths" column is NOT empty)

1. **No agent authorization**: The Discord @mention check does not verify that the user has any permission to query sensitive project data. Any Discord guild member can trigger full context retrieval (plans, rooms, stats, search history) and prompt injection into Gemini.

2. **System prompt / user content not separated**: At `agent-bridge.js:119-121`, the system prompt and user question are concatenated into a single `user` role message. There is no structural API-level separation (e.g., Gemini's `systemInstruction` field is not used). An attacker can append instructions that override or extend the system prompt.

3. **DASHBOARD_URL not validated**: `DASHBOARD_URL` can be any string. If compromised (env injection, `.env` file write via unauthenticated `/api/env` endpoint), all bot API calls — including those carrying `X-API-Key` — are routed to an attacker-controlled server.

4. **Second-order prompt injection via plan content**: FastAPI's `POST /api/plans/create` is unauthenticated. An attacker can plant arbitrary content into the plan store. When the bot calls `getPlans()` or `semanticSearch()`, this content is retrieved and injected into the Gemini prompt as trusted context.

5. **MCP room_dir path traversal**: `warroom-server.py` and `channel-server.py` accept `room_dir` as an arbitrary path. No check constrains the path to the expected `.agents/war-rooms/` tree. A compromised or malicious MCP client could write status/channel files to arbitrary filesystem locations.

6. **from_role not validated in channel-server**: `post_message()` does not validate `from_role` against `VALID_ROLES`. An agent can impersonate any role (including `manager`) in the channel log.

7. **Hardcoded vault key on non-macOS**: When `OSTWIN_VAULT_KEY` is unset and the platform is not macOS, the publicly known key `ostwin-default-insecure-key-32ch` is used to encrypt the vault. Any attacker with read access to `~/.ostwin/mcp/.vault.enc` can decrypt all stored secrets.

8. **Vault plaintext fallback**: If the `cryptography` package is not installed, vault data is stored and read as plaintext JSON, with no encryption whatsoever.

9. **API key leaked to arbitrary host**: `headers['X-API-Key']` is set once at module load time and sent with every `fetchJSON` call. If `DASHBOARD_URL` is attacker-controlled, the API key is exfiltrated on the first request.
