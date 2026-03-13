<#
.SYNOPSIS
    Parses a plan file and spawns war-rooms for each epic/task.

.DESCRIPTION
    Reads a plan markdown file, extracts epics and tasks with their goals,
    creates war-rooms for each, and starts the manager loop.

    Replaces: run.sh

.PARAMETER PlanFile
    Path to the plan markdown file.
.PARAMETER ProjectDir
    Project root. Default: current directory.
.PARAMETER DryRun
    Parse and show what would be created, but don't actually create rooms or start the loop.

.EXAMPLE
    ./Start-Plan.ps1 -PlanFile "./plans/plan-001.md" -ProjectDir "/project"
    ./Start-Plan.ps1 -PlanFile "./plans/plan-001.md" -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$PlanFile,

    [string]$ProjectDir = (Get-Location).Path,

    [switch]$DryRun
)

# --- Resolve paths ---
$agentsDir = Join-Path $ProjectDir ".agents"
if (-not (Test-Path $agentsDir)) {
    # Fallback: look relative to script
    $agentsDir = $PSScriptRoot | Split-Path
}

$newWarRoom = Join-Path $agentsDir "war-rooms" "New-WarRoom.ps1"
$managerLoop = Join-Path $agentsDir "roles" "manager" "Start-ManagerLoop.ps1"

# --- Import modules ---
$logModule = Join-Path $agentsDir "lib" "Log.psm1"
if (Test-Path $logModule) { Import-Module $logModule -Force }

# --- Validate plan file ---
if (-not (Test-Path $PlanFile)) {
    Write-Error "Plan file not found: $PlanFile"
    exit 1
}

$planContent = Get-Content $PlanFile -Raw

# --- Parse plan: extract epics and tasks ---
$parsed = [System.Collections.Generic.List[PSObject]]::new()
$roomIndex = 1

# Pattern: ### EPIC-NNN or ### TASK-NNN sections
$epicPattern = '###\s+(EPIC-\d+)\s*[—–-]\s*(.+)'
$taskPattern = '- \[[ x]\]\s+(TASK-\d+)\s*[—–-]\s*(.+)'
$dodPattern = '(?s)#### Definition of Done\s*\n(.*?)(?=####|###|---|\z)'
$acPattern = '(?s)#### Acceptance Criteria\s*\n(.*?)(?=####|###|---|\z)'

# Extract epics
$epicMatches = [regex]::Matches($planContent, $epicPattern)

foreach ($em in $epicMatches) {
    $epicRef = $em.Groups[1].Value
    $epicDesc = $em.Groups[2].Value.Trim()

    # Find the epic section content
    $epicStart = $em.Index
    $nextEpicMatch = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
    $epicEnd = if ($nextEpicMatch) { $nextEpicMatch.Index } else { $planContent.Length }
    $epicSection = $planContent.Substring($epicStart, $epicEnd - $epicStart)

    # Extract DoD
    $dod = @()
    if ($epicSection -match $dodPattern) {
        $dodBlock = $Matches[1]
        $dod = [regex]::Matches($dodBlock, '- \[[ x]\]\s*(.+)') | ForEach-Object { $_.Groups[1].Value.Trim() }
    }

    # Extract AC
    $ac = @()
    if ($epicSection -match $acPattern) {
        $acBlock = $Matches[1]
        $ac = [regex]::Matches($acBlock, '- \[[ x]\]\s*(.+)') | ForEach-Object { $_.Groups[1].Value.Trim() }
    }

    $parsed.Add([PSCustomObject]@{
        RoomId      = "room-$('{0:D3}' -f $roomIndex)"
        TaskRef     = $epicRef
        Description = $epicDesc
        DoD         = $dod
        AC          = $ac
        Type        = 'epic'
    })
    $roomIndex++
}

# If no epics found, try parsing standalone tasks
if ($parsed.Count -eq 0) {
    $taskMatches = [regex]::Matches($planContent, $taskPattern)
    foreach ($tm in $taskMatches) {
        $parsed.Add([PSCustomObject]@{
            RoomId      = "room-$('{0:D3}' -f $roomIndex)"
            TaskRef     = $tm.Groups[1].Value
            Description = $tm.Groups[2].Value.Trim()
            DoD         = @()
            AC          = @()
            Type        = 'task'
        })
        $roomIndex++
    }
}

if ($parsed.Count -eq 0) {
    Write-Error "No epics or tasks found in plan file: $PlanFile"
    exit 1
}

# --- Extract plan_id from embedded config ---
$planId = ""
if ($planContent -match '"plan_id"\s*:\s*"([^"]+)"') {
    $planId = $Matches[1]
}

# --- Display what will be created ---
Write-Host ""
Write-Host "=== Ostwin Plan Launcher ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Plan: $PlanFile"
Write-Host "  Plan ID: $planId"
Write-Host "  Project: $ProjectDir"
Write-Host "  War-rooms to create: $($parsed.Count)"
Write-Host ""

foreach ($entry in $parsed) {
    $dodCount = if ($entry.DoD) { $entry.DoD.Count } else { 0 }
    $acCount = if ($entry.AC) { $entry.AC.Count } else { 0 }
    Write-Host "  $($entry.RoomId) → $($entry.TaskRef) — $($entry.Description) (DoD: $dodCount, AC: $acCount)" -ForegroundColor White
}
Write-Host ""

if ($DryRun) {
    Write-Host "[DRY RUN] No rooms created." -ForegroundColor Yellow
    exit 0
}

# --- Set up war-rooms directory ---
$warRoomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR }
               else { Join-Path $ProjectDir ".war-rooms" }
$env:WARROOMS_DIR = $warRoomsDir

# --- Create war-rooms ---
foreach ($entry in $parsed) {
    $args = @{
        RoomId           = $entry.RoomId
        TaskRef          = $entry.TaskRef
        TaskDescription  = $entry.Description
        WorkingDir       = $ProjectDir
        WarRoomsDir      = $warRoomsDir
        PlanId           = $planId
    }

    if ($entry.DoD -and $entry.DoD.Count -gt 0) {
        $args['DefinitionOfDone'] = $entry.DoD
    }
    if ($entry.AC -and $entry.AC.Count -gt 0) {
        $args['AcceptanceCriteria'] = $entry.AC
    }

    & $newWarRoom @args
}

# --- Start the manager loop ---
Write-Host ""
Write-Host "[STARTING] Manager loop..." -ForegroundColor Green
& $managerLoop -WarRoomsDir $warRoomsDir
