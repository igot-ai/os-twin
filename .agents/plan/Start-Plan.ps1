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

    [switch]$Review,

    [switch]$SkipLoop,

    [switch]$Unified
)

# --- Resolve paths ---
# The agentsDir must point to the Ostwin *installation* (where scripts like
# New-WarRoom.ps1 and Start-ManagerLoop.ps1 live), NOT the target project's
# .agents folder which might only contain .war-rooms or project-local config.
#
# Resolution order:
#   1. $OSTWIN_HOME env var (explicit override)
#   2. $ProjectDir/.agents — but ONLY if it contains the required scripts
#   3. Fallback: derive from $PSScriptRoot (the script's own install location)
$installDir = $PSScriptRoot | Split-Path   # e.g. /Users/paulaan/.ostwin

if ($env:OSTWIN_HOME -and (Test-Path $env:OSTWIN_HOME)) {
    $agentsDir = $env:OSTWIN_HOME
} else {
    $agentsDir = Join-Path $ProjectDir ".agents"
    $sentinel  = Join-Path $agentsDir "war-rooms" "New-WarRoom.ps1"
    if (-not (Test-Path $sentinel)) {
        # Project .agents dir is missing or doesn't contain Ostwin scripts — use installation
        $agentsDir = $installDir
    }
}

$newWarRoom = Join-Path $agentsDir "war-rooms" "New-WarRoom.ps1"
$managerLoop = Join-Path $agentsDir "roles" "manager" "Start-ManagerLoop.ps1"
$buildDag = Join-Path $agentsDir "plan" "Build-DependencyGraph.ps1"
$buildPlanningDag = Join-Path $agentsDir "plan" "Build-PlanningDAG.ps1"
$postMessage = Join-Path $agentsDir "channel" "Post-Message.ps1"
$waitForMessage = Join-Path $agentsDir "channel" "Wait-ForMessage.ps1"

# --- Import modules ---
$logModule = Join-Path $agentsDir "lib" "Log.psm1"
if (Test-Path $logModule) { 
    $logModule = (Resolve-Path $logModule).Path
    Import-Module $logModule -Force 
}
$utilsModule = Join-Path $agentsDir "lib" "Utils.psm1"
if (Test-Path $utilsModule) { 
    $utilsModule = (Resolve-Path $utilsModule).Path
    Import-Module $utilsModule -Force 
}
$configModule = Join-Path $agentsDir "lib" "Config.psm1"
if (Test-Path $configModule) { 
    $configModule = (Resolve-Path $configModule).Path
    Import-Module $configModule -Force 
}

# --- Helper Functions ---
# (Test-Underspecified now in Utils.psm1)

# --- Validate plan file ---
if (-not (Test-Path $PlanFile -PathType Leaf)) {
    Write-Error "Plan file not found or is not a file: $PlanFile"
    exit 1
}

# --- Validate project dir ---
if (-not (Test-Path $ProjectDir -PathType Container)) {
    Write-Error "-ProjectDir must be a directory. It is currently set to: $ProjectDir. If you passed multiple files to 'ostwin run', the second file was interpreted as the ProjectDir."
    exit 1
}

# --- Resolve config ---
$config = Get-OstwinConfig

if ($config.manager -and $config.manager.unified_plan_negotiation -eq $true) {
    $Unified = $true
}

# --- Resolve timeout ---
# $planReviewTimeout = ... (deprecated in favor of channel timeouts)
if ($env:PLAN_REVIEW_TIMEOUT_SECONDS) {
    $planReviewTimeout = [int]$env:PLAN_REVIEW_TIMEOUT_SECONDS
} elseif ($config.manager.plan_review_timeout_seconds) {
    $planReviewTimeout = [int]$config.manager.plan_review_timeout_seconds
}

# --- Resolve war-rooms directory (provisional — finalized after plan parsing) ---
$warRoomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR }
               else { Join-Path $ProjectDir ".war-rooms" }
$env:WARROOMS_DIR = $warRoomsDir
$warRoomsDirFromEnv = [bool]$env:WARROOMS_DIR -and -not ($env:WARROOMS_DIR -eq (Join-Path $ProjectDir ".war-rooms"))

# --- Bootstrap room-000 for plan negotiation ---
$room000Dir = Join-Path $warRoomsDir "room-000"
$negotiationTask = @"
Unified Plan Negotiation

The project plan at '$PlanFile' requires review and potential refinement. 

