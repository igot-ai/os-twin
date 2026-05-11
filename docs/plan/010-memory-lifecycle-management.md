# Plan 010: Memory Lifecycle Management

**Status:** Draft
**Date:** 2026-05-06
**Depends on:** Plan 009 (centralized storage)

---

## What is this?

Ostwin is a multi-agent orchestrator. When you run a plan (e.g., "build a gold mining game"), multiple AI agents (architect, engineer, QA) work in parallel inside "war-rooms." These agents have a **shared memory system** — they can save notes, search previous learnings, and build a knowledge graph that persists across sessions.

### How memory works today

- Each plan gets its own memory namespace, stored centrally at `~/.ostwin/memory/<plan_id>/`
- Inside each namespace: `notes/` (markdown files with metadata) and `vectordb/` (semantic search index)
- Agents save memories via the MCP tool `save_memory` (e.g., "we decided to use TypeScript for this project")
- Agents search memories via `search_memory` (semantic vector search with time-decay reranking)
- A project-level symlink (`project/.memory → ~/.ostwin/memory/<plan_id>/`) lets you browse notes from the project directory
- All AI calls (LLM completions for analysis, embeddings for vector search) go through a centralized AI gateway with monitoring

### What you can do today

| Action | How | Works? |
|---|---|---|
| Save a memory | Agent calls `save_memory` during work | Yes |
| Search memories | Agent calls `search_memory` | Yes |
| Browse notes | `ls project/.memory/notes/` or MemoryTab in dashboard | Yes |
| View memory graph | Dashboard → plan → Memory tab | Yes |
| Monitor pool health | Dashboard → MCP page → Memory Pool panel | Yes |
| Delete a single note | Not available | No |
| Clear all memories for a plan | `rm -rf ~/.ostwin/memory/<plan_id>/` | Manual only |
| Archive memories before re-running | Not available | No |
| Export memories | Not available | No |
| Manage from CLI | Not available | No |

### The problem

Memories persist forever. When you re-run a plan, agents see old notes from previous runs. Sometimes this is helpful (agents remember past decisions). Sometimes it's harmful (old architecture notes conflict with a new approach). **Users have no way to manage this** — no clear, no archive, no export, no delete. The only option is `rm -rf`.

---

## Features (what this plan adds)

### For the dashboard user

1. **Clear Memory** — one-click button in the Memory tab to wipe all notes for a plan. Confirmation modal prevents accidents.

2. **Archive Memory** — save current memories to a timestamped archive (`<plan_id>.archive-20260506/`), then start fresh. Nothing lost, agents start clean.

3. **Export Memory** — download all notes as a `.tar.gz` file. Useful for backup, sharing, or moving to another machine.

4. **Delete Individual Notes** — trash icon next to each note in the Memory tab. Remove a specific outdated or wrong memory without clearing everything.

5. **Namespace Management** — see all plan memory namespaces in the Memory Pool panel with note counts, disk usage, and management buttons.

### For the CLI user

```bash
ostwin memory list                      # List all plan namespaces with stats
ostwin memory stats <plan_id>           # Show stats for a specific plan
ostwin memory tree <plan_id>            # Show note directory tree
ostwin memory clear <plan_id> --force   # Delete all notes for a plan
ostwin memory delete <plan_id> <id>     # Delete a single note
ostwin memory archive <plan_id>         # Archive and start fresh
ostwin memory export <plan_id>          # Download as .tar.gz
```

### For agents (MCP tools)

- `delete_memory` tool exposed via HTTP MCP — agents can remove their own outdated notes

### For the REST API consumer

```
GET    /api/amem/namespaces                    List all namespaces
DELETE /api/amem/{plan_id}                     Clear all notes
DELETE /api/amem/{plan_id}/notes/{note_id}     Delete single note
POST   /api/amem/{plan_id}/archive             Archive namespace
GET    /api/amem/{plan_id}/export              Download as tar.gz
```

---

## Problem

