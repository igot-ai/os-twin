# Agent OS — Expand-Plan.ps1 Pester Tests

BeforeAll {
    $script:ExpandPlan = Join-Path $PSScriptRoot "Expand-Plan.ps1"
}

Describe "Expand-Plan.ps1" {
    BeforeEach {
        $script:tempDir = Join-Path $TestDrive "expand-plan-tests-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:tempDir -Force | Out-Null
        $script:planFile = Join-Path $script:tempDir "PLAN.md"
        
        # Create a mock agent script that writes a predefined output
        $script:mockAgent = Join-Path $script:tempDir "mock-agent.sh"
        @"
#!/bin/bash
# Mock agent script
PROMPT="`$*"

if [[ "`$PROMPT" != *"Short desc."* ]]; then
  echo "TEST FAILED: Prompt did not contain the epic text"
  exit 1
fi

echo '## Epic: EPIC-001 — Expanded Title

This is an expanded description.

depends_on: [EPIC-000]
complexity: XL

#### Definition of Done
- [ ] Requirement 1
- [ ] Requirement 2
- [ ] Requirement 3
- [ ] Requirement 4
- [ ] Requirement 5

#### Acceptance Criteria
- [ ] Test 1
- [ ] Test 2
- [ ] Test 3
- [ ] Test 4
- [ ] Test 5'
"@ | Out-File -FilePath $script:mockAgent -Encoding utf8 -NoNewline
        chmod +x $script:mockAgent
    }

    It "fails if plan file does not exist" {
        $badPath = Join-Path $script:tempDir "nonexistent.md"
        $result = pwsh -NoProfile -Command "& '$script:ExpandPlan' -PlanFile '$badPath'" 2>&1
        $LASTEXITCODE | Should -Not -Be 0
        ($result -join "`n") | Should -Match "Plan file not found"
    }

    It "skips well-specified epics" {
        $content = @"
# Plan: Test

## Epic: EPIC-002 — Fully Spec'd

Description

#### Definition of Done
- [ ] One
- [ ] Two
- [ ] Three
- [ ] Four
- [ ] Five

#### Acceptance Criteria
- [ ] T1
- [ ] T2
- [ ] T3
- [ ] T4
- [ ] T5
"@
        $content | Out-File -FilePath $script:planFile -Encoding utf8
        $outputFile = Join-Path $script:tempDir "PLAN.refined.md"

        $output = pwsh -NoProfile -Command "& '$script:ExpandPlan' -PlanFile '$script:planFile' -AgentCmd '$script:mockAgent'" 2>&1
        ($output -join "`n") | Should -Match "is already well-specified. Skipping."
        
        $refinedContent = Get-Content $outputFile -Raw
        $refinedContent.Trim() | Should -Be $content.Trim()
    }

    It "expands underspecified epics" {
        $content = @"
# Plan: Test

## Config
working_dir: /tmp

## Epic: EPIC-001 — Simple Title

Short desc.

#### Definition of Done
- [ ] One

---

## Notes
Review before starting.
"@
        $content | Out-File -FilePath $script:planFile -Encoding utf8
        $outputFile = Join-Path $script:tempDir "PLAN.refined.md"

        $output = pwsh -NoProfile -Command "& '$script:ExpandPlan' -PlanFile '$script:planFile' -AgentCmd '$script:mockAgent'" 2>&1
        ($output -join "`n") | Should -Match "Expanding EPIC-001"
        ($output -join "`n") | Should -Match "Success: EPIC-001 expanded"

        Test-Path $outputFile | Should -BeTrue
        $refinedContent = Get-Content $outputFile -Raw
        
        $refinedContent | Should -Match "Expanded Title"
        $refinedContent | Should -Match "depends_on:"
        $refinedContent | Should -Match "complexity: XL"
        $refinedContent | Should -Match "- \[ \] Requirement 5"
        $refinedContent | Should -Match "- \[ \] Test 5"
        $refinedContent | Should -Match "## Config"
        $refinedContent | Should -Match "working_dir: /tmp"
        $refinedContent | Should -Match "## Notes"
        $refinedContent | Should -Match "Review before starting."
        
        # Original should be preserved
        $originalContent = Get-Content $script:planFile -Raw
        $originalContent | Should -Not -Match "Expanded Title"
    }

    It "expands epics with ### headers without deleting subsequent epics" {
        $content = @"
# Plan: Test

### EPIC-001 — Simple Title

Short desc.

#### Definition of Done
- [ ] One

### EPIC-002 — Another Title

Another short desc.

#### Definition of Done
- [ ] One
- [ ] Two
- [ ] Three
- [ ] Four
- [ ] Five

#### Acceptance Criteria
- [ ] One
- [ ] Two
- [ ] Three
- [ ] Four
- [ ] Five
"@
        $content | Out-File -FilePath $script:planFile -Encoding utf8
        $outputFile = Join-Path $script:tempDir "PLAN.refined.md"

        $output = pwsh -NoProfile -Command "& '$script:ExpandPlan' -PlanFile '$script:planFile' -AgentCmd '$script:mockAgent'" 2>&1
        ($output -join "`n") | Should -Match "Expanding EPIC-001"
        ($output -join "`n") | Should -Match "Success: EPIC-001 expanded"
        ($output -join "`n") | Should -Match "EPIC-002 is already well-specified. Skipping."

        Test-Path $outputFile | Should -BeTrue
        $refinedContent = Get-Content $outputFile -Raw
        
        $refinedContent | Should -Match "Expanded Title"
        # We must verify EPIC-002 is still present in the file and wasn't swallowed by EPIC-001's regex
        $refinedContent | Should -Match "### EPIC-002 — Another Title"
        $refinedContent | Should -Match "Another short desc."
    }

    It "runs in DryRun mode without modifying files" {
        $content = @"
# Plan: Test

## Epic: EPIC-001 — Simple Title

Short desc.

#### Definition of Done
- [ ] One
"@
        $content | Out-File -FilePath $script:planFile -Encoding utf8
        $outputFile = Join-Path $script:tempDir "PLAN.refined.md"

        $output = pwsh -NoProfile -Command "& '$script:ExpandPlan' -PlanFile '$script:planFile' -DryRun -AgentCmd '$script:mockAgent'" 2>&1
        ($output -join "`n") | Should -Match "\[DryRun\] Would expand EPIC-001"
        
        Test-Path $outputFile | Should -BeFalse
    }
}
