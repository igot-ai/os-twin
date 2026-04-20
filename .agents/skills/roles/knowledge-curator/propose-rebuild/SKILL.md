---
name: propose-rebuild
description: Propose a rebuild of a corrupted or degraded knowledge namespace, including backup, deletion, and re-import steps.
tags: [knowledge, rebuild, repair, recovery, namespace]
trust_level: standard
---

# propose-rebuild

## Overview

Propose a rebuild plan for a corrupted or severely degraded knowledge namespace. This skill generates a step-by-step recovery plan including backup, deletion, and re-import of all content. **Important:** The curator does not execute the rebuild directly — this skill produces a proposal for user approval and engineer execution.

## Trigger Phrases

- "propose rebuild for namespace X"
- "rebuild corrupted namespace X"
- "repair namespace X"
- "recovery plan for X"
- "reset namespace X"

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| namespace | string | Yes | Target namespace name |
| reason | string | No | Reason for rebuild (default: "degraded quality") |
| backup_first | boolean | No | Create backup before rebuild (default: true) |

## Steps

### 1. Validate Namespace Exists

```python
namespaces = knowledge_list_namespaces()
target = find(namespaces, lambda ns: ns.name == namespace)

if not target:
    return {"error": f"Namespace '{namespace}' not found", "code": "NAMESPACE_NOT_FOUND"}
```

### 2. Assess Rebuild Necessity

Identify conditions that warrant a rebuild:

| Condition | Severity | Action |
|-----------|----------|--------|
| Corrupted vector index | Critical | Rebuild required |
| Missing entities | High | Consider rebuild |
| Query failures | High | Rebuild recommended |
| Stale/inconsistent data | Medium | Refresh may suffice |
| Performance degradation | Medium | Optimize or rebuild |

### 3. Gather Source Information

```python
# Collect import history for re-import after rebuild
sources = []
for imp in target.imports:
    if imp.status == "completed":
        sources.append({
            "folder_path": imp.folder_path,
            "files_count": imp.files_count,
            "imported_at": imp.finished_at
        })
```

### 4. Create Backup (if requested)

```python
if backup_first:
    backup_result = knowledge_backup_namespace(namespace)
    backup_path = backup_result.archive_path
```

### 5. Generate Rebuild Plan

```markdown
## Rebuild Proposal for {namespace}

### Current State
- Files indexed: {stats.files_indexed}
- Vectors: {stats.vectors}
- Entities: {stats.entities}
- Last updated: {updated_at}

### Issues Identified
- [List of issues requiring rebuild]

### Rebuild Steps

1. **Backup** (optional but recommended)
   ```bash
   # Via MCP tool
   knowledge_backup_namespace("{namespace}")
   ```
   Backup will be saved to: {backup_path}

2. **Delete Namespace**
   ```python
   # Requires confirmation
   knowledge_delete_namespace("{namespace}", confirm=True)
   ```

3. **Re-create Namespace**
   ```python
   knowledge_create_namespace("{namespace}", language="English")
   ```

4. **Re-import Sources**
   For each source folder:
   ```python
   knowledge_import_folder("{namespace}", "{folder_path}")
   ```

5. **Verify Rebuild**
   ```python
   # Check new stats
   knowledge_list_namespaces()
   # Run test queries
   knowledge_query("{namespace}", "test", mode="raw")
   ```

### Estimated Duration
- Backup: ~1 minute per GB
- Deletion: Instant
- Re-import: ~30 seconds per 100 files

### Rollback Plan
If rebuild fails, restore from backup:
```python
knowledge_restore_namespace("{backup_path}", as_name="{namespace}", overwrite=True, confirm=True)
```
```

### 6. Request User Approval

The curator presents the proposal and asks for explicit confirmation before any destructive operations.

## Outputs

Returns a rebuild proposal:

```json
{
  "namespace": "project_docs",
  "rebuild_required": true,
  "reason": "Corrupted vector index detected",
  "backup_recommended": true,
  "estimated_duration_minutes": 15,
  "source_folders": [
    "/Users/me/projects/docs",
    "/Users/me/projects/api-reference"
  ],
  "proposal_markdown": "# Rebuild Proposal...\n\n...",
  "requires_confirmation": true
}
```

## Example Usage

```
User: "Propose a rebuild for the project_docs namespace"

Curator: I'll analyze the 'project_docs' namespace and generate a rebuild proposal.

[knowledge_list_namespaces()]
[knowledge_get_graph("project_docs", limit=100)]

**Rebuild Proposal for 'project_docs'**

### Current State
| Metric | Value |
|--------|-------|
| Files indexed | 42 |
| Vectors | 1,500 |
| Entities | 120 |
| Last updated | 2026-04-15 |

### Issues Identified
1. Empty graph detected - entities may have been corrupted
2. Recent queries returning inconsistent results

### Recommended Action: REBUILD

**Rebuild Steps:**

1. **Backup** (recommended)
   ```
   knowledge_backup_namespace("project_docs")
   ```
   Estimated time: ~30 seconds

2. **Delete Namespace** ⚠️ Destructive
   ```
   knowledge_delete_namespace("project_docs", confirm=True)
   ```
   Requires your explicit confirmation.

3. **Re-create & Re-import**
   ```
   knowledge_create_namespace("project_docs")
   knowledge_import_folder("project_docs", "/Users/me/projects/docs")
   knowledge_import_folder("project_docs", "/Users/me/projects/api-reference")
   ```

4. **Verify**
   Run test queries to confirm successful rebuild.

**Estimated Total Time:** 15 minutes

**Do you want to proceed with this rebuild?**
Please confirm with "yes, proceed with rebuild" to execute.
```

## Safety Notes

- **Never execute rebuild without explicit user confirmation**
- Always backup before deletion when possible
- Document all source folders for re-import
- Verify backups are valid before proceeding
- Have a rollback plan ready
- Escalate to engineer for complex rebuilds

## When to Rebuild vs. Refresh

| Situation | Action |
|-----------|--------|
| Content outdated | Refresh (non-destructive) |
| Index corrupted | Rebuild (destructive) |
| Performance degraded | Audit first, rebuild if needed |
| Missing entities | Refresh, then rebuild if persists |
| Schema change required | Rebuild (may need code changes) |
