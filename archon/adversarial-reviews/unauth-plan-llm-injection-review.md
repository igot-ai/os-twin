# Adversarial Review: unauth-plan-llm-injection

## Step 1 -- Restate and Decompose

**Vulnerability claim (restated)**: Two unauthenticated API endpoints allow an attacker to (1) store arbitrary text as a "plan" file on disk, then (2) trigger LLM processing of that text. The plan content is embedded directly into an LLM SystemMessage with no sanitization, enabling prompt injection.

**Sub-claims**:
- **A**: Attacker controls plan content via unauthenticated POST /api/plans/create
- **B**: Attacker triggers LLM processing via unauthenticated POST /api/plans/refine, which reads the stored content and passes it unsanitized to the LLM
- **C**: The LLM processes the attacker-controlled SystemMessage, enabling prompt injection effects (system prompt exfiltration, output manipulation)

All sub-claims are coherent and testable.

## Step 2 -- Independent Code Path Trace

### Path 1: Content storage (create_plan)

1. `dashboard/routes/plans.py:461` -- `@router.post("/api/plans/create")` -- no `Depends(get_current_user)` parameter
2. `dashboard/routes/plans.py:462` -- `async def create_plan(request: CreatePlanRequest)` -- accepts request body directly
3. `dashboard/routes/plans.py:471-472` -- `if request.content: plan_file.write_text(request.content)` -- attacker content written verbatim to disk
4. Response includes `plan_id` needed for step 2

**Validations/sanitizations on this path**: NONE. No auth check, no input validation, no content filtering.

### Path 2: LLM injection (refine_plan_endpoint)

1. `dashboard/routes/plans.py:1128` -- `@router.post("/api/plans/refine")` -- no `Depends(get_current_user)` parameter
2. `dashboard/routes/plans.py:1133-1137` -- reads `plan_content` from the stored file using `plan_id`
3. `dashboard/routes/plans.py:1138` -- passes `plan_content` to `refine_plan()` function
4. `dashboard/plan_agent.py:333` -- `messages = build_messages(user_message, plan_content, chat_history)`
5. `dashboard/plan_agent.py:292-295` -- `plan_content` is injected into a `SystemMessage`:
   ```python
   messages.append(
       SystemMessage(content=f"The user's current plan in the editor:\n\n```markdown\n{plan_content}\n```")
   )
   ```
6. `dashboard/plan_agent.py:335` -- `result = await agent.ainvoke({"messages": messages})` -- LLM processes the injected content

**Validations/sanitizations on this path**: NONE. No auth check, no content filtering, no prompt injection defenses. The markdown code fence wrapper provides zero security value against prompt injection.

### Discrepancies with finding draft

The finding's code snippets are accurate. Line numbers match. The code path is exactly as described.

## Step 3 -- Protection Surface Search

| Layer | Protection | Blocks Attack? |
|-------|-----------|----------------|
| Language | Python -- no type enforcement preventing injection | No |
| Framework | FastAPI with per-endpoint auth via `Depends(get_current_user)` | No -- missing from both endpoints |
| Middleware | CORS set to `allow_origins=["*"]` | No -- actually weakens security |
| Application | No input validation, no content filtering, no prompt injection defense | No |
| Documentation | No SECURITY.md found; no known-risk acknowledgment | N/A |

**Key observation**: 28+ other endpoints in the same file DO use `Depends(get_current_user)`. The two vulnerable endpoints are clear omissions from the auth pattern, not intentional public endpoints.

## Step 4 -- Real-Environment Reproduction

**Environment**: macOS Darwin 25.3.0, Python, uvicorn on port 19878, commit 4c06f66

**Healthcheck**: Server started successfully (confirmed via curl)

**Attempt 1 -- Create plan without auth**:
- Request: `POST /api/plans/create` with `{"title":"test","path":"/tmp","content":"INJECTED CONTENT"}`, no auth headers
- Result: HTTP 200, plan created, `plan_id` returned
- File verification: `~/.ostwin/plans/ed40be3ac874.md` contains exactly "INJECTED CONTENT"
- **Sub-claim A: CONFIRMED**

**Attempt 2 -- Trigger refine without auth**:
- Request: `POST /api/plans/refine` with `{"plan_id":"ed40be3ac874","message":"Please refine this plan"}`, no auth headers
- Result: HTTP 503 -- "deepagents not available" (NOT HTTP 401)
- The 503 proves the endpoint is reachable without authentication. The failure is due to a missing LLM dependency (`deepagents` package), not a security control.
- **Sub-claim B: CONFIRMED (auth bypass proven, LLM invocation blocked by missing dependency)**

