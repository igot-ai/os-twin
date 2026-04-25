# Plan 007: Memory MCP — stdio to HTTP Transport

**Status:** Draft
**Date:** 2026-04-23
**Scope:** Mount the Agentic Memory MCP server as a Streamable HTTP endpoint inside the FastAPI dashboard at `/api/knowledge/mcp`. Multi-tenant via a memory pool with per-persist_dir instances, refcounting, configurable idle kill, and fast startup.

---

## Motivation

Currently every agent spawns its own `mcp_server.py` process via stdio. This means:

- N agents = N memory system instances, N vector DB handles, N auto-sync threads
- Concurrent processes contend on the zvec file lock (mitigated with a 30s retry, but still wasteful)
- No way for the dashboard frontend to call MCP tools directly
- ~1GB RAM duplicated per process for ML models (torch, sentence-transformers)

Moving to a single HTTP-hosted process with a memory pool eliminates lock contention, reduces resource usage to one ML runtime + lightweight per-project instances, and opens the door for the dashboard (or any HTTP client) to call memory tools natively.

---

## Architecture

### Before (stdio, per-agent)

```
Plan A:
  agent-1 ──stdio──► mcp_server.py (pid 1) ──► project-a/.memory/
  agent-2 ──stdio──► mcp_server.py (pid 2) ──► project-a/.memory/  ← lock contention
  agent-3 ──stdio──► mcp_server.py (pid 3) ──► project-a/.memory/

Plan B:
  agent-4 ──stdio──► mcp_server.py (pid 4) ──► project-b/.memory/
  agent-5 ──stdio──► mcp_server.py (pid 5) ──► project-b/.memory/  ← lock contention

Total: 5 processes, 5 ML runtimes (~5GB), 5 sync threads, constant lock contention
```

### After (HTTP, memory pool inside dashboard)

```
                                         ┌──────────────────────────────┐
                                         │        Memory Pool           │
                                         │                              │
Plan A agents ──┐                        │  project-a/.memory           │
  agent-1       │                        │  → AgenticMemorySystem A     │
  agent-2       ├── POST /api/knowledge/ │    refs=3, sync thread ✓     │
  agent-3       │   mcp?persist_dir=...  │                              │
                │                        │  project-b/.memory           │
Plan B agents ──┤                        │  → AgenticMemorySystem B     │
  agent-4       │                        │    refs=2, sync thread ✓     │
  agent-5       ┘                        │                              │
                                         │  ML runtime (shared, 1x)    │
dashboard-fe ────────────────────────────│    torch, sentence-xformers  │
                                         └──────────────────────────────┘

Total: 1 process, 1 ML runtime (~1GB), 2 sync threads, zero lock contention
```

### Three-tier resource model

```
Tier 1: ML runtime  (process lifetime — never unloaded)
  torch, transformers, sentence-transformers, embedding model
  ~9s first load, ~1GB RAM, shared across all instances

Tier 2: Memory instance  (managed by pool — created/killed per persist_dir)
  AgenticMemorySystem: in-memory notes dict, vector DB handle, sync thread
  ~200ms create (after tier 1 ready), ~10-50MB RAM per project

Tier 3: MCP session  (per agent connection)
  Binds a session ID to a persist_dir → memory instance
  ~0ms overhead, just a dict lookup
```

### How the mount works

The MCP Python SDK (`FastMCP`) has a `.streamable_http_app()` method that returns a Starlette ASGI app with a single route at `/mcp`. Mounting this Starlette app at `/api/knowledge` inside the FastAPI dashboard places the MCP endpoint at:

```
POST   /api/knowledge/mcp   ← JSON-RPC requests (tool calls)
GET    /api/knowledge/mcp   ← SSE stream (server notifications)
DELETE /api/knowledge/mcp   ← session teardown
```

### How an agent specifies its persist_dir

Query parameter on the connection URL:

```
POST /api/knowledge/mcp?persist_dir=/home/user/project-a/.memory
```

The MCP config template becomes:

```json
"memory": {
  "type": "remote",
  "url": "http://localhost:3366/api/knowledge/mcp?persist_dir={env:MEMORY_PERSIST_DIR}"
}
```

`{env:MEMORY_PERSIST_DIR}` is already resolved per-agent by the compile step (`mcp-extension.sh compile`), so each agent automatically connects to the right memory system.

---

## Memory Pool Design

### MemorySlot

Each unique `persist_dir` gets one slot:

