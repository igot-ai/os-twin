---
name: ontology-knowledge
description: Use this skill to explore ontology namespaces in the knowledge base.
---

# ontology-knowledge

## Overview

Evaluates retrieval quality of knowledge namespaces by running probe queries across all three modes (`raw`, `graph`, `summarized`), measuring latency, and scoring each namespace as `healthy`, `degraded`, or `critical`.

## When to Use

- During periodic quality audits
- After a large import to verify queryability
- When users report poor retrieval or missing results
- When `curate-namespace` reveals suspicious stats (files > 0 but entities = 0)

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `knowledge_list_namespaces` | Get baseline stats per namespace |
| `knowledge_query` | Run probe queries in `raw`, `graph`, `summarized` modes |

## Instructions

### 1. Establish Baseline Stats

```
knowledge_list_namespaces()
```

Record per-namespace: `files_indexed`, `chunks`, `entities`, `relations`. Flag:
- Files > 0 but chunks = 0 → ingestion failure
- Chunks > 0 but entities = 0 → LLM extraction unavailable

### 2. Design Probe Queries

For each namespace, construct 3–5 probes:
1. **Broad topic** — "What is this project about?"
2. **Specific fact** — "What is the API rate limit?"
3. **Entity name** — "Tell me about AuthService"
4. **Edge-case** — a query about something that shouldn't exist
5. **Cross-document** — "How do X and Y relate?"

### 3. Run Probes in All Modes

```
knowledge_query("ns", "query", mode="raw", top_k=5)
knowledge_query("ns", "query", mode="graph", top_k=5)
knowledge_query("ns", "query", mode="summarized", top_k=5)
```

Record: `chunks` count, `entities`, `answer`, `latency_ms`, `warnings`.

### 4. Score Namespace Health

| Score | Criteria |
|-------|----------|
| **Healthy** | All probes return relevant results, latency within bounds, no warnings |
| **Degraded** | Sparse/irrelevant results, high latency, or `llm_unavailable` warning |
| **Critical** | Empty results from most probes, possible index corruption |

### 5. Produce Quality Audit Report

Save `quality-audit.md` with per-namespace probe results, health scores, and recommendations. Flag degraded/critical namespaces for `propose-rebuild`.

## Anti-Patterns

- **Do not** skip baseline stats — you need context before probing
- **Do not** use only one query mode — compare all three
- **Do not** ignore `warnings` in query responses
- **Do not** audit mid-import — wait for completion first

## Verification

1. All namespaces probed with multiple queries across all modes
2. Each namespace has a health score
3. Degraded/critical namespaces have documented issues
4. `quality-audit.md` artifact produced