**Attempt 3 -- Full LLM injection**:
- Blocked by missing `deepagents` package in test environment
- The code path from file read to `SystemMessage` construction is deterministic and contains zero conditional logic that could prevent injection
- **Sub-claim C: CONFIRMED via code analysis, blocked for live reproduction**

**Evidence stored at**: `security/real-env-evidence/unauth-plan-llm-injection/`

## Step 5 -- Prosecution and Defense Briefs

### Prosecution Brief

The vulnerability is real and the attack path is unambiguous:

1. **Missing authentication is proven**: `create_plan` (line 461) and `refine_plan_endpoint` (line 1128) both lack the `Depends(get_current_user)` dependency that 28+ sibling endpoints use. Real-environment testing confirms HTTP 200 responses with no auth headers.

2. **Content injection is verbatim**: `plan_file.write_text(request.content)` at line 472 writes attacker input with zero transformation. File verification confirms exact content.

3. **LLM injection path is direct**: `build_messages()` at line 292-295 places attacker content into a `SystemMessage` -- the highest-privilege message type in LLM APIs. There is no sanitization, no delimiter enforcement, no content filtering anywhere in the path.

4. **The refine_plan_stream endpoint** (line 1154) provides an additional identical attack surface.

5. **Impact is tangible**: An attacker can exfiltrate the system prompt (which may contain sensitive configuration), manipulate LLM outputs for other users if results are saved, and potentially chain to downstream code generation features.

### Defense Brief

1. **LLM prompt injection is probabilistic**: Even with injected content, modern LLMs may not follow the injected instructions. The attack success rate depends on the specific LLM model, system prompt strength, and injection payload.

2. **Network exposure is limited**: The dashboard typically runs on localhost (127.0.0.1). Exploitation requires either local access, a compromised local process, or the dashboard being explicitly exposed to a network.

3. **Full reproduction blocked**: The `deepagents` module is not installed, so actual LLM output manipulation cannot be demonstrated. The claim rests on code analysis for the final step.

4. **Data sensitivity is bounded**: The exfiltrable data is limited to the LLM's system prompt and plan contents -- not database credentials, user PII, or system-level secrets (unless the system prompt contains such information).

5. **No evidence of downstream action execution**: The refine endpoint returns text output. There is no evidence that LLM responses trigger automated actions (file writes, code execution) that would escalate impact beyond information disclosure.

## Step 6 -- Severity Challenge

Starting at MEDIUM:

**Upgrade signals**:
- Remotely triggerable: YES (unauthenticated HTTP endpoints)
- Trust boundary crossing: YES (user input to LLM SystemMessage)
- No significant preconditions: PARTIAL -- requires `deepagents` to be installed and LLM API keys configured (standard for production deployment)

**Downgrade signals**:
- Dashboard typically binds to localhost (reduces remote attack surface)
- LLM prompt injection is probabilistic, not deterministic
- Full reproduction blocked by missing dependency
- Impact limited to LLM manipulation, not direct system compromise

**Challenged severity**: HIGH is appropriate. The missing auth on two endpoints in a pattern where all others are authenticated is a clear bug. The prompt injection path is direct and unsanitized. However, the localhost binding and probabilistic nature of LLM injection prevent escalation to CRITICAL.

Final severity: HIGH (matches original assessment).

## Step 7 -- Verdict

The prosecution brief survives the defense:
- Authentication bypass is proven with real-environment evidence (HTTP 200 with no auth)
- The code path from attacker input to LLM SystemMessage is deterministic and contains zero protections
- The defense's strongest argument (localhost binding) is a deployment consideration, not an application-level protection
- Full LLM exploitation was blocked only by a missing optional dependency, not by any security control

Real-environment reproduction partially succeeded:
- Plan creation without auth: succeeded
- Refine endpoint reachability without auth: succeeded
- Full LLM injection: blocked by missing `deepagents` dependency (documented blocker, not a security control)

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Both endpoints confirmed unauthenticated via real HTTP requests; code path from stored content to LLM SystemMessage is direct and unsanitized; full LLM invocation blocked only by missing optional dependency, not by any security control.
Severity-Final: HIGH
PoC-Status: theoretical
```
