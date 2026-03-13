# Plan: Human-in-the-Loop Framework

> Priority: 3 (depends on: Plan 5 quality gates)
> Parallel: ✅ After dependencies

## Goal

Build the escalation engine, approval workflow, and multi-channel notification system for seamless human intervention.

## Epics

### EPIC-001 — Escalation Engine & Approval Workflow

#### Definition of Done
- [ ] `human/Invoke-Escalation.ps1` — rules engine with YAML policies
- [ ] `human/Request-Approval.ps1` — block-until-approved workflow
- [ ] `human/policies/escalation.yaml` — configurable trigger rules
- [ ] `human/policies/auto-approve.yaml` — auto-approval rules

#### Acceptance Criteria
- [ ] `failed-final` state triggers escalation notification
- [ ] Critical-path tasks block until human approves
- [ ] Cost threshold triggers pause-and-notify
- [ ] All human decisions logged in audit trail

#### Tasks
- [ ] TASK-001 — Implement Invoke-Escalation.ps1 with YAML policy parser
- [ ] TASK-002 — Implement Request-Approval.ps1 with blocking workflow
- [ ] TASK-003 — Create escalation and auto-approve policy files
- [ ] TASK-004 — Integrate escalation into Start-ManagerLoop.ps1

### EPIC-002 — Multi-Channel Notifiers

#### Definition of Done
- [ ] `human/notifiers/Send-TerminalNotice.ps1`
- [ ] `human/notifiers/Send-SlackNotice.ps1`
- [ ] `human/notifiers/Send-WebhookNotice.ps1`

#### Acceptance Criteria
- [ ] Terminal notifications display formatted alerts
- [ ] Slack notifications send to configured channel
- [ ] Webhook notifications POST JSON to configured URL

#### Tasks
- [ ] TASK-005 — Implement Send-TerminalNotice.ps1
- [ ] TASK-006 — Implement Send-SlackNotice.ps1 with Slack API
- [ ] TASK-007 — Implement Send-WebhookNotice.ps1 with generic POST

---

## Configuration

```json
{
    "plan_id": "007-human-in-loop",
    "priority": 3,
    "goals": {
        "definition_of_done": [
            "Escalation engine with YAML policy rules",
            "Approval workflow with blocking and non-blocking modes",
            "Multi-channel notifications: terminal, Slack, webhook",
            "All human decisions logged in audit trail"
        ],
        "acceptance_criteria": [
            "failed-final triggers escalation",
            "Cost threshold triggers pause",
            "Notifications delivered to configured channels"
        ]
    }
}
```
