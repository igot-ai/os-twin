    It "expands ### formatted epics and preserves section boundaries" {
        $content = @"
# Plan

### EPIC-003 Title

Short description.

#### Definition of Done
- [ ] 1

#### Acceptance Criteria
- [ ] 1

### EPIC-004 Next Epic
Content of the next epic
"@
        $content | Out-File -FilePath $script:planFile -Encoding utf8
        $outputFile = Join-Path $script:tempDir "PLAN.refined.md"

        $output = pwsh -NoProfile -Command "& '$script:ExpandPlan' -PlanFile '$script:planFile' -AgentCmd '$script:mockAgent'" 2>&1
        $output | Out-Host

        $refinedContent = Get-Content $outputFile -Raw
        $refinedContent | Should -Match "### EPIC-004 Next Epic"
        $refinedContent | Should -Match "Content of the next epic"
    }