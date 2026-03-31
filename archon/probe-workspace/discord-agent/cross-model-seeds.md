# Cross-Model Seeds: discord-agent

---

## CROSS-01: Prompt Injection + System Instruction Gap — Maximum Injection Reliability

Source-A: PH-01 from backward-reasoner (round-1-hypotheses.md) — Direct Prompt Injection via Discord @mention
Source-B: PH-11 from contradiction-reasoner (round-2-hypotheses.md) — Gemini user-role Conflation / System Instruction Bypass
Connection: Both target `agent-bridge.js:119-122`. PH-01 identifies that the user message is concatenated into the prompt. PH-11 explains WHY injection is so reliable: the Gemini SDK's `systemInstruction` field is not used, so the "system prompt" placed at the start of the user message has no structural authority over later injected instructions. PH-11's insight about `user` role conflation directly amplifies PH-01's exploitability — the attacker doesn't need to craft sophisticated bypass; any sufficiently assertive instruction succeeds.
Combined hypothesis: The combination of verbatim user input concatenation (PH-01) and absence of the Gemini `systemInstruction` API field (PH-11) means the "system prompt" block has exactly zero enforcement power. An attacker who sends a short, direct instruction override will succeed with near-certainty, without needing to escape or bypass any structural delimiter.
Test direction for causal-verifier: Verify that `getGenerativeModel({ model: geminiModel })` at agent-bridge.js:116 does not pass `systemInstruction`. Confirm that `generateContent` call at line 119 uses only `contents` with `role: 'user'`. The counterfactual: if `systemInstruction` were used, the system prompt would have structural authority. Absence of this field = confirmed vulnerability.

---

## CROSS-02: Second-Order Injection + encodeURIComponent False Safety — Persistent Injection via Search Results

Source-A: PH-02 from backward-reasoner (round-1-hypotheses.md) — Second-Order Prompt Injection via Attacker-Planted Plan Content
Source-B: PH-12 from contradiction-reasoner (round-2-hypotheses.md) — encodeURIComponent False Safety — Injection Preserved in Search Results
Connection: Both target the same data flow: attacker-planted FastAPI content → `semanticSearch()` results → `contextBlock` → Gemini prompt. PH-02 identifies the unauthenticated plan creation endpoint as the injection source. PH-12 identifies that `encodeURIComponent` on the search query does not sanitize the search RESULTS. Together they close the full attack chain: PH-02 explains how to plant content, PH-12 explains why that content survives into the prompt despite the URL encoding being applied.
Combined hypothesis: An attacker creates a plan via `POST /api/plans/create` (no auth) containing adversarial instructions. When any Discord user @mentions the bot with a query matching the planted content, `semanticSearch()` retrieves the planted message (line 70: `r.body.slice(0, 200)`) and injects it into the Gemini prompt as "Relevant Messages." The `encodeURIComponent` step only protects the URL parameter, not the response body content. The planted injection is persistent and triggers for any bot query — the original attacker need not be online.
Test direction for causal-verifier: Verify that `semanticSearch()` at agent-bridge.js:65-71 returns attacker-controlled content from planted plans. Confirm that search result bodies are inserted at line 111 without any sanitization. The counterfactual: if search results were sanitized or stripped of markdown before insertion, the injection would be neutralized.

---

## CROSS-03: Hardcoded Vault Key + World-Readable Vault File — Complete Secret Exposure

Source-A: PH-04 from backward-reasoner (round-1-hypotheses.md) — Vault Decryption via Known Hardcoded Key
Source-B: PH-20 from contradiction-reasoner (round-2-hypotheses.md) — Vault File World-Readable (Missing chmod)
Connection: Both target `~/.ostwin/mcp/.vault.enc` created by `EncryptedFileVault._save_data()` at vault.py:136-145. PH-04 establishes that the encryption key is publicly known when `OSTWIN_VAULT_KEY` is absent. PH-20 establishes that the vault file is world-readable (no `chmod 0600`). These two findings compound: the known key is necessary for decryption but the world-readable file makes the attack accessible to any local user without privilege escalation. Either finding alone is significant; together they represent trivial secret exposure for any co-tenant on the host.
Combined hypothesis: On a non-macOS multi-user server where `OSTWIN_VAULT_KEY` is unset, the vault file at `~/.ostwin/mcp/.vault.enc` is both world-readable (default umask) and decryptable with the publicly known key `base64.urlsafe_b64encode(b"ostwin-default-insecure-key-32ch")`. Any local user can: (1) read the file, (2) apply the Fernet key, (3) obtain all stored API tokens and secrets — with zero privileges beyond local shell access.
Test direction for causal-verifier: Check vault.py `_save_data()` for any `os.chmod()` or `os.umask()` call. Confirm absence. Verify `_get_encryption_key()` returns the hardcoded key when env var is absent. Counterfactual: if `open(self.path, 'wb')` were followed by `os.chmod(self.path, 0o600)`, the world-readable risk would be eliminated independently of the key issue.

---

