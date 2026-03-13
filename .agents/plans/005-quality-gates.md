# Plan: Quality Gate Pipeline

> Priority: 2 (depends on: Plan 2 role engine, Plan 4 observability)
> Parallel: ✅ After dependencies

## Goal

Build the automated quality gate pipeline that runs lint, test, coverage, security, and goal pre-checks before QA review.

## Epics

### EPIC-001 — Quality Gate Scripts

#### Definition of Done
- [ ] `quality/gates/Invoke-LintGate.ps1` + tests
- [ ] `quality/gates/Invoke-TestGate.ps1` + tests
- [ ] `quality/gates/Invoke-CoverageGate.ps1` + tests
- [ ] `quality/gates/Invoke-SecurityGate.ps1` + tests
- [ ] `quality/gates/Invoke-GoalPreCheck.ps1` + tests
- [ ] Gate pipeline runner: `Invoke-QualityPipeline.ps1`

#### Acceptance Criteria
- [ ] Gates run automatically after engineer posts "done"
- [ ] Each gate outputs pass/fail with evidence
- [ ] Failed gates block QA review and trigger retry
- [ ] Gate results written to war-room audit trail

#### Tasks
- [ ] TASK-001 — Implement Invoke-LintGate.ps1 (configurable linter)
- [ ] TASK-002 — Implement Invoke-TestGate.ps1 (run project tests)
- [ ] TASK-003 — Implement Invoke-CoverageGate.ps1 (threshold from config)
- [ ] TASK-004 — Implement Invoke-SecurityGate.ps1 (SAST scan)
- [ ] TASK-005 — Implement Invoke-GoalPreCheck.ps1 (verify DoD addressed)
- [ ] TASK-006 — Implement Invoke-QualityPipeline.ps1 (orchestrate gates)

### EPIC-002 — Benchmarks & Feedback Analysis

#### Definition of Done
- [ ] `quality/benchmarks/Invoke-Benchmark.ps1` — score output against rubric
- [ ] `quality/feedback/Get-FeedbackPatterns.ps1` — analyze recurring QA failures
- [ ] Historical score tracking in `history.json`

#### Acceptance Criteria
- [ ] `ostwin quality report --plan auth-system` generates quality summary
- [ ] Feedback patterns identify top 3 recurring failure types

#### Tasks
- [ ] TASK-007 — Implement scoring rubric and Invoke-Benchmark.ps1
- [ ] TASK-008 — Implement Get-FeedbackPatterns.ps1 with pattern detection

---

## Configuration

```json
{
    "plan_id": "005-quality-gates",
    "priority": 2,
    "goals": {
        "definition_of_done": [
            "Quality gate pipeline with lint, test, coverage, security gates",
            "Goal pre-check verifies DoD before QA",
            "Benchmarks score agent output",
            "Feedback analysis identifies recurring failures"
        ],
        "acceptance_criteria": [
            "Gates run automatically after engineer done message",
            "Failed gates block QA and trigger retry",
            "ostwin quality report generates summary"
        ]
    }
}
```
