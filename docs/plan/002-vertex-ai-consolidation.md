# Plan: Consolidate All LLM Calls to Google Vertex AI

**Status:** Proposed
**Author:** tcuong1000
**Date:** 2026-04-21
**Depends on:** [unified-llm-module.md](./unified-llm-module.md)

## Goal

Route all cloud LLM calls through Google Vertex AI. One auth method (ADC), one billing account, one provider.

## Current State: 3 Cloud Providers + 3 Local Models

### Cloud LLM calls

| Caller | Provider | Model | Auth |
|---|---|---|---|
| Memory completion | Gemini (via litellm) | `gemini-3-flash-preview` | `GOOGLE_API_KEY` |
| Memory embedding | Gemini (via litellm) | `gemini-embedding-001` | `GOOGLE_API_KEY` |
| Knowledge graph | Anthropic (direct SDK) | `claude-sonnet-4-5-20251022` | `ANTHROPIC_API_KEY` |
| Plan agent | LangChain (auto-detect) | Gemini / Claude / GPT | `GOOGLE_API_KEY` or `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` |
| Bot chat | Gemini (direct SDK, TS) | `gemini-3-flash-preview` | `GOOGLE_API_KEY` |
| Bot audio | Gemini (direct SDK, TS) | `gemini-3-flash-preview` | `GOOGLE_API_KEY` |
| War-room agents | OpenCode CLI | `google-vertex/gemini-*` | ADC (gcloud) |

### Local models (stay local)

| Caller | Model | Purpose |
|---|---|---|
| Memory embedding | `all-MiniLM-L6-v2` | Vector search (when `embedding_backend=sentence-transformer`) |
| Knowledge embedding | `BAAI/bge-small-en-v1.5` | Knowledge graph chunk embedding |
| zvec_store | `microsoft/harrier-oss-v1-0.6b` | War-room message semantic search |

## Target State: Vertex AI Only

### Cloud LLM calls (all via Vertex)

| Caller | Vertex AI Model | litellm Prefix |
|---|---|---|
| Memory completion | Gemini 3 Flash | `vertex_ai/gemini-3-flash-preview` |
| Memory embedding | Gemini Embedding | `vertex_ai/text-embedding-005` |
| Knowledge graph | Claude on Model Garden | `vertex_ai/claude-sonnet-4-5-20251022` |
| Plan agent | Gemini 3 Flash | `vertex_ai/gemini-3-flash-preview` |
| Bot chat | Gemini 3 Flash | Direct SDK with Vertex endpoint |
| Bot audio | Gemini 3 Flash | Direct SDK with Vertex endpoint |
| War-room agents | Gemini (various) | Already on Vertex via OpenCode |

### Auth: ADC only

```bash
gcloud auth application-default login --project igot-studio
gcloud auth application-default set-quota-project igot-studio
export GOOGLE_VERTEX_LOCATION=global
```

No more `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` required for cloud calls. All auth goes through Application Default Credentials.

### Local models (unchanged)

Local SentenceTransformer models stay as-is. They run on-device with zero latency and zero cost. Replacing them with Vertex API calls would add ~200ms latency and per-request billing for no benefit.

## What Changes

### Python: unified module uses `vertex_ai/` prefix

```python
# shared/llm/config.py
DEFAULT_PROVIDER = "vertex_ai"
DEFAULT_COMPLETION_MODEL = "vertex_ai/gemini-3-flash-preview"
DEFAULT_EMBEDDING_MODEL = "vertex_ai/text-embedding-005"

# For Claude tasks (knowledge graph entity extraction)
CLAUDE_MODEL = "vertex_ai/claude-sonnet-4-5-20251022"
```

litellm handles Vertex AI auth via ADC automatically when the model prefix is `vertex_ai/`.

### Knowledge graph: Anthropic SDK -> litellm Vertex

**Before** (`dashboard/knowledge/llm.py`):
```python
import anthropic
client = anthropic.Anthropic(api_key=self.api_key)
response = client.messages.create(
    model="claude-sonnet-4-5-20251022",
    messages=[{"role": "user", "content": prompt}],
)
```

