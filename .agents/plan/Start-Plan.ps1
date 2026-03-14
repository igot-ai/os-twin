<#
.SYNOPSIS
    Parses a plan file and spawns war-rooms for each epic/task.

.DESCRIPTION
    Reads a plan markdown file, extracts epics and tasks with their goals
    and dependencies, creates war-rooms for each, builds the dependency
    graph (DAG), and starts the manager loop.

    Supports -Resume to restart from existing war-rooms without recreating them.

    Replaces: run.sh

.PARAMETER PlanFile
    Path to the plan markdown file.
.PARAMETER ProjectDir
    Project root. Default: current directory.
.PARAMETER DryRun
    Parse and show what would be created, but don't actually create rooms or start the loop.
.PARAMETER Resume
    Skip room creation, rebuild DAG from existing rooms, and restart the manager loop.
    Rooms in 'blocked' state will be reset to 'pending' if their upstream deps are no longer failed.
.PARAMETER Expand
    Automatically run plan expansion before creating rooms.
.PARAMETER Review
    Wait for human review and approval after plan expansion.

.EXAMPLE
    ./Start-Plan.ps1 -PlanFile "./plans/plan-001.md" -ProjectDir "/project"
    ./Start-Plan.ps1 -PlanFile "./plans/plan-001.md" -DryRun
    ./Start-Plan.ps1 -PlanFile "./plans/plan-001.md" -Resume
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$PlanFile,

    [string]$ProjectDir = (Get-Location).Path,

    [switch]$DryRun,

    [switch]$Resume,

    [switch]$Expand,

    [switch]$Review
)

# --- Resolve paths ---
$agentsDir = Join-Path $ProjectDir ".agents"
if (-not (Test-Path $agentsDir)) {
    # Fallback: look relative to script
    $agentsDir = $PSScriptRoot | Split-Path
}

$newWarRoom = Join-Path $agentsDir "war-rooms" "New-WarRoom.ps1"
$managerLoop = Join-Path $agentsDir "roles" "manager" "Start-ManagerLoop.ps1"
$buildDag = Join-Path $agentsDir "plan" "Build-DependencyGraph.ps1"

# --- Import modules ---
$logModule = Join-Path $agentsDir "lib" "Log.psm1"
if (Test-Path $logModule) { Import-Module $logModule -Force }
$utilsModule = Join-Path $agentsDir "lib" "Utils.psm1"
if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }
$configModule = Join-Path $agentsDir "lib" "Config.psm1"
if (Test-Path $configModule) { Import-Module $configModule -Force }

# --- Validate plan file ---
if (-not (Test-Path $PlanFile)) {
    Write-Error "Plan file not found: $PlanFile"
    exit 1
}

# --- Plan Expansion (Manager Loop Startup Integration) ---
$config = Get-OstwinConfig

$planContentForCheck = Get-Content $PlanFile -Raw
$hasUnderspecified = $false

$epicPatternCheck = '(?m)^(## Epic:\s+|###\s+)(EPIC-\d+)\s*[—–-]\s*(.+)$'
$dodPatternCheck = '(?s)#### Definition of Done\s*\n(.*?)(?=####|###|---|\z)'
$acPatternCheck = '(?s)#### Acceptance Criteria\s*\n(.*?)(?=####|###|---|\z)'
$descPatternCheck = '(?m)^(?s)(?:## Epic:\s+|###\s+)EPIC-\d+\s*[—–-]\s*.+?\n(.*?)(?=####|\z)'

$epicMatchesCheck = [regex]::Matches($planContentForCheck, $epicPatternCheck)
foreach ($em in $epicMatchesCheck) {
    $epicStart = $em.Index
    $nextMatch = $epicMatchesCheck | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
    $epicEnd = if ($nextMatch) { $nextMatch.Index } else { $planContentForCheck.Length }
    $epicSection = $planContentForCheck.Substring($epicStart, $epicEnd - $epicStart)

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

    if ($dodCount -lt 1 -or $acCount -lt 1 -or $bulletCount -lt 2) {
        $hasUnderspecified = $true
        break
    }
}

$shouldExpand = $Expand -or ($config.manager -and $config.manager.auto_expand_plan -eq $true) -or $hasUnderspecified

