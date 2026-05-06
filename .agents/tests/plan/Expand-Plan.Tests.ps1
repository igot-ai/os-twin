# Agent OS — Expand-Plan.ps1 Pester Tests

BeforeAll {
    $script:ExpandPlan = Join-Path (Resolve-Path "$PSScriptRoot/../../plan").Path "Expand-Plan.ps1"
}

Describe "Expand-Plan.ps1" {
    BeforeEach {
        $script:tempDir = Join-Path $TestDrive "expand-plan-tests-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:tempDir -Force | Out-Null
        $script:planFile = Join-Path $script:tempDir "PLAN.md"
        
        # Create a mock agent script that writes a predefined output
        $expandedOutput = @"
## EPIC-001 - Expanded Title

This is an expanded description.

#### Implementation Strategy
1. Phase 1: Setup
2. Phase 2: Implementation

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
- [ ] Test 5
"@
        if ($IsWindows) {
            $script:mockAgent = Join-Path $script:tempDir "mock-agent.ps1"
            @"
`$prompt = `$args -join ' '
if (`$prompt -notlike '*Short desc.*') {
    Write-Error 'TEST FAILED: Prompt did not contain the epic text'
    exit 1
}
Write-Output @'
$expandedOutput
'@
"@ | Out-File -FilePath $script:mockAgent -Encoding utf8 -NoNewline
        } else {
            $script:mockAgent = Join-Path $script:tempDir "mock-agent.sh"
            @"
#!/bin/bash
PROMPT="`$*"
if [[ "`$PROMPT" != *"Short desc."* ]]; then
  echo "TEST FAILED: Prompt did not contain the epic text"
  exit 1
fi
echo '$($expandedOutput -replace "'", "'\\''")' 
"@ | Out-File -FilePath $script:mockAgent -Encoding utf8 -NoNewline
            chmod +x $script:mockAgent
        }
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

## EPIC-002 - Fully Spec'd

- Description bullet 1
- Description bullet 2

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

        $output = pwsh -NoProfile -Command "& '$script:ExpandPlan' -PlanFile '$script:planFile' -AgentCmd '$script:mockAgent'" 2>&1
        ($output -join "`n") | Should -Match "is already well-specified. Skipping."

        # Plan file must be unchanged (no expansion performed)
        $updatedContent = Get-Content $script:planFile -Raw
        $updatedContent.Trim() | Should -Be $content.Trim()
    }

    It "expands underspecified epics" {
        $content = @"
# Plan: Test

## Config
working_dir: /tmp

## EPIC-001 — Simple Title

Short desc.

#### Definition of Done
- [ ] One

---

## Notes
Review before starting.
"@
        $content | Out-File -FilePath $script:planFile -Encoding utf8

        $output = pwsh -NoProfile -Command "& '$script:ExpandPlan' -PlanFile '$script:planFile' -AgentCmd '$script:mockAgent'" 2>&1
        ($output -join "`n") | Should -Match "Expanding EPIC-001"
        ($output -join "`n") | Should -Match "\[DONE\]"

        # Plan file is updated in-place — no .refined.md created
        $refinedFile = Join-Path $script:tempDir "PLAN.refined.md"
        Test-Path $refinedFile | Should -BeFalse

        $updatedContent = Get-Content $script:planFile -Raw
        $updatedContent | Should -Match "Expanded Title"
        $updatedContent | Should -Match "depends_on:"
        $updatedContent | Should -Match "complexity: XL"
        $updatedContent | Should -Match "- \[ \] Requirement 5"
        $updatedContent | Should -Match "#### Implementation Strategy"
        $updatedContent | Should -Match "Phase 1: Setup"
        $updatedContent | Should -Match "- \[ \] Test 5"
        $updatedContent | Should -Match "## Config"
        $updatedContent | Should -Match "working_dir: /tmp"
        $updatedContent | Should -Match "## Notes"
        $updatedContent | Should -Match "Review before starting."
    }

    It "expands epics with ## EPIC- headers without deleting subsequent epics" {
        $content = @"
# Plan: Test

## EPIC-001 - Simple Title

Short desc.

#### Definition of Done
- [ ] One

## EPIC-002 - Another Title

- Bullet 1
- Bullet 2

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

        $output = pwsh -NoProfile -Command "& '$script:ExpandPlan' -PlanFile '$script:planFile' -AgentCmd '$script:mockAgent'" 2>&1
        ($output -join "`n") | Should -Match "Expanding EPIC-001"
        ($output -join "`n") | Should -Match "\[DONE\]"
        ($output -join "`n") | Should -Match "EPIC-002 is already well-specified. Skipping."

        # Plan file is updated in-place
        $refinedFile = Join-Path $script:tempDir "PLAN.refined.md"
        Test-Path $refinedFile | Should -BeFalse

        $updatedContent = Get-Content $script:planFile -Raw
        $updatedContent | Should -Match "Expanded Title"
        # EPIC-002 must still be present and not swallowed by EPIC-001's regex
        $updatedContent | Should -Match "## EPIC-002 - Another Title"
        $updatedContent | Should -Match "Another short desc."
    }

    It "runs in DryRun mode without modifying files" {
        $content = @"
# Plan: Test

## EPIC-001 - Simple Title

Short desc.

#### Definition of Done
- [ ] One
"@
        $content | Out-File -FilePath $script:planFile -Encoding utf8

        $output = pwsh -NoProfile -Command "& '$script:ExpandPlan' -PlanFile '$script:planFile' -DryRun -AgentCmd '$script:mockAgent'" 2>&1
        ($output -join "`n") | Should -Match "\[DryRun\] Would expand EPIC-001"

        # Original file must be untouched in DryRun
        $updatedContent = Get-Content $script:planFile -Raw
        $updatedContent.Trim() | Should -Be $content.Trim()
    }

    It "POSTs expanded content to the dashboard save endpoint" {
        $content = @"
# Plan: Test

## EPIC-001 - Simple Title

Short desc.

#### Definition of Done
- [ ] One
"@
        $content | Out-File -FilePath $script:planFile -Encoding utf8

        # --- Start a mock HTTP server on an ephemeral port ---
        $port = Get-Random -Minimum 19000 -Maximum 19999
        $mockPort = $port
        $captured = Join-Path $script:tempDir "captured_body.json"

        $serverJob = Start-Job -ScriptBlock {
            param($port, $outFile)
            $listener = [System.Net.HttpListener]::new()
            $listener.Prefixes.Add("http://localhost:$port/")
            $listener.Start()
            try {
                $ctx = $listener.GetContext()
                $reader = [System.IO.StreamReader]::new($ctx.Request.InputStream)
                $body = $reader.ReadToEnd()
                $body | Out-File -FilePath $outFile -Encoding utf8 -NoNewline
                $ctx.Response.StatusCode = 200
                $respBytes = [System.Text.Encoding]::UTF8.GetBytes('{"ok":true}')
                $ctx.Response.ContentLength64 = $respBytes.Length
                $ctx.Response.OutputStream.Write($respBytes, 0, $respBytes.Length)
                $ctx.Response.OutputStream.Close()
            }
            finally { $listener.Stop() }
        } -ArgumentList $mockPort, $captured

        Start-Sleep -Milliseconds 400   # let listener bind

        try {
            $env:DASHBOARD_URL = "http://localhost:$mockPort"
            $output = pwsh -NoProfile -Command "
                `$env:DASHBOARD_URL = 'http://localhost:$mockPort'
                & '$script:ExpandPlan' -PlanFile '$script:planFile' -PlanId 'testplan123' -AgentCmd '$script:mockAgent'
            " 2>&1
        }
        finally {
            $env:DASHBOARD_URL = $null
            $serverJob | Wait-Job -Timeout 5 | Out-Null
            Remove-Job $serverJob -Force -ErrorAction SilentlyContinue
        }

        # Verify the save endpoint was called and body contains expanded content
        Test-Path $captured | Should -BeTrue -Because "mock server should have received a POST body"
        $body = Get-Content $captured -Raw | ConvertFrom-Json
        $body.content | Should -Match "Expanded Title"
        $body.change_source | Should -Be "expansion"

        # Verify dashboard sync message in output
        ($output -join "`n") | Should -Match "Synced to dashboard"
    }

    It "does not call the save endpoint in DryRun mode" {
        $content = @"
# Plan: Test

## EPIC-001 - Simple Title

Short desc.

#### Definition of Done
- [ ] One
"@
        $content | Out-File -FilePath $script:planFile -Encoding utf8

        # --- Start a mock HTTP server that records whether it was hit ---
        $port = Get-Random -Minimum 19000 -Maximum 19999
        $hitFile = Join-Path $script:tempDir "was_hit.txt"

        $serverJob = Start-Job -ScriptBlock {
            param($port, $hitFile)
            $listener = [System.Net.HttpListener]::new()
            $listener.Prefixes.Add("http://localhost:$port/")
            $listener.Start()
            try {
                # Wait up to 3 seconds for a request
                $task = $listener.GetContextAsync()
                if ($task.Wait(3000)) {
                    "HIT" | Out-File -FilePath $hitFile -Encoding utf8 -NoNewline
                    $ctx = $task.Result
                    $ctx.Response.StatusCode = 200
                    $ctx.Response.OutputStream.Close()
                }
            }
            finally { $listener.Stop() }
        } -ArgumentList $port, $hitFile

        Start-Sleep -Milliseconds 400

        try {
            pwsh -NoProfile -Command "
                `$env:DASHBOARD_URL = 'http://localhost:$port'
                & '$script:ExpandPlan' -PlanFile '$script:planFile' -PlanId 'testplan123' -DryRun -AgentCmd '$script:mockAgent'
            " 2>&1 | Out-Null
        }
        finally {
            $serverJob | Wait-Job -Timeout 5 | Out-Null
            Remove-Job $serverJob -Force -ErrorAction SilentlyContinue
        }

        # In DryRun mode — server must NOT have been hit
        (Test-Path $hitFile) | Should -BeFalse -Because "DryRun must not call the save API"
    }

    It "does not run holistic dependency analysis (moved to Review-Dependencies.ps1)" {
        # Expand-Plan no longer runs dependency analysis — that responsibility
        # moved to Review-Dependencies.ps1 which runs AFTER war-rooms are created.
        # This test verifies Expand-Plan does NOT output dep analysis messages.
        $content = @"
# Plan: Multi-EPIC Dep Test

## EPIC-001 - Database Schema

Short desc.

#### Definition of Done
- [ ] Schema created

## EPIC-002 - API Layer

Short desc.

#### Definition of Done
- [ ] API endpoints
"@
        $content | Out-File -FilePath $script:planFile -Encoding utf8

        # Mock agent that returns per-EPIC expansion only
        if ($IsWindows) {
            $depMockAgent = Join-Path $script:tempDir "dep-mock-agent.ps1"
            @'
$prompt = $args -join ' '
if ($prompt -like '*## EPIC-002*') {
    Write-Output @"
## EPIC-002 - API Layer

This builds REST APIs on top of the database.

#### Definition of Done
- [ ] REST endpoints implemented
- [ ] Input validation
- [ ] Error handling
- [ ] API documentation
- [ ] Integration tests

#### Acceptance Criteria
- [ ] GET /resources returns 200
- [ ] POST /resources creates record
- [ ] Invalid input returns 422
- [ ] Auth required returns 401
- [ ] Rate limiting works

depends_on: []
"@
    exit 0
}
if ($prompt -like '*EPIC-001*') {
    Write-Output @"
## EPIC-001 - Database Schema

This builds the database foundation.

#### Definition of Done
- [ ] Schema migrations created
- [ ] Indexes optimized
- [ ] Seed data scripts
- [ ] Schema docs updated
- [ ] Migration rollback tested

#### Acceptance Criteria
- [ ] Tables created successfully
- [ ] Foreign keys enforced
- [ ] Rollback works cleanly
- [ ] Seed data loads
- [ ] Performance baseline set

depends_on: []
"@
    exit 0
}
Write-Error "UNEXPECTED PROMPT"
exit 1
'@ | Out-File -FilePath $depMockAgent -Encoding utf8 -NoNewline
        } else {
            $depMockAgent = Join-Path $script:tempDir "dep-mock-agent.sh"
            @'
#!/bin/bash
PROMPT="$*"

if [[ "$PROMPT" == *"## EPIC-002"* ]]; then
  echo "## EPIC-002 - API Layer

This builds REST APIs on top of the database.

#### Definition of Done
- [ ] REST endpoints implemented
- [ ] Input validation
- [ ] Error handling
- [ ] API documentation
- [ ] Integration tests

#### Acceptance Criteria
- [ ] GET /resources returns 200
- [ ] POST /resources creates record
- [ ] Invalid input returns 422
- [ ] Auth required returns 401
- [ ] Rate limiting works

depends_on: []"
  exit 0
fi

if [[ "$PROMPT" == *"EPIC-001"* ]]; then
  echo "## EPIC-001 - Database Schema

This builds the database foundation.

#### Definition of Done
- [ ] Schema migrations created
- [ ] Indexes optimized
- [ ] Seed data scripts
- [ ] Schema docs updated
- [ ] Migration rollback tested

#### Acceptance Criteria
- [ ] Tables created successfully
- [ ] Foreign keys enforced
- [ ] Rollback works cleanly
- [ ] Seed data loads
- [ ] Performance baseline set

depends_on: []"
  exit 0
fi

echo "UNEXPECTED PROMPT"
exit 1
'@ | Out-File -FilePath $depMockAgent -Encoding utf8 -NoNewline
            chmod +x $depMockAgent
        }

        $output = pwsh -NoProfile -Command "& '$script:ExpandPlan' -PlanFile '$script:planFile' -AgentCmd '$depMockAgent'" 2>&1
        $outputStr = $output -join "`n"

        # Expand-Plan should NOT run dep analysis
        $outputStr | Should -Not -Match "DEP-ANALYSIS"
        $outputStr | Should -Not -Match "Analyzing dependencies"

        # .planning-DAG.json should NOT be created by Expand-Plan
        $dagFile = Join-Path $script:tempDir ".planning-DAG.json"
        Test-Path $dagFile | Should -BeFalse
    }
}
