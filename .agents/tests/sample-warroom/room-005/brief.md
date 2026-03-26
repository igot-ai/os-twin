# EPIC-005

osTwin Agent Orchestration Layer

**Phase:** 4
**Owner:** Supervisor Agent (osTwin)
**Priority:** P0 — Differentiator
**Estimated Effort:** 4 days

### Description

This is where the demo becomes mind-blowing. Wire osTwin's Agent OS as the operational backbone that not only BUILT the app but continuously OPERATES it. Four specialized agents work autonomously: the Content Writer generates campaigns, the Segment Builder identifies new opportunities, the A/B Test Runner optimizes performance, and the Analytics Reporter delivers merchant insights — all coordinated through osTwin's agent orchestration.

### Definition of Done

- [ ] All 4 agents operate autonomously on scheduled and event-triggered cadences
- [ ] Agent actions are auditable via activity log visible to merchant
- [ ] Merchants can "talk to" their AI marketing manager via chat interface
- [ ] Agent recommendations improve over time based on performance feedback loop
- [ ] Dashboard shows agent activity timeline with business impact metrics

### Tasks

- [ ] **T-005.1** — Define osTwin Agent specifications:

  **Content Writer Agent**
  - Trigger: New segment created, campaign scheduled, weekly refresh
  - Actions: Generate content variants, suggest A/B tests, refresh stale content
  - Constraints: Brand voice guidelines, product catalog boundaries, compliance rules

  **Segment Builder Agent**
  - Trigger: Daily data analysis, significant behavior shift detected
  - Actions: Suggest new segments, merge overlapping segments, retire empty segments
  - Constraints: Minimum segment size (50 members), maximum overlap threshold (70%)

  **A/B Test Runner Agent**
  - Trigger: Campaign launch, significance threshold reached, performance anomaly
  - Actions: Design test matrix, monitor results, promote winners, pause losers
  - Constraints: Minimum sample size, maximum test duration, statistical validity

  **Analytics Reporter Agent**
  - Trigger: Weekly schedule, campaign end, merchant query
  - Actions: Generate performance reports, identify trends, recommend optimizations
  - Output: Natural language insight summaries + data visualizations

- [ ] **T-005.2** — Build agent orchestration controller:
  ```
  AgentOrchestrator
    ├── scheduleAgent(agentType, cron, merchantId)
    ├── triggerAgent(agentType, event, context)
    ├── getAgentStatus(merchantId) → running/idle/error
    └── getAgentHistory(merchantId) → action log with outcomes
  ```
- [ ] **T-005.3** — Implement merchant-facing AI chat interface:
  - "Show me my best performing segment this week"
  - "Create a campaign for customers who haven't bought in 60 days"
  - "Why did conversion drop on the VIP banner?"
  - Routes to appropriate agent, returns structured response + action
- [ ] **T-005.4** — Build agent activity dashboard:
  - Timeline view of all agent actions
  - Impact metrics per agent action (revenue influenced, segments created, tests completed)
  - Agent "confidence" indicator on each recommendation
  - Merchant approval workflow for high-impact actions (optional guardrail)
- [ ] **T-005.5** — Implement feedback loop: agent recommendations marked as accepted/rejected feed back into future suggestions
- [ ] **T-005.6** — Create agent performance analytics:
  - Content Writer: average variant performance, creative diversity score
  - Segment Builder: segment precision (conversion lift vs. general population)
  - A/B Test Runner: test velocity, win rate, average lift discovered
  - Analytics Reporter: insight accuracy, actionability score

### Acceptance Criteria

- [ ] Content Writer Agent generates campaign for new segment without human input within 30 seconds
- [ ] Segment Builder Agent identifies a new high-value segment from cold data within first 24 hours
- [ ] A/B Test Runner correctly promotes winning variant and logs rationale
- [ ] Chat interface responds to "create a win-back campaign" with a complete campaign draft in < 20 seconds
- [ ] Agent activity log shows clear cause → action → outcome chain for audit
- [ ] Feedback loop demonstrably improves content quality over 3+ cycles



## Working Directory
/Users/paulaan/PycharmProjects/omega-persona

## Created
2026-03-26T10:29:15Z
