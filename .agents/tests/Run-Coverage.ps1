#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run Pester tests with code coverage for core agent lifecycle scripts.

.DESCRIPTION
    Generates an XML coverage report (JaCoCo format) for:
      - Start-ManagerLoop.ps1
      - Start-EphemeralAgent.ps1
      - Start-DynamicRole.ps1
      - Invoke-Agent.ps1

    See: https://pester.dev/docs/usage/code-coverage

.EXAMPLE
    ./Run-Coverage.ps1
    ./Run-Coverage.ps1 -TestPath .agents/tests/roles/manager
#>
param(
    [string]$TestPath = '',
    [string]$OutputDir = ''
)

$scriptRoot = $PSScriptRoot
$repoRoot   = (Resolve-Path (Join-Path $scriptRoot ".." "..")).Path
$agentsDir  = Join-Path $repoRoot ".agents"

$coverageOutputDir = if ($OutputDir) { $OutputDir } else { Join-Path $scriptRoot "coverage" }
if (-not (Test-Path $coverageOutputDir)) {
    New-Item -ItemType Directory -Path $coverageOutputDir -Force | Out-Null
}

$config = New-PesterConfiguration

# --- Test discovery ---
$config.Run.Path = if ($TestPath) { $TestPath } else { Join-Path $scriptRoot }
$config.Run.Exit = $false

# --- Output ---
$config.Output.Verbosity = "Detailed"

# --- Test results (JUnit XML for CI) ---
$config.TestResult.Enabled    = $true
$config.TestResult.OutputPath = Join-Path $coverageOutputDir "test-results.xml"
$config.TestResult.OutputFormat = "JUnitXml"

# --- Code coverage ---
$config.CodeCoverage.Enabled = $true
$config.CodeCoverage.Path    = @(
    (Join-Path $agentsDir "roles" "manager"  "Start-ManagerLoop.ps1"),
    (Join-Path $agentsDir "roles" "_base"    "Start-EphemeralAgent.ps1"),
    (Join-Path $agentsDir "roles" "_base"    "Start-DynamicRole.ps1"),
    (Join-Path $agentsDir "roles" "_base"    "Invoke-Agent.ps1")
)
$config.CodeCoverage.OutputPath   = Join-Path $coverageOutputDir "coverage.xml"
$config.CodeCoverage.OutputFormat = "JaCoCo"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Agent OS — Pester Coverage Run" -ForegroundColor Cyan
Write-Host "  Test path : $($config.Run.Path)" -ForegroundColor Cyan
Write-Host "  Coverage  : $($config.CodeCoverage.OutputPath)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$result = Invoke-Pester -Configuration $config

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
if ($result.FailedCount -eq 0) {
    Write-Host "  PASSED: $($result.PassedCount) tests" -ForegroundColor Green
} else {
    Write-Host "  FAILED: $($result.FailedCount) / $($result.TotalCount) tests" -ForegroundColor Red
}
Write-Host "  Coverage report: $($config.CodeCoverage.OutputPath)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

exit $result.FailedCount
