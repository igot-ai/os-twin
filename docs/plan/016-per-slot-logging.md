# Plan 016: Per-Slot Memory Logging

**Status:** Draft
**Date:** 2026-05-12

---

## Problem

The memory system runs inside the dashboard as a single process. All log output goes to `~/.ostwin/dashboard/stdout.log` — mixed with dashboard HTTP logs, knowledge service logs, and everything else. When debugging a specific plan's memory behavior (why links weren't created, why save failed), you have to grep through a noisy shared log.

---

## Design

Each memory pool slot writes its own log file at `<persist_dir>/memory.log`. Since `persist_dir` is centralized at `~/.ostwin/memory/<plan_id>/` with a symlink from `project/.memory/`, the log is accessible from both locations:

```
~/.ostwin/memory/d6aff5dcdb4e/
├── notes/
├── vectordb/
└── memory.log          ← per-slot log

~/ostwin-workingdir/gold-mining/
└── .memory → ~/.ostwin/memory/d6aff5dcdb4e/
    └── memory.log      ← same file via symlink
```

### What gets logged

Every memory operation for that plan:

```
2026-05-12 14:56:44 [INFO] save_memory: id=abc123 content_len=329
2026-05-12 14:56:45 [INFO] AI embed: model=gemini/gemini-embedding-001 latency=48ms
2026-05-12 14:56:46 [INFO] AI complete: purpose=memory latency=2100ms
2026-05-12 14:56:46 [INFO] Evolution: 2 links created → [def456, ghi789]
2026-05-12 14:56:46 [INFO] Note saved: path=architecture/decisions/mvc-separation.md
2026-05-12 14:57:44 [INFO] Auto-sync: written=1, merged=0
2026-05-12 15:02:44 [INFO] Slot killed (idle timeout)
```

Errors with full tracebacks:

```
2026-05-12 14:56:45 [ERROR] Error analyzing content
Traceback (most recent call last):
  File "memory_system.py", line 645, in analyze_content
    response = self._completion_fn(prompt, response_format=schema)
  ...
```

### How it works

1. **MemorySlot gets a `log_handler` field** — a `logging.FileHandler` pointing at `<persist_dir>/memory.log`
2. **On slot creation** — handler is created and stored on the slot
3. **On tool call** — `_get_memory_for_plan()` attaches the slot's handler to the `agentic_memory` logger before returning the system
4. **After tool call** — handler is detached (so other slots don't write to this file)
5. **On slot kill** — handler is flushed and closed

### Thread safety

The handler attach/detach uses a `ContextVar` to track the active handler per-request. Multiple concurrent requests to different plans each get their own handler. The `FileHandler` itself is thread-safe (Python's logging module handles locking internally).

---

## Changes

### `memory_pool.py`

```python
@dataclass
class MemorySlot:
    system: Any
    persist_dir: str
    ...
    log_handler: Optional[logging.FileHandler] = None   # NEW

class MemoryPool:
    def _create_slot(self, persist_dir):
        ...
        # Create per-slot log file
        log_path = os.path.join(persist_dir, "memory.log")
        handler = logging.FileHandler(log_path)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
        slot.log_handler = handler

    def _cleanup_slot(self, slot):
        ...
        # Flush and close log handler
        if slot.log_handler:
            slot.log_handler.flush()
            slot.log_handler.close()
```

### `memory_mcp.py`

```python
_active_log_handler: ContextVar[Optional[logging.Handler]] = ContextVar(
    "_active_log_handler", default=None
)

def _get_memory_for_plan():
    ...
    slot = pool.get_or_create(persist_dir)

    # Attach per-slot log handler
    mem_logger = logging.getLogger("agentic_memory")
    old_handler = _active_log_handler.get()
    if old_handler:
        mem_logger.removeHandler(old_handler)
    if slot.log_handler:
        mem_logger.addHandler(slot.log_handler)
        _active_log_handler.set(slot.log_handler)

    return slot.system
```

---

## Files to change

| File | Change |
|---|---|
| `.agents/memory/memory_pool.py` | Add `log_handler` to `MemorySlot`, create in `_create_slot`, close in `_cleanup_slot` |
| `dashboard/routes/memory_mcp.py` | Attach/detach slot handler in `_get_memory_for_plan()` |

---

## Verification

```bash
# 1. Save a memory
curl -X POST 'http://localhost:3366/api/memory-pool/mcp?plan_id=test' ...

# 2. Check the log file
cat ~/.ostwin/memory/test/memory.log

# 3. Check via project symlink
cat ~/ostwin-workingdir/gold-mining/.memory/memory.log

# 4. Verify errors are logged with tracebacks
# (break something intentionally, check the log)

# 5. Verify slot kill flushes the log
ostwin dashboard restart
cat ~/.ostwin/memory/test/memory.log  # should end with "Slot killed"
```