### Your Instructions:
1. Read the current plan from the filesystem.
2. Verify if epics/tasks are well-specified (detailed Description, DoD, and AC).
3. If underspecified or if you see improvements, refine the plan in-place using your tools.
4. Once the plan is ready for implementation, post a 'plan-approve' message to the channel.
5. If you cannot proceed without more context, post 'plan-reject' with your feedback.
"@
if (-not $DryRun -and -not (Test-Path $room000Dir)) {
    & $newWarRoom -RoomId "room-000" -TaskRef "PLAN-REVIEW" -TaskDescription $negotiationTask -WarRoomsDir $warRoomsDir -WorkingDir $ProjectDir -AssignedRole "architect" -CandidateRoles @("architect","manager") | Out-Null
} elseif (-not $DryRun -and (Test-Path $room000Dir)) {
    # --- Update room-000 if the plan file has changed ---
    $room000Config = Join-Path $room000Dir "config.json"
    if (Test-Path $room000Config) {
        $r0cfg = Get-Content $room000Config -Raw | ConvertFrom-Json
        $oldDesc = if ($r0cfg.assignment -and $r0cfg.assignment.description) { $r0cfg.assignment.description } else { "" }
        if ($oldDesc -and $oldDesc -notmatch [regex]::Escape($PlanFile)) {
            Write-Warning "room-000 references a different plan file. Updating to current plan: $PlanFile"
            $r0cfg.assignment.description = $negotiationTask
            $r0cfg.assignment.title = "Unified Plan Negotiation"
            $r0cfg | ConvertTo-Json -Depth 10 | Out-File -FilePath $room000Config -Encoding utf8
            # Update brief.md
            $briefFile = Join-Path $room000Dir "brief.md"
            if (Test-Path $briefFile) {
                "# PLAN-REVIEW`n`n$negotiationTask" | Out-File -FilePath $briefFile -Encoding utf8
            }
            # Reset status if stuck on old plan
            $r0Status = if (Test-Path (Join-Path $room000Dir "status")) { (Get-Content (Join-Path $room000Dir "status") -Raw).Trim() } else { "pending" }
            if ($r0Status -in @('developing', 'optimize', 'review', 'triage', 'failed', 'failed-final')) {
                Write-Host "  → Resetting room-000 to pending (was: $r0Status)" -ForegroundColor Yellow
                "pending" | Out-File -FilePath (Join-Path $room000Dir "status") -Encoding utf8 -NoNewline
                # Clear stale channel messages
                $channelFile = Join-Path $room000Dir "channel.jsonl"
                if (Test-Path $channelFile) { "" | Out-File -FilePath $channelFile -Encoding utf8 }
                # Clear old PID files
                $pidDir = Join-Path $room000Dir "pids"
                if (Test-Path $pidDir) { Get-ChildItem $pidDir -Filter "*.pid" | Remove-Item -Force -ErrorAction SilentlyContinue }
            }
        }
    }
}

# --- Check for refined plan ---
$refinedFile = $PlanFile -replace '\.md$', '.refined.md'
if ((-not $Expand) -and (Test-Path $refinedFile) -and ($PlanFile -notmatch '\.refined\.md$')) {
    Write-Host "Using Existing Refined Plan: $refinedFile" -ForegroundColor Cyan
    $PlanFile = $refinedFile
}

# --- Patterns for parsing ---
# Pattern: ## EPIC-NNN - Description (supports ## and ###)
$epicPattern = '(?m)^#{2,3}\s+(EPIC-\d+)\s*[-—–?]\s*(.+)$'
$taskPattern = '(?m)^\s*[-*]\s+\[[ x]\]\s+(TASK-\d+)\s*[-—–]\s*(.+)$'
$dodPattern = '(?s)#### Definition of Done\s*\n(.*?)(?=####|^#{1,3}\s+EPIC-|---|\z)'
$acPattern = '(?s)#### Acceptance Criteria\s*\n(.*?)(?=####|^#{1,3}\s+EPIC-|---|\z)'
$depsPattern = '(?m)^\s*depends_on:\s*\[([^\]]*)\]\s*$'

# Patterns for per-epic metadata (accept both singular Role: and plural Roles:)
$rolesPattern = '(?m)^Roles?:\s*(.+)$'
$objectivePattern = '(?m)^Objective:\s*(.+)$'
$workingDirPattern = '(?m)^Working_dir:\s*(.+)$'
$pipelinePattern = '(?m)^Pipeline:\s*(.+)$'
$capabilitiesPattern = '(?m)^Capabilities:\s*(.+)$'
$descPattern = '(?s)^#{2,3}\s+EPIC-\d+\s*[-—–?]\s*.+?\n(.*?)(?=####|^#{1,3}\s+EPIC-|---|\z)'
$lifecyclePattern = '(?ism)^Lifecycle:[^\S\r\n]*\r?\n[^\S\r\n]*```[a-z]*\r?\n(.*?)\r?\n[^\S\r\n]*```'

# --- Plan Expansion Logic (Requirement 6) ---
$planContent = Get-Content $PlanFile -Raw
$isUnderspecified = Test-Underspecified -Content $planContent

if ($isUnderspecified) {
    Write-Host "Detected underspecified epics" -ForegroundColor Cyan
}

$expandPlanScript = Join-Path $agentsDir "plan" "Expand-Plan.ps1"
$shouldExpand = $Expand -or ($isUnderspecified -and $config.manager.auto_expand_plan -eq $true)
if ($shouldExpand -and (Test-Path $expandPlanScript)) {
    Write-OstwinLog "Detected underspecified epics or forced expansion. Running Expand-Plan..."
    $expandOutFile = $PlanFile -replace '\.md$', '.refined.md'
    if ($DryRun) {
        Write-Host "  [DRY RUN] Would expand epics (e.g. EPIC-001) in $PlanFile → $expandOutFile" -ForegroundColor Yellow
    } else {
        & $expandPlanScript -PlanFile $PlanFile -OutFile $expandOutFile
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Plan expanded successfully: $expandOutFile" -ForegroundColor Green
            
            # Log for manager review (Requirement for tests)
            if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
                $diff = "Expansion diff placeholder" 
                if (Get-Command git -ErrorAction SilentlyContinue) { $diff = git diff --no-index $PlanFile $expandOutFile }
                Write-OstwinLog -Message "Plan expansion diff:`n$diff`n" -Level "info" -Caller "manager"
            }

            $PlanFile = $expandOutFile
            $planContent = Get-Content $PlanFile -Raw
        }
    }
}

