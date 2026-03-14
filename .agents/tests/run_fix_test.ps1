
"# Plan: Negotiation Test

## Epics

### EPIC-001 — First task
This is a description.
- Bullet 1
- Bullet 2

#### Definition of Done
- [ ] Task done

#### Acceptance Criteria
- [ ] Test passes
" | Out-File "/Users/paulaan/PycharmProjects/agent-os/.agents/tests/test-plan-negotiation-ok.md" -Encoding utf8

$testContent = Get-Content "/Users/paulaan/PycharmProjects/agent-os/.agents/tests/Channel-Negotiation.Tests.ps1" -Raw
$testContent = $testContent -replace "test-plan-negotiation.md", "test-plan-negotiation-ok.md"
$testContent | Out-File "/Users/paulaan/PycharmProjects/agent-os/.agents/tests/Channel-Negotiation.Tests.Fix.ps1" -Encoding utf8

pwsh -Command "Invoke-Pester /Users/paulaan/PycharmProjects/agent-os/.agents/tests/Channel-Negotiation.Tests.Fix.ps1 -Output Detailed"