```python
class MemorySlot:
    system: AgenticMemorySystem   # the actual memory system
    persist_dir: str              # canonical absolute path
    ref_count: int                # active sessions using this slot
    last_activity: float          # time.monotonic() of last tool call
    created_at: float             # time.monotonic() of slot creation
    sync_thread: threading.Thread # 60s auto-sync for this instance
    sync_stop: threading.Event    # signal to stop sync thread
    kill_timer: threading.Timer | None  # pending kill, if draining
```

### MemoryPool

```python
class MemoryPool:
    _slots: dict[str, MemorySlot]    # keyed by canonical persist_dir
    _lock: threading.Lock            # guards _slots mutations
    _ml_ready: threading.Event       # set once tier 1 ML imports finish
    _config: PoolConfig              # all configurable knobs

    def acquire(self, persist_dir: str) -> MemorySlot
    def release(self, persist_dir: str) -> None
    def touch(self, persist_dir: str) -> None      # update last_activity
    def kill_slot(self, persist_dir: str) -> None   # final sync + cleanup
    def kill_all(self) -> None                      # dashboard shutdown
    def stats(self) -> dict                         # for health endpoint
```

### Session lifecycle

```
agent connects                 agent disconnects              idle timeout fires
     │                               │                              │
     ▼                               ▼                              ▼
 ┌────────┐                    ┌──────────┐                   ┌──────────┐
 │ active │───────────────────►│ draining │──────────────────►│  killed  │
 │        │                    │          │                    │          │
 │ refs=3 │  last agent leaves │ refs=0   │  IDLE_TIMEOUT_S   │ sync     │
 │ sync ✓ │                    │ sync ✓   │  expires          │ cleanup  │
 └────────┘                    │ timer ✓  │                   │ remove   │
                               └──────────┘                   └──────────┘
                                    │
                          agent reconnects before timeout?
                                    │
                                    ▼
                               ┌────────┐
                               │ active │  cancel timer, refs++
                               └────────┘
```

### Acquire / Release

```python
def acquire(self, persist_dir: str) -> MemorySlot:
    persist_dir = os.path.realpath(persist_dir)  # canonical
    with self._lock:
        slot = self._slots.get(persist_dir)
        if slot:
            slot.ref_count += 1
            slot.last_activity = time.monotonic()
            if slot.kill_timer:
                slot.kill_timer.cancel()
                slot.kill_timer = None
            return slot
        # Enforce max pool size
        if len(self._slots) >= self._config.max_instances:
            self._evict_least_active()
        # New slot — fast because ML is already loaded (tier 1)
        self._ml_ready.wait(timeout=self._config.ml_ready_timeout_s)
        slot = self._create_slot(persist_dir)
        self._slots[persist_dir] = slot
        return slot

def release(self, persist_dir: str):
    persist_dir = os.path.realpath(persist_dir)
    with self._lock:
        slot = self._slots.get(persist_dir)
        if not slot:
            return
        slot.ref_count = max(0, slot.ref_count - 1)
        if slot.ref_count <= 0:
            slot.kill_timer = threading.Timer(
                self._config.idle_timeout_s,
                self.kill_slot, args=[persist_dir]
            )
            slot.kill_timer.daemon = True
            slot.kill_timer.start()
```

### Kill

```python
def kill_slot(self, persist_dir: str):
    with self._lock:
        slot = self._slots.get(persist_dir)
        if not slot or slot.ref_count > 0:
            return  # agent reconnected, abort kill
        self._slots.pop(persist_dir)
    # Outside lock — these can be slow
    slot.sync_stop.set()           # stop 60s sync thread
    slot.system.sync_to_disk()     # final flush
    # Let GC reclaim AgenticMemorySystem + vector handles
    logger.info("Killed memory slot: %s", persist_dir)

def kill_all(self):
    """Called on dashboard shutdown."""
    with self._lock:
        dirs = list(self._slots.keys())
    for d in dirs:
        self.kill_slot(d)
```

---

## Configuration

All pool behavior is configurable via environment variables (prefixed `MEMORY_POOL_`) and/or `config.default.json`. Follows the same pattern as the existing `agentic_memory/config.py`.

### Config dataclass