**After**:
```python
from shared.llm import get_completion
response = get_completion(
    prompt=prompt,
    model="vertex_ai/claude-sonnet-4-5-20251022",
    system=system_prompt,
)
```

Same Claude model, same quality, but routed through Vertex AI Model Garden. Auth via ADC instead of `ANTHROPIC_API_KEY`.

### Plan agent: LangChain model detection simplified

**Before** (`dashboard/plan_agent.py`):
```python
def detect_model():
    if os.environ.get("GOOGLE_API_KEY"):
        return "gemini-3-flash-preview", "google_genai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude-sonnet-4-20250514", "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "gpt-4o", "openai"
```

**After**:
```python
def detect_model():
    return "gemini-3-flash-preview", "google_vertexai"
    # Vertex AI auth via ADC — no API key checks needed
```

LangChain supports `google_vertexai` provider natively.

### Bot TypeScript: AI Studio -> Vertex endpoint

**Before** (`bot/src/agent-bridge.ts`):
```typescript
import { GoogleGenerativeAI } from '@google/generative-ai';
const genAI = new GoogleGenerativeAI(config.GOOGLE_API_KEY);
```

**After**:
```typescript
import { VertexAI } from '@google-cloud/vertexai';
const vertexAI = new VertexAI({
    project: config.VERTEX_PROJECT,
    location: config.VERTEX_LOCATION,
});
const model = vertexAI.getGenerativeModel({ model: config.GEMINI_MODEL });
```

Same Gemini model, same API shape, but authenticated via ADC. The `@google-cloud/vertexai` SDK is the Vertex equivalent of `@google/generative-ai`.

### Memory embedding: Gemini AI Studio -> Vertex

**Before** (`memory/retrievers.py`):
```python
litellm.embedding(model="gemini/gemini-embedding-001", input=texts)
```

**After**:
```python
litellm.embedding(model="vertex_ai/text-embedding-005", input=texts)
```

Model `text-embedding-005` is the latest Vertex embedding model. Higher quality than `gemini-embedding-001`.

## What Doesn't Change

| Component | Why |
|---|---|
| Local SentenceTransformer models | Zero latency, zero cost, run on-device |
| OpenCode `run` CLI | Already uses `google-vertex/` prefix |
| HuggingFace / Ollama / SGLang backends | Optional local backends, not cloud |
| Test mocks | Tests mock the unified interface, not the provider |

## API Keys: Before vs After

### Before (4 keys needed)

```bash
# ~/.ostwin/.env
GOOGLE_API_KEY=AIza...        # Memory, bot, plan_agent
ANTHROPIC_API_KEY=sk-ant-...  # Knowledge graph
OPENAI_API_KEY=sk-...         # Plan agent fallback
GOOGLE_VERTEX_LOCATION=global # War-room agents
```

### After (ADC only)

```bash
# One-time setup
gcloud auth application-default login --project igot-studio
gcloud auth application-default set-quota-project igot-studio

# ~/.ostwin/.env
GOOGLE_VERTEX_PROJECT=igot-studio
GOOGLE_VERTEX_LOCATION=global
# No API keys needed — ADC handles auth
```

## Claude on Vertex AI Model Garden

### Availability

Claude models are available on Vertex AI via the Model Garden in these regions:
- `us-east5` (Ohio)
- `europe-west1` (Belgium)
- `asia-southeast1` (Singapore)

**Not available in `global` region.** The knowledge graph calls that use Claude need to specify a supported region.

### Configuration

```python
# For Claude on Vertex
CLAUDE_VERTEX_LOCATION = "us-east5"  # Must be a region with Claude access

# litellm handles the routing
response = litellm.completion(
    model="vertex_ai/claude-sonnet-4-5-20251022",
    messages=[...],
    vertex_ai_location="us-east5",
)
```

### Pricing

Claude on Vertex uses the same per-token pricing as Anthropic direct, but billed through your Google Cloud account. No separate Anthropic billing.

### Fallback

If Claude is not available on Vertex (region not enabled, quota not provisioned), the unified module can fall back to Gemini for knowledge graph tasks:

