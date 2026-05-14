# Plan 008: Restore AI Gateway + Memory Pool Integration

**Status:** Draft
**Date:** 2026-05-04
**Depends on:** Plan 006 (AI gateway), Plan 007 (HTTP transport)
**Problem:** Paul's commits (`596f85db`, `1bc56158`, `11d90499`, `8f90170e`) overwrote Plan 006 and partially broke Plan 007. The memory system is back to using `llm_controller.py` (6 controller classes, litellm direct calls) instead of the centralized `dashboard/ai/` gateway.

---

## Current State (broken)

Two completely separate AI stacks with zero code sharing:

```
Memory System (.agents/memory/)          Dashboard AI Gateway (dashboard/ai/)
┌─────────────────────────────┐          ┌──────────────────────────────┐
│ llm_controller.py (563 ln)  │          │ dashboard/llm_client.py      │
│  6 controller classes:      │          │  native SDK abstraction      │
│  - GeminiController→litellm │          │  OpenAI, Google, Anthropic   │
│  - OllamaController→litellm│          │                              │
│  - OpenAIController→openai  │          │ dashboard/ai/completion.py   │
│  - OpenRouterController     │          │  → llm_client.create_client()│
│  - HuggingFaceController    │          │                              │
│  - SGLangController→HTTP    │          │ dashboard/ai/config.py       │
├─────────────────────────────┤          │  → MasterSettings + env vars │
│ retrievers.py (817 ln)      │          ├──────────────────────────────┤
│  4 embedding classes:       │          │ dashboard/knowledge/         │
│  - SentenceTransformer      │          │   embeddings.py              │
│  - GeminiEmbedding→litellm  │          │   KnowledgeEmbedder          │
│  - OllamaEmbedding→ollama   │          └──────────────────────────────┘
│  - VertexEmbedding→genai    │
├─────────────────────────────┤               NOT CONNECTED
│ config.py (269 ln)          │          ←─────────────────────→
│  own config chain:          │
│  config.default.json        │
│  + ~/.ostwin/.agents/config  │
│  + MEMORY_* env vars        │
└─────────────────────────────┘
```

### What's broken

| Issue | Source | Impact |
|---|---|---|
| `_ensure_correct_interpreter()` not guarded | Paul's merge reverted the `__name__` guard | Dashboard crashes when importing `mcp_server.py` for HTTP pool |
| `config.default.json` missing `pool` section | Paul's merge deleted it | Pool config not settable via JSON (falls back to defaults — functional but not configurable) |
| `llm_controller.py` still exists (563 lines) | Plan 006 never completed/was reverted | 6 redundant LLM controller classes duplicating gateway logic |
| `retrievers.py` uses litellm/ollama/genai directly | Plan 006 reverted | 4 redundant embedding classes duplicating gateway logic |
| Two separate config chains | Never unified | Memory system ignores `MasterSettings` provider config; dashboard AI gateway ignores `MEMORY_*` env vars |

### What Paul's commits added (must keep)

| Feature | Files | Why it matters |
|---|---|---|
| New `LLMController` with more backends | `llm_controller.py` | Added SGLang, HuggingFace, improved Gemini — but should be replaced by gateway, not kept |
| Memory config reads `~/.ostwin/.agents/config.json` | `config.py` | Dashboard settings integration — **keep this** |
| `VertexEmbeddingFunction` (google.genai SDK) | `retrievers.py` | Direct Vertex AI embedding — should route through gateway instead |
| Process termination + PID management | `Invoke-Agent.ps1`, `ManagerLoop-Helpers.psm1` | Agent lifecycle — **keep all of this** |
| Memory system hot-reload from dashboard | `mcp_server.py` config-dirty flag | Settings changes apply without restart — **keep this** |
| Pool improvements (cleanup thread tracking) | `memory_pool.py` | Better cleanup — **keep this** |
| `memory_mcp.py` plan_id routing | `memory_mcp.py` | Plan-based namespace isolation — **keep this** |

---

## Target State

```
Memory System (.agents/memory/)          Dashboard AI Gateway (dashboard/ai/)
┌─────────────────────────────┐          ┌──────────────────────────────┐
│ memory_system.py            │          │ dashboard/ai/__init__.py     │
│  → get_completion()  ───────┼────────→ │  get_completion()            │
│  → get_embedding()   ───────┼────────→ │  get_embedding()             │
│                             │          │                              │
│ retrievers.py               │          │ dashboard/ai/completion.py   │
│  embed_fn = get_embedding   │          │  → llm_client → providers    │
│  (no more 4 classes)        │          │                              │
│                             │          │ dashboard/ai/config.py       │
│ config.py                   │          │  → MasterSettings            │
│  reads purpose='memory'  ───┼────────→ │  → memory_model field        │
│  from gateway config        │          └──────────────────────────────┘
├─────────────────────────────┤
│ ❌ llm_controller.py DELETED│
│ (563 lines removed)         │
└─────────────────────────────┘
```

