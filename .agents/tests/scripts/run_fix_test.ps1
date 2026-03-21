$AgentsDir = (Resolve-Path "$PSScriptRoot/../..").Path

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
" | Out-File "$AgentsDir/tests/fixtures/test-plan-negotiation-ok.md" -Encoding utf8

$testContent = Get-Content "$AgentsDir/tests/channel/Channel-Negotiation.Tests.ps1" -Raw
$testContent = $testContent -replace "test-plan-negotiation.md", "test-plan-negotiation-ok.md"
$testContent | Out-File "$AgentsDir/tests/channel/Channel-Negotiation.Tests.Fix.ps1" -Encoding utf8

pwsh -Command "Invoke-Pester '$AgentsDir/tests/channel/Channel-Negotiation.Tests.Fix.ps1' -Output Detailed"
