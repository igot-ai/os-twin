# Plan: Unified LLM Module

**Status:** Proposed
**Author:** tcuong1000
**Date:** 2026-04-21

## Problem

The codebase has **5 different ways** to call cloud LLMs and **3 different embedding integrations**, each with its own API key handling, error handling, model selection, retry logic, and timeout config.

### Current state

```
bot/agent-bridge.ts ────────── @google/generative-ai  (direct, TypeScript)
bot/audio-transcript.ts ────── @google/generative-ai  (direct, TypeScript)

memory/llm_controller.py ──── litellm.completion()    (6 controller classes)
                            ── openai.OpenAI()          (direct)
                            ── requests.post() to SGLang (raw HTTP)

memory/retrievers.py ────────── litellm.embedding()     (Gemini)
                              ── SentenceTransformer()    (local)

dashboard/knowledge/llm.py ── anthropic.Anthropic()     (direct)
dashboard/knowledge/embeddings.py ── SentenceTransformer() (local, different model)
dashboard/plan_agent.py ────── langchain.init_chat_model() (auto-detect)
                             ── deepagents.create_deep_agent()
dashboard/zvec_store.py ────── SentenceTransformer()     (local, yet another model)
```

### Concrete issues

1. **API keys checked in 4+ places** -- `GOOGLE_API_KEY` is read by memory, bot, plan_agent, and knowledge separately. No single source of truth.
2. **No shared retry/fallback** -- memory has retry in `llm_controller.py`, knowledge has none, plan_agent has its own fallback chain.
3. **6 controller classes for one function** -- `llm_controller.py` has `OpenAIController`, `OllamaController`, `SGLangController`, `OpenRouterController`, `HuggingFaceController`, `GeminiController`. All do the same thing: send a prompt, get text back.
4. **3 embedding models, no shared interface** -- memory uses `gemini-embedding-001`, knowledge uses `BAAI/bge-small-en-v1.5`, zvec_store uses `microsoft/harrier-oss-v1-0.6b`. Each loaded independently.
5. **Model names hardcoded** -- `gemini-3-flash-preview` appears in memory config, bot config, plan_agent, and role configs. Changing the default model requires edits in 4+ files.

## Proposed Solution

### New module: `shared/llm/`

```
shared/llm/
├── __init__.py          # Public API: get_completion(), get_embedding()
├── config.py            # Unified config: model, provider, API keys, timeouts
├── providers/
│   ├── __init__.py
│   ├── gemini.py        # Google Gemini (via litellm)
│   ├── anthropic.py     # Anthropic Claude (via litellm)
│   ├── openai.py        # OpenAI GPT (via litellm)
│   ├── local.py         # Ollama, SGLang, HuggingFace
│   └── embedding.py     # All embedding: Gemini, SentenceTransformer
├── retry.py             # Shared retry/timeout/fallback logic
└── registry.py          # Provider auto-detection from env vars
```

### Public API

Two functions. That's it.

```python
from shared.llm import get_completion, get_embedding

# Completion — works with any provider
response = get_completion(
    prompt="Extract keywords from this text...",
    model="gemini-3-flash-preview",      # optional, uses default
    response_format={"type": "json"},     # optional
    max_tokens=1000,                      # optional
    timeout=30,                           # optional
)

# Embedding — works with Gemini API or local SentenceTransformer
vectors = get_embedding(
    texts=["PostgreSQL indexing strategies"],
    model="gemini-embedding-001",         # or "all-MiniLM-L6-v2" for local
)
```

### Provider auto-detection

The module checks environment variables and picks the first available:

```python
# registry.py
def detect_provider() -> str:
    if os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    raise RuntimeError("No LLM API key found")
```

### Config unification

One config instead of 5:

```json
{
  "llm": {
    "default_model": "gemini-3-flash-preview",
    "default_embedding_model": "gemini-embedding-001",
    "fallback_chain": ["gemini", "anthropic", "openai"],
    "timeout_seconds": 30,
    "max_retries": 2
  }
}
```

Source priority:
1. Function call parameters (highest)
2. Environment variables (`LLM_MODEL`, `LLM_PROVIDER`)
3. Config file (`~/.ostwin/.env` or `config.json`)
4. Defaults (lowest)

## Migration Plan

### What changes

| Caller | Before | After |
|---|---|---|
| `memory/memory_system.py` | `self.llm_controller.llm.get_completion(prompt)` | `get_completion(prompt)` |
| `memory/retrievers.py` | `litellm.embedding(model=..., input=...)` | `get_embedding(texts, model=...)` |
| `memory/mcp_server.py` | Constructs `AgenticMemorySystem(llm_backend=..., llm_model=...)` | Constructs `AgenticMemorySystem()` (reads from unified config) |
| `dashboard/knowledge/llm.py` | `anthropic.Anthropic().messages.create(...)` | `get_completion(prompt, model="claude-...")` |
| `dashboard/knowledge/embeddings.py` | `SentenceTransformer(model).encode()` | `get_embedding(texts, model="local/bge-small-en-v1.5")` |
| `dashboard/zvec_store.py` | `SentenceTransformer(model).encode()` | `get_embedding(texts, model="local/harrier-oss-v1-0.6b")` |