# --- Parse plan: extract ALL epics and tasks (Requirement 1) ---
# Parse global working_dir from PLAN.md
if ($planContent -match '(?m)^working_dir:\s*(.+)$') {
    $globalWorkingDir = $Matches[1].Trim()
    if ($globalWorkingDir -and (Test-Path $globalWorkingDir)) {
        $ProjectDir = (Resolve-Path $globalWorkingDir).Path
        Write-Host "  Project: $ProjectDir" -ForegroundColor DarkGray
        # Re-resolve war-rooms dir to follow the plan's working_dir (unless explicitly set via env)
        if (-not $warRoomsDirFromEnv) {
            $warRoomsDir = Join-Path $ProjectDir ".war-rooms"
            $env:WARROOMS_DIR = $warRoomsDir
            $room000Dir = Join-Path $warRoomsDir "room-000"
        }
    } elseif ($globalWorkingDir -and $globalWorkingDir -ne '...') {
        Write-Warning "working_dir '$globalWorkingDir' not found. Falling back to ProjectDir: $ProjectDir"
    }
}

$parsed = [System.Collections.Generic.List[PSObject]]::new()
$roomIndex = 1


# Extract epics
$epicMatches = [regex]::Matches($planContent, $epicPattern)

foreach ($em in $epicMatches) {
    $epicRef = $em.Groups[1].Value
    $epicDesc = $em.Groups[2].Value.Trim()

    # Find the epic section content
    $epicStart = $em.Index
    $nextEpicMatch = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
    
    # EPIC-END should be the next EPIC header or the next level 2 header (e.g. ## Tasks)
    $nextSectionMatch = [regex]::Matches($planContent, '(?m)^##\s+') | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
    
    $epicEnd = $planContent.Length
    if ($nextEpicMatch) {
        $epicEnd = $nextEpicMatch.Index
    } elseif ($nextSectionMatch) {
        $epicEnd = $nextSectionMatch.Index
    }
    
    $epicSection = $planContent.Substring($epicStart, $epicEnd - $epicStart)

    # Extract Roles (comma-separated or multiple lines, stripping comments and placeholders)
    # Supports both singular "Role:" and plural "Roles:"
    $roles = @()
    $hasExplicitRoles = $false
    $roleMatches = [regex]::Matches($epicSection, $rolesPattern)
    if ($roleMatches.Count -gt 0) {
        $hasExplicitRoles = $true
    }
    foreach ($rm in $roleMatches) {
        $line = $rm.Groups[1].Value
        $line = $line -replace '\(.*$', ''
        $roles += ($line -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '[a-zA-Z0-9]' -and $_ -notmatch '^<.*>$' }
    }
    $roles = $roles | Select-Object -Unique | Where-Object { $_ }
    if ($roles.Count -eq 0) { $roles = @("engineer") }

    # Extract Objective (per-epic mission directive)
    $epicObjective = ""
    if ($epicSection -match $objectivePattern) {
        $epicObjective = $Matches[1].Trim()
    }

    # Extract per-epic working directory override
    $epicWorkingDir = ""
    if ($epicSection -match $workingDirPattern) {
        $epicWorkingDir = $Matches[1].Trim()
    }

    # Extract description body
    $descBody = ""
    $descPattern = '(?s)^#{2,3}\s+EPIC-\d+\s*[-—–]\s*.+?\n(.*?)(?=####|^#{1,3}\s+EPIC-|---|\z)'
    if ($epicSection -match $descPattern) {
        $descBody = $Matches[1].Trim()
    }

    # Extract Pipeline directive
    $epicPipeline = ""
    if ($epicSection -match $pipelinePattern) {
        $epicPipeline = $Matches[1].Trim()
    }

    # Extract Capabilities directive
    $epicCapabilities = @()
    if ($epicSection -match $capabilitiesPattern) {
        $epicCapabilities = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    }

    # Extract Lifecycle directive
    $epicLifecycle = ""
    if ($epicSection -match $lifecyclePattern) {
        $epicLifecycle = $Matches[1].Trim()
    }

    # Extract DoD
    $dod = @()
    if ($epicSection -match $dodPattern) {
        $dodBlock = $Matches[1]
        $dod = [regex]::Matches($dodBlock, '(?m)^[-*] \[[ x]\]\s*(.+)') | ForEach-Object { $_.Groups[1].Value.Trim() }
    }

    # Extract AC
    $ac = @()
    if ($epicSection -match $acPattern) {
        $acBlock = $Matches[1]
        $ac = [regex]::Matches($acBlock, '(?m)^[-*] \[[ x]\]\s*(.+)') | ForEach-Object { $_.Groups[1].Value.Trim() }
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
        RoomId           = "room-$('{0:D3}' -f $roomIndex)"
        TaskRef          = $epicRef
        Description      = $epicDesc
        DescBody         = $descBody
        Objective        = $epicObjective
        DoD              = $dod
        AC               = $ac
        DependsOn        = $depsOn
        Type             = 'epic'
        Roles            = $roles
        HasExplicitRoles = $hasExplicitRoles
        EpicWorkingDir   = $epicWorkingDir
        Pipeline         = $epicPipeline
        Capabilities     = $epicCapabilities
        Lifecycle        = $epicLifecycle
    })
    $roomIndex++
}

