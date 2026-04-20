---
name: set-retention
description: Configure retention policy for a knowledge namespace, controlling automatic cleanup of old imports.
tags: [knowledge, retention, ttl, cleanup, policy]
trust_level: standard
---

# set-retention

## Overview

Configure a retention policy for a knowledge namespace. Retention policies control automatic cleanup of old imports based on TTL (time-to-live) settings. The background retention sweeper periodically checks and removes expired import records.

## Trigger Phrases

- "set retention for namespace X"
- "configure TTL for X"
- "apply retention policy to X"
- "set namespace X to expire after N days"
- "configure auto-delete for X"

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| namespace | string | Yes | Target namespace name |
| policy | string | Yes | Policy type: "manual" or "ttl_days" |
| ttl_days | integer | No | Days before imports expire (required if policy="ttl_days") |
| auto_delete_when_empty | boolean | No | Delete namespace when all imports expire (default: false) |

## Policy Types

### manual (default)
- No automatic cleanup
- Imports persist until manually deleted
- Best for: permanent reference materials, core documentation

### ttl_days
- Automatically delete import records older than `ttl_days`
- If `auto_delete_when_empty=true`, namespace itself is deleted when empty
- Best for: time-sensitive content, project snapshots, experimental data

## Steps

### 1. Validate Namespace Exists

```python
namespaces = knowledge_list_namespaces()
target = find(namespaces, lambda ns: ns.name == namespace)

if not target:
    return {"error": f"Namespace '{namespace}' not found", "code": "NAMESPACE_NOT_FOUND"}
```

### 2. Validate Policy Parameters

```python
if policy == "ttl_days":
    if ttl_days is None or ttl_days < 1:
        return {"error": "ttl_days must be a positive integer when policy is 'ttl_days'"}
    if ttl_days > 3650:  # 10 years max
        return {"error": "ttl_days cannot exceed 3650 (10 years)"}
```

### 3. Apply Retention Policy

Since retention is configured via the REST API, document the policy change:

```python
# Retention is applied via PUT /api/knowledge/namespaces/{namespace}/retention
# The curator documents the change in the curation report

retention_config = {
    "namespace": namespace,
    "policy": policy,
    "ttl_days": ttl_days if policy == "ttl_days" else None,
    "auto_delete_when_empty": auto_delete_when_empty,
    "configured_at": datetime.now(timezone.utc).isoformat()
}
```

### 4. Document the Change

Add to curation report:
```markdown
### Retention Policy Update

| Namespace | Policy | TTL | Auto-Delete |
|-----------|--------|-----|-------------|
| {namespace} | {policy} | {ttl_days} days | {auto_delete_when_empty} |

**Rationale:** [Explain why this policy was chosen]
```

## Recommended Retention Policies

| Namespace Type | Policy | TTL | Auto-Delete |
|----------------|--------|-----|-------------|
| Core documentation | manual | N/A | No |
| Active project | ttl_days | 90 | No |
| Sprint archives | ttl_days | 180 | No |
| Experimental | ttl_days | 7 | Yes |
| Temporary imports | ttl_days | 1 | Yes |

## Outputs

Returns a retention policy result:

```json
{
  "namespace": "project_docs",
  "policy": "ttl_days",
  "ttl_days": 90,
  "auto_delete_when_empty": false,
  "status": "configured",
  "message": "Retention policy updated. Next sweep will occur within 6 hours."
}
```

## Example Usage

```
User: "Set project_docs to expire after 90 days, but don't auto-delete"

Curator: I'll configure a 90-day TTL retention policy for 'project_docs' namespace without auto-deletion.

**Retention Policy Configuration:**

| Setting | Value |
|---------|-------|
| Namespace | project_docs |
| Policy | ttl_days |
| TTL | 90 days |
| Auto-delete when empty | No |

This means:
- Import records older than 90 days will be automatically removed
- The namespace will persist even if all imports are removed
- The retention sweeper runs every 6 hours

To apply this change, use the REST API:
```
PUT /api/knowledge/namespaces/project_docs/retention
{
  "policy": "ttl_days",
  "ttl_days": 90,
  "auto_delete_when_empty": false
}
```
```

## Safety Notes

- Retention policies only affect import **records**, not the actual indexed data
- The sweeper does NOT delete vectors or entities directly
- Namespace deletion via `auto_delete_when_empty` is irreversible
- Always backup important namespaces before enabling aggressive TTL policies
