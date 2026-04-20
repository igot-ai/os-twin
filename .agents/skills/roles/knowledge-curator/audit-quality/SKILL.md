---
name: audit-quality
description: Audit the quality of a knowledge namespace by analyzing query performance, result relevance, and index health.
tags: [knowledge, quality, audit, performance, monitoring]
trust_level: standard
---

# audit-quality

## Overview

Perform a quality audit of a knowledge namespace. This skill analyzes query performance, result relevance, and index health to identify issues that may affect retrieval quality.

## Trigger Phrases

- "audit quality of namespace X"
- "check query quality for X"
- "assess namespace X performance"
- "quality check for X"
- "diagnose namespace X issues"

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| namespace | string | Yes | Target namespace name |
| sample_queries | list | No | Custom queries to test (default: built-in samples) |
| top_k | integer | No | Number of results per query (default: 5) |

## Steps

### 1. Validate Namespace Exists

```python
namespaces = knowledge_list_namespaces()
target = find(namespaces, lambda ns: ns.name == namespace)

if not target:
    return {"error": f"Namespace '{namespace}' not found", "code": "NAMESPACE_NOT_FOUND"}
```

### 2. Run Diagnostic Queries

```python
# Default sample queries for quality testing
default_queries = [
    "overview",
    "summary",
    "introduction",
    "how to",
    "example"
]

queries_to_test = sample_queries or default_queries
results = []

for query in queries_to_test:
    result = knowledge_query(namespace, query, mode="raw", top_k=top_k)
    results.append({
        "query": query,
        "chunks_count": len(result.chunks),
        "latency_ms": result.latency_ms,
        "has_results": len(result.chunks) > 0,
        "warnings": result.warnings
    })
```

### 3. Analyze Graph Health

```python
graph = knowledge_get_graph(namespace, limit=100)

graph_health = {
    "node_count": len(graph.nodes),
    "edge_count": len(graph.edges),
    "avg_connections": len(graph.edges) * 2 / max(len(graph.nodes), 1),
    "is_empty": len(graph.nodes) == 0
}
```

### 4. Calculate Quality Metrics

| Metric | Calculation | Target |
|--------|-------------|--------|
| Query success rate | queries_with_results / total_queries | > 80% |
| Avg latency | mean(latency_ms) | < 500ms |
| Graph density | edges / (nodes * (nodes-1)) | > 0.01 |
| Vector coverage | vectors / files_indexed | > 10 |

### 5. Identify Quality Issues

```python
issues = []

# Check query success rate
success_rate = sum(1 for r in results if r.has_results) / len(results)
if success_rate < 0.8:
    issues.append({
        "severity": "warning",
        "type": "low_query_success",
        "message": f"Only {success_rate*100:.0f}% of queries returned results"
    })

# Check latency
avg_latency = sum(r.latency_ms for r in results) / len(results)
if avg_latency > 500:
    issues.append({
        "severity": "info",
        "type": "slow_queries",
        "message": f"Average query latency: {avg_latency:.0f}ms"
    })

# Check graph health
if graph_health.is_empty:
    issues.append({
        "severity": "warning",
        "type": "empty_graph",
        "message": "No entities extracted - LLM may be unavailable"
    })
```

### 6. Generate Recommendations

| Issue | Recommendation |
|-------|----------------|
| Low query success | Re-import with LLM for better extraction |
| High latency | Consider namespace splitting for large datasets |
| Empty graph | Check ANTHROPIC_API_KEY availability |
| Low vector coverage | Re-import documents |

## Outputs

Returns a quality audit result:

```json
{
  "namespace": "project_docs",
  "overall_quality": "good|degraded|poor",
  "metrics": {
    "query_success_rate": 0.85,
    "avg_latency_ms": 120,
    "graph_density": 0.05,
    "vector_coverage": 35.7
  },
  "query_results": [
    {
      "query": "overview",
      "has_results": true,
      "chunks_count": 5,
      "latency_ms": 95
    }
  ],
  "graph_health": {
    "node_count": 120,
    "edge_count": 45,
    "is_empty": false
  },
  "issues": [],
  "recommendations": []
}
```

## Quality Thresholds

| Metric | Good | Degraded | Poor |
|--------|------|----------|------|
| Query success rate | > 90% | 70-90% | < 70% |
| Avg latency | < 200ms | 200-500ms | > 500ms |
| Graph density | > 0.05 | 0.01-0.05 | < 0.01 |

## Example Usage

```
User: "Audit the quality of project_docs namespace"

Curator: I'll perform a quality audit of the 'project_docs' namespace.

[knowledge_list_namespaces()]
[knowledge_query("project_docs", "overview", mode="raw", top_k=5)]
[knowledge_query("project_docs", "summary", mode="raw", top_k=5)]
[knowledge_query("project_docs", "example", mode="raw", top_k=5)]
[knowledge_get_graph("project_docs", limit=100)]

**Quality Audit Report for 'project_docs'**

| Metric | Value | Status |
|--------|-------|--------|
| Query success rate | 85% | ✅ Good |
| Avg latency | 120ms | ✅ Good |
| Graph nodes | 120 | ✅ Healthy |
| Graph edges | 45 | ✅ Connected |

**Overall Quality: GOOD**

No issues detected. The namespace is performing well.

**Recommendations:**
- Continue monitoring with weekly quality audits
- Consider setting up automated alerts for latency > 500ms
```

## Continuous Monitoring

For ongoing quality monitoring, schedule regular audits:

| Frequency | Use Case |
|-----------|----------|
| Daily | High-traffic namespaces |
| Weekly | Standard production namespaces |
| Monthly | Archive/reference namespaces |