```python
@dataclass
class PoolConfig:
    # --- Instance lifecycle ---
    idle_timeout_s: int = 300           # kill instance after 5 min idle (0 = never kill)
    max_instances: int = 10             # max concurrent memory systems in pool
    eviction_policy: str = "lru"        # "lru" | "oldest" | "none"

    # --- ML preload ---
    ml_preload: bool = True             # preload ML on dashboard start
    ml_ready_timeout_s: int = 30        # max wait for ML if agent arrives early

    # --- Per-instance sync ---
    sync_interval_s: int = 60           # auto-sync interval per instance
    sync_on_kill: bool = True           # final sync_to_disk before kill

    # --- Security ---
    allowed_paths: list[str] = None     # restrict persist_dir to these prefixes
                                        # e.g. ["/home/user/ostwin-workingdir/"]
                                        # None = allow any path (trust the agent)

    # --- Dashboard integration ---
    dashboard_port: int = 3366          # for building the remote MCP URL
    mount_path: str = "/api/knowledge"  # where the MCP app is mounted
```

### Environment variable mapping

| Env var | Config field | Default |
|---|---|---|
| `MEMORY_POOL_IDLE_TIMEOUT` | `idle_timeout_s` | `300` (5 min) |
| `MEMORY_POOL_MAX_INSTANCES` | `max_instances` | `10` |
| `MEMORY_POOL_EVICTION` | `eviction_policy` | `lru` |
| `MEMORY_POOL_ML_PRELOAD` | `ml_preload` | `true` |
| `MEMORY_POOL_ML_TIMEOUT` | `ml_ready_timeout_s` | `30` |
| `MEMORY_POOL_SYNC_INTERVAL` | `sync_interval_s` | `60` |
| `MEMORY_POOL_SYNC_ON_KILL` | `sync_on_kill` | `true` |
| `MEMORY_POOL_ALLOWED_PATHS` | `allowed_paths` | _(none — allow all)_ |

### JSON config (in `config.default.json`)

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
    "allowed_paths": null
  }
}
```

### Eviction policies

When `max_instances` is reached and a new `persist_dir` arrives:

| Policy | Behavior |
|---|---|
| `lru` | Kill the slot with the oldest `last_activity` (least recently used) |
| `oldest` | Kill the slot with the oldest `created_at` |
| `none` | Reject the new connection with an error (hard cap) |

Only slots with `ref_count == 0` are eligible for eviction. If all slots are active, the new connection waits (up to `ml_ready_timeout_s`) for one to drain, then fails.

---

## Startup Timeline

```
t=0     Dashboard starts
        ├── FastAPI begins accepting HTTP
        └── ML preload thread starts (tier 1)

t≈9s    ML preload complete (_ml_ready.set())

t=?     First agent connects: POST /api/knowledge/mcp?persist_dir=/path-a/.memory
        ├── If t < 9s: waits for _ml_ready (up to ml_ready_timeout_s)
        ├── pool.acquire("/path-a/.memory")
        │   ├── Creates AgenticMemorySystem (~200ms: load notes, open vectordb)
        │   └── Starts 60s sync thread for this slot
        └── MCP session bound to slot, returns Mcp-Session-Id

t=?     Second agent (same plan): POST /api/knowledge/mcp?persist_dir=/path-a/.memory
        ├── pool.acquire("/path-a/.memory")  → existing slot, refs++ (~0ms)
        └── MCP session bound to same slot

t=?     Agent from different plan: POST /api/knowledge/mcp?persist_dir=/path-b/.memory
        ├── pool.acquire("/path-b/.memory")  → new slot (~200ms)
        └── Separate instance, separate sync thread

t=?     All plan-a agents disconnect
        ├── pool.release() for each → refs drops to 0
        └── Kill timer starts (idle_timeout_s)

t+300s  Kill timer fires (no reconnection)
        ├── Final sync_to_disk()
        ├── Stop sync thread
        └── Remove slot from pool, GC reclaims resources
```

### Timing summary

| Event | Latency |
|---|---|
| Dashboard cold start → HTTP ready | <2s (ML loads in background) |
| First agent, ML not ready yet | Up to `ml_ready_timeout_s` (default 30s) |
| First agent, ML ready | ~200ms (notes + vectordb init) |
| New persist_dir, ML ready | ~200ms |
| Reconnect to existing persist_dir | ~0ms (pool hit, refcount bump) |
| Tool call on active slot | Same as current (~10ms search, ~10s save with LLM) |
| Kill timer fires | ~1s (final sync + cleanup) |

---

## Files to Change

### 1. `.agents/memory/mcp_server.py` — guard self-healing interpreter

The `_ensure_correct_interpreter()` function re-execs the process with the memory venv's Python if the current interpreter lacks `requests`. Essential for stdio mode but breaks when imported by the dashboard.

**Change:** wrap the call with `if __name__ == "__main__":`.

```python
# Before
_ensure_correct_interpreter()

