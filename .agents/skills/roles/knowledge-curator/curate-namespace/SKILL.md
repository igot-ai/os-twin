---
name: curate-namespace
description: Perform a comprehensive curation audit of a knowledge namespace, assessing health, identifying issues, and generating recommendations.
tags: [knowledge, curation, audit, namespace]
trust_level: standard
---

# curate-namespace

## Overview

Perform a comprehensive curation audit of a knowledge namespace. This skill assesses namespace health, identifies issues (stale data, low quality, oversized storage), and generates actionable recommendations.

## Trigger Phrases

- "curate namespace X"
- "audit namespace X"
- "assess namespace health"
- "review namespace X"
- "check namespace quality"

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| namespace | string | Yes | Name of the namespace to curate |
| deep | boolean | No | Perform deep analysis including query samples (default: false) |

## Steps

### 1. Gather Namespace Metadata

```python
# Get namespace list and find target
namespaces = knowledge_list_namespaces()
target = find(namespaces, lambda ns: ns.name == namespace)

if not target:
    return {"error": f"Namespace '{namespace}' not found"}
```

### 2. Assess Basic Health Metrics

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| `stats.files_indexed` | > 0 | 0 | N/A |
| `stats.vectors` | > 0 | 0 | N/A |
| `stats.entities` | > 0 | 0-10 | N/A |
| `stats.relations` | > 0 | 0-5 | N/A |
| `imports[].status` | all completed | any running | any failed |
| `updated_at` (last modified) | < 30 days | 30-90 days | > 90 days |

### 3. Identify Issues

```python
issues = []

# Check for empty namespace
if target.stats.vectors == 0:
    issues.append({
        "severity": "warning",
        "type": "empty_namespace",
        "message": "Namespace has no vectors indexed"
    })

# Check for stale imports
for imp in target.imports:
    if imp.status == "failed":
        issues.append({
            "severity": "warning",
            "type": "failed_import",
            "message": f"Import job {imp.job_id} failed"
        })

# Check for old data
from datetime import datetime, timezone
age_days = (datetime.now(timezone.utc) - target.updated_at).days
if age_days > 90:
    issues.append({
        "severity": "info",
        "type": "stale_data",
        "message": f"Namespace not updated in {age_days} days"
    })
```

### 4. Sample Query Quality (if deep=true)

```python
if deep:
    # Run sample queries to assess retrieval quality
    sample_queries = ["test", "overview", "summary"]
    for q in sample_queries:
        result = knowledge_query(namespace, q, mode="raw", top_k=5)
        if not result.chunks:
            issues.append({
                "severity": "info",
                "type": "empty_query_result",
                "message": f"Query '{q}' returned no results"
            })
```

### 5. Generate Recommendations

Based on identified issues, generate recommendations:

| Issue | Recommendation |
|-------|----------------|
| Empty namespace | Consider deletion or import data |
| Stale data (>90 days) | Schedule refresh or apply TTL retention |
| Failed imports | Retry import or check source folder |
| Low entity count | May indicate extraction issues |

## Outputs

Returns a curation result dict:

```json
{
  "namespace": "project_docs",
  "health": "healthy|degraded|critical",
  "metrics": {
    "files_indexed": 42,
    "vectors": 1500,
    "entities": 120,
    "relations": 45,
    "last_updated": "2026-04-15T10:00:00Z",
    "age_days": 5
  },
  "issues": [
    {
      "severity": "info",
      "type": "stale_data",
      "message": "Namespace not updated in 45 days"
    }
  ],
  "recommendations": [
    "Consider setting a 90-day TTL retention policy",
    "Schedule weekly refresh for active content"
  ]
}
```

## Example Usage

```
User: "Curate the project_docs namespace"

Curator: I'll perform a curation audit of the 'project_docs' namespace.

[knowledge_list_namespaces()]
[knowledge_get_graph("project_docs")]

The namespace has:
- 42 files indexed
- 1,500 vectors
- 120 entities
- 45 relations

**Health Status: HEALTHY**

**Issues Found:**
- Namespace not updated in 45 days (info)

**Recommendations:**
1. Consider setting a 90-day TTL retention policy
2. Schedule weekly refresh for active content
```
