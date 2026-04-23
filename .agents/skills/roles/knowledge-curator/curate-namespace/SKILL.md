---
name: curate-namespace
description: Use this skill to manage the full namespace lifecycle — list existing namespaces, create new ones, import document folders, and monitor import progress.
---

# curate-namespace

## Overview

This is the core namespace lifecycle skill for the Knowledge Curator. It covers the day-to-day operations of listing, creating, and populating knowledge namespaces. Every curation session should start here to understand the current state before taking any action.

## When to Use

- At the start of every curation session — call `knowledge_list_namespaces()` first
- When a user asks to create a new knowledge base
- When importing documents from a local folder into a namespace
- When checking on the progress of a running import job
- When producing a namespace inventory report

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `knowledge_list_namespaces` | List all namespaces with stats (file count, chunk count, entity count, storage) |
| `knowledge_create_namespace` | Create a new namespace with name, language, and description |
| `knowledge_import_folder` | Import all supported files from an absolute folder path into a namespace |
| `knowledge_get_import_status` | Poll a background import job by job_id until completion |

## Instructions

### 1. Inventory — List All Namespaces

Always start by listing existing namespaces:

```
knowledge_list_namespaces()
```

Review the returned stats for each namespace:
- `stats.files_indexed` — number of source files processed
- `stats.chunks` — number of text chunks stored
- `stats.entities` — number of entities extracted by the LLM
- `stats.relations` — number of entity-entity relations in the graph
- `stats.vectors` — number of embedding vectors

Flag namespaces that are:
- **Empty** — 0 files, 0 chunks (created but never populated)
- **Partially imported** — files indexed but 0 entities (LLM extraction may have failed)
- **Stale** — `updated_at` is significantly older than expected

### 2. Create a Namespace

When creating a new namespace, validate these constraints:

- **Name format:** lowercase alphanumeric + dashes/underscores, 1–64 chars, must start with a letter or digit
- **Language:** human language of the expected content (default `"English"`) — used by the LLM during entity extraction
- **Description:** optional but recommended for discoverability

```
knowledge_create_namespace("project_docs", "English", "Internal product handbook v3")
```

**Error codes to handle:**
- `INVALID_NAMESPACE_ID` — name doesn't match the naming rules
- `NAMESPACE_EXISTS` — namespace already exists (use `knowledge_import_folder` to add content)
- `MAX_NAMESPACES_REACHED` — namespace quota exceeded

### 3. Import Documents

Import all supported files from an absolute folder path:

```
knowledge_import_folder("project_docs", "/Users/me/projects/docs")
```

**Pre-import validation:**
- Path MUST be absolute (relative paths are rejected with `INVALID_FOLDER_PATH`)
- Path MUST exist and be a directory
- Supported types: docx, pdf, xlsx, pptx, html, txt, md, csv, json, xml, yaml, yml, rtf, png, jpg, jpeg, gif, bmp, tiff, webp

**Auto-creation:** If the namespace doesn't exist, `knowledge_import_folder` auto-creates it.

**Force re-import:** Set `force=True` to re-process files whose content hash already exists (useful when source files changed but filename/path stayed the same).

### 4. Monitor Import Progress

After `knowledge_import_folder` returns a `job_id`, poll for progress:

```
knowledge_get_import_status("project_docs", "abc-123-uuid")
```

**Job states:** `pending → running → completed | failed | interrupted | cancelled`

**Polling strategy:**
- Wait 5–10 seconds between polls for small imports (< 50 files)
- Wait 30 seconds between polls for large imports (> 100 files)
- Stop polling when state is `completed`, `failed`, or `cancelled`

**On failure:** Report the `errors` field from the status response. Common causes:
- Missing `ANTHROPIC_API_KEY` — images skipped, entity extraction may be empty
- File read errors — permissions or corrupted files
- LLM rate limiting — retry with smaller batch

### 5. Produce Namespace Inventory Report

After completing the curation session, produce `namespace-inventory.md`:

```markdown
# Namespace Inventory — [Date]

## Summary
- Total namespaces: N
- Total files indexed: N
- Total chunks: N

## Per-Namespace Status

| Namespace | Files | Chunks | Entities | Relations | Status | Last Updated |
|-----------|-------|--------|----------|-----------|--------|-------------|
| project_docs | 42 | 1,204 | 356 | 189 | healthy | 2026-04-23 |
| temp_test | 0 | 0 | 0 | 0 | empty | 2026-04-20 |

## Actions Taken
- [list of operations performed]

## Recommendations
- [follow-up actions]
```

## Anti-Patterns

- **Do not** create namespaces with uppercase letters or spaces — the name validation will reject them
- **Do not** use relative paths with `knowledge_import_folder` — always use absolute paths
- **Do not** spam `knowledge_get_import_status` faster than every 5 seconds — it's a background job
- **Do not** skip the initial `knowledge_list_namespaces` call — you need the baseline to make informed decisions
- **Do not** call `knowledge_import_folder` without confirming the folder path with the user

## Verification

After completing this skill:
1. All namespaces are listed with current stats
2. Any new namespaces were created with valid names and descriptions
3. Import jobs were submitted and polled to completion
4. The `namespace-inventory.md` artifact was produced