One stack. All LLM/embedding calls go through `dashboard/ai/`. The memory system specifies `purpose='memory'` to get the right model. Config flows from `MasterSettings` → `dashboard/ai/config.py` → memory system.

---

## Changes

### Phase 1: Fix Plan 007 breaks (no logic changes)

**1.1 Guard `_ensure_correct_interpreter()`**

```python
# mcp_server.py line 66
# Before (Paul's revert):
_ensure_correct_interpreter()

# After:
if __name__ == "__main__":
    _ensure_correct_interpreter()
```

**1.2 Restore `pool` section in `config.default.json`**

```json
{
  "pool": {
    "idle_timeout_s": 300,
    "max_instances": 10,
    "eviction_policy": "lru",
    "ml_preload": true,
    "ml_ready_timeout_s": 30,
    "sync_interval_s": 60,
    "sync_on_kill": true,
    "allowed_paths": null,
    "sweep_interval_s": 30
  }
}
```

### Phase 2: Wire memory system to gateway (no fallback — gateway is mandatory)

**Design decision:** All AI calls go through `dashboard/ai/` — no litellm fallback, no `llm_controller.py` fallback. Stdio mode also calls the gateway over HTTP (`POST /api/ai/complete`, `POST /api/ai/embed`). This means the dashboard must be running for memory to work. This is intentional:
- One call path, one config, one monitoring surface
- Users can see every LLM/embedding call in the AI Monitor
- No hidden litellm calls that bypass the gateway

**2.1 `memory_system.py` — replace `llm_controller` with gateway**

3 call sites to change:

| Location | Before | After |
|---|---|---|
| `analyze_content()` | `self.llm_controller.llm.get_completion(prompt, response_format=...)` | `get_completion(prompt, purpose='memory', response_format=...)` |
| `_llm_resolve_conflict()` | `self.llm_controller.llm.get_completion(prompt)` | `get_completion(prompt, purpose='memory')` |
| `_get_evolution_decision()` | `self.llm_controller.llm.get_completion(prompt, response_format=...)` | `get_completion(prompt, purpose='memory', response_format=...)` |

Import change:
```python
# Before:
from .llm_controller import LLMController

# After:
from dashboard.ai import get_completion
```

Remove `self.llm_controller` from `__init__`. Remove `llm_backend`, `llm_model`, `api_key`, `sglang_host`, `sglang_port` constructor params (gateway handles provider selection via config).

**For stdio mode:** `mcp_server.py` imports the gateway. Since `mcp_server.py` runs as a subprocess, it needs `dashboard/` on `sys.path`. The `_ensure_correct_interpreter()` already adds the right venv. Add `dashboard/` to `sys.path` alongside the existing `sys.path` manipulation in `mcp_server.py`. If the dashboard is not running, stdio mode will fail with a clear error.

**2.2 `retrievers.py` — replace 4 embedding classes with `get_embedding()`**

| Before (4 classes, 4 SDKs) | After (1 call) |
|---|---|
| `SentenceTransformerEmbedding` (local) | `get_embedding(texts, model='local/<model>')` |
| `GeminiEmbeddingFunction` (litellm) | `get_embedding(texts, purpose='memory')` |
| `OllamaEmbeddingFunction` (ollama SDK) | `get_embedding(texts, purpose='memory')` |
| `VertexEmbeddingFunction` (google.genai) | `get_embedding(texts, purpose='memory')` |

The `ZvecRetriever` and `ChromaRetriever` constructors receive an `embed_fn` callable instead of instantiating a class based on `embedding_backend`.

```python
from dashboard.ai import get_embedding

def _make_embed_fn():
    """Return an embedding function that routes through the gateway."""
    def embed(texts):
        return get_embedding(texts, purpose='memory')
    return embed
```

Delete the 4 embedding classes. The `_truncate_to_dim()` logic moves into the gateway's embedding handler or stays as a post-processing step.

**2.3 `config.py` — simplify, defer to gateway config**

Remove `llm` and `embedding` sections from `MemoryConfig` — the gateway owns model selection. Keep `vector`, `search`, `evolution`, `sync`, `disabled_tools`, `pool` sections.

The memory system no longer needs to know which LLM provider or embedding model to use. It just calls `get_completion(purpose='memory')` and the gateway resolves the model from `MasterSettings.ai.memory_model`.

