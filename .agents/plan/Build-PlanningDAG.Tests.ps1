<#
.SYNOPSIS
    Pester tests for Build-PlanningDAG.ps1
#>

Describe "Build-PlanningDAG" {
    BeforeAll {
        $script:builder = Join-Path $PSScriptRoot "Build-PlanningDAG.ps1"
    }

    Context "Input Validation" {
        It "fails when plan file doesn't exist" {
            $output = & $script:builder -PlanFile "/nonexistent/plan.md" 2>&1
            ($output -join "`n") | Should -Match "Plan file not found"
        }

        It "exits gracefully when no epics found" {
            $emptyPlan = Join-Path $TestDrive "empty.md"
            "# Plan: Empty`nNo epics here." | Out-File $emptyPlan -Encoding utf8
            $output = & $script:builder -PlanFile $emptyPlan 6>&1 2>&1
            ($output -join "`n") | Should -Match "No epics found"
        }
    }

    Context "DryRun Mode" {
        BeforeEach {
            $script:testPlan = Join-Path $TestDrive "test-plan.md"
            @"
# Plan: Test

## EPIC-1 - Auth Module
Build JWT authentication.

## EPIC-2 - Dashboard
Build dashboard UI.
"@ | Out-File $script:testPlan -Encoding utf8
        }

        It "shows epics without calling AI" {
            $output = & $script:builder -PlanFile $script:testPlan -DryRun 6>&1 2>&1
            $outputStr = $output -join "`n"
            $outputStr | Should -Match "DRY RUN"
            $outputStr | Should -Match "EPIC-1"
            $outputStr | Should -Match "EPIC-2"
        }

        It "does not write output file in dry-run" {
            $outFile = Join-Path $TestDrive ".planning-DAG.json"
            & $script:builder -PlanFile $script:testPlan -DryRun 2>&1 | Out-Null
            Test-Path $outFile | Should -Be $false
        }
    }

    Context "Mock Agent Output" {
        BeforeEach {
            $script:testPlan = Join-Path $TestDrive "agent-plan.md"
            @"
# Plan: Test Roles

## EPIC-1 - Data Pipeline
Roles: engineer
Build data processing pipeline.

## EPIC-2 - Reports
Build PDF reports from data.
"@ | Out-File $script:testPlan -Encoding utf8

            # Mock agent: a simple .ps1 script that returns JSON
            $script:mockAgent = Join-Path $TestDrive "mock-agent.ps1"
            @'
param([string]$Prompt)
@"
{
  "nodes": [
    {
      "task_ref": "EPIC-1",
      "title": "Data Pipeline",
      "role": "engineer",
      "candidate_roles": ["engineer"],
      "depends_on": [],
      "rationale": "Data processing is engineering work"
    },
    {
      "task_ref": "EPIC-2",
      "title": "Reports",
      "role": "reporter",
      "candidate_roles": ["reporter", "engineer"],
      "depends_on": ["EPIC-1"],
      "rationale": "Reports need data from pipeline"
    }
  ],
  "topological_order": ["EPIC-1", "EPIC-2"]
}
"@
'@ | Out-File $script:mockAgent -Encoding utf8
        }

        It "generates planning-DAG.json with correct structure" {
            $outFile = Join-Path $TestDrive ".planning-DAG.json"
            & $script:builder -PlanFile $script:testPlan -OutFile $outFile -AgentCmd $script:mockAgent 2>&1 | Out-Null
            Test-Path $outFile | Should -Be $true

            $dag = Get-Content $outFile -Raw | ConvertFrom-Json
            $dag.stage | Should -Be "planning"
            $dag.total_nodes | Should -Be 2
        }

        It "preserves candidate_roles as arrays" {
            $outFile = Join-Path $TestDrive ".planning-DAG-arrays.json"
            & $script:builder -PlanFile $script:testPlan -OutFile $outFile -AgentCmd $script:mockAgent 2>&1 | Out-Null

            $rawJson = Get-Content $outFile -Raw
            # Verify arrays in raw JSON (not just PowerShell objects)
            $rawJson | Should -Match '"candidate_roles":\s*\['
            $rawJson | Should -Match '"depends_on":\s*\['
        }

        It "assigns correct roles from AI analysis" {
            $outFile = Join-Path $TestDrive ".planning-DAG-roles.json"
            & $script:builder -PlanFile $script:testPlan -OutFile $outFile -AgentCmd $script:mockAgent 2>&1 | Out-Null

            $dag = Get-Content $outFile -Raw | ConvertFrom-Json
            $epic1 = $dag.nodes | Where-Object { $_.task_ref -eq 'EPIC-1' }
            $epic2 = $dag.nodes | Where-Object { $_.task_ref -eq 'EPIC-2' }
            $epic1.role | Should -Be 'engineer'
            $epic2.role | Should -Be 'reporter'
        }

        It "includes topological_order" {
            $outFile = Join-Path $TestDrive ".planning-DAG-topo.json"
            & $script:builder -PlanFile $script:testPlan -OutFile $outFile -AgentCmd $script:mockAgent 2>&1 | Out-Null

            $dag = Get-Content $outFile -Raw | ConvertFrom-Json
            $dag.topological_order[0] | Should -Be 'EPIC-1'
            $dag.topological_order[1] | Should -Be 'EPIC-2'
        }

        It "includes generated_at and source metadata" {
            $outFile = Join-Path $TestDrive ".planning-DAG-meta.json"
            & $script:builder -PlanFile $script:testPlan -OutFile $outFile -AgentCmd $script:mockAgent 2>&1 | Out-Null

            $dag = Get-Content $outFile -Raw | ConvertFrom-Json
            $dag.generated_at | Should -Not -BeNullOrEmpty
            $dag.source | Should -Be "agent-plan.md"
        }
    }

    Context "Normalization" {
        BeforeEach {
            $script:testPlan = Join-Path $TestDrive "norm-plan.md"
            "# Plan: Norm`n`n## EPIC-1 - Test`nTest." | Out-File $script:testPlan -Encoding utf8

            # Mock agent returns bare strings instead of arrays (the bug we guard against)
            $script:badMockAgent = Join-Path $TestDrive "bad-mock-agent.ps1"
            @'
param([string]$Prompt)
@"
{
  "nodes": [
    {
      "task_ref": "EPIC-1",
      "title": "Test",
      "role": "engineer",
      "candidate_roles": "engineer",
      "depends_on": null,
      "rationale": "test"
    }
  ]
}
"@
'@ | Out-File $script:badMockAgent -Encoding utf8
        }

        It "normalizes bare string candidate_roles to array" {
            $outFile = Join-Path $TestDrive ".planning-DAG-norm.json"
            & $script:builder -PlanFile $script:testPlan -OutFile $outFile -AgentCmd $script:badMockAgent 2>&1 | Out-Null

            $rawJson = Get-Content $outFile -Raw
            $rawJson | Should -Match '"candidate_roles":\s*\['
        }

        It "normalizes null depends_on to empty array" {
            $outFile = Join-Path $TestDrive ".planning-DAG-null.json"
            & $script:builder -PlanFile $script:testPlan -OutFile $outFile -AgentCmd $script:badMockAgent 2>&1 | Out-Null

            $rawJson = Get-Content $outFile -Raw
            $rawJson | Should -Match '"depends_on":\s*\['
        }
    }
}
