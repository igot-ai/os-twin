<#
.SYNOPSIS
    Parses lifecycle blocks from a plan.md and generates lifecycle.json objects.

.DESCRIPTION
    End-to-end demonstration/test script that:
    1. Reads a plan.md file
    2. Extracts all Lifecycle: code blocks (ASCII diagrams)
    3. Pairs each lifecycle with its EPIC reference
    4. Calls ConvertFrom-AsciiLifecycle to parse each one
    5. Outputs the resulting lifecycle.json structures

    Use -WriteFiles to write lifecycle.json files to a target directory.

.PARAMETER PlanFile
    Path to the plan markdown file.
.PARAMETER WriteFiles
    If set, writes lifecycle.json files to OutputDir instead of stdout.
.PARAMETER OutputDir
    Directory to write lifecycle.json files (one per EPIC). Default: current dir.

.EXAMPLE
    # Show parsed lifecycles
    ./create_bash_lifecycle_loop.ps1 ./plans/my-plan.md

    # Write lifecycle.json files
    ./create_bash_lifecycle_loop.ps1 ./plans/my-plan.md -WriteFiles -OutputDir ./out
#>
param(
    [Parameter(Position = 0)]
    [string]$PlanFile = (Join-Path $PSScriptRoot '..' '..' 'plans' 'PLAN.template.md'),

    [switch]$WriteFiles,

    [string]$OutputDir = '.'
)

$ErrorActionPreference = "Stop"

# --- Load the parser ---
$parserScript = Join-Path $PSScriptRoot '..' '..' 'lifecycle' 'ConvertFrom-AsciiLifecycle.ps1'
if (-not (Test-Path $parserScript)) {
    Write-Error "Parser not found: $parserScript"
    exit 1
}
. $parserScript

# --- Validate plan file ---
if (-not (Test-Path $PlanFile)) {
    Write-Error "Plan file not found: $PlanFile"
    exit 1
}

$content = Get-Content $PlanFile -Raw

# --- Extract EPIC references ---
$epicPattern = '(?m)^#{2,3}\s+(EPIC-\d+)\s*[-—–?]\s*(.+)$'
$epicMatches = [regex]::Matches($content, $epicPattern)

# --- Extract Lifecycle blocks ---
$lifecyclePattern = '(?ism)^Lifecycle:[^\S\r\n]*\r?\n[^\S\r\n]*```[a-z]*\r?\n(.*?)\r?\n[^\S\r\n]*```'
$lifecycleMatches = [regex]::Matches($content, $lifecyclePattern)

if ($lifecycleMatches.Count -eq 0) {
    Write-Host "No lifecycle blocks found in $PlanFile." -ForegroundColor Yellow
    exit 0
}

# --- Pair lifecycles with EPICs by position ---
# Each Lifecycle: block belongs to the EPIC whose section it appears in
$results = [System.Collections.Generic.List[PSObject]]::new()

foreach ($lm in $lifecycleMatches) {
    $lifecyclePos = $lm.Index
    $lifecycleText = $lm.Groups[1].Value.Trim()

    # Find which EPIC this lifecycle belongs to
    $ownerEpic = $null
    $ownerDesc = ""
    foreach ($em in $epicMatches) {
        $epicStart = $em.Index
        $nextEpic = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
        $epicEnd = if ($nextEpic) { $nextEpic.Index } else { $content.Length }

        if ($lifecyclePos -ge $epicStart -and $lifecyclePos -lt $epicEnd) {
            $ownerEpic = $em.Groups[1].Value
            $ownerDesc = $em.Groups[2].Value.Trim()
            break
        }
    }

    if (-not $ownerEpic) {
        $ownerEpic = "UNKNOWN"
        $ownerDesc = "(no EPIC found for this lifecycle)"
    }

    # Parse the ASCII lifecycle into a lifecycle.json object
    $parsed = ConvertFrom-AsciiLifecycle -Text $lifecycleText

    $results.Add([PSCustomObject]@{
        EpicRef       = $ownerEpic
        EpicDesc      = $ownerDesc
        AsciiText     = $lifecycleText
        LifecycleJson = $parsed
    })
}

# --- Output ---
Write-Host ""
Write-Host "  Lifecycle Parser Results" -ForegroundColor Cyan
Write-Host "  Plan: $PlanFile"
Write-Host "  Found: $($results.Count) lifecycle(s) paired with EPICs"
Write-Host ""

$index = 1
foreach ($result in $results) {
    Write-Host "--- [$($result.EpicRef)] $($result.EpicDesc) ---" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  ASCII:" -ForegroundColor DarkGray
    $result.AsciiText -split "`n" | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    Write-Host ""

    if ($result.LifecycleJson) {
        $json = $result.LifecycleJson | ConvertTo-Json -Depth 10
        Write-Host "  lifecycle.json:" -ForegroundColor Green
        $json -split "`n" | ForEach-Object { Write-Host "    $_" -ForegroundColor White }

        # Summarize the state machine
        $states = $result.LifecycleJson.states
        $initial = $result.LifecycleJson.initial_state
        $stateNames = @()
        foreach ($prop in $states.PSObject.Properties) { $stateNames += $prop.Name }
        $agentStates = $stateNames | Where-Object { $_ -notin @('manager-triage', 'plan-revision', 'fixing') }
        Write-Host ""
        Write-Host "  Flow: $initial → $($agentStates -join ' → ') → passed" -ForegroundColor Cyan
        $fixState = $states.'fixing'
        if ($fixState) {
            Write-Host "  Fix loop: fixing ($($fixState.role)) → $($fixState.transitions.done)" -ForegroundColor DarkYellow
        }

        # Write file if requested
        if ($WriteFiles) {
            $fileName = "$($result.EpicRef.ToLower())-lifecycle.json"
            $filePath = Join-Path $OutputDir $fileName
            $json | Out-File -FilePath $filePath -Encoding utf8 -Force
            Write-Host "  Written: $filePath" -ForegroundColor Green
        }
    } else {
        Write-Host "  [PARSE FAILED]" -ForegroundColor Red
    }

    Write-Host ""
    $index++
}

Write-Host "Done! $($results.Count) lifecycle(s) processed." -ForegroundColor Green
