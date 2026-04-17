# Memory Merge — Multi-Agent Consistency

## Problem

ostwin runs multiple agents in parallel war-rooms. Each agent spawns its own
stdio MCP memory server process. These processes share the same `notes/` and
`vectordb/` directories but have **independent in-memory state**.

```
Agent A (room-000)          Agent B (room-001)
   ┌──────────┐               ┌──────────┐
   │ memories  │               │ memories  │
   │ (dict)    │               │ (dict)    │
   └────┬──┬──┘               └────┬──┬──┘
        │  │                       │  │
        │  └── retriever (zvec) ──┘  │
        │          ↕ file lock       │
        └──── notes/ (shared fs) ───┘
```

Without synchronization:
- Agent A saves note X → Agent B never sees it (stale in-memory dict).
- Agent B calls `sync_to_disk` → deletes note X as an "orphan".
- `vectordb/` and `notes/` can drift (a note exists on disk but has no vector, or vice versa).

## Solution: Bidirectional Merge

`merge_from_disk()` reconciles the two sources of truth (disk and in-memory)
**without destroying data from either side**.

### Reconciliation Rules

| Case | Disk | Memory | Action |
|------|------|--------|--------|
| 1 | exists | missing | **Adopt from disk** — add to `self.memories` + vectordb |
| 2 | missing | exists | **Keep in memory** — will be written to disk by `sync_to_disk` |
| 3 | exists | exists (same content) | **Skip** — already consistent |
| 4 | exists | exists (different content) | **Last-modified wins** — compare `last_modified` timestamps; ties go to disk (external edits are assumed intentional) |

### Key Differences from Old `sync_from_disk`

| Behavior | Old `sync_from_disk` | New `merge_from_disk` |
|---|---|---|
| Memory-only notes | **Deleted** (treated as removed) | **Preserved** (another agent may have created them) |
| Vectordb rebuild | Full wipe + re-embed everything | **Incremental** — only changed notes get updated |
| Conflict resolution | Disk always wins | **`last_modified` wins**, ties → disk |
| Orphan deletion | Yes (dangerous with concurrent agents) | **Never** |

### Call Flow

```
sync_to_disk()
  ├── 1. merge_from_disk()        ← reconcile disk ↔ memory
  │     ├── load all notes from disk
  │     ├── case 1: disk-only → add to memory + vectordb
  │     ├── case 2: memory-only → count, no action
  │     ├── case 3: identical → skip
  │     └── case 4: conflict → compare last_modified, update loser
  │
  └── 2. write all self.memories to disk (touch_modified=False)
```

## The `last_modified` Field

Added to `MemoryNote` to track **content modification time** (as opposed to
`last_accessed` which tracks retrieval and `timestamp` which tracks creation).

```
---
id: "abc-123"
timestamp: "202604010900"         ← created
last_accessed: "202604021400"     ← last searched/retrieved
last_modified: "202604011030"     ← last content/metadata change
---
```

- Set automatically by `_save_note()` whenever a note is written.
- Backwards compatible: old notes without this field default to `timestamp`.
- Used as the tiebreaker for merge conflict resolution.

## Multi-Agent Scenario

```
Time    Agent A                     Disk (shared)              Agent B
────    ───────                     ─────────────              ───────
t0      loads notes {1,2}           notes/ has {1,2}           loads notes {1,2}
t1      saves note 3                notes/ has {1,2,3}
t2                                                             saves note 4
t3                                  notes/ has {1,2,3,4}
t4      sync_to_disk()
        ├── merge_from_disk()
        │   note 3: identical ✓
        │   note 4: disk-only → adopt
        ├── write {1,2,3,4}
        └── done
t5                                                             sync_to_disk()
                                                               ├── merge_from_disk()
                                                               │   note 3: disk-only → adopt
                                                               │   note 4: identical ✓
                                                               ├── write {1,2,3,4}
                                                               └── done
```

After both syncs, all agents and disk have notes {1,2,3,4}. No data loss.

## Conflict Example

```
Time    Agent A                     Disk                       Agent B
────    ───────                     ────                       ───────
t0      note-5 content="v1"        note-5 content="v1"        note-5 content="v1"
        last_modified=t0           last_modified=t0            last_modified=t0

t1      updates note-5 to "v2"     note-5 content="v2"
        last_modified=t1           last_modified=t1

t2                                                             updates note-5 to "v3"
                                   note-5 content="v3"         last_modified=t2
                                   last_modified=t2

t3      sync_to_disk()
        ├── merge_from_disk()
        │   note-5: conflict!
        │   disk=t2 vs memory=t1
        │   disk wins (t2 > t1)
        │   memory updated to "v3"
        └── writes "v3" to disk
```

## Limitations

- **No real-time notification.** Agents only see each other's changes when
  `merge_from_disk()` runs. Between merges, each agent operates on a snapshot.
- **Vectordb still uses file locking.** Two agents embedding simultaneously
  will serialize via zvec's lock (with 30s retry).
- **`sync_from_disk()` is preserved** for backwards compatibility but is
  **unsafe in multi-agent mode** — it deletes memory-only notes.

## Inspecting Merge Activity

Merge operations are logged to `.memory/mcp_server.log`:

```bash
cat <project>/.memory/mcp_server.log | grep -i "merge\|sync\|save_memory"
```