if ($shouldExpand -and ($PlanFile -notmatch '\.refined\.md$')) {
    $expandScript = Join-Path $agentsDir "plan" "Expand-Plan.ps1"
    if (Test-Path $expandScript) {
        if ($hasUnderspecified) {
            Write-Host ""
            Write-Host "=== Plan Refinement Required ===" -ForegroundColor Yellow
            Write-Host "Detected underspecified epics. Auto-triggering plan refinement..." -ForegroundColor Yellow
            $Review = $true
        } else {
            Write-OstwinLog -Message "Auto-expanding plan: $PlanFile" -Level "INFO" -Caller "manager"
        }
        
        $refinedFile = $PlanFile -replace "(?i)\.md`$", ".refined.md"
        if ($refinedFile -eq $PlanFile) { $refinedFile = $PlanFile + ".refined.md" }

        $expandArgs = @{
            PlanFile = $PlanFile
            OutFile = $refinedFile
        }
        if ($DryRun) { $expandArgs.Add("DryRun", $true) }

        & $expandScript @expandArgs

        if ($LASTEXITCODE -ne 0 -and $?) {
            Write-Error "Failed to expand plan."
            exit 1
        }
        
        if (-not $DryRun -and (Test-Path $refinedFile)) {
            $diffSummary = git diff --no-index --stat $PlanFile $refinedFile | Out-String
            if (-not $diffSummary) { $diffSummary = "No changes or git not available" }
            Write-OstwinLog -Message "Plan expansion diff:`n$diffSummary" -Level "INFO" -Caller "manager"
            
            $PlanFile = $refinedFile
            
            if ($Review) {
                Write-Host ""
                Write-Host "Plan expanded to: $PlanFile" -ForegroundColor Green
                Write-Host "Please review the expanded plan." -ForegroundColor Green
                Read-Host -Prompt "Press [Enter] to approve and continue, or Ctrl+C to abort..."
            }
        }
    } else {
        Write-Warning "Expand-Plan.ps1 not found at $expandScript, skipping expansion."
    }
}

$planContent = Get-Content $PlanFile -Raw

# --- Parse plan: extract epics and tasks ---
$parsed = [System.Collections.Generic.List[PSObject]]::new()
$roomIndex = 1

# Pattern: ### EPIC-NNN or ### TASK-NNN sections
$epicPattern = '(?m)^(## Epic:\s+|###\s+)(EPIC-\d+)\s*[—–-]\s*(.+)$'
$taskPattern = '- \[[ x]\]\s+(TASK-\d+)\s*[—–-]\s*(.+)'
$dodPattern = '(?s)#### Definition of Done\s*\n(.*?)(?=####|###|---|\z)'
$acPattern = '(?s)#### Acceptance Criteria\s*\n(.*?)(?=####|###|---|\z)'
$depsPattern = '(?m)^\s*depends_on:\s*\[([^\]]*)\]\s*$'

# Patterns for per-epic metadata
$rolesPattern = '(?m)^Roles:\s*(.+)$'
$workingDirPattern = '(?m)^Working_dir:\s*(.+)$'

# Extract epics
$epicMatches = [regex]::Matches($planContent, $epicPattern)