```python
# Fields REMOVED from MemoryConfig:
#   llm: LLMConfig        → gateway handles this
#   embedding: EmbeddingConfig  → gateway handles this

# Fields KEPT:
#   vector: VectorConfig
#   search: SearchConfig
#   evolution: EvolutionConfig
#   sync: SyncConfig
#   disabled_tools: list
#   pool: PoolConfig (for HTTP transport)
```

### Phase 3: Delete dead code

**3.1 Delete `llm_controller.py`**

563 lines. 6 controller classes. All replaced by one `get_completion()` call. No fallback. Delete it.

**3.2 Delete embedding classes from `retrievers.py`**

Remove `SentenceTransformerEmbedding`, `GeminiEmbeddingFunction`, `OllamaEmbeddingFunction`, `VertexEmbeddingFunction`. ~200 lines.

**3.3 Remove direct litellm imports from `memory_system.py`**

The `_ensure_ml_imports()` currently lazy-imports `litellm.completion`. Remove it. The gateway handles its own imports.

**3.4 Remove litellm from memory system dependencies**

Remove `litellm` from `.agents/memory/pyproject.toml` (or `requirements.txt`). It's a `dashboard/` dependency only (used by `dashboard/ai/` internally if needed), not a memory system dependency.

### Phase 4: Tests

**4.1 Update mock targets**

All tests that mock `llm_controller.llm.get_completion` change to mock `dashboard.ai.get_completion`:

```python
# Before:
with patch.object(system.llm_controller.llm, 'get_completion', return_value='...')

# After:
with patch('dashboard.ai.get_completion', return_value='...')
```

**4.2 Update mock targets for embeddings**

Tests that mock embedding classes change to mock `dashboard.ai.get_embedding`.

**4.3 Keep test_llm_controller.py**

Keep it but mark as skipped/deprecated — tests the old code that no longer runs. Remove in a follow-up cleanup.

**4.4 New test: verify gateway is the only AI call path**

```python
def test_no_direct_litellm_imports():
    """memory_system.py must not import litellm directly."""
    import ast
    source = Path('agentic_memory/memory_system.py').read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert 'litellm' not in alias.name
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or 'litellm' not in node.module
```

---

## Verification

```bash
# 1. Plan 007 still works (HTTP pool)
curl -s http://localhost:3366/api/memory-pool/health | python3 -m json.tool

# 2. Save a memory — ALL calls go through dashboard/ai/
curl -s -X POST 'http://localhost:3366/api/memory-pool/mcp?plan_id=test' \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"save_memory","arguments":{"content":"Test note for gateway verification."}}}'
# Dashboard AI monitor should show the completion + embedding calls

# 3. AI Monitor shows memory calls
curl -s http://localhost:3366/api/ai/stats
# Should include memory-purpose calls

# 4. No litellm in memory system
grep -r "import litellm" .agents/memory/agentic_memory/memory_system.py
# Should return nothing

# 5. llm_controller.py is deleted
ls .agents/memory/agentic_memory/llm_controller.py
# Should return "No such file"

# 6. All tests pass
cd .agents/memory && python -m pytest tests/ -v
```

---

## Risk Mitigation

| Risk | Mitigation |
|---|---|
| Dashboard must be running for memory | This is already true for HTTP mode (Plan 007). For stdio: document that dashboard is required. Memory is useless without the dashboard anyway (no agent orchestration). |
| Paul's features break | Keep all PID/process management, config.py settings integration, memory_mcp plan_id routing. Only change the AI calling path. |
| Config simplification breaks something | `MEMORY_*` env vars for model selection are removed. Model selection goes through `MasterSettings.ai.memory_model`. Document the migration. |
| Tests break | Update all mock targets from `llm_controller` to `dashboard.ai`. No dual-path complexity. |

---

## Files Changed

| File | Change | Lines |
|---|---|---|
| `.agents/memory/mcp_server.py` | Guard `_ensure_correct_interpreter`, add dashboard to sys.path | ~10 |
| `.agents/memory/config.default.json` | Restore `pool` section | ~12 |
| `.agents/memory/agentic_memory/memory_system.py` | Replace `llm_controller` with `dashboard.ai.get_completion` | ~40 |
| `.agents/memory/agentic_memory/retrievers.py` | Replace 4 embedding classes with `dashboard.ai.get_embedding` | -200, +20 |
| `.agents/memory/agentic_memory/config.py` | Remove `llm` and `embedding` config sections | -30 |
| `.agents/memory/agentic_memory/llm_controller.py` | **DELETE** | -563 |
| Tests | Update all mock targets | ~30 |

**Total: ~650 lines deleted, ~110 lines added. Net: -540 lines.**