Memories persist forever across plan runs. Users have no way to clear, archive, or manage them — from CLI, dashboard, or API. The only option is `rm -rf ~/.ostwin/memory/<plan_id>/`.

### What's missing

| Layer | Read | Write | Delete/Clear | Archive |
|---|---|---|---|---|
| CLI (`ostwin`) | None | None | None | None |
| REST API | GET notes/tree/stats | POST via MCP only | None | None |
| Dashboard UI | MemoryTab (view) | Via agents only | None | None |
| MCP tools (HTTP) | search, tree, grep, find | save_memory | None (delete_memory not exposed) | None |

---

## Design

### Three operations, three layers

```
                    CLI                    REST API                Dashboard UI
                    ostwin memory ...      /api/memory/...         MemoryTab + MemoryPool

  List namespaces   ostwin memory list     GET /namespaces         MemoryPool panel
  View stats        ostwin memory stats    GET /:id/stats          MemoryTab header
  Clear all notes   ostwin memory clear    DELETE /:id             "Clear Memory" button
  Delete one note   ostwin memory delete   DELETE /:id/notes/:nid  Delete icon per note
  Archive           ostwin memory archive  POST /:id/archive       "Archive" button
  Export            ostwin memory export   GET /:id/export         "Export" button
```

### Storage layout after archive

```
~/.ostwin/memory/
├── d6aff5dcdb4e/                     ← active namespace
│   ├── notes/
│   └── vectordb/
├── d6aff5dcdb4e.archive-20260506/    ← archived (timestamped)
│   ├── notes/
│   └── vectordb/
└── _global/
```

Archive = rename `<plan_id>/` to `<plan_id>.archive-<YYYYMMDD>/`, then create empty `<plan_id>/`. Old data preserved, agents start fresh.

---

## Changes

### Phase 1: Backend — AgenticMemorySystem.clear()

Add to `memory_system.py`:
```python
def clear(self) -> dict:
    """Delete all notes, clear vector index, remove files."""
    count = len(self.memories)
    self.memories.clear()
    self.retriever.clear()
    if self._notes_dir:
        shutil.rmtree(self._notes_dir, ignore_errors=True)
        os.makedirs(self._notes_dir, exist_ok=True)
    self._dirty = True
    return {"cleared": count}
```

### Phase 2: Backend — REST API endpoints

Add to `dashboard/routes/amem.py`:

```
DELETE /api/amem/{plan_id}                    → clear all notes for plan
DELETE /api/amem/{plan_id}/notes/{note_id}    → delete single note
POST   /api/amem/{plan_id}/archive            → archive namespace
GET    /api/amem/{plan_id}/export             → download as zip
GET    /api/amem/namespaces                   → list all namespaces with stats
```

### Phase 3: Backend — Expose delete_memory in HTTP MCP

Add `delete_memory` tool to `dashboard/routes/memory_mcp.py`:
```python
@mcp.tool()
def delete_memory(memory_id: str) -> str:
    """Delete a specific memory note by ID."""
    mem = _get_memory_for_plan()
    mem.delete(memory_id)
    return json.dumps({"id": memory_id, "status": "deleted"})
```

### Phase 4: CLI — `ostwin memory` subcommand

Add to `.agents/bin/ostwin`:

```
ostwin memory list                     List all memory namespaces with stats
ostwin memory stats [plan_id]          Show stats for a namespace
ostwin memory tree [plan_id]           Show note tree
ostwin memory clear <plan_id>          Clear all notes (requires --force)
ostwin memory delete <plan_id> <id>    Delete a single note
ostwin memory archive <plan_id>        Archive namespace, start fresh
ostwin memory export <plan_id>         Export namespace as .tar.gz
```

Implementation: calls the REST API endpoints from Phase 2.

### Phase 5: Dashboard UI

**5.1 MemoryTab** — add action buttons to the header:

```
┌──────────────────────────────────────────────────────┐
│ Memory (24 notes)              [Archive] [Clear] [↗] │
│──────────────────────────────────────────────────────│
│ Note list │ Graph │ Note detail                       │
```

