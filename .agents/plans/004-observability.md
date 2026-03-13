# Plan: Observability — Tracing & Metrics

> Priority: 1 (foundation — unblocks Plans 5, 6)  
> Parallel: ✅ No dependencies

## Goal

Implement distributed tracing, metrics collection, and trace correlation so every agent action is observable and queryable.

## Epics

### EPIC-001 — Distributed Tracing

#### Definition of Done
- [ ] `observe/New-Trace.ps1` — create trace context (trace_id, span_id)
- [ ] `observe/New-Span.ps1` — create child spans
- [ ] `observe/Close-Span.ps1` — close span with duration
- [ ] Trace correlation: every log line carries trace_id, span_id, room_id
- [ ] JSON schemas for trace-span and log-event

#### Acceptance Criteria
- [ ] Plan run generates a trace_id propagated to all war-rooms
- [ ] Each war-room session creates child spans (engineer, QA, gates)
- [ ] `ostwin observe traces --plan auth-system` lists all spans
- [ ] Pester tests verify trace context propagation

#### Tasks
- [ ] TASK-001 — Implement New-Trace.ps1 and New-Span.ps1
- [ ] TASK-002 — Add trace context to Start-ManagerLoop.ps1
- [ ] TASK-003 — Add trace context to Start-Engineer.ps1 and Start-QA.ps1
- [ ] TASK-004 — Create JSON schemas for spans and events

### EPIC-002 — Metrics Collection

#### Definition of Done
- [ ] `observe/Write-Metric.ps1` — emit metric points
- [ ] Key metrics: room_duration, retry_count, qa_pass_rate, token_usage, cost
- [ ] SQLite storage for queryable history
- [ ] Metric point JSON schema

#### Acceptance Criteria
- [ ] `ostwin observe metrics` shows current metric values
- [ ] `Export-ToSqlite.ps1` stores traces and metrics
- [ ] Historical queries work: time range, room, plan filters

#### Tasks
- [ ] TASK-005 — Implement Write-Metric.ps1 with metric types (counter, gauge, histogram)
- [ ] TASK-006 — Emit metrics from manager loop and agent runners
- [ ] TASK-007 — Enhance Export-ToSqlite.ps1 for traces and metrics tables

---

## Configuration

```json
{
    "plan_id": "004-observability",
    "priority": 1,
    "goals": {
        "definition_of_done": [
            "Distributed tracing with trace_id and span_id",
            "Metrics collection for key operational metrics",
            "SQLite storage for queryable history",
            "Trace correlation in all log lines"
        ],
        "acceptance_criteria": [
            "Plan run generates traceable spans",
            "ostwin observe commands work",
            "Metrics queryable from SQLite"
        ]
    }
}
```
