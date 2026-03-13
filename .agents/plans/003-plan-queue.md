# Plan: Plan Queue & Continuous Execution

> Priority: 1 (foundation — unblocks Plan 6)
> Parallel: ✅ No dependencies

## Goal

Implement a plan queue with FIFO + priority ordering, continuous execution mode, plan templates, and automatic archival.

## Epics

### EPIC-001 — Plan Queue Infrastructure

#### Definition of Done
- [ ] `plans/queue/` directory for queued plans
- [ ] `plans/active/` for currently executing plans
- [ ] `plans/completed/` for archived finished plans
- [ ] `plans/failed/` for failed plans needing human review
- [ ] `Start-PlanQueue.ps1` — dequeue and process plans
- [ ] `Watch-Queue.ps1` — continuous 24/7 mode

#### Acceptance Criteria
- [ ] `ostwin queue add plan.md --priority 1` adds plan to queue
- [ ] `ostwin run --continuous` processes queue forever
- [ ] Completed plans auto-archive with RELEASE.md and quality report
- [ ] Failed plans move to failed/ directory

#### Tasks
- [ ] TASK-001 — Create queue directory structure and queue metadata format
- [ ] TASK-002 — Implement Start-PlanQueue.ps1 with FIFO dequeue
- [ ] TASK-003 — Implement Watch-Queue.ps1 for 24/7 continuous mode
- [ ] TASK-004 — Implement plan archival to completed/ and failed/

### EPIC-002 — Plan Templates & Dependencies

#### Definition of Done
- [ ] Plan templates: feature.md, release.md, hotfix.md
- [ ] Task dependency graph: `depends_on: [TASK-001]`
- [ ] Scheduler resolves ordering before spawning rooms

#### Acceptance Criteria
- [ ] `ostwin plan create --template feature` scaffolds from template
- [ ] Tasks with dependencies spawn only after deps complete
- [ ] Circular dependency detection raises error

#### Tasks
- [ ] TASK-005 — Create plan template files in plans/templates/
- [ ] TASK-006 — Implement dependency parsing in Start-Plan.ps1
- [ ] TASK-007 — Add dependency resolution to scheduler with cycle detection

---

## Configuration

```json
{
    "plan_id": "003-plan-queue",
    "priority": 1,
    "goals": {
        "definition_of_done": [
            "Plan queue with FIFO and priority ordering",
            "Continuous execution mode watches queue 24/7",
            "Completed plans auto-archive",
            "Plan templates available",
            "Task dependency graph with cycle detection"
        ],
        "acceptance_criteria": [
            "ostwin queue add works",
            "ostwin run --continuous processes queue",
            "Completed plans archived with reports"
        ]
    }
}
```
