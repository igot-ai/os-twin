<#
.SYNOPSIS
    Maximizes planning detail in a PLAN.md using AI refinement.

.DESCRIPTION
    Parses a plan markdown file, identifies epics, and uses an AI architect
    to expand each epic into a detailed plan with clear Definition of Done,
    Acceptance Criteria, and dependency analysis.

.PARAMETER PlanFile
    Path to the raw plan markdown file.
.PARAMETER OutFile
    Path to write the refined plan. Defaults to <original>.refined.md next to the source file.
.PARAMETER DryRun
    Show what would be refined without calling the AI or writing the file.
.PARAMETER AgentCmd
    Optional path to a custom agent runner script. Used in tests to inject a mock AI.
    When not set, the real Invoke-Agent.ps1 with the 'architect' role is used.

.EXAMPLE
    ./Expand-Plan.ps1 -PlanFile "./plans/plan-001.md"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$PlanFile,

    [string]$OutFile = '',

    [switch]$DryRun,

    [string]$AgentCmd = ''
)

# --- Resolve paths ---
$scriptDir = $PSScriptRoot
$agentsDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
$invokeAgent = Join-Path $agentsDir "roles" "_base" "Invoke-Agent.ps1"
$logModule = Join-Path $agentsDir "lib" "Log.psm1"
$utilsModule = Join-Path $agentsDir "lib" "Utils.psm1"

if (Test-Path $logModule) { Import-Module $logModule -Force }
if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }

# --- Validate plan file ---
if (-not (Test-Path $PlanFile)) {
    Write-Error "Plan file not found: $PlanFile"
    exit 1
}

$planContent = Get-Content $PlanFile -Raw
$planBase = [IO.Path]::GetFileNameWithoutExtension($PlanFile)
$planDir = Split-Path $PlanFile
if (-not $OutFile) {
    $OutFile = Join-Path $planDir "${planBase}.refined.md"
}

# --- Parsing logic ---
$epicPattern = '(?m)^(## Epic:\s+|###\s+)(EPIC-\d+)\s*[—–-]\s*(.+)$'

$epicMatches = [regex]::Matches($planContent, $epicPattern)
if ($epicMatches.Count -eq 0) {
    Write-Host "No epics found to refine in $PlanFile"
    exit 0
}

Write-Host ""
Write-Host "=== Ostwin Plan Expander ===" -ForegroundColor Cyan
Write-Host "  Plan: $PlanFile"
Write-Host "  Epics to refine: $($epicMatches.Count)"
Write-Host ""

# --- Refinement loop ---
$refinedEpics = @{}

# Create a temporary room for expansion
$warRoomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR }
               else { Join-Path (Split-Path $agentsDir) ".war-rooms" }
$expansionRoom = Join-Path $warRoomsDir "room-expansion"
if (-not (Test-Path $expansionRoom)) {
    New-Item -ItemType Directory -Path $expansionRoom -Force | Out-Null
}

