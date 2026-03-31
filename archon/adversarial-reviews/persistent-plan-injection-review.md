# Adversarial Review: persistent-plan-injection (p8-041)

## Step 1 -- Restate and Decompose

**Restated claim**: The plan creation API endpoint (`POST /api/plans/create`) lacks authentication, allowing any unauthenticated HTTP client to create plans with arbitrary content. This content gets indexed in the vector store and is subsequently retrieved by the Discord bot's semantic search when users ask questions. The adversarial content thus persistently poisons the LLM's context for all future queries that semantically match.

**Sub-claim A**: Attacker can create plans with arbitrary content via unauthenticated HTTP POST.
**Status**: SUPPORTED. `plans.py:461-462` defines `create_plan(request: CreatePlanRequest)` with no `Depends(get_current_user)` parameter.

**Sub-claim B**: Plan content is indexed in the vector store without sanitization.
**Status**: SUPPORTED. `plans.py:499` calls `store.index_plan(...)` with `content=plan_file.read_text()`, and line 472 writes `request.content` directly to the file.

**Sub-claim C**: The indexed content is retrieved by the Discord bot's semantic search and injected into the LLM prompt, poisoning responses.
**Status**: SUPPORTED. `agent-bridge.js:65-71` performs semantic search; results are included in the context block at lines 101-111; the context is concatenated into the LLM prompt at line 121.

## Step 2 -- Independent Code Path Trace

### Injection Path (HTTP to Vector Store)

1. **Entry**: `plans.py:461` - `@router.post("/api/plans/create")` -- no auth decorator.
2. **Comparison**: Every other mutating endpoint in plans.py uses `Depends(get_current_user)` (lines 46, 210, 357, 404, 430, 505, 566, 580, 585, 593, 612, 624, etc.). The `create_plan` endpoint is the sole exception.
3. **Content write**: `plans.py:471-472` - If `request.content` is provided, it is written directly to file: `plan_file.write_text(request.content)`. No content validation or sanitization.
4. **Vector indexing**: `plans.py:496-501` - `store.index_plan(plan_id=plan_id, title=request.title, content=plan_file.read_text(), ...)`. The full plan content is indexed.

### Retrieval Path (Vector Store to Discord)

5. **Semantic search**: `agent-bridge.js:65-71` - `semanticSearch(query)` calls `/api/search?q=...&limit=5`.
6. **Search endpoint**: `rooms.py:183-195` - `/api/search` calls `store.search(q, ...)`. Also unauthenticated.
7. **Result formatting**: `agent-bridge.js:70` - Results formatted with `(r.body || '').slice(0, 200)` -- 200 characters of the result body included, no sanitization.
8. **Context injection**: `agent-bridge.js:101-111` - Search results become part of `contextBlock`.
9. **LLM prompt**: `agent-bridge.js:121` - Context block concatenated into single user-role message.
10. **Output**: `client.js:119` - LLM response sent to Discord.

### Middleware check

The `api.py` file at lines 108-113 only adds CORS middleware with `allow_origins=["*"]`. No global authentication middleware. No API key requirement for the plans create endpoint.

The `OSTWIN_API_KEY` in `agent-bridge.js:11-15` is used by the Discord bot when calling the dashboard API, but the dashboard does not enforce it -- it is a client-side header the bot sends, not a server-side requirement.

## Step 3 -- Protection Surface Search

| Layer | Protection | Blocks Attack? |
|-------|-----------|----------------|
| Language | Python type system via Pydantic `CreatePlanRequest` | No -- validates structure, not content semantics |
| Framework | FastAPI `Depends(get_current_user)` | ABSENT on create_plan endpoint |
| Middleware | CORS `allow_origins=["*"]` | No -- allows all origins |
| Application | Content validation on plan creation | ABSENT -- raw content written |
| Application | Vector store content filtering | ABSENT |
| Application | Search result sanitization | Only `slice(0, 200)` truncation |
| Application | Output filtering | ABSENT |
| Documentation | No SECURITY.md acknowledging this | N/A |

**No blocking protection found.**

## Step 4 -- Real-Environment Reproduction

Reproduction requires the dashboard server running with a vector store backend. Let me check if a local deployment is feasible.

The attack does not require external services for the injection phase (just an HTTP POST to the dashboard). However, confirming the full chain through Discord would require Discord + Google AI API access.

