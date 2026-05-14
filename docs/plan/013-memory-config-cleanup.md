# Plan 013: Memory Configuration Cleanup

**Status:** Draft
**Date:** 2026-05-07

---

## Problem

Memory configuration is fragmented across 4 sources with dead fields, wrong labels, and disconnected paths. Settings changed in the dashboard UI don't always reach the runtime.

### Current state: 4 config sources, none agree

```
Dashboard Settings UI          config.json["memory"]          .env vars              config.default.json
┌─────────────────────┐       ┌────────────────────────┐     ┌──────────────────┐   ┌──────────────────┐
│ vector_backend ✓    │──────►│ vector_backend ✓       │     │ MEMORY_LLM_      │   │ llm.backend      │
│ context_aware ✓     │       │ llm_backend (DEAD)     │     │ MEMORY_EMBEDDING │   │ embedding.model  │
│ auto_sync ✓         │       │ llm_model (DEAD)       │     │ (override layer) │   │ evolution.max_   │
│ sync_interval ✓     │       │ embedding_backend(DEAD)│     │                  │   │ search.similarity│
│ ttl_days (WRONG)    │       │ enabled (DEAD)         │     │                  │   │ pool.idle_timeout│
│                     │       │ max_summary_bytes(DEAD)│     │                  │   │ disabled_tools   │
│ MISSING:            │       │ auto_publish_on (DEAD) │     │                  │   │                  │
│  max_links          │       │                        │     │                  │   │ MISSING from UI  │
│  similarity_weight  │       │                        │     │                  │   │ and config.json  │
│  pool settings      │       │                        │     │                  │   │                  │
└─────────────────────┘       └────────────────────────┘     └──────────────────┘   └──────────────────┘
```

### Bugs found

| Bug | Impact |
|---|---|
| `ai/config.py` calls `resolver.load()` which doesn't exist | `MasterSettings.ai` namespace (memory_model, completion_model) is NEVER read. AI gateway always falls back to env vars. |
| `ttl_days` labeled "Auto-delete old entries" in UI | Runtime uses it as search ranking decay (`decay_half_life_days`), NOT deletion. No auto-delete exists. |
| 5 dead fields in config.json | `enabled`, `max_summary_bytes`, `max_detail_bytes`, `max_context_entries`, `auto_publish_on_done` — no code reads them |
| `llm_backend`, `llm_model`, `embedding_backend`, `embedding_model` in MemorySettings | Persisted but never used — AI gateway ignores them |
| 6 runtime settings not in UI | `context_aware_tree`, `max_links`, `similarity_weight`, `decay_half_life_days`, `conflict_resolution`, `disabled_tools` |
| Pool config not in Settings | `idle_timeout_s`, `max_instances`, `eviction_policy` — only via env vars |
| `auto_sync` only works for stdio | HTTP pool uses its own `sync_interval_s` from PoolConfig, ignoring the Settings value |

---

## Design

### Single config flow: Settings UI → config.json → runtime

```
Dashboard Settings UI (MemoryPanel)
  │
  ▼ PUT /api/settings/memory
config.json["memory"]          ← single source of truth
  │
  ├─► memory_pool.py reads it (HTTP pool mode)
  └─► mcp_server.py reads it (stdio mode, with hot-reload via dirty flag)
```

### New MemorySettings model (matches what runtime actually uses)

```python
class MemorySettings(BaseModel):
    # -- Vector store --
    vector_backend: str = "zvec"

    # -- Behaviour --
    context_aware: bool = True
    context_aware_tree: bool = False
    max_links: int = 3

    # -- Search tuning --
    similarity_weight: float = 0.8
    decay_half_life_days: float = 30.0

    # -- Sync --
    auto_sync: bool = True
    sync_interval_s: int = 60
    conflict_resolution: str = "last_modified"

    # -- Tool visibility --
    disabled_tools: list[str] = Field(default_factory=lambda: [
        "read_memory", "update_memory", "delete_memory",
        "link_memories", "unlink_memories", "memory_stats",
        "sync_from_disk", "sync_to_disk", "graph_snapshot"
    ])

    # -- Pool (HTTP transport) --
    pool_idle_timeout_s: int = 300
    pool_max_instances: int = 10
    pool_eviction_policy: str = "lru"
    pool_sync_interval_s: int = 60
```