- **Clear** → `DELETE /api/amem/{plan_id}` with confirmation modal
- **Archive** → `POST /api/amem/{plan_id}/archive` with confirmation
- **Export** → `GET /api/amem/{plan_id}/export` triggers download

**5.2 MemoryTab note list** — add delete icon per note:

```
┌─────────────────────────────┐
│ 🔵 Gold Mining Architecture  [🗑]  │
│ 🔵 Engine Interface Docs     [🗑]  │
```

Click trash → `DELETE /api/amem/{plan_id}/notes/{note_id}` with confirmation.

**5.3 MemoryPoolPanel** — add namespace management:

```
┌─────────────────────────────────────────────────────────┐
│ Memory Pool                                             │
├─────────────┬─────────────┬─────────────┬──────────────┤
│ ML Runtime  │ Active Slots│ Idle Timeout│ Total Notes  │
├─────────────┴─────────────┴─────────────┴──────────────┤
│                                                         │
│ Namespaces:                                             │
│ ─────────────────────────────────────────────────────── │
│ d6aff5dcdb4e  Gold Mining Game  24 notes  1.2MB  [Arc] │
│ _global                         0 notes   0B    [Clr] │
└─────────────────────────────────────────────────────────┘
```

Show all namespaces from `~/.ostwin/memory/` with:
- plan_id → title lookup from plan registry
- Note count
- Disk usage
- Archive / Clear buttons

---

## API Design

### List namespaces

```
GET /api/amem/namespaces

Response:
[
  {
    "plan_id": "d6aff5dcdb4e",
    "title": "Gold Mining Game",
    "notes_count": 24,
    "disk_bytes": 1258000,
    "created_at": "2026-05-04T11:18:14Z",
    "last_modified": "2026-05-04T11:18:14Z",
    "is_active": true,      // has an active pool slot
    "archived_versions": 0
  },
  {
    "plan_id": "_global",
    "title": "(Global)",
    "notes_count": 0,
    "disk_bytes": 0,
    ...
  }
]
```

### Clear namespace

```
DELETE /api/amem/{plan_id}

Response:
{
  "plan_id": "d6aff5dcdb4e",
  "cleared": 24,
  "action": "cleared"
}
```

If the namespace has an active pool slot, the slot is killed first (sync + cleanup).

### Archive namespace

```
POST /api/amem/{plan_id}/archive

Response:
{
  "plan_id": "d6aff5dcdb4e",
  "archived_to": "d6aff5dcdb4e.archive-20260506",
  "notes_archived": 24,
  "action": "archived"
}
```

Renames `<plan_id>/` to `<plan_id>.archive-<YYYYMMDD>/`, creates fresh empty `<plan_id>/`. Kills active pool slot if exists.

### Delete single note

```
DELETE /api/amem/{plan_id}/notes/{note_id}

Response:
{
  "plan_id": "d6aff5dcdb4e",
  "note_id": "abc-123",
  "action": "deleted"
}
```

### Export namespace

```
GET /api/amem/{plan_id}/export

Response: application/gzip
Content-Disposition: attachment; filename="memory-d6aff5dcdb4e.tar.gz"
```

Streams a tar.gz of the entire namespace directory.

---

## Files to change

| File | Change |
|---|---|
| `.agents/memory/agentic_memory/memory_system.py` | Add `clear()` method |
| `dashboard/routes/amem.py` | Add DELETE, POST archive, GET export, GET namespaces endpoints |
| `dashboard/routes/memory_mcp.py` | Add `delete_memory` tool |
| `.agents/bin/ostwin` | Add `memory` subcommand dispatch |
| `dashboard/fe/src/components/plan/MemoryTab.tsx` | Add Clear/Archive/Export buttons + delete per note |
| `dashboard/fe/src/components/mcp/MemoryPoolPanel.tsx` | Add namespace list with management buttons |
| Tests | New tests for clear, archive, delete, export endpoints |