# After
if __name__ == "__main__":
    _ensure_correct_interpreter()
```

Also: refactor `get_memory()` to accept an optional `persist_dir` parameter so the pool can route tool calls to the correct instance. Currently `get_memory()` returns a module-level singleton — it needs to be session-aware.

### 2. `.agents/memory/memory_pool.py` — new file

The `MemoryPool` and `MemorySlot` classes as described above. Responsibilities:

- Manage pool of `AgenticMemorySystem` instances keyed by `persist_dir`
- Refcounting via `acquire()` / `release()`
- Idle kill with configurable timeout
- Eviction when `max_instances` reached
- ML preload on construction
- `kill_all()` for dashboard shutdown
- `stats()` for observability

### 3. `.agents/memory/pool_config.py` — new file

`PoolConfig` dataclass with env var overrides. Same pattern as existing `agentic_memory/config.py`.

### 4. `dashboard/routes/knowledge.py` — new file

Responsibilities:

1. Add `.agents/memory` to `sys.path` (same pattern as `amem.py`)
2. Create the `MemoryPool` singleton (triggers ML preload)
3. Build a custom FastMCP instance whose tool functions route through the pool:
   - Extract `persist_dir` from the MCP session context
   - Call `pool.acquire()` on session init, `pool.release()` on disconnect
   - Call `pool.touch()` on every tool call
4. Call `.streamable_http_app()` to get the Starlette ASGI app
5. Export the app for mounting in `api.py`

### 5. `dashboard/api.py` — mount + lifecycle

```python
from dashboard.routes.knowledge import knowledge_mcp_app

# Mount before catch-all, after API routers
app.mount("/api/knowledge", knowledge_mcp_app)
```

Add shutdown hook:

```python
@app.on_event("shutdown")
async def on_shutdown():
    # ... existing shutdown code ...
    from dashboard.routes.knowledge import memory_pool
    if memory_pool:
        memory_pool.kill_all()
```

### 6. `dashboard/requirements.txt` — add missing deps

```
litellm>=1.16.11
rank_bm25>=0.2.2
nltk>=3.8.1
scikit-learn>=1.3.2
```

### 7. `.agents/memory/agentic_memory/config.py` — extend with pool section

Add the `pool` section to `config.default.json` and the `PoolConfig` loading logic. Keeps all memory config in one place.

---

## Design Decisions

### D1: Multi-tenant via memory pool (not single instance)

**Decision:** One `AgenticMemorySystem` instance per unique `persist_dir`, managed by a pool with refcounting and idle kill.

**Rationale:** Multiple plans run simultaneously with different `.memory/` directories. A single-instance design would force all plans to share one directory or require the dashboard to only serve one project. The pool preserves per-project isolation while sharing the expensive ML runtime.

### D2: Stateful sessions (not stateless)

**Decision:** Stateful MCP sessions. Each session is bound to a `persist_dir` via query parameter on connect.

**Rationale:** The pool needs to track which sessions use which memory instance for refcounting. Stateful sessions provide:
- `acquire()` on session init → refcount++
- `release()` on session disconnect → refcount--
- Correct routing of tool calls to the right instance via session context

Stateless mode would require passing `persist_dir` on every single request, which is redundant and prevents proper lifecycle management.

### D3: REST endpoints alongside MCP

**Decision:** Keep existing `amem.py` routes at `/api/amem/...` for REST. `/api/knowledge/mcp` is MCP-only.

**Rationale:** `app.mount("/api/knowledge", ...)` owns all requests under that prefix. Since `amem.py` already provides per-plan graph, notes, tree, and stats endpoints, there's no need to duplicate. The two systems complement each other:
- `/api/amem/{plan_id}/...` — REST, per-plan, reads from disk (no running instance needed)
- `/api/knowledge/mcp` — MCP protocol, session-based, uses live in-memory instance

### D4: Agent config update (deferred)

**Decision:** Defer MCP config template changes. stdio continues to work for agents.

The template change is straightforward when ready:

```json
"memory": {
  "type": "remote",
  "url": "http://localhost:{env:DASHBOARD_PORT}/api/knowledge/mcp?persist_dir={env:MEMORY_PERSIST_DIR}"
}
```

This plan focuses on getting the HTTP pool running. Agent migration happens incrementally once validated.

### D5: persist_dir validation (configurable)

**Decision:** Optional allowlist via `MEMORY_POOL_ALLOWED_PATHS`.

When set, the pool rejects any `persist_dir` that doesn't start with one of the allowed prefixes. When unset, any path is accepted (trusts the agent).

Example: `MEMORY_POOL_ALLOWED_PATHS=/home/user/ostwin-workingdir/,/tmp/test/`

---

## Dependency Check

The dashboard's `requirements.txt` already includes:

- `mcp[cli]>=1.1.3` — provides `FastMCP`, `streamable_http_app()`
- `zvec>=0.2.0` — vector store
- `sentence-transformers>=3.0` — embeddings
- `torch` — ML backend

Missing deps to add:

```
litellm>=1.16.11
rank_bm25>=0.2.2
nltk>=3.8.1
scikit-learn>=1.3.2
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Dashboard crash kills all memory systems | All agents lose MCP access | Agents can fall back to `memory-cli.py`; dashboard restart re-creates instances on reconnect |
| Zombie slots if agent crashes without disconnect | Slot never released, ref_count stuck | Health-check sweep: periodically verify sessions are alive, force-release dead ones |
| ML preload delays first agent | Up to 9s wait on cold start | `ml_ready_timeout_s` is configurable; ML preload starts immediately on dashboard boot |
| Too many concurrent plans exhaust RAM | Pool grows unbounded | `max_instances` cap + eviction policy; idle slots are killed |
| Path traversal via persist_dir | Security risk | `allowed_paths` allowlist; `os.path.realpath()` canonicalization |
| Multiple dashboard instances | Two pools writing to same `.memory/` | Same as current multi-agent stdio situation; zvec retry handles it. Document: run one dashboard per host. |