## CROSS-04: from_role Dead Code + Memory Ledger Poisoning — Agent System Trust Collapse

Source-A: PH-07 from backward-reasoner (round-1-hypotheses.md) — channel-server from_role Manager Impersonation
Source-B: PH-17 from contradiction-reasoner (round-2-hypotheses.md) — Memory Ledger Poisoning via publish()
Connection: Both target the MCP layer's trust model for multi-agent communication. PH-07 shows that the channel log can be corrupted with fake manager commands (unvalidated `from_role`). PH-17 shows that shared memory can be poisoned with false architectural decisions (unvalidated `author_role` in `publish()`). Together they represent a complete trust collapse in the agent coordination system: an attacker (or a compromised/prompt-injected agent) can simultaneously forge channel commands AND poison the knowledge base that agents use for context. Agents have no way to distinguish legitimate from forged communications.
Combined hypothesis: A single compromised agent (or prompt-injected bot via PH-01 chain) can: (1) post fake manager task assignments to the channel via `post_message(from_role='manager')`, and (2) publish false architectural decisions to shared memory via `publish(author_role='architect')`. Other agents, seeing consistent "manager" and "architect" agreement across both channels, will act on the forged instructions with high confidence. This is a multi-channel influence attack against the agent coordination system.
Test direction for causal-verifier: Verify `from_role` is not validated in `channel-server.py:post_message()` AND `author_role` is not validated in `memory-server.py:publish()`. Confirm both values are written verbatim to their respective stores. The counterfactual: if either function validated its role parameter against a known-good list, the impersonation would require a different vector.

---

## CROSS-05: Discord @mention Prompt Injection Chain → DASHBOARD_URL Exfiltration Enablement

Source-A: PH-01 + PH-03 from backward-reasoner (round-1-hypotheses.md) — Direct Prompt Injection + API Key Exfiltration
Source-B: PH-11 from contradiction-reasoner (round-2-hypotheses.md) — System Instruction Bypass
Connection: PH-01/PH-11 establish that prompt injection fully controls LLM output. PH-03 establishes that DASHBOARD_URL must be poisoned to exfiltrate the API key. The connection: while PH-03 requires environment-level access to modify DASHBOARD_URL, PH-01/PH-11's injection can cause the LLM to output the API key if it appears in the context (e.g., if a future code change logs it, or if the bot has access to env variables via any tool). More immediately: prompt injection can instruct the bot to provide instructions for how to modify its own environment, or to relay information about what environment variables are set (e.g., `is OSTWIN_API_KEY set?`).
Combined hypothesis: Prompt injection (PH-01 + PH-11) gives an attacker control over LLM output. If the bot's context ever includes sensitive values (API keys, vault secrets via injected plans), the attacker can instruct the LLM to output them directly. Furthermore, if an attacker achieves DASHBOARD_URL compromise (PH-03) by other means (CI injection, .env write via unauthenticated FastAPI endpoint), they can silently exfiltrate the API key on the next bot interaction — no user action is visible.
Test direction for causal-verifier: Verify that `OSTWIN_API_KEY` never appears in the Gemini prompt context (it should not — it's in `headers` only, not in the contextBlock). If confirmed absent from prompt, PH-03 exfiltration requires separate DASHBOARD_URL compromise and cannot be achieved via prompt injection alone. This would scope PH-03 as requiring a separate prerequisite.

---

## CROSS-06: MCP room_dir Path Traversal + Memory Poisoning — Agent System Filesystem Takeover

Source-A: PH-06 from backward-reasoner (round-1-hypotheses.md) — MCP room_dir Path Traversal
Source-B: PH-17 from contradiction-reasoner (round-2-hypotheses.md) — Memory Ledger Poisoning
Connection: Both exploit the MCP stdio interface with no authentication. PH-06 allows writing arbitrary files to the filesystem via `warroom-server.py`. PH-17 allows writing false entries to the shared memory ledger. The combination: if `room_dir` can traverse to the memory ledger directory (`../../../../.agents/memory/`), the `update_status()` tool's writes (creating a `status` file there) would not directly corrupt the ledger. However, `report_progress()` writes a `progress.json` file — if the path is manipulated to write to a directory the memory system reads from, there's an indirect interaction. The more direct chain is: use `room_dir` traversal to overwrite actual war-room status files with falsified data.
Combined hypothesis: A compromised MCP client can: (1) use `room_dir` path traversal in `warroom-server.py` to write files outside the intended war-rooms directory, AND (2) use `publish()` to inject false decisions into shared memory. These two MCP trust gap exploits together allow full corruption of both the operational state (room status files) and the knowledge layer (memory ledger).
Test direction for causal-verifier: Verify that `os.path.join(room_dir, 'status')` in warroom-server.py:71 does NOT canonicalize or restrict `room_dir`. Test whether `room_dir = '../../../.agents/memory/'` causes files to be written under the memory directory. The counterfactual: if `room_dir` were validated with `os.path.realpath()` against a known allowed prefix, the traversal would be blocked.