foreach ($em in $epicMatches) {
    $epicRef = $em.Groups[2].Value
    $epicDesc = $em.Groups[3].Value.Trim()

    # Find the epic section content
    $epicStart = $em.Index
    $nextEpicMatch = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
    $epicEnd = if ($nextEpicMatch) { $nextEpicMatch.Index } else { $planContent.Length }
    $epicSection = $planContent.Substring($epicStart, $epicEnd - $epicStart)

    # Extract Roles (comma-separated, e.g. "engineer:fe" or "engineer:fe, engineer:be")
    $roles = @()
    if ($epicSection -match $rolesPattern) {
        $roles = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    }
    # Default to "engineer" if no roles specified
    if ($roles.Count -eq 0) { $roles = @("engineer") }

    # Extract per-epic working directory override
    $epicWorkingDir = ""
    if ($epicSection -match $workingDirPattern) {
        $epicWorkingDir = $Matches[1].Trim()
    }

    # Extract description body
    $descBody = ""
    $descPattern = '(?m)^(?s)(?:## Epic:\s+|###\s+)EPIC-\d+\s*[—–-]\s*.+?\n(.*?)(?=####|\z)'
    if ($epicSection -match $descPattern) {
        $descBody = $Matches[1].Trim()
    }

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

    # Extract depends_on
    $depsOn = @()
    if ($epicSection -match $depsPattern) {
        $rawDeps = $Matches[1]
        if ($rawDeps.Trim()) {
            $depsOn = ($rawDeps -split ',') | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ }
        }
    }

    $parsed.Add([PSCustomObject]@{
        RoomId      = "room-$('{0:D3}' -f $roomIndex)"
        TaskRef     = $epicRef
        Description = $epicDesc
        DescBody    = $descBody
        DoD         = $dod
        AC          = $ac
        DependsOn   = $depsOn
        Type        = 'epic'
        Roles       = $roles
        EpicWorkingDir = $epicWorkingDir
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
            DescBody    = ""
            DoD         = @()
            AC          = @()
            DependsOn   = @()
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
if ($Resume) {
    Write-Host "  Mode: RESUME (using existing war-rooms)" -ForegroundColor Yellow
} else {
    Write-Host "  War-rooms to create: $($parsed.Count)"
}
Write-Host ""

$hasDeps = $false
foreach ($entry in $parsed) {
    $dodCount = if ($entry.DoD) { $entry.DoD.Count } else { 0 }
    $acCount = if ($entry.AC) { $entry.AC.Count } else { 0 }
    $rolesStr = if ($entry.Roles) { ($entry.Roles -join ', ') } else { 'engineer' }
    $depStr = ""
    if ($entry.DependsOn -and $entry.DependsOn.Count -gt 0) {
        $depStr = " [depends_on: $($entry.DependsOn -join ', ')]"
        $hasDeps = $true
    }
    Write-Host "  $($entry.RoomId) → $($entry.TaskRef) — $($entry.Description) (Roles: $rolesStr, DoD: $dodCount, AC: $acCount)$depStr" -ForegroundColor White
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

# --- Resume mode: reset blocked rooms if upstream cleared ---
if ($Resume) {
    Write-Host "[RESUME] Checking existing war-rooms..." -ForegroundColor Yellow
    $roomDirs = Get-ChildItem -Path $warRoomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue
    foreach ($rd in $roomDirs) {
        $statusFile = Join-Path $rd.FullName "status"
        $status = if (Test-Path $statusFile) { (Get-Content $statusFile -Raw).Trim() } else { "pending" }
        $tr = if (Test-Path (Join-Path $rd.FullName "task-ref")) { (Get-Content (Join-Path $rd.FullName "task-ref") -Raw).Trim() } else { "?" }
        Write-Host "  $($rd.Name) [$tr]: $status"

        # Reset blocked rooms to pending so they can be re-evaluated
        if ($status -eq 'blocked') {
            Write-Host "    → Resetting to pending" -ForegroundColor Yellow
            if (Get-Command Set-WarRoomStatus -ErrorAction SilentlyContinue) {
                Set-WarRoomStatus -RoomDir $rd.FullName -NewStatus "pending"
            } else {
                "pending" | Out-File -FilePath $statusFile -Encoding utf8 -NoNewline
            }
            # Reset qa_retries counter
            $qaRetriesFile = Join-Path $rd.FullName "qa_retries"
            if (Test-Path $qaRetriesFile) { Remove-Item $qaRetriesFile -Force }
        }
    }
    Write-Host ""
} else {
    # --- Create war-rooms ---
    foreach ($entry in $parsed) {
        # Resolve working directory: per-epic override > project dir
        $resolvedWorkingDir = $ProjectDir
        if ($entry.EpicWorkingDir) {
            $candidate = Join-Path $ProjectDir $entry.EpicWorkingDir
            if (Test-Path $candidate) {
                $resolvedWorkingDir = $candidate
            } else {
                $resolvedWorkingDir = $entry.EpicWorkingDir  # absolute path
            }
        }

        # Use the first role as the primary assigned role (e.g. "engineer:fe")
        $primaryRole = if ($entry.Roles -and $entry.Roles.Count -gt 0) { $entry.Roles[0] } else { "engineer" }

        $roomArgs = @{
            RoomId           = $entry.RoomId
            TaskRef          = $entry.TaskRef
            TaskDescription  = $entry.Description
            WorkingDir       = $resolvedWorkingDir
            WarRoomsDir      = $warRoomsDir
            PlanId           = $planId
            Role             = $primaryRole
        }

        if ($entry.DoD -and $entry.DoD.Count -gt 0) {
            $roomArgs['DefinitionOfDone'] = $entry.DoD
        }
        if ($entry.AC -and $entry.AC.Count -gt 0) {
            $roomArgs['AcceptanceCriteria'] = $entry.AC
        }
        if ($entry.DependsOn -and $entry.DependsOn.Count -gt 0) {
            $roomArgs['DependsOn'] = $entry.DependsOn
        }

        & $newWarRoom @roomArgs
    }
}

# --- Build dependency graph ---
if ($hasDeps -or $Resume) {
    Write-Host "[DAG] Building dependency graph..." -ForegroundColor Cyan
    & $buildDag -WarRoomsDir $warRoomsDir
}

# --- Start the manager loop ---
Write-Host ""
Write-Host "[STARTING] Manager loop..." -ForegroundColor Green
& $managerLoop -WarRoomsDir $warRoomsDir