---

## Observability

The pool exposes a `stats()` method, accessible via a health endpoint added as a `FastMCP.custom_route()`:

```
GET /api/knowledge/health
```

Returns:

```json
{
  "ml_ready": true,
  "active_slots": 2,
  "total_sessions": 5,
  "slots": [
    {
      "persist_dir": "/home/user/project-a/.memory",
      "ref_count": 3,
      "notes_count": 142,
      "idle_seconds": 12,
      "sync_thread_alive": true,
      "created_ago_s": 3600
    },
    {
      "persist_dir": "/home/user/project-b/.memory",
      "ref_count": 2,
      "notes_count": 87,
      "idle_seconds": 45,
      "sync_thread_alive": true,
      "created_ago_s": 1200
    }
  ],
  "config": {
    "idle_timeout_s": 300,
    "max_instances": 10,
    "eviction_policy": "lru",
    "sync_interval_s": 60
  }
}
```

---

## Verification

### 1. Basic MCP handshake

```bash
curl -X POST 'http://localhost:3366/api/knowledge/mcp?persist_dir=/tmp/test/.memory' \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
    "protocolVersion":"2025-03-26",
    "capabilities":{},
    "clientInfo":{"name":"test","version":"0.1"}
  }}'
```

### 2. Tool call (memory_tree)

```bash
curl -X POST 'http://localhost:3366/api/knowledge/mcp?persist_dir=/tmp/test/.memory' \
  -H "Content-Type: application/json" \
  -H "Mcp-Session-Id: <from init response>" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{
    "name":"memory_tree","arguments":{}
  }}'
```

### 3. Multi-tenant isolation

```bash
# Two different persist_dirs should get independent memory systems
curl -X POST '...?persist_dir=/tmp/plan-a/.memory' ...  # saves note "A"
curl -X POST '...?persist_dir=/tmp/plan-b/.memory' ...  # saves note "B"
# search in plan-a should NOT find note "B"
```

### 4. Idle kill

```bash
# Connect, then disconnect, wait idle_timeout_s, verify slot is killed
curl ... initialize ...
curl ... DELETE (session teardown) ...
sleep 310  # idle_timeout_s + margin
curl http://localhost:3366/api/knowledge/health  # slot should be gone
```

### 5. Auto-sync

```bash
# Check .memory/mcp_server.log for "Auto-sync to disk" entries at sync_interval_s intervals
tail -f /tmp/test/.memory/mcp_server.log
```

### 6. Existing REST routes unaffected

```bash
curl http://localhost:3366/api/amem/{plan_id}/graph   # should still work
curl http://localhost:3366/api/amem/{plan_id}/notes    # should still work
```
