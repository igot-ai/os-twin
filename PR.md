# Fix: Persist LLM Model Settings Across Dashboard Restarts

## Summary

Settings changes made in the `/settings` UI were silently lost on every dashboard restart (including re-runs of `install.sh`). Three independent root causes are fixed:

1. **Master model** was stored only in an in-memory singleton — never written to `config.json`
2. **Memory/knowledge model** env vars were silently overridden by `.env.sh` on every agent launch, ignoring explicit `config.json` values
3. **Ollama LLM calls** always failed silently because `is_available()` required an API key that local ollama doesn't need

## Problem

After configuring models in the Settings UI (`/settings`) and restarting the dashboard:

- The **master agent model** reset to the hardcoded default (`gemini-3.1-pro-preview` / `google-vertex`) because `PUT /api/settings/master-model` only updated an in-memory Python object, never persisting to `config.json`
- The **memory LLM/embedding backend** was overridden back to Gemini by the `.env.sh` hook on every agent subprocess launch, even when the user had explicitly chosen ollama in `config.json`
- The **memory `save_memory` MCP tool** only triggered `/api/embed` calls and never called the LLM for analysis, because `BaseLLMWrapper.is_available()` returned `False` for ollama (no API key), causing `analyze_content()` to silently return empty metadata

## Root Causes

### 1. Master model: in-memory only, never persisted

**File:** `dashboard/routes/settings.py:159-169`

`PUT /master-model` called `set_master_model()` which only updated `_master_config` (an in-memory dataclass). No code wrote the value to `config.json`. On restart, `_master_config = MasterAgentConfig()` re-initialized with hardcoded defaults. Nothing in the startup sequence read `config.json`'s `runtime.master_agent_model` back.

### 2. `.env.sh` auto-promotion ignored user config

**File:** `.agents/installer/setup-env.sh:107-116`

The `.env.sh` hook unconditionally promoted memory backend to Gemini when `GOOGLE_API_KEY` was set, without checking if the user had explicitly chosen a different backend in `config.json`. This overrode user settings on every agent subprocess launch.

### 3. Ollama `is_available()` always returned False

**File:** `dashboard/llm_wrapper.py:73-77`

`BaseLLMWrapper.is_available()` required `_resolve_api_key()` to return a truthy value. Ollama runs locally and doesn't use API keys, so `PROVIDER_API_KEYS` had no entry for it. This caused `is_available()` → `False`, making `MemoryLLM.get_completion()` skip the LLM call entirely and return empty JSON. The memory system's `analyze_content()` then produced `{"keywords": [], "context": "General", "tags": []}` — only embeddings ran, no LLM analysis.

## Changes

### `dashboard/routes/settings.py`
- `PUT /master-model` now persists to `config.json` via `resolver.patch_namespace("runtime", {"master_agent_model": ...})` in addition to updating the in-memory singleton

### `dashboard/master_agent.py`
- Added `init_master_from_config()` — called once on startup
- Reads `runtime.master_agent_model` from `config.json` → applies to in-memory `_master_config`
- Reads `memory.*` settings → sets `MEMORY_LLM_BACKEND`, `MEMORY_LLM_MODEL`, `MEMORY_EMBEDDING_BACKEND`, `MEMORY_EMBEDDING_MODEL` env vars (using `setdefault` so explicit env vars still win)
- Reads `knowledge.*` settings → sets `OSTWIN_KNOWLEDGE_LLM_PROVIDER`, `OSTWIN_KNOWLEDGE_LLM_MODEL`, `OSTWIN_KNOWLEDGE_EMBED_PROVIDER`, `OSTWIN_KNOWLEDGE_EMBED_MODEL` env vars

### `dashboard/tasks.py`
- Startup calls `init_master_from_config()` before `get_master_client()` so the restored model is used for client initialization

### `dashboard/llm_wrapper.py`
- `is_available()` now resolves the API key first; if found, uses it
- If no key found and provider is `ollama`, returns `True` (local provider, no auth needed)
- Other providers without a key still return `False`

### `.agents/installer/setup-env.sh`
- `.env.sh` hook is now **ollama-first** instead of gemini-first
- Reads `memory.llm_backend` from `config.json` via Python one-liner before deciding defaults
- If user set a backend in `config.json`, that value is exported
- If no config and `GOOGLE_API_KEY` is available, promotes to gemini (backward compatible)
- If no config and no Google key, defaults to ollama with `llama3.2` / `leoipulsar/harrier-0.6b`

## Testing

- All 36 existing tests pass (`test_master_agent.py`, `test_settings_master_model.py`)
- Manual verification:
  - `BaseLLMWrapper(model='llama3.2', provider='ollama').is_available()` → `True`
  - `BaseLLMWrapper(model='gpt-4', provider='openai').is_available()` → `False` (no key)
  - `BaseLLMWrapper(model='llama3.2', provider='ollama', api_key='test').is_available()` → `True` (key used)

## Migration

No migration needed. On next dashboard restart:
- `init_master_from_config()` reads existing `runtime.master_agent_model` from `config.json`
- If the field is empty/missing, the hardcoded default (`gemini-3.1-pro-preview`) is used as before
- Users who previously set a model via the UI need to set it one more time — this time it will persist