```python
KNOWLEDGE_MODEL = os.environ.get(
    "KNOWLEDGE_LLM_MODEL",
    "vertex_ai/claude-sonnet-4-5-20251022"
)
# Falls back to Gemini if Claude isn't provisioned
KNOWLEDGE_MODEL_FALLBACK = "vertex_ai/gemini-3-flash-preview"
```

## Migration Phases

### Phase 1: Unified module with Vertex default

1. Build `shared/llm/` from [unified-llm-module.md](./unified-llm-module.md)
2. Set `vertex_ai/` as the default provider prefix
3. litellm handles ADC auth automatically
4. Tests pass with mocked providers (no real API needed)

### Phase 2: Memory system -> Vertex

1. Change `LLM_BACKEND` default from `gemini` to `vertex_ai`
2. Change embedding model from `gemini/gemini-embedding-001` to `vertex_ai/text-embedding-005`
3. Remove `GOOGLE_API_KEY` dependency from memory MCP config
4. Run 84 memory tests

### Phase 3: Knowledge graph -> Vertex Claude

1. Replace `anthropic.Anthropic()` with `get_completion(model="vertex_ai/claude-...")`
2. Remove `ANTHROPIC_API_KEY` dependency
3. Configure `vertex_ai_location` for Claude region
4. Run knowledge smoke tests

### Phase 4: Plan agent -> Vertex

1. Simplify `detect_model()` to always use Vertex
2. Change LangChain provider from `google_genai` to `google_vertexai`
3. Remove `OPENAI_API_KEY` fallback

### Phase 5: Bot TypeScript -> Vertex SDK

1. Replace `@google/generative-ai` with `@google-cloud/vertexai`
2. Update bot config: `GOOGLE_API_KEY` -> `VERTEX_PROJECT` + `VERTEX_LOCATION`
3. Auth via ADC (same as Python side)
4. Run 373 bot tests

### Phase 6: Cleanup

1. Remove `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` from install.sh env setup
2. Update AGENTS.md with new auth instructions
3. Remove `llm_controller.py` (6 dead classes)
4. Update MCP config templates

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Claude not provisioned on Vertex | Knowledge graph falls back to Gemini | Configurable `KNOWLEDGE_LLM_MODEL` with Gemini fallback |
| ADC not configured | All LLM calls fail | Clear error message + setup instructions in `ostwin init` |
| Vertex quota limits | Rate limiting under concurrent agents | Already handled — ostwin runs max ~12 agents per plan |
| `text-embedding-005` produces different vectors than `gemini-embedding-001` | Existing vector stores become incompatible | Run `consolidate_memories` once after migration to re-embed |
| Bot TypeScript SDK change | Breaking API differences | `@google-cloud/vertexai` has the same `generateContent` API shape |
| Region-specific Claude | Extra config needed | Default to `us-east5`, configurable via `VERTEX_CLAUDE_LOCATION` |

## Cost Impact

| Component | Before | After |
|---|---|---|
| Memory completion | AI Studio free tier / pay-per-use | Vertex pay-per-use (same pricing) |
| Memory embedding | AI Studio free tier | Vertex pay-per-use |
| Knowledge graph | Anthropic direct billing | Vertex billing (same per-token price) |
| Plan agent | Varies by provider | Vertex billing |
| Bot | AI Studio free tier | Vertex pay-per-use |
| Local embeddings | Free (on-device) | Free (unchanged) |

**Net effect:** Consolidates 3 billing accounts (Google AI Studio, Anthropic, OpenAI) into 1 (Google Cloud). Per-token pricing is comparable across all three. The main savings is operational simplicity, not raw cost.

## Decision Checklist

Before starting implementation:

- [ ] Verify Claude is available on Vertex in the target project (`igot-studio`)
- [ ] Verify `text-embedding-005` is available in the target region
- [ ] Decide whether to keep `GOOGLE_API_KEY` as a fallback for AI Studio (simpler dev setup)
- [ ] Decide whether bot TypeScript migration is Phase 5 or a separate PR
- [ ] Estimate vector re-embedding time for existing memory stores (depends on note count)