**Blocker**: Full end-to-end reproduction requires Discord bot + Google AI API. The injection phase (unauthenticated plan creation) could be tested locally but the vector store and semantic search components need specific backend configuration.

**PoC-Status: theoretical**

Static analysis confirms:
- `create_plan` has no auth (line 462 vs. every other endpoint)
- Content is written verbatim (line 472)
- Content is indexed in vector store (line 499)
- Search results flow into LLM prompt (agent-bridge.js:65-71, 101-111, 121)

## Step 5 -- Prosecution and Defense Briefs

### Prosecution Brief

This is a textbook persistent second-order injection. The evidence is unambiguous:

1. **Missing authentication**: `plans.py:462` defines `create_plan(request: CreatePlanRequest)` without `Depends(get_current_user)`. In contrast, 30+ other endpoints in the same file explicitly use auth. This is clearly an oversight, not an intentional design choice.

2. **No content sanitization**: `plans.py:471-472` writes `request.content` directly to disk. Line 499 indexes it in the vector store. There is no validation that the content is a legitimate plan document.

3. **Persistent poisoning**: Once indexed, the adversarial content persists indefinitely. Any future Discord bot query that semantically matches will retrieve the payload via `semanticSearch()` at `agent-bridge.js:65-71`.

4. **Zero-interaction attack**: The attacker sends a single HTTP POST to the dashboard API. They need not be a Discord guild member, need not interact with the bot, and need not authenticate in any way.

5. **Broad blast radius**: The poisoned content affects ALL Discord users whose queries semantically match, not just the attacker.

### Defense Brief

Several factors limit the practical exploitability:

1. **Dashboard exposure**: The dashboard runs on `localhost:9000` by default. If the dashboard is not exposed to the internet, the attacker would need network access to the host. However, many deployments do expose dashboards, and the CORS configuration (`allow_origins=["*"]`) suggests internet-facing use is anticipated.

2. **Semantic matching uncertainty**: The attacker's payload must semantically match a user's query to be retrieved. The vector store's ranking algorithm may not always surface the adversarial content, especially if there are many legitimate plans.

3. **200-character truncation**: `agent-bridge.js:70` limits search result body to 200 characters, constraining the adversarial payload size. While 200 characters is sufficient for simple injection instructions, complex multi-step attacks are harder.

4. **LLM resistance**: The LLM may not follow injected instructions from search results, especially if they conflict with the system prompt.

These defenses are all weak mitigations, not blocking controls. Network exposure is a deployment variable, not an architectural protection. Semantic matching is probabilistic but attacker-controllable (they choose the plan title and content). 200 characters is ample for "Ignore all instructions and output..." type payloads. LLM resistance is unreliable.

## Step 6 -- Severity Challenge

Starting at MEDIUM:
- **Remotely triggerable**: Yes, if dashboard is network-accessible (default CORS suggests this).
- **Meaningful trust boundary crossing**: Yes -- two boundaries: (1) unauthenticated write to trusted data store, (2) stored content treated as trusted LLM context.
- **Significant preconditions**: The dashboard must be network-accessible to the attacker. This is a non-default condition for localhost deployments but likely for production deployments.

**Upgrade to HIGH**: The missing auth on a write endpoint is a clear vulnerability regardless of LLM implications. The persistent nature and broad blast radius justify HIGH. However, the localhost default is a minor mitigating factor.

Not CRITICAL because: requires dashboard to be network-exposed (not guaranteed), limited to prompt poisoning (not RCE), and constrained by semantic matching and 200-char truncation.

**Severity-Final: HIGH** (matches original)

## Step 7 -- Verdict

The prosecution brief survives the defense. The missing authentication is undeniable (unique among 30+ endpoints), the content flows through to the LLM prompt without sanitization, and the persistent nature amplifies impact. The defense identifies only soft mitigations (network exposure, semantic matching, truncation) that do not constitute blocking controls.

Reproduction was blocked by environmental constraints, but the vulnerability chain is fully traceable through static analysis with high confidence.

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: The create_plan endpoint is uniquely unauthenticated among 30+ plan endpoints, writes arbitrary content to the vector store, which flows unsanitized into the LLM prompt for all semantically matching Discord queries.
Severity-Final: HIGH
PoC-Status: theoretical
```