foreach ($em in $epicMatches) {
    $epicRef = $em.Groups[2].Value
    $epicTitle = $em.Groups[3].Value.Trim()

    # Find epic section
    $epicStart = $em.Index
    $nextMatch = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
    $epicEnd = if ($nextMatch) { $nextMatch.Index } else { $planContent.Length }
    $epicSection = $planContent.Substring($epicStart, $epicEnd - $epicStart)

    # --- Check if already well-specified ---
    $dodPatternCheck = '(?s)#### Definition of Done\s*\n(.*?)(?=####|###|---|\z)'
    $acPatternCheck = '(?s)#### Acceptance Criteria\s*\n(.*?)(?=####|###|---|\z)'
    $descPatternCheck = '(?m)^(?s)(?:## Epic:\s+|###\s+)EPIC-\d+\s*[—–-]\s*.+?\n(.*?)(?=####|\z)'

    $descBody = ""
    if ($epicSection -match $descPatternCheck) { $descBody = $Matches[1].Trim() }
    
    $dodCount = 0
    if ($epicSection -match $dodPatternCheck) {
        $dodCount = ([regex]::Matches($Matches[1], '- \[[ x]\]\s*(.+)')).Count
    }
    
    $acCount = 0
    if ($epicSection -match $acPatternCheck) {
        $acCount = ([regex]::Matches($Matches[1], '- \[[ x]\]\s*(.+)')).Count
    }

    $bulletCount = 0
    if ($descBody) {
        $bulletCount = ([regex]::Matches($descBody, '(?m)^[-*]\s+')).Count
    }

    # Threshold: same as Start-Plan.ps1 — 5 DoD, 5 AC, 2 description bullets
    if ($dodCount -ge 5 -and $acCount -ge 5 -and $bulletCount -ge 2) {
        Write-Host "  ${epicRef} is already well-specified. Skipping."
        continue
    }

    if ($DryRun) {
        Write-Host "  [DryRun] Would expand ${epicRef}: ${epicTitle}"
        continue
    }

    Write-Host "  Expanding ${epicRef}: ${epicTitle}..." -NoNewline

    $prompt = @"
You are a Senior Software Architect. Your task is to REFINE and EXPAND a high-level Epic into a detailed implementation plan.

## Original Epic
$epicSection

## Instructions
Maximize the detail in this plan. Your output MUST be a single markdown block representing the expansion of this Epic, following the Ostwin template:

1. **Description**: Expand the 1-2 line description into 3-5 paragraphs. Cover technical approach, key components, and potential risks.
2. **Implementation Strategy**: Provide a sequential breakdown of the phases required to build this Epic. This should serve as the "detail plan for the team".
3. **Definition of Done (DoD)**: List at least 5 crystal-clear, verifiable conditions (e.g., "Unit test coverage >= 80%", "Lint clean", "Documentation updated").
4. **Acceptance Criteria (AC)**: List at least 5 testable scenarios (e.g., "User can login with valid JWT", "System rejects expired tokens with 401").
5. **Dependencies**: Identify if this depends on other EPICs from the plan (based on the reference NNN in EPIC-NNN). Format as: depends_on: [EPIC-NNN]

## Format Requirement
Return ONLY the refined markdown starting with '### $epicRef — $epicTitle'. Do not include any other text, chatter, or preamble.

### EXAMPLE OUTPUT
### EPIC-001 — Build Auth Module

[Detailed Description here...]

#### Definition of Done
- [ ] Core logic implemented
- [ ] ... (4 more)

#### Acceptance Criteria
- [ ] Scenario 1
- [ ] ... (4 more)

depends_on: []
"@

    $result = if ($AgentCmd) {
        $output = & $AgentCmd $prompt | Out-String
        $code = if ($?) { 0 } else { 1 }
        [PSCustomObject]@{ ExitCode = $code; Output = $output }
    } else {
        & $invokeAgent -RoomDir $expansionRoom -RoleName "architect" `
                         -Prompt $prompt -TimeoutSeconds 300
    }

    if ($result.ExitCode -eq 0) {
        $refinedEpics[$epicRef] = $result.Output.Trim()
        Write-Host " [DONE]" -ForegroundColor Green
    } else {
        Write-Host " [FAILED]" -ForegroundColor Red
        Write-Warning "Refinement failed for ${epicRef}: $($result.Output)"
        $refinedEpics[$epicRef] = $epicSection # Fallback to original
    }
}

if ($DryRun) {
    Write-Host ""
    Write-Host "[DRY RUN] Complete. No changes made." -ForegroundColor Yellow
    exit 0
}

# --- Assemble refined plan ---
$newPlanContent = $planContent

foreach ($ref in $refinedEpics.Keys) {
    # Find the original epic section again to replace it
    $targetMatch = [regex]::Match($newPlanContent, "(?m)^(## Epic:\s+|###\s+)${ref}\s*[—–-]\s*.+$")
    if ($targetMatch.Success) {
        $start = $targetMatch.Index
        # Find end of section: next header (any level) or horizontal rule
        $afterRef = $newPlanContent.Substring($start + $targetMatch.Length)
        $nextSectionMatch = [regex]::Match($afterRef, "(?m)^(#+|---)")
        $end = if ($nextSectionMatch.Success) { $start + $targetMatch.Length + $nextSectionMatch.Index } else { $newPlanContent.Length }
        
        $newPlanContent = $newPlanContent.Remove($start, $end - $start).Insert($start, $refinedEpics[$ref] + "`n")
    }
}

# Ensure spacing is correct and save
$newPlanContent | Out-File -FilePath $OutFile -Encoding utf8

Write-Host ""
Write-Host "[PLAN] Refined plan saved to: $OutFile" -ForegroundColor Green
Write-Host ""

# Clean up temporary room
Remove-Item $expansionRoom -Recurse -Force -ErrorAction SilentlyContinue
