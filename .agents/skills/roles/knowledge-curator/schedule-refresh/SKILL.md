---
name: schedule-refresh
description: Schedule or trigger a refresh of a knowledge namespace by re-importing all source folders.
tags: [knowledge, refresh, schedule, update, reindex]
trust_level: standard
---

# schedule-refresh

## Overview

Schedule or immediately trigger a refresh of a knowledge namespace. Refreshing re-imports all source folders from the namespace's import history, updating the index with the latest content from the source files.

## Trigger Phrases

- "refresh namespace X"
- "schedule refresh for X"
- "reindex namespace X"
- "update knowledge base X"
- "sync namespace X with source"

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| namespace | string | Yes | Target namespace name |
| schedule | string | No | Schedule type: "now", "daily", "weekly" (default: "now") |

## Steps

### 1. Validate Namespace Exists

```python
namespaces = knowledge_list_namespaces()
target = find(namespaces, lambda ns: ns.name == namespace)

if not target:
    return {"error": f"Namespace '{namespace}' not found", "code": "NAMESPACE_NOT_FOUND"}
```

### 2. Check Import History

```python
imports = target.imports
if not imports:
    return {
        "error": f"Namespace '{namespace}' has no import history to refresh",
        "suggestion": "Use knowledge_import_folder to add content first"
    }
```

### 3. Check for In-Progress Imports

```python
running = [imp for imp in imports if imp.status in ("pending", "running")]
if running:
    return {
        "error": f"Cannot refresh while imports are in progress",
        "running_jobs": [imp.job_id for imp in running]
    }
```

### 4. Trigger Refresh

```python
# Use the knowledge_refresh_namespace MCP tool
result = knowledge_refresh_namespace(namespace)

return {
    "namespace": namespace,
    "status": "refreshing",
    "job_ids": result.job_ids,
    "imports_count": result.imports_count
}
```

### 5. Monitor Progress

```python
# Poll job status
for job_id in result.job_ids:
    status = knowledge_get_import_status(namespace, job_id)
    # Report progress to user
```

## Schedule Types

### now (default)
- Immediately triggers refresh of all source folders
- Returns job IDs for progress tracking
- Best for: urgent updates, after source file changes

### daily
- Sets up recurring refresh every 24 hours
- Requires external scheduler (cron, systemd timer)
- Best for: frequently updated content

### weekly
- Sets up recurring refresh every 7 days
- Requires external scheduler
- Best for: moderately changing content

## Outputs

Returns a refresh result:

```json
{
  "namespace": "project_docs",
  "status": "refreshing",
  "job_ids": ["job-abc-123", "job-def-456"],
  "imports_count": 2,
  "message": "Refresh triggered for 2 source folders. Poll job_ids for progress."
}
```

## Example Usage

```
User: "Refresh the project_docs namespace"

Curator: I'll trigger a refresh of the 'project_docs' namespace.

[knowledge_list_namespaces()]
[knowledge_refresh_namespace("project_docs")]

**Refresh Triggered**

| Detail | Value |
|--------|-------|
| Namespace | project_docs |
| Jobs submitted | 2 |
| Job IDs | job-abc-123, job-def-456 |

The following source folders will be re-imported:
1. /Users/me/projects/docs
2. /Users/me/projects/api-reference

I'll monitor the progress. Would you like me to poll the job status?

[knowledge_get_import_status("project_docs", "job-abc-123")]
[knowledge_get_import_status("project_docs", "job-def-456")]

**Current Status:**
- job-abc-123: running (45%)
- job-def-456: pending

Refresh in progress. Estimated completion: ~2 minutes.
```

## Scheduling Recommendations

| Content Type | Refresh Frequency | Rationale |
|--------------|-------------------|-----------|
| Active project docs | Daily | Frequent updates |
| API reference | Weekly | Less frequent changes |
| Archived docs | Manual | Rarely changes |
| User manuals | Weekly | Moderate updates |

## Safety Notes

- Refreshes use `force=True` to re-process all files
- Concurrent imports are blocked per-namespace
- Large namespaces may take several minutes to refresh
- Always check job status before triggering another refresh