**Removed:** `llm_backend`, `llm_model`, `embedding_backend`, `embedding_model`, `vector_store`, `ttl_days`, `enabled`, `max_summary_bytes`, `max_detail_bytes`, `max_context_entries`, `auto_publish_on_done`

**Added:** `context_aware_tree`, `max_links`, `similarity_weight`, `decay_half_life_days`, `conflict_resolution`, `disabled_tools`, `pool_idle_timeout_s`, `pool_max_instances`, `pool_eviction_policy`, `pool_sync_interval_s`

**Renamed:** `auto_sync_interval` → `sync_interval_s`, `ttl_days` → `decay_half_life_days`

---

## Changes

### Phase 1: Fix `ai/config.py` resolver bug

The `_load_from_settings()` function calls `resolver.load()` which doesn't exist. Fix:

```python
# Before (always throws AttributeError):
settings = resolver.load()

# After:
settings = resolver.get_master_settings()
```

This makes the `MasterSettings.ai` namespace (memory_model, completion_model) actually reach the AI gateway. Users can finally control which model the gateway uses from Settings → Provider Config.

### Phase 2: Clean up MemorySettings model

Replace the current model in `dashboard/models.py` with the new one above.

### Phase 3: Update MemoryPanel UI

Add the missing fields to the Settings UI:
- **Search Tuning** section: similarity_weight slider, decay_half_life_days input
- **Evolution** section: max_links input, context_aware_tree toggle
- **Pool** section: idle_timeout, max_instances, eviction_policy
- **Advanced** collapsible: disabled_tools checkboxes, conflict_resolution

Remove the `ttl_days` field (was mislabeled). Replace with `decay_half_life_days` with correct label: "Search decay half-life (days) — older notes rank lower".

### Phase 4: Wire pool config through Settings

Make `pool_config.py` read from `config.json["memory"]` (via `load_config()`) instead of only from env vars and `config.default.json["pool"]`. Priority: Settings UI → env vars → config.default.json defaults.

### Phase 5: Update `agentic_memory/config.py`

Update `_load_system_settings()` to map the new field names:
- Remove dead field mappings (`llm_backend`, `embedding_backend`, etc.)
- Add new field mappings (`max_links`, `similarity_weight`, `pool_*`)

### Phase 6: Clean up config.json on disk

Migration: on first read, remove dead keys from `config.json["memory"]` and write the cleaned version back. Handled in `config.py:_load_system_settings()` with a one-time cleanup pass.

---

## Files to change

| File | Change |
|---|---|
| `dashboard/ai/config.py` | Fix `resolver.load()` → `resolver.get_master_settings()` |
| `dashboard/models.py` | Replace `MemorySettings` with cleaned version |
| `dashboard/fe/src/components/settings/MemoryPanel.tsx` | Add missing fields, remove dead fields |
| `dashboard/fe/src/types/settings.ts` | Update `MemorySettings` TypeScript type |
| `.agents/memory/agentic_memory/config.py` | Update field mappings, add cleanup pass |
| `.agents/memory/pool_config.py` | Read from config.json["memory"] pool fields |

---

## Verification

```bash
# 1. Change max_links in Settings UI → verify it reaches memory_system
curl -X PUT http://localhost:3366/api/settings/memory \
  -H "Authorization: Bearer $KEY" \
  -d '{"max_links": 5}'
# Save a memory → check if evolution creates up to 5 links

# 2. Change pool_idle_timeout_s in Settings UI → verify pool uses it
curl -X PUT http://localhost:3366/api/settings/memory \
  -H "Authorization: Bearer $KEY" \
  -d '{"pool_idle_timeout_s": 120}'
# Check pool health → should show idle_timeout_s: 120

# 3. Change AI model in Settings → verify gateway uses it
curl -X PUT http://localhost:3366/api/settings/ai \
  -H "Authorization: Bearer $KEY" \
  -d '{"memory_model": "gemini-2.0-flash"}'
# Save a memory → AI Monitor should show gemini-2.0-flash
```