### What gets deleted

| File | Lines | Reason |
|---|---|---|
| `memory/llm_controller.py` | ~500 | 6 controller classes replaced by unified module |
| Duplicate API key lookups | ~50 scattered | Single source in `shared/llm/config.py` |
| Provider-specific imports | ~30 scattered | Hidden behind `shared/llm/` |

### What stays unchanged

| Component | Reason |
|---|---|
| **Bot TypeScript** (`agent-bridge.ts`, `audio-transcript.ts`) | Different language, different runtime. Can't share Python module. |
| **`plan_agent.py` LangChain** (`init_chat_model`, `create_deep_agent`) | LangChain manages its own model lifecycle for tool-calling agent chains. Different pattern from simple prompt-in/text-out. |
| **OpenCode `run`** (CLI) | It's a process invocation, not an API call. The model is configured via `--model` flag and role config. |
| **Local models** (SentenceTransformer, HuggingFace, Ollama, SGLang) | Wrapped behind the same `get_embedding()` / `get_completion()` interface, but the underlying libraries stay. |

## Implementation Phases

### Phase 1: Core module (no callers changed yet)

1. Create `shared/llm/` with `get_completion()`, `get_embedding()`, config, and provider registry
2. Use `litellm` as the unified backend (it already supports Gemini, Anthropic, OpenAI, Ollama)
3. Write tests for the module itself
4. **No existing code changes** -- new module only

### Phase 2: Memory system migration

1. Replace `llm_controller.py` usage in `memory_system.py` with `get_completion()`
2. Replace `GeminiEmbeddingFunction` / `SentenceTransformerEmbeddingFunction` in `retrievers.py` with `get_embedding()`
3. Delete `llm_controller.py` (6 classes)
4. Update `mcp_server.py` to use unified config
5. Run all 84 memory tests

### Phase 3: Knowledge graph migration

1. Replace `KnowledgeLLM._complete()` in `knowledge/llm.py` with `get_completion()`
2. Replace `KnowledgeEmbedder` in `knowledge/embeddings.py` with `get_embedding()`
3. Run knowledge smoke tests

### Phase 4: Dashboard embedding migration

1. Replace `SentenceTransformer` in `zvec_store.py` with `get_embedding()`
2. Run dashboard tests

### Phase 5: Cleanup

1. Remove orphaned imports
2. Update docs
3. Verify all tests pass

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Breaking memory system | High -- agents lose memory | 80 unit + 4 integration tests verify behavior before and after |
| Breaking knowledge graph | Medium -- KG search stops working | Knowledge smoke tests (18) cover entity extraction and query |
| Breaking plan agent | Low -- plan_agent keeps LangChain | Minimal change (only if we decide to migrate it) |
| Provider-specific features lost | Medium -- Anthropic `system` param, Gemini `response_format` | Provider adapters handle translation of provider-specific params |
| litellm version dependency | Low -- already a dependency | Pin version in requirements.txt |
| Performance regression | Low -- one extra function call layer | Negligible overhead (nanoseconds vs seconds for API calls) |

## Size Estimate

| Component | Lines |
|---|---|
| `shared/llm/` module (new) | ~300 |
| Delete `llm_controller.py` | -500 |
| Update memory callers | ~20 changes |
| Update knowledge callers | ~15 changes |
| Update embedding callers | ~10 changes |
| Tests for unified module | ~100 |
| **Net change** | **~-100 lines** |

## Decision Criteria

This refactor is worth doing if:

- [x] Multiple modules call LLMs (yes: 5 Python + 2 TypeScript)
- [x] API key management is duplicated (yes: 4+ places)
- [x] Model names are hardcoded in multiple files (yes)
- [x] No shared retry/fallback logic (yes)
- [x] Existing tests cover all callers (yes: 457+ tests)
- [x] The unified interface is simpler than what exists (yes: 2 functions vs 6 classes)

## Open Questions

1. **Should `plan_agent.py` migrate?** It uses LangChain's `init_chat_model` which returns a `BaseChatModel` used in agent chains. The unified module returns raw text. These are different patterns. Recommendation: leave `plan_agent.py` on LangChain for now, but have it read model/provider config from the unified config.

2. **Should the bot TypeScript code use the same config?** It can't import a Python module, but it could read the same `~/.ostwin/.env` config for model names and API keys. Recommendation: yes, unify the config file; no, don't try to share code across languages.

3. **Should local models (SentenceTransformer) go through litellm?** litellm doesn't support local SentenceTransformer. Recommendation: keep local embedding as a separate code path inside `shared/llm/embedding.py`, selected by a `local/` model prefix.

4. **Should we keep backward compatibility for `llm_backend` config?** The memory system's `config.default.json` has `llm_backend: "gemini"` and `embedding_backend: "gemini"`. Recommendation: support these as aliases during transition, log a deprecation warning.