# Extract standalone tasks (Requirement 1)
$taskMatches = [regex]::Matches($planContent, $taskPattern)
foreach ($tm in $taskMatches) {
    # Skip if the task is inside an epic block
    $isInsideEpic = $false
    foreach ($em in $epicMatches) {
        $epicStart = $em.Index
        $nextEpicMatch = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
        
        $nextSec = [regex]::Matches($planContent, '(?m)^##\s+') | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
        $epicEnd = $planContent.Length
        if ($nextEpicMatch) { $epicEnd = $nextEpicMatch.Index }
        elseif ($nextSec) { $epicEnd = $nextSec.Index }

        if ($tm.Index -ge $epicStart -and $tm.Index -lt $epicEnd) {
            $isInsideEpic = $true
            break
        }
    }

    if (-not $isInsideEpic) {
        $taskRef = $tm.Groups[1].Value
        # Avoid duplicates if already parsed as an epic
        if (-not ($parsed | Where-Object { $_.TaskRef -eq $taskRef })) {
            $parsed.Add([PSCustomObject]@{
                RoomId      = "room-$('{0:D3}' -f $roomIndex)"
                TaskRef     = $taskRef
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
}

if ($parsed.Count -eq 0) {
    Write-Error "No epics or tasks found in plan file: $PlanFile"
    exit 1
}

# --- Auto-inject PLAN-REVIEW as a dependency (Requirement 2) ---
foreach ($item in $parsed) {
    if ($item.DependsOn -notcontains "PLAN-REVIEW") {
        $item.DependsOn = @("PLAN-REVIEW") + $item.DependsOn
    }
}

# --- Generate / load planning-DAG.json for advisory role assignment ---
$planningDagFile = Join-Path (Split-Path $PlanFile) ".planning-DAG.json"
if (-not $DryRun -and (Test-Path $buildPlanningDag)) {
    if (-not (Test-Path $planningDagFile) -or $Expand) {
        Write-Host "[PLANNING-DAG] Generating advisory DAG from plan content..." -ForegroundColor Cyan
        & $buildPlanningDag -PlanFile $PlanFile -OutFile $planningDagFile
    }
    # Merge planning-DAG roles AND dependencies into parsed entries (advisory)
    if (Test-Path $planningDagFile) {
        try {
            $planningDag = Get-Content $planningDagFile -Raw | ConvertFrom-Json
            foreach ($pdNode in $planningDag.nodes) {
                $matchedEntry = $parsed | Where-Object { $_.TaskRef -eq $pdNode.task_ref }
                if (-not $matchedEntry) { continue }

                # --- Merge advisory roles (only where no explicit Roles: directive in markdown) ---
                if (-not $matchedEntry.HasExplicitRoles -and $pdNode.role) {
                    Write-Host "  [PLANNING-DAG] $($pdNode.task_ref): role $($matchedEntry.Roles[0]) → $($pdNode.role) (advisory)" -ForegroundColor Yellow
                    $matchedEntry.Roles = @($pdNode.candidate_roles)
                }

                # --- Merge advisory depends_on (only where no explicit depends_on in markdown) ---
                # If the entry only has the auto-injected PLAN-REVIEW dependency (no author-specified deps),
                # adopt the AI-suggested inter-epic dependencies.
                $hasExplicitDeps = $matchedEntry.DependsOn | Where-Object { $_ -ne 'PLAN-REVIEW' }
                if (-not $hasExplicitDeps -and $pdNode.depends_on -and @($pdNode.depends_on).Count -gt 0) {
                    $aiDeps = @($pdNode.depends_on) | Where-Object { $_ -and $_ -ne 'PLAN-REVIEW' }
                    if ($aiDeps.Count -gt 0) {
                        $matchedEntry.DependsOn = @("PLAN-REVIEW") + $aiDeps
                        Write-Host "  [PLANNING-DAG] $($pdNode.task_ref): deps → $($matchedEntry.DependsOn -join ', ') (advisory)" -ForegroundColor Yellow
                    }
                }
            }
        } catch {
            Write-Warning "Failed to read planning-DAG.json: $_"
        }
    }
}

# --- Extract plan_id ---
# Primary: derive from the plan filename (the stem IS the plan_id, e.g. 107240b7fe28.md → 107240b7fe28)
$planId = [System.IO.Path]::GetFileNameWithoutExtension($PlanFile)
# Strip .refined suffix if present (e.g. 107240b7fe28.refined → 107240b7fe28)
$planId = $planId -replace '\.refined$', ''
# Fallback: extract from embedded JSON config in the plan content
if (-not $planId -or $planId -eq 'PLAN.template') {
    if ($planContent -match '"plan_id"\s*:\s*"([^"]+)"') {
        $planId = $Matches[1]
    }
}

# --- Register plan in the local registry so the dashboard can see it ---
if (-not $DryRun) {
    try {
        $plansDir = Join-Path $agentsDir "plans"
        if (-not (Test-Path $plansDir)) {
            New-Item -ItemType Directory -Path $plansDir -Force | Out-Null
        }

        $registryPlanFile = Join-Path $plansDir "$planId.md"
        $resolvedPlanFile = (Resolve-Path $PlanFile).Path
        $resolvedRegistryFile = $null
        if (Test-Path $registryPlanFile) {
            $resolvedRegistryFile = (Resolve-Path $registryPlanFile).Path
        }

        if (-not $resolvedRegistryFile -or $resolvedRegistryFile -ne $resolvedPlanFile) {
            $shouldCopy = $true
            if (Test-Path $registryPlanFile) {
                $srcTime = (Get-Item $PlanFile).LastWriteTimeUtc
                $dstTime = (Get-Item $registryPlanFile).LastWriteTimeUtc
                $shouldCopy = $srcTime -gt $dstTime
            }
            if ($shouldCopy) {
                Copy-Item -Path $PlanFile -Destination $registryPlanFile -Force
            }
        }

        $metaFile = Join-Path $plansDir "$planId.meta.json"
        $meta = @{}
        if (Test-Path $metaFile) {
            try {
                $existing = Get-Content $metaFile -Raw | ConvertFrom-Json
                if ($existing) {
                    foreach ($prop in $existing.PSObject.Properties) {
                        $meta[$prop.Name] = $prop.Value
                    }
                }
            } catch {
                $meta = @{}
            }
        }

        $title = $planId
        if ($planContent -match '(?m)^#\s*(?:Plan|PLAN):\s*(.+)$') {
            $title = $Matches[1].Trim()
        }

        $meta["plan_id"] = $planId
        if ($title) { $meta["title"] = $title }
        if (-not $meta["created_at"]) { $meta["created_at"] = (Get-Date).ToUniversalTime().ToString("o") }
        if (-not $meta["status"] -or $meta["status"] -in @("draft","stored")) { $meta["status"] = "active" }
        if ($ProjectDir) { $meta["working_dir"] = $ProjectDir }
        if ($ProjectDir) { $meta["warrooms_dir"] = (Join-Path $ProjectDir ".war-rooms") }
        $meta["launched_at"] = (Get-Date).ToUniversalTime().ToString("o")
        $meta["source_plan_file"] = $PlanFile

        $meta | ConvertTo-Json -Depth 10 | Out-File -FilePath $metaFile -Encoding utf8
    } catch {
        Write-Warning "Failed to register plan for dashboard: $_"
    }
}

# --- Manager Pre-flight skill coverage check ---
$testSkillCoverage = Join-Path $agentsDir "plan" "Test-SkillCoverage.ps1"
if (Test-Path $testSkillCoverage) {
    & $testSkillCoverage -PlanParsed $parsed -ProjectDir $ProjectDir -RoomDir $room000Dir | Out-Null
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
    
    # --- RESET MECHANISM: Clear failed-final/blocked rooms ---
    $targetWarRoomsDir = Join-Path $ProjectDir ".war-rooms"
    if (Test-Path $targetWarRoomsDir) {
        $rooms = Get-ChildItem -Path $targetWarRoomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue
        foreach ($rd in $rooms) {
            $statusFile = Join-Path $rd.FullName "status"
            if (Test-Path $statusFile) {
                $status = (Get-Content $statusFile -Raw).Trim()
                if ($status -eq "failed-final" -or $status -eq "blocked") {
                    Write-Host "  → Resetting $($rd.Name) to pending (was: $status)" -ForegroundColor Yellow
                    "pending" | Out-File -FilePath $statusFile -Encoding utf8 -NoNewline
                    
                    # Reset retry counters
                    $retriesFile = Join-Path $rd.FullName "retries"
                    if (Test-Path $retriesFile) { "0" | Out-File -FilePath $retriesFile -Encoding utf8 -NoNewline }
                    $qaRetriesFile = Join-Path $rd.FullName "qa_retries"
                    if (Test-Path $qaRetriesFile) { Remove-Item $qaRetriesFile -Force -ErrorAction SilentlyContinue }

                    # Clear old PID files
                    $pidDir = Join-Path $rd.FullName "pids"
                    if (Test-Path $pidDir) { Get-ChildItem $pidDir -Filter "*.pid" | Remove-Item -Force -ErrorAction SilentlyContinue }
                } elseif ($status -eq "fixing") {
                    Write-Host "  → Moving $($rd.Name) from fixing to developing" -ForegroundColor Yellow
                    "developing" | Out-File -FilePath $statusFile -Encoding utf8 -NoNewline
                    
                    # Clear old PID files
                    $pidDir = Join-Path $rd.FullName "pids"
                    if (Test-Path $pidDir) { Get-ChildItem $pidDir -Filter "*.pid" | Remove-Item -Force -ErrorAction SilentlyContinue }
                }
            }
        }
    }
    
    # Rebuild progress.json and PROGRESS.md to reflect the resets
    $updateProgressScript = Join-Path $agentsDir "plan" "Update-Progress.ps1"
    if (Test-Path $updateProgressScript) {
        & $updateProgressScript -WarRoomsDir $warRoomsDir
    }
} else {
    Write-Host "  War-rooms to create: $($parsed.Count + 1)" # +1 for room-000
}
Write-Host ""
Write-Host "  room-000 → PLAN-REVIEW — Unified Plan Negotiation (Roles: architect)" -ForegroundColor White

    foreach ($entry in $parsed) {
        $dodCount = if ($entry.DoD) { $entry.DoD.Count } else { 0 }
        $acCount = if ($entry.AC) { $entry.AC.Count } else { 0 }
        $rolesStr = if ($entry.Roles) { ($entry.Roles -join ', ') } else { 'engineer' }
        $depStr = ""
        if ($entry.DependsOn -and $entry.DependsOn.Count -gt 0) {
            $depStr = " [depends_on: $($entry.DependsOn -join ', ')]"
        }
        Write-Host "  $($entry.RoomId) → $($entry.TaskRef) — $($entry.Description) (Roles: $rolesStr, DoD: $dodCount, AC: $acCount)$depStr" -ForegroundColor White
    }
Write-Host ""

if ($DryRun) {
    # --- Show DAG structure in DryRun ---
    $nodes = @(@{ Id = "PLAN-REVIEW"; DependsOn = @() })
    foreach ($entry in $parsed) {
        $nodes += @{ Id = $entry.TaskRef; DependsOn = $entry.DependsOn }
    }
    
    try {
        $topo = & $buildDag -Nodes $nodes -Validate
        if ($topo) {
            Write-Host "  Dependency Graph (Topological Order):" -ForegroundColor Cyan
            Write-Host "  $($topo.Id -join ' -> ')" -ForegroundColor Gray
        }
    } catch {
        Write-Warning "Could not build dependency graph: $($_.Exception.Message)"
    }

    Write-Host ""
    Write-Host "[DRY RUN] No rooms created." -ForegroundColor Yellow
    exit 0
}

# --- Room Creation Logic ---
function New-PlanWarRooms {
    param($PlanFile, $ProjectDir, $warRoomsDir, $agentsDir, $parsed, $planId)
    
    # --- Re-parse plan in case it changed during negotiation ---
    $planContent = Get-Content $PlanFile -Raw
    $parsed = [System.Collections.Generic.List[PSObject]]::new()
    $roomIndex = 1
    # Patterns needed for re-parsing
    $epicPattern = '(?m)^#{2,3}\s+(EPIC-\d+)\s*[-—–?]\s*(.+)$'
    $taskPattern = '(?m)^\s*[-*]\s+\[[ x]\]\s+(TASK-\d+)\s*[-—–]\s*(.+)$'
    $dodPattern = '(?s)#### Definition of Done\s*\n(.*?)(?=####|^#{1,3}\s+EPIC-|---|\z)'
    $acPattern = '(?s)#### Acceptance Criteria\s*\n(.*?)(?=####|^#{1,3}\s+EPIC-|---|\z)'
    $depsPattern = '(?m)^\s*depends_on:\s*\[([^\]]*)\]\s*$'
    $rolesPattern = '(?m)^Roles?:\s*(.+)$'
    $workingDirPattern = '(?m)^Working_dir:\s*(.+)$'
    $objectivePattern = '(?m)^Objective:\s*(.+)$'
    $pipelinePattern = '(?m)^Pipeline:\s*(.+)$'
    $capabilitiesPattern = '(?m)^Capabilities:\s*(.+)$'
    $descPattern = '(?s)^#{2,3}\s+EPIC-\d+\s*[-—–?]\s*.+?\n(.*?)(?=####|^#{1,3}\s+EPIC-|---|\z)'
    $lifecyclePattern = '(?ism)^Lifecycle:[^\S\r\n]*\r?\n[^\S\r\n]*```[a-z]*\r?\n(.*?)\r?\n[^\S\r\n]*```'

    $epicMatches = [regex]::Matches($planContent, $epicPattern)
    foreach ($em in $epicMatches) {
        $epicRef = $em.Groups[1].Value
        $epicDesc = $em.Groups[2].Value.Trim()
        $epicStart = $em.Index
        $nextEpicMatch = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
        $epicEnd = if ($nextEpicMatch) { $nextEpicMatch.Index } else { $planContent.Length }
        $epicSection = $planContent.Substring($epicStart, $epicEnd - $epicStart)
        $roles = @()
        $roleMatches = [regex]::Matches($epicSection, $rolesPattern)
        foreach ($rm in $roleMatches) {
            $line = $rm.Groups[1].Value
            $line = $line -replace '\(.*$', ''
            $roles += ($line -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '[a-zA-Z0-9]' -and $_ -notmatch '^<.*>$' }
        }
        $roles = $roles | Select-Object -Unique | Where-Object { $_ }
        if ($roles.Count -eq 0) { $roles = @("engineer") }
        $epicWorkingDir = ""
        if ($epicSection -match $workingDirPattern) { $epicWorkingDir = $Matches[1].Trim() }
        $epicObjective = ""
        if ($epicSection -match $objectivePattern) { $epicObjective = $Matches[1].Trim() }
        $epicPipeline = ""
        if ($epicSection -match $pipelinePattern) { $epicPipeline = $Matches[1].Trim() }
        $epicCapabilities = @()
        if ($epicSection -match $capabilitiesPattern) {
            $epicCapabilities = ($Matches[1].Trim() -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        }
        $descBody = ""
        if ($epicSection -match $descPattern) { $descBody = $Matches[1].Trim() }
        $epicLifecycle = ""
        if ($epicSection -match $lifecyclePattern) { $epicLifecycle = $Matches[1].Trim() }
        $dod = @()
        if ($epicSection -match $dodPattern) {
            $dodBlock = $Matches[1]
            $dod = [regex]::Matches($dodBlock, '(?m)^[-*] \[[ x]\]\s*(.+)') | ForEach-Object { $_.Groups[1].Value.Trim() }
        }
        $ac = @()
        if ($epicSection -match $acPattern) {
            $acBlock = $Matches[1]
            $ac = [regex]::Matches($acBlock, '(?m)^[-*] \[[ x]\]\s*(.+)') | ForEach-Object { $_.Groups[1].Value.Trim() }
        }
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
            Objective   = $epicObjective
            Pipeline    = $epicPipeline
            Capabilities = $epicCapabilities
            Lifecycle   = $epicLifecycle
        })
        $roomIndex++
    }
    # Extract standalone tasks
    $taskMatches = [regex]::Matches($planContent, $taskPattern)
    foreach ($tm in $taskMatches) {
        $isInsideEpic = $false
        foreach ($em in $epicMatches) {
            $epicStart = $em.Index
            $nextEpicMatch = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
            
            $nextSec = [regex]::Matches($planContent, '(?m)^##\s+') | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
            $epicEnd = $planContent.Length
            if ($nextEpicMatch) { $epicEnd = $nextEpicMatch.Index }
            elseif ($nextSec) { $epicEnd = $nextSec.Index }

            if ($tm.Index -ge $epicStart -and $tm.Index -lt $epicEnd) {
                $isInsideEpic = $true
                break
            }
        }

        if (-not $isInsideEpic) {
            $taskRef = $tm.Groups[1].Value
            # Avoid duplicates if already parsed as an epic
            if (-not ($parsed | Where-Object { $_.TaskRef -eq $taskRef })) {
                $parsed.Add([PSCustomObject]@{
                    RoomId      = "room-$('{0:D3}' -f $roomIndex)"
                    TaskRef     = $taskRef
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
    }
    # Auto-inject PLAN-REVIEW dependency
    foreach ($item in $parsed) {
        if ($item.DependsOn -notcontains "PLAN-REVIEW") {
            $item.DependsOn = @("PLAN-REVIEW") + $item.DependsOn
        }
    }

    # --- Merge advisory deps from planning-DAG.json (mirrors first-parse logic) ---
    $planningDagFile = Join-Path (Split-Path $PlanFile) ".planning-DAG.json"
    if (Test-Path $planningDagFile) {
        try {
            $planningDag = Get-Content $planningDagFile -Raw | ConvertFrom-Json
            foreach ($pdNode in $planningDag.nodes) {
                $matchedEntry = $parsed | Where-Object { $_.TaskRef -eq $pdNode.task_ref }
                if (-not $matchedEntry) { continue }
                $hasExplicitDeps = $matchedEntry.DependsOn | Where-Object { $_ -ne 'PLAN-REVIEW' }
                if (-not $hasExplicitDeps -and $pdNode.depends_on -and @($pdNode.depends_on).Count -gt 0) {
                    $aiDeps = @($pdNode.depends_on) | Where-Object { $_ -and $_ -ne 'PLAN-REVIEW' }
                    if ($aiDeps.Count -gt 0) {
                        $matchedEntry.DependsOn = @("PLAN-REVIEW") + $aiDeps
                        Write-Host "  [PLANNING-DAG] $($pdNode.task_ref): deps → $($matchedEntry.DependsOn -join ', ') (advisory)" -ForegroundColor Yellow
                    }
                }
            }
        } catch {
            Write-Warning "Failed to read planning-DAG.json for dep merge: $_"
        }
    }

    # --- Create missing war-rooms or reconcile existing ones ---
    $newWarRoom = Join-Path $agentsDir "war-rooms" "New-WarRoom.ps1"
    foreach ($entry in $parsed) {
        $roomPath = Join-Path $warRoomsDir $entry.RoomId
        if (Test-Path $roomPath) {
            $existingConfigPath = Join-Path $roomPath "config.json"
            if (-not (Test-Path $existingConfigPath)) {
                # Stale room directory without config.json — remove and recreate
                Write-Warning "Stale room $($entry.RoomId) found (no config.json). Removing and recreating."
                Remove-Item -Path $roomPath -Recurse -Force
            } else {
                # --- RECONCILE: update existing room's role assignment from plan ---
                $primaryRole = if ($entry.Roles -and $entry.Roles.Count -gt 0) { $entry.Roles[0] } else { "engineer" }
                $candidateRoles = @(if ($entry.Roles -and $entry.Roles.Count -gt 0) { $entry.Roles } else { @("engineer", "qa") })
                try {
                    $existingConfig = Get-Content $existingConfigPath -Raw | ConvertFrom-Json
                    $currentRole = if ($existingConfig.assignment.assigned_role) { $existingConfig.assignment.assigned_role } else { "engineer" }
                    if ($currentRole -ne $primaryRole) {
                        Write-Host "    [RECONCILE] $($entry.RoomId): role $currentRole → $primaryRole (from plan Roles: directive)" -ForegroundColor Yellow
                        $existingConfig.assignment.assigned_role = $primaryRole
                        $existingConfig.assignment.candidate_roles = $candidateRoles
                        $existingConfig | ConvertTo-Json -Depth 10 | Out-File -FilePath $existingConfigPath -Encoding utf8
                    }
                } catch {
                    Write-Host "    [WARN] Failed to reconcile $($entry.RoomId): $($_.Exception.Message)" -ForegroundColor Yellow
                }
                continue
            }
        }

        $resolvedWorkingDir = $ProjectDir
        if ($entry.EpicWorkingDir) {
            $candidate = Join-Path $ProjectDir $entry.EpicWorkingDir
            if (Test-Path $candidate) { $resolvedWorkingDir = $candidate }
            else { $resolvedWorkingDir = $entry.EpicWorkingDir }
        }

        $primaryRole = if ($entry.Roles -and $entry.Roles.Count -gt 0) { $entry.Roles[0] } else { "engineer" }
        $fullDesc = $entry.Description
        if ($entry.Objective) {
            $fullDesc = "Objective: $($entry.Objective)`n`n$fullDesc"
        }
        if ($entry.DescBody) {
            $fullDesc = "$fullDesc`n`n$($entry.DescBody)"
        }

        $candidateRoles = @(if ($entry.Roles -and $entry.Roles.Count -gt 0) { $entry.Roles } else { @("engineer", "qa") })
        $roomArgs = @{
            RoomId           = $entry.RoomId
            TaskRef          = $entry.TaskRef
            TaskDescription  = $fullDesc
            WorkingDir       = $resolvedWorkingDir
            WarRoomsDir      = $warRoomsDir
            PlanId           = $planId
            AssignedRole     = $primaryRole
            CandidateRoles   = $candidateRoles
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
        if ($entry.Pipeline) {
            $roomArgs['Pipeline'] = $entry.Pipeline
        }
        if ($entry.RequiredCapabilities -and $entry.RequiredCapabilities.Count -gt 0) {
            $roomArgs['RequiredCapabilities'] = $entry.RequiredCapabilities
        }
        if ($entry.Lifecycle) {
            $roomArgs['Lifecycle'] = $entry.Lifecycle
        }

        & $newWarRoom @roomArgs
    }

    # --- Build dependency graph ---
    Write-Host "[DAG] Building dependency graph..." -ForegroundColor Cyan
    $buildDag = Join-Path $agentsDir "plan" "Build-DependencyGraph.ps1"
    $null = & $buildDag -WarRoomsDir $warRoomsDir
}

# --- Unified Negotiation Handoff ---
if ($Unified -and ($Review -or $Expand) -and -not $Resume) {
    # In Unified mode, we create the rooms UPFRONT because the handoff exits
    New-PlanWarRooms -PlanFile $PlanFile -ProjectDir $ProjectDir -warRoomsDir $warRoomsDir -agentsDir $agentsDir -parsed $parsed -planId $planId
    
    Write-Host "[UNIFIED] Handing off plan negotiation to Manager Loop." -ForegroundColor Cyan
    $env:PLAN_FILE = $PlanFile
    & $managerLoop -WarRoomsDir $warRoomsDir -Review -PlanFile $PlanFile
    exit 0
}

# --- Auto-Pass room-000 if no review/expand needed ---
if ($Unified -and -not ($Review -or $Expand) -and -not $Resume) {
    "passed" | Out-File -FilePath (Join-Path $room000Dir "status") -Encoding utf8 -NoNewline
}

# --- Unified Negotiation Loop (Legacy / Blocking) ---
$shouldNegotiate = -not $Resume -and -not $Unified

while ($shouldNegotiate) {
    # Decide if we need review
    if (-not $Review) {
        break
    }

    # Post for review
    $reviewMsgId = & $postMessage -RoomDir $room000Dir -From "manager" -To "architect" -Type "review" -Ref "PLAN-REVIEW" -Body $planContent
    Write-Host "Plan posted to room-000 for review. Waiting for approval (timeout: ${planReviewTimeout}s)..." -ForegroundColor Cyan

    # Wait for plan-approve, plan-reject, or plan-update
    $waitResultRaw = & $waitForMessage -RoomDir $room000Dir -WaitType "plan-approve", "plan-reject", "plan-update" -After $reviewMsgId -TimeoutSeconds $planReviewTimeout
    
    if ($LASTEXITCODE -ne 0 -or -not $waitResultRaw) {
        Write-Error "Plan negotiation timed out or failed."
        exit 1
    }

    $waitResult = $waitResultRaw | ConvertFrom-Json
    if (-not $waitResult -or -not $waitResult.type) {
        Write-Error "Invalid response from channel."
        exit 1
    }

    if ($waitResult.type -eq "plan-approve") {
        Write-Host "Plan approved via channel!" -ForegroundColor Green
        break
    } elseif ($waitResult.type -eq "plan-update") {
        Write-Host "Manual plan update detected. Reloading..." -ForegroundColor Yellow
        if ($waitResult.body.Trim()) {
            $waitResult.body.Trim() | Out-File -FilePath $PlanFile -Encoding utf8
        }
        # loop back to re-read it
        continue
    } else {
        # plan-reject
        $feedback = $waitResult.body
        Write-Host "Plan rejected with feedback: $feedback" -ForegroundColor Yellow
        
        # --- Apply feedback via Unified Plan Expander ---
        Write-Host "Applying feedback via AI architect..." -ForegroundColor Cyan
        $expandScript = Join-Path $agentsDir "plan" "Expand-Plan.ps1"
        & $expandScript -PlanFile $PlanFile -OutFile $PlanFile -Feedback $feedback -RoomDir $room000Dir -DryRun:$DryRun
        
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to apply feedback via AI. Please update the plan manually."
        } else {
            Write-Host "Plan updated with feedback." -ForegroundColor Green
        }
        
        $Review = $true # Ensure we keep reviewing if it was rejected once
    }
}

# --- Pre-flight: Index project codebase for semantic search ---
# TEMPORARILY DISABLED — requires GEMINI_API_KEY
# $codeIndexScript = Join-Path $agentsDir "memory" "code_index.py"
# if (Test-Path $codeIndexScript) {
#     Write-Host ""
#     Write-Host "[INDEX] Indexing project codebase for semantic search..." -ForegroundColor Cyan
#     $indexPython = Join-Path $agentsDir ".venv" "bin" "python"
#     if (-not (Test-Path $indexPython)) {
#         $indexPython = Join-Path $HOME ".ostwin" ".venv" "bin" "python"
#     }
#     if (-not (Test-Path $indexPython)) { $indexPython = "python3" }
#     $memoryEnv = Join-Path $ProjectDir ".env"
#     if (Test-Path $memoryEnv) {
#         Get-Content $memoryEnv | ForEach-Object {
#             if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$' -and $_ -notmatch '^\s*#') {
#                 $envKey = $Matches[1]; $envVal = $Matches[2].Trim('"').Trim("'")
#                 if (-not [Environment]::GetEnvironmentVariable($envKey)) {
#                     [Environment]::SetEnvironmentVariable($envKey, $envVal)
#                 }
#             }
#         }
#     }
#     try {
#         & $indexPython $codeIndexScript build --path $ProjectDir
#         Write-Host "[INDEX] ✓ Code index updated." -ForegroundColor Green
#     } catch {
#         Write-Warning "[INDEX] Code indexing failed (non-fatal): $_"
#     }
# }
Write-Host "[INDEX] Skipped (temporarily disabled)" -ForegroundColor Yellow

# --- Create missing war-rooms (after negotiation) ---
New-PlanWarRooms -PlanFile $PlanFile -ProjectDir $ProjectDir -warRoomsDir $warRoomsDir -agentsDir $agentsDir -parsed $parsed -planId $planId

# --- Start the manager loop ---
if (-not $SkipLoop) {
    Write-Host ""
    Write-Host "[STARTING] Manager loop..." -ForegroundColor Green
    & $managerLoop -WarRoomsDir $warRoomsDir
} else {
    Write-Host "[SKIPPED] Manager loop (SkipLoop requested)." -ForegroundColor Yellow
}
