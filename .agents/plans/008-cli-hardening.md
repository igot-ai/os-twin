# Plan: CLI Hardening & New Commands

> Priority: 2 (depends on: Plan 1 all PS1 ports)
> Parallel: ✅ After dependencies

## Goal

Harden the `ostwin` CLI with new commands for queue, observe, quality, and ensure all dispatches use PowerShell with proper argument translation.

## Epics

### EPIC-001 — New CLI Commands

#### Definition of Done
- [ ] `ostwin queue add/list/remove` — plan queue management
- [ ] `ostwin observe traces/metrics` — observability queries
- [ ] `ostwin quality report/gates` — quality reporting
- [ ] `ostwin team roster/assign` — team management
- [ ] All new commands dispatch to PowerShell scripts

#### Acceptance Criteria
- [ ] `ostwin --help` shows all new commands
- [ ] Every command works with both `--flag` and `-Flag` syntax
- [ ] Tab completion for subcommands (zsh/bash)

#### Tasks
- [ ] TASK-001 — Add ostwin queue commands (add, list, remove, status)
- [ ] TASK-002 — Add ostwin observe commands (traces, metrics, query)
- [ ] TASK-003 — Add ostwin quality commands (report, gates, benchmark)
- [ ] TASK-004 — Add ostwin team commands (roster, assign, health)

### EPIC-002 — CLI Polish & Testing

#### Definition of Done
- [ ] Shell completion scripts (zsh, bash)
- [ ] `ostwin doctor` — comprehensive diagnostic tool
- [ ] CLI integration tests via Pester
- [ ] Version bump to v0.2.0

#### Acceptance Criteria
- [ ] Tab completion works for all commands
- [ ] `ostwin doctor` checks all dependencies and config
- [ ] CLI tests verify all command dispatches

#### Tasks
- [ ] TASK-005 — Generate shell completion scripts
- [ ] TASK-006 — Implement ostwin doctor command
- [ ] TASK-007 — Write CLI integration tests
- [ ] TASK-008 — Version bump and changelog

---

## Configuration

```json
{
    "plan_id": "008-cli-hardening",
    "priority": 2,
    "goals": {
        "definition_of_done": [
            "New CLI commands for queue, observe, quality, team",
            "Shell completion for zsh and bash",
            "ostwin doctor diagnostic tool",
            "CLI integration tests"
        ],
        "acceptance_criteria": [
            "All commands dispatch to PowerShell scripts",
            "Tab completion works",
            "Version bumped to v0.2.0"
        ]
    }
}
```
