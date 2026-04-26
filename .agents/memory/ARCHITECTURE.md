# Memory System Architecture

## Data Stores

The memory system has **three** data stores. Understanding their relationship is critical.

```
┌─────────────────────────────────────────────────┐
│                 .memory/                         │
│                                                  │
│  notes/               vectordb/                  │
│  ├── backend/          └── memories/             │
│  │   └── postgres.md       ├── LOCK              │
│  └── frontend/             ├── index files       │
│      └── react.md          └── metadata_json     │
│                                                  │
│  self.memories (in-memory dict, per-process)     │
└─────────────────────────────────────────────────┘
```

### 1. `notes/` — Markdown files on disk

**Role:** Source of truth for note content and metadata.

Each note is a `.md` file with YAML frontmatter containing `id`, `name`, `path`, `content_hash`, `last_modified`, `tags`, `keywords`, `context`, `links`, etc. The file content after the frontmatter is the note's actual text.

### 2. `vectordb/` — zvec vector database on disk

**Role:** Derived search index. Can be rebuilt entirely from `notes/`.

Stores embedding vectors (for semantic search) and a copy of note metadata in `metadata_json` (including `content_hash` and full `content`). Each entry is keyed by the note's UUID.

### 3. `self.memories` — In-memory dict (per-process)

**Role:** Working copy for the current MCP server process.

Loaded from `notes/` at startup. Each process has its own independent copy. Multiple concurrent processes each have their own `self.memories` that may diverge.

## Consistency

### Definition

**Consistent** means: for every note, the `content_hash` stored in the vectordb entry matches the `content_hash` computed from the note in `notes/`. If they match, the embedding vector is up-to-date. If they don't, the vector is stale and search results may be wrong.

### What causes inconsistency

| Cause | Result |
|---|---|
| Process crash between `_save_note()` and `retriever.add_document()` | Note exists in `notes/`, missing from vectordb |
| Note content updated but vector not re-embedded | Note hash ≠ vectordb hash (stale vector) |
| Orphan vector (note deleted from `notes/`, vector remains) | Vectordb has entry with no corresponding note |

### How inconsistency is detected

The `merge_from_disk()` method compares:

```python
stored_hashes = retriever.get_stored_hashes(all_note_ids)
for note_id in all_notes:
    if stored_hashes.get(note_id) != note.content_hash:
        # INCONSISTENT — fix vectordb
```

### How inconsistency is fixed

**Always fix vectordb. Never change notes.**

`notes/` is the source of truth. When a mismatch is found:

- **Note exists, vector missing** → embed the note and insert into vectordb
- **Note exists, hash mismatch** → delete old vector, re-embed from note content
- **Vector exists, note missing** → orphan (currently not cleaned up; search filters it out via `if memory:` check)

Notes are never modified, deleted, or overwritten to match vectordb.

## The `content_hash` Field

SHA-256 (first 16 hex chars) computed from:

```python
parts = [content, context, keywords (sorted), tags (sorted)]
hash = sha256("\n".join(parts))[:16]
```

Stored in three places:
1. Note frontmatter (`notes/*.md`)
2. Vectordb metadata (`metadata_json.content_hash`)
3. In-memory `MemoryNote.content_hash` property

Used for:
- **Consistency check**: compare note hash vs vectordb hash
- **Conflict resolution**: same hash = duplicate, different hash = real conflict
- **Merge optimization**: compare hashes instead of full content strings

## Multi-Agent Architecture

### Process model

Each agent gets its own stdio MCP server process. Multiple processes share the same `notes/` and `vectordb/` on disk.

```
Agent A (room-000)           Agent B (room-001)
     │                            │
     ▼                            ▼
MCP Process A               MCP Process B
  self.memories               self.memories
  (independent)               (independent)
     │                            │
     └──── notes/ (shared) ───────┘
     └──── vectordb/ (shared) ────┘
```

### Locking

zvec uses exclusive file locks. The retriever uses **short-lived handles** (not persistent):

- **Read operations** (search, fetch): open read-only handle, execute, release. Multiple readers coexist.
- **Write operations** (insert, delete): open read-write handle with 30s retry, execute, release. Lock held for milliseconds.

### Synchronization

Agents synchronize via the **auto-sync timer** (default: every 60 seconds):

```
sync_to_disk()
  ├── 1. merge_from_disk()     ← pull in other agents' notes
  │     ├── disk-only notes → adopt into memory + vectordb
  │     ├── memory-only notes → keep (will be written next)
  │     ├── same hash → skip
  │     ├── different hash → last_modified wins (or LLM merge)
  │     └── verify vectordb consistency → fix mismatches
  │
  └── 2. write all self.memories to disk
```

There is no real-time notification between agents. Agent B only sees Agent A's notes when B's auto-sync fires.

### Conflict resolution

When two notes have the same UUID but different content (one in memory, one on disk):

- **`last_modified`** (default): newer timestamp wins. Ties go to disk.
- **`llm`** (configurable): LLM merges both versions into one. Falls back to `last_modified` on failure.

Config: `config.default.json` → `sync.conflict_resolution`

### Filepath collision

When two notes have the same `name` and `path` (and thus the same filepath) but different UUIDs:

- **Same `content_hash`**: true duplicate. Second write is skipped.
- **Different `content_hash`**: real conflict. `last_modified` determines which note gets the filepath. The loser's write is rejected (not written to disk).

## Import Docs

Place `.md` files in `.memory/docs/`. On MCP server startup:

1. Rename `docs/` to `.docs_imported_<timestamp>` (atomic, prevents other agents from re-processing)
2. Walk all `.md` files
3. Derive `name` from filename, `path` from directory structure
4. LLM generates `tags`, `keywords`, `context`, `links`, `summary`
5. Skip duplicates (same `content_hash` already in memory)
6. Save to `notes/` + vectordb

## Key Principles

1. **`notes/` is the source of truth.** Vectordb is derived. When in doubt, fix vectordb to match notes.
2. **Never delete another agent's work.** `sync_to_disk` does not remove "orphan" files. They may belong to another process.
3. **Append-only across processes.** Each process can add notes and update its own notes. Never remove files you didn't create.
4. **Short-lived locks.** No persistent vectordb handles. Open, execute, release. Contention window is milliseconds.
5. **Hash is the arbiter.** Content equality is determined by `content_hash`, not raw string comparison.
