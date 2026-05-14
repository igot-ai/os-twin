---
title: DAG Format
description: Reference for DAG.json structure, Kahn's algorithm, wave scheduling, and both DAG builders.
sidebar:
  order: 9
---

The DAG (Directed Acyclic Graph) is the execution plan that determines the order in which war-rooms are activated. It is stored as `DAG.json` in the war-rooms directory.

## DAG.json Structure

```json
{
  "generated_at": "2026-03-27T12:27:48Z",
  "total_nodes": 9,
  "max_depth": 1,
  "nodes": { },
  "topological_order": [],
  "critical_path": [],
  "critical_path_length": 2,
  "waves": { }
}
```

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `generated_at` | `string` | ISO 8601 generation timestamp |
| `total_nodes` | `int` | Total number of nodes in the DAG |
| `max_depth` | `int` | Maximum dependency depth |
| `topological_order` | `string[]` | Valid execution order |
| `critical_path` | `string[]` | Longest dependency chain |
| `critical_path_length` | `int` | Length of the critical path |

## Node Schema

Each node represents a war-room:

```json
{
  "EPIC-001": {
    "room_id": "room-001",
    "task_ref": "EPIC-001",
    "role": "engineer",
    "candidate_roles": ["engineer"],
    "depends_on": "PLAN-REVIEW",
    "dependents": [],
    "depth": 1,
    "on_critical_path": false
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `room_id` | `string` | Associated war-room directory |
| `task_ref` | `string` | Epic or task reference |
| `role` | `string` | Primary assigned role |
| `candidate_roles` | `string[]` | All roles that may work on this node |
| `depends_on` | `string\|null` | Upstream dependency (single or null) |
| `dependents` | `string[]` | Downstream nodes that depend on this |
| `depth` | `int` | Distance from root (0-indexed) |
| `on_critical_path` | `bool` | Whether this node is on the critical path |

## The PLAN-REVIEW Root

Every DAG has a `PLAN-REVIEW` root node at depth 0:

```json
{
  "PLAN-REVIEW": {
    "room_id": "room-000",
    "task_ref": "PLAN-REVIEW",
    "role": "architect",
    "candidate_roles": ["architect", "manager"],
    "depends_on": null,
    "dependents": ["EPIC-001", "EPIC-002", "EPIC-003"],
    "depth": 0,
    "on_critical_path": true
  }
}
```

`PLAN-REVIEW` always:
- Maps to `room-000`
- Has `depends_on: null` (no upstream)
- Is on the critical path
- Runs the architect role
- Must pass before any epic starts

## Wave Scheduling

Waves group nodes by depth for parallel execution:

```json
{
  "waves": {
    "0": ["PLAN-REVIEW"],
    "1": ["EPIC-001", "EPIC-002", "EPIC-003", "EPIC-004"],
    "2": ["EPIC-005", "EPIC-006"]
  }
}
```

The manager processes waves sequentially:
1. **Wave 0**: Execute `PLAN-REVIEW`
2. **Wave 1**: When wave 0 passes, launch all wave-1 rooms in parallel
3. **Wave 2**: When all wave-1 dependencies pass, launch wave-2 rooms

Within a wave, all rooms run concurrently up to `max_concurrent_rooms`.

## Kahn's Algorithm

OSTwin uses Kahn's algorithm for topological sorting:

1. Compute in-degree for each node
2. Enqueue all nodes with in-degree 0 (roots)
3. While the queue is not empty:
   - Dequeue a node, append to sorted order
   - For each dependent, decrement in-degree
   - If in-degree reaches 0, enqueue
4. If sorted order length equals total nodes, the graph is a valid DAG
5. Otherwise, a cycle exists (error)

The algorithm also computes:
- **Depth**: Maximum distance from any root
- **Critical path**: Longest chain through the DAG
- **Waves**: Nodes grouped by depth

## Critical Path

The critical path is the longest dependency chain. It determines the minimum wall-clock time for plan execution (assuming unlimited parallelism).

```json
{
  "critical_path": ["PLAN-REVIEW", "EPIC-002"],
  "critical_path_length": 2
}
```

Nodes on the critical path are flagged with `on_critical_path: true` and may receive priority scheduling.

## DAG Builders

OSTwin includes two DAG builders:

### PowerShell Builder

The primary builder runs inside the manager loop. It:
1. Parses `PLAN.md` for epic definitions
2. Extracts `depends_on` fields
3. Runs Kahn's algorithm
4. Creates room directories
5. Writes `DAG.json`

Located in the manager PowerShell scripts.

### Python Builder

A standalone Python builder for testing and validation:

```bash
python -m agents.dag_builder PLAN.md --output DAG.json
```

Both builders produce identical `DAG.json` output. The Python builder is used in CI tests.

## Validation Rules

The DAG builder enforces:

| Rule | Error |
|------|-------|
| No cycles | `Circular dependency detected: EPIC-001 → EPIC-002 → EPIC-001` |
| Valid references | `Unknown dependency: EPIC-099` |
| Single root | `Multiple roots found` (warning, not error) |
| Connected graph | `Orphan nodes: EPIC-007` (warning) |

## Runtime Updates

The DAG is immutable once generated. Runtime state changes (pass, fail) are tracked in individual room `status` files, not in DAG.json.

The manager checks the DAG to determine which rooms can be activated:

```
for each room in current_wave:
    if all dependencies are "passed":
        activate room
```

:::tip
Use `--dry-run` with `ostwin run` to generate and inspect the DAG without executing any rooms.
:::

:::note
Multi-dependency support (`depends_on` as an array) is handled by the room's `config.json`, while `DAG.json` flattens to single parent for topological ordering. Rooms with multiple dependencies wait for all parents.
:::
