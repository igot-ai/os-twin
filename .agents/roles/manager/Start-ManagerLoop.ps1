<#
.SYNOPSIS
    Manager orchestration loop — the brain of Agent OS.

.DESCRIPTION
    Monitors all war-rooms, routes work between engineers and QA,
    handles retries, deadlock detection, state timeouts, and release cycles.
    Runs continuously until all rooms pass or the process is terminated.

    Replaces: roles/manager/loop.sh

    State-machine per room:
        pending → engineering → qa-review → passed
                            ↓ error/timeout      ↓ fail
                          fixing ←←←←←←←←←←←←←←←←
                          (retries exhausted → failed-final)

.PARAMETER ConfigPath
    Path to config.json. Default: AGENT_OS_CONFIG env var or .agents/config.json.
.PARAMETER WarRoomsDir
    Directory containing war-room directories. Default: WARROOMS_DIR env var.

.EXAMPLE
    ./Start-ManagerLoop.ps1
    ./Start-ManagerLoop.ps1 -ConfigPath ./config.json -WarRoomsDir ./war-rooms
#>
[CmdletBinding()]
param(
    [string]$ConfigPath = '',
    [string]$WarRoomsDir = '',
    [switch]$Review,
    [string]$PlanFile = $env:PLAN_FILE
)

# --- Resolve paths ---
$scriptDir = $PSScriptRoot
$agentsDir = (Resolve-Path (Join-Path $scriptDir ".." "..")).Path
$channelDir = Join-Path $agentsDir "channel"
$releaseDir = Join-Path $agentsDir "release"
$managerPidFile = Join-Path $agentsDir "manager.pid"

$postMessage = Join-Path $channelDir "Post-Message.ps1"
$readMessages = Join-Path $channelDir "Read-Messages.ps1"
$startEngineer = Join-Path $agentsDir "roles" "engineer" "Start-Engineer.ps1"
$startQA = Join-Path $agentsDir "roles" "qa" "Start-QA.ps1"
$startArchitect = Join-Path $agentsDir "roles" "architect" "Start-Architect.ps1"

# --- Import modules ---
$logModule = Join-Path $agentsDir "lib" "Log.psm1"
$utilsModule = Join-Path $agentsDir "lib" "Utils.psm1"
if (Test-Path $logModule) { Import-Module $logModule -Force }
if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }

# --- Helper functions ---

# --- Resolve config ---
if (-not $ConfigPath) {
    $ConfigPath = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG }
                  else { Join-Path $agentsDir "config.json" }
}
$config = Get-Content $ConfigPath -Raw | ConvertFrom-Json

$maxConcurrent = $config.manager.max_concurrent_rooms
$pollInterval = $config.manager.poll_interval_seconds
$maxRetries = $config.manager.max_engineer_retries
$maxRedesigns = if ($config.manager.max_redesigns) { $config.manager.max_redesigns } else { 2 }
$stateTimeout = if ($config.manager.state_timeout_seconds) { $config.manager.state_timeout_seconds } else { 900 }

# --- Resolve war-rooms dir ---
if (-not $WarRoomsDir) {
    $WarRoomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR }
                   else { Join-Path $agentsDir "war-rooms" }
}

# --- Load DAG if present ---
$dagFile = Join-Path $WarRoomsDir "DAG.json"
$hasDag = Test-Path $dagFile
$testDepsReady = Join-Path $agentsDir "plan" "Test-DependenciesReady.ps1"
$updateProgress = Join-Path $agentsDir "plan" "Update-Progress.ps1"
$maxQaRetries = 10
$script:lastProgressUpdate = 0
$script:dagCache = $null
$script:dagMtime = $null
$script:rolesCache = $null
$script:rolesCacheMtime = 0

# --- Write PID ---
$PID | Out-File -FilePath $managerPidFile -Encoding utf8 -NoNewline

# --- Graceful shutdown handler ---
$script:shuttingDown = $false
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    $script:shuttingDown = $true
} | Out-Null

# --- Log startup ---
$logFn = Get-Command Write-OstwinLog -ErrorAction SilentlyContinue
if ($logFn) {
    Write-OstwinLog -Level INFO -Message "Starting Ostwin Manager Loop"
}
else {
    Write-Host "[MANAGER] Starting Ostwin Manager Loop"
}
Write-Host "  Max concurrent rooms: $maxConcurrent"
Write-Host "  Poll interval: ${pollInterval}s"
Write-Host "  Max retries per task: $maxRetries"
Write-Host "  State timeout: ${stateTimeout}s"
Write-Host ""

# --- Pre-flight checks ---
# Resolve-RoomSkills: Before spawning a worker, search the dashboard API
# for skills matching the epic's requirements and write them to the room config.
$dashboardBaseUrl = if ($env:OSTWIN_DASHBOARD_URL) { $env:OSTWIN_DASHBOARD_URL } else { "http://localhost:9000" }

function Resolve-RoomSkills {
    param([string]$RoomDir, [string]$TaskRef, [string]$AssignedRole)
    $roomConfigFile = Join-Path $RoomDir "config.json"
    if (-not (Test-Path $roomConfigFile)) { return }
    $rc = Get-Content $roomConfigFile -Raw | ConvertFrom-Json

    # Skip if skill_refs already populated
    if ($rc.skill_refs -and $rc.skill_refs.Count -gt 0) { return }

    # Build search query from full brief.md content
    $query = $TaskRef
    $briefFile = Join-Path $RoomDir "brief.md"
    if (Test-Path $briefFile) {
        $briefContent = (Get-Content $briefFile -Raw -ErrorAction SilentlyContinue)
        if ($briefContent) {
            $query = $briefContent
        }
    }

    try {
        $encodedQuery = [System.Uri]::EscapeDataString($query)
        $encodedRole = [System.Uri]::EscapeDataString($AssignedRole)
        $url = "${dashboardBaseUrl}/api/skills/search?q=${encodedQuery}&role=${encodedRole}&limit=5"
        $apiHeaders = if (Get-Command Get-OstwinApiHeaders -ErrorAction SilentlyContinue) { Get-OstwinApiHeaders } else { @{} }
        $response = Invoke-RestMethod -Uri $url -Method GET -Headers $apiHeaders -TimeoutSec 5 -ErrorAction Stop
        if ($response -and $response.Count -gt 0) {
            # Limit to top 5 results
            $topSkills = @($response | Select-Object -First 5)
            $skillNames = @($topSkills | ForEach-Object { $_.name })

            # Write skill_refs to room config.json
            $rc | Add-Member -NotePropertyName "skill_refs" -NotePropertyValue $skillNames -Force
            $rc | ConvertTo-Json -Depth 10 | Out-File -FilePath $roomConfigFile -Encoding utf8 -Force

            # Copy skill directories from AGENTS_DIR to room skills dir
            $roomSkillsDir = Join-Path $RoomDir "skills"
            if (-not (Test-Path $roomSkillsDir)) {
                New-Item -ItemType Directory -Path $roomSkillsDir -Force | Out-Null
            }

            foreach ($skill in $topSkills) {
                $relPath = $skill.relative_path
                if (-not $relPath) { continue }

                # relative_path is like "skills/roles/engineer/write-tests"
                $srcDir = Join-Path $agentsDir $relPath
                if (-not (Test-Path $srcDir)) {
                    # Also try under the home install dir
                    $homeSrc = Join-Path (Join-Path $env:HOME ".ostwin") $relPath
                    if (Test-Path $homeSrc) { $srcDir = $homeSrc }
                    else { continue }
                }

                $destDir = Join-Path $roomSkillsDir $skill.name
                if (Test-Path $destDir) {
                    Remove-Item -Path $destDir -Recurse -Force -ErrorAction SilentlyContinue
                }
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null
                Copy-Item -Path (Join-Path $srcDir "*") -Destination $destDir -Recurse -Force -ErrorAction SilentlyContinue
            }

            Write-Log "INFO" "[$TaskRef] Resolved $($skillNames.Count) skills for ${AssignedRole}: $($skillNames -join ', ')"
        }
    }
    catch {
        Write-Log "WARN" "[$TaskRef] Skill resolution failed (dashboard may be offline): $_"
    }
}

# --- Helper functions ---
function Get-ActiveCount {
    $count = 0
    Get-ChildItem -Path $WarRoomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue | ForEach-Object {
        $s = if (Test-Path (Join-Path $_.FullName "status")) {
            (Get-Content (Join-Path $_.FullName "status") -Raw).Trim()
        } else { "pending" }
        if ($s -in @('engineering', 'qa-review', 'fixing')) { $count++ }
    }
    return $count
}

function Get-MsgCount {
    param([string]$RoomDir, [string]$MsgType)
    try {
        $msgs = & $readMessages -RoomDir $RoomDir -FilterType $MsgType -AsObject
        if ($msgs) { return $msgs.Count }
    }
    catch { }
    return 0
}

function Get-LatestBody {
    param([string]$RoomDir, [string]$MsgType)
    try {
        $msgs = & $readMessages -RoomDir $RoomDir -FilterType $MsgType -Last 1 -AsObject
        if ($msgs -and $msgs.Count -gt 0) { return $msgs[-1].body }
    }
    catch { }
    return ""
}

function Test-StateTimedOut {
    param([string]$RoomDir)
    $changedFile = Join-Path $RoomDir "state_changed_at"
    if (-not (Test-Path $changedFile)) { return $false }
    $changedAt = [int](Get-Content $changedFile -Raw).Trim()
    $now = [int][double]::Parse((Get-Date -UFormat %s))
    return (($now - $changedAt) -gt $stateTimeout)
}

function Stop-RoomProcesses {
    param([string]$RoomDir)
    $pidDir = Join-Path $RoomDir "pids"
    if (-not (Test-Path $pidDir)) { return }
    Get-ChildItem $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue | ForEach-Object {
        $pidVal = (Get-Content $_.FullName -Raw).Trim()
        if ($pidVal -match '^\d+$') {
            try { Stop-Process -Id ([int]$pidVal) -Force -ErrorAction SilentlyContinue } catch { }
        }
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    }
}

function Write-RoomStatus {
    param([string]$RoomDir, [string]$NewStatus)
    if (Get-Command Set-WarRoomStatus -ErrorAction SilentlyContinue) {
        Set-WarRoomStatus -RoomDir $RoomDir -NewStatus $NewStatus
    }
    else {
        $oldStatus = if (Test-Path (Join-Path $RoomDir "status")) {
            (Get-Content (Join-Path $RoomDir "status") -Raw).Trim()
        } else { "unknown" }
        $NewStatus | Out-File -FilePath (Join-Path $RoomDir "status") -Encoding utf8 -NoNewline
        $epoch = [int][double]::Parse((Get-Date -UFormat %s))
        $epoch.ToString() | Out-File -FilePath (Join-Path $RoomDir "state_changed_at") -Encoding utf8 -NoNewline
        $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        "$ts STATUS $oldStatus -> $NewStatus" | Out-File -Append -FilePath (Join-Path $RoomDir "audit.log") -Encoding utf8
    }
}

function Write-Log {
    param([string]$Level, [string]$Message)
    if (Get-Command Write-OstwinLog -ErrorAction SilentlyContinue) {
        Write-OstwinLog -Level $Level -Message $Message
    }
    else {
        Write-Host "[MANAGER] $Message"
    }
}

function Write-SpawnLock {
    param([string]$RoomDir, [string]$Role)
    $pidDir = Join-Path $RoomDir "pids"
    if (-not (Test-Path $pidDir)) { New-Item -ItemType Directory -Path $pidDir -Force | Out-Null }
    $lockFile = Join-Path $pidDir "$Role.spawned_at"
    $epoch = [int][double]::Parse((Get-Date -UFormat %s))
    $epoch.ToString() | Out-File -FilePath $lockFile -Encoding utf8 -NoNewline
}

function Test-SpawnLock {
    param([string]$RoomDir, [string]$Role, [int]$GracePeriodSeconds = 30)
    $lockFile = Join-Path $RoomDir "pids" "$Role.spawned_at"
    if (-not (Test-Path $lockFile)) { return $false }
    try {
        $spawnedAt = [int](Get-Content $lockFile -Raw).Trim()
        $now = [int][double]::Parse((Get-Date -UFormat %s))
        return (($now - $spawnedAt) -lt $GracePeriodSeconds)
    } catch { return $false }
}

function Start-WorkerJob {
    param(
        [string]$RoomDir,
        [string]$Role,
        [string]$Script,
        [string]$TaskRef = '',
        [switch]$SkipLockCheck
    )
    if (-not $SkipLockCheck) {
        # Check if a spawn is already in flight
        if (Test-SpawnLock -RoomDir $RoomDir -Role $Role) {
            Write-Log "DEBUG" "[$TaskRef] Spawn lock active for '$Role' — skipping duplicate spawn."
            return $false
        }
        # Also check if the process is already alive
        $existingPid = Join-Path $RoomDir "pids" "$Role.pid"
        if (Test-PidAlive $existingPid) {
            Write-Log "DEBUG" "[$TaskRef] Process already alive for '$Role' — skipping duplicate spawn."
            return $false
        }
    }
    Write-SpawnLock -RoomDir $RoomDir -Role $Role
    Start-Job -ScriptBlock {
        param($s, $r)
        & $s -RoomDir $r
    } -ArgumentList $Script, $RoomDir | Out-Null
    return $true
}

function Get-CachedDag {
    if (-not (Test-Path $dagFile)) { return $null }
    $mtime = (Get-Item $dagFile).LastWriteTimeUtc.Ticks
    if ($script:dagCache -and $script:dagMtime -eq $mtime) {
        return $script:dagCache
    }
    $script:dagCache = Get-Content $dagFile -Raw | ConvertFrom-Json
    $script:dagMtime = $mtime
    return $script:dagCache
}

function Set-BlockedDescendants {
    param([string]$FailedTaskRef)
    if (-not $hasDag) { return }
    $dag = Get-CachedDag
    if (-not $dag) { return }

    # BFS through dependents
    $bfsQueue = [System.Collections.Queue]::new()
    $bfsQueue.Enqueue($FailedTaskRef)
    $visited = @{}

    while ($bfsQueue.Count -gt 0) {
        $current = $bfsQueue.Dequeue()
        if ($visited.ContainsKey($current)) { continue }
        $visited[$current] = $true

        $node = $dag.nodes.$current
        if (-not $node) { continue }
        $dependents = $node.dependents
        if (-not $dependents) { continue }
        foreach ($dep in $dependents) {
            $depNode = $dag.nodes.$dep
            if (-not $depNode) { continue }
            $depRoomDir = Join-Path $WarRoomsDir $depNode.room_id
            if (-not (Test-Path (Join-Path $depRoomDir "status"))) { continue }
            $depStatus = (Get-Content (Join-Path $depRoomDir "status") -Raw).Trim()
            if ($depStatus -eq "pending") {
                Write-Log "WARN" "[$dep] Blocked: upstream $FailedTaskRef failed"
                Write-RoomStatus $depRoomDir "blocked"
            }
            $bfsQueue.Enqueue($dep)
        }
    }
}

function Invoke-ManagerTriage {
    param([string]$RoomDir, [string]$QaFeedback)
    # Guard: no feedback means nothing to classify
    if (-not $QaFeedback -or $QaFeedback.Trim() -eq '') {
        return 'no-feedback'
    }
    # --- Classification: keyword matching ---
    $designKeywords = 'architecture|design|scope|interface|contract|api-design|redesign|structural'
    $planKeywords   = 'specification|acceptance criteria|definition of done|brief|missing requirement|requirements|out of scope'
    if ($QaFeedback -match $designKeywords) {
        return 'design-issue'
    }
    if ($QaFeedback -match $planKeywords) {
        return 'plan-gap'
    }
 
    # --- Capability-aware routing (NEW) ---
    $capabilityMatching = $true
    if ($null -ne $config.manager.capability_matching) { $capabilityMatching = $config.manager.capability_matching }
    
    # --- Subcommand-aware routing (EPIC-006) ---
    $roomConfigFile = Join-Path $RoomDir "config.json"
    if (Test-Path $roomConfigFile) {
        $rc = Get-Content $roomConfigFile -Raw | ConvertFrom-Json
        $assignedRole = if ($rc.assignment -and $rc.assignment.assigned_role) { $rc.assignment.assigned_role } else { "engineer" }
        $baseRole = $assignedRole -replace ':.*$', ''
        
        # Check for overrides first (EPIC-006)
        $overrideDir = Join-Path $RoomDir (Join-Path "overrides" $baseRole)
        $roleDir = if (Test-Path $overrideDir) { $overrideDir } else { Join-Path $agentsDir (Join-Path "roles" $baseRole) }
        $subcommandsFile = Join-Path $roleDir "subcommands.json"
        
        if (Test-Path $subcommandsFile) {
            $subcommands = Get-Content $subcommandsFile -Raw | ConvertFrom-Json
            # Load subcommand-failure analysis script (similar to Analyze-TaskRequirements)
            $analyzeSubcommandScript = Join-Path $agentsDir "roles" "_base" "Analyze-SubcommandFailure.ps1"
            if (Test-Path $analyzeSubcommandScript) {
                try {
                    $analysis = & $analyzeSubcommandScript -QaFeedback $QaFeedback -Subcommands $subcommands
                    if ($analysis.Confidence -ge 0.7 -and $analysis.SubcommandName) {
                        return "subcommand-failure:$($analysis.SubcommandName)"
                    }
                } catch { }
            } else {
                # Fallback: simple keyword matching for subcommand entrypoints
                foreach ($sc in $subcommands.subcommands.PSObject.Properties) {
                    $scName = $sc.Name
                    $scEntry = $sc.Value.entrypoint
                    if ($QaFeedback -match $scName -or ($scEntry -and $QaFeedback -match (Split-Path $scEntry -Leaf))) {
                        return "subcommand-failure:$scName"
                    }
                }
            }
        }
    }

    if ($capabilityMatching) {
        $analyzeScript = Join-Path $agentsDir "roles" "_base" "Analyze-TaskRequirements.ps1"
        if (Test-Path $analyzeScript) {
            try {
                $analysis = & $analyzeScript -TaskDescription $QaFeedback -AgentsDir $agentsDir
                if ($analysis.Confidence -ge 0.6 -and $analysis.RequiredCapabilities.Count -gt 0) {
                    # If the failure is about a specific domain, route to that specialist
                    $specialistCaps = @('security', 'database', 'infrastructure', 'architecture')
                    $matched = $analysis.RequiredCapabilities | Where-Object { $_ -in $specialistCaps }
                    if ($matched -and $matched.Count -gt 0) {
                        return 'design-issue'  # Route to specialist via architect-review path
                    }
                }
            } catch { }
        }
    }
 
    # --- Heuristic: repeated failure (same feedback >=60% word overlap) ---
    $retries = if (Test-Path (Join-Path $RoomDir "retries")) {
        [int](Get-Content (Join-Path $RoomDir "retries") -Raw).Trim()
    } else { 0 }
    if ($retries -ge 2) {
        try {
            $failMsgs = & $readMessages -RoomDir $RoomDir -FilterType "fail" -AsObject
            if ($failMsgs -and $failMsgs.Count -ge 2) {
                $prev = $failMsgs[-2].body
                $curr = $failMsgs[-1].body
                $prevWords = ($prev -split '\W+') | Where-Object { $_.Length -gt 3 } | Sort-Object -Unique
                $currWords = ($curr -split '\W+') | Where-Object { $_.Length -gt 3 } | Sort-Object -Unique
                if ($prevWords.Count -gt 0 -and $currWords.Count -gt 0) {
                    $overlap = ($prevWords | Where-Object { $currWords -contains $_ }).Count
                    $maxSet = [Math]::Max($prevWords.Count, $currWords.Count)
                    $similarity = $overlap / $maxSet
                    if ($similarity -ge 0.6) {
                        return 'design-issue'
                    }
                }
            }
        } catch { }
    }
    return 'implementation-bug'
}

function Write-TriageContext {
    param(
        [string]$RoomDir,
        [string]$Classification,
        [string]$QaFeedback,
        [string]$ArchitectGuidance,
        [string]$ManagerNotes
    )
    $artifactsDir = Join-Path $RoomDir "artifacts"
    if (-not (Test-Path $artifactsDir)) {
        New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null
    }
    $contextFile = Join-Path $artifactsDir "triage-context.md"
    $actionLine = switch ($Classification) {
        'implementation-bug' { "Engineer: Fix the specific issues listed in QA's report above." }
        'design-issue'       { "Engineer: Follow the architect's guidance above to redesign the approach." }
        'plan-gap'           { "Engineer: The brief has been updated. Re-read brief.md and implement accordingly." }
        default              { "Engineer: Address the issues identified above." }
    }
    $guidanceSection = if ($ArchitectGuidance) { $ArchitectGuidance } else { "_Not consulted — classified as implementation bug._" }
    $content = @"
# Manager Triage Context

## Classification: $Classification

## QA Failure Report
$QaFeedback

## Architect Guidance
$guidanceSection

## Manager's Direction
$ManagerNotes

## Action Required
$actionLine
"@
    $content | Out-File -FilePath $contextFile -Encoding utf8 -Force
}

function Handle-PlanApproval {
    param([string]$TaskRef)
    if ($TaskRef -eq 'PLAN-REVIEW') {
        Write-Log "INFO" "[PLAN-REVIEW] Plan approved. Unblocking dependent rooms..."
        # Re-build DAG so manager sees updated wave structure
        $buildDagScript = Join-Path $agentsDir "plan" "Build-DependencyGraph.ps1"
        if (Test-Path $buildDagScript) {
            & $buildDagScript -WarRoomsDir $WarRoomsDir
            # Clear cache to force reload
            $script:dagCache = $null
            $script:hasDag = $true
        }
    }
}

# === MAIN LOOP ===
$iteration = 0
$stallCycles = 0

while (-not $script:shuttingDown) {
    $iteration++

    # --- Hot-reload: check for new roles every 30s ---
    $nowEpochHR = [int][double]::Parse((Get-Date -UFormat %s))
    if (($nowEpochHR - $script:rolesCacheMtime) -ge 30) {
        $getAvailableRoles = Join-Path $agentsDir "roles" "_base" "Get-AvailableRoles.ps1"
        if (Test-Path $getAvailableRoles) {
            try {
                $newRoles = & $getAvailableRoles -AgentsDir $agentsDir -WarRoomsDir $WarRoomsDir
                if ($script:rolesCache -and $newRoles.Count -ne $script:rolesCache.Count) {
                    $newNames = ($newRoles | ForEach-Object { $_.Name }) -join ', '
                    Write-Log "INFO" "Roles hot-reload: $($newRoles.Count) roles available ($newNames)"
                }
                $script:rolesCache = $newRoles
            } catch { }
        }
        $script:rolesCacheMtime = $nowEpochHR
    }

    $roomCount = 0
    $allPassed = $true
    $allTerminal = $true
    $failedCount = 0
    $activeWithNoPid = 0
    $totalActive = 0

    $roomDirs = Get-ChildItem -Path $WarRoomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue

    foreach ($roomDirInfo in $roomDirs) {
        if ($script:shuttingDown) { break }

        $roomDir = $roomDirInfo.FullName
        $roomCount++
        $roomId = $roomDirInfo.Name

        $status = if (Test-Path (Join-Path $roomDir "status")) {
            (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
        } else { "pending" }

        $taskRef = if (Test-Path (Join-Path $roomDir "task-ref")) {
            (Get-Content (Join-Path $roomDir "task-ref") -Raw).Trim()
        } elseif (Test-Path (Join-Path $roomDir "config.json")) {
            $rc = Get-Content (Join-Path $roomDir "config.json") -Raw | ConvertFrom-Json
            if ($rc.task_ref) { $rc.task_ref } else { "UNKNOWN" }
        } else { "UNKNOWN" }

        $retries = if (Test-Path (Join-Path $roomDir "retries")) {
            [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
        } else { 0 }

        # --- Resolve Worker Script via centralized Resolve-Role ---
        $roomConfigFile = Join-Path $roomDir "config.json"
        $roomLifecycleFile = Join-Path $roomDir "lifecycle.json"
        $lifecycle = if (Test-Path $roomLifecycleFile) { Get-Content $roomLifecycleFile -Raw | ConvertFrom-Json } else { $null }
        $stateDef = if ($lifecycle -and $lifecycle.states -and $lifecycle.states.$status) { $lifecycle.states.$status } else { $null }
        if (-not (Test-Path $roomConfigFile)) {
            # Skip non-war-room directories like room-expansion, room-test
            continue
        }
        $assignedRole = "engineer"
 
        # If the state has a role, prefer that. Else fall back to config assignment.
        if ($stateDef -and $stateDef.role) {
            $assignedRole = $stateDef.role
        } elseif (Test-Path $roomConfigFile) {
            $rc = Get-Content $roomConfigFile -Raw | ConvertFrom-Json
            if ($rc.assignment -and $rc.assignment.assigned_role) {
                $assignedRole = $rc.assignment.assigned_role
            }
        }
        $baseRole = $assignedRole -replace ':.*$', ''
 
        # --- Override detection (EPIC-006) ---
        $overrideDir = Join-Path $roomDir (Join-Path "overrides" $baseRole)
        $effectiveRoleDir = if (Test-Path $overrideDir) {
            if ((Test-Path (Join-Path $overrideDir "subcommands.json")) -or (Test-Path (Join-Path $overrideDir "role.json"))) { $overrideDir } else { $null }
        } else { $null }

        $resolveRoleScript = Join-Path $agentsDir "roles" "_base" "Resolve-Role.ps1"
        if (Test-Path $resolveRoleScript) {
            $resolveArgs = @{
                RoleName    = $assignedRole
                AgentsDir   = $agentsDir
                WarRoomsDir = $WarRoomsDir
            }
            if ($effectiveRoleDir) {
                $resolveArgs['RolePath'] = $effectiveRoleDir
            }
            if ($script:rolesCache) {
                $resolveArgs['AvailableRoles'] = $script:rolesCache
            }
            $resolved = & $resolveRoleScript @resolveArgs
            $workerScript = $resolved.Runner
        } else {
            # Inline fallback if Resolve-Role.ps1 doesn't exist yet
            $workerScript = $null
            $registryPath = Join-Path $agentsDir "roles" "registry.json"
            if (Test-Path $registryPath) {
                $registry = Get-Content $registryPath -Raw | ConvertFrom-Json
                $matchedRole = $registry.roles | Where-Object { $_.name -eq $baseRole }
                if ($matchedRole -and $matchedRole.runner) {
                    $runnerRel = $matchedRole.runner -replace '/', [System.IO.Path]::DirectorySeparatorChar
                    $runnerPath = Join-Path $agentsDir $runnerRel
                    if (Test-Path $runnerPath) { $workerScript = $runnerPath }
                }
            }
            if (-not $workerScript) {
                $workerScript = Join-Path $agentsDir "roles" "_base" "Start-EphemeralAgent.ps1"
            }
        }

        switch ($status) {
            'pending' {
                $allPassed = $false
                $allTerminal = $false

                # --- DEPENDENCY GATE ---
                if ($hasDag) {
                    $depResult = & $testDepsReady -RoomDir $roomDir -WarRoomsDir $WarRoomsDir
                    if (-not $depResult.Ready) {
                        if ($depResult.Reason -eq 'blocked') {
                            Write-Log "WARN" "[$taskRef] Blocked by $($depResult.BlockedBy)"
                            Write-RoomStatus $roomDir "blocked"
                        }
                        # still waiting or now blocked — skip this room
                        continue
                    }
                }

                # --- ON-THE-FLY PIPELINE GENERATION ---
                $roomLifecycleCheck = Join-Path $roomDir "lifecycle.json"
                $smartAssignment = $false
                if ($config.manager.smart_assignment) { $smartAssignment = $config.manager.smart_assignment }
                $dynamicPipelines = $true
                if ($null -ne $config.manager.dynamic_pipelines) { $dynamicPipelines = $config.manager.dynamic_pipelines }

                if ($dynamicPipelines -and -not (Test-Path $roomLifecycleCheck)) {
                    $analyzeScript = Join-Path $agentsDir "roles" "_base" "Analyze-TaskRequirements.ps1"
                    $resolvePipeline = Join-Path $agentsDir "lifecycle" "Resolve-Pipeline.ps1"
                    if ((Test-Path $analyzeScript) -and (Test-Path $resolvePipeline)) {
                        $briefFile = Join-Path $roomDir "brief.md"
                        $taskDesc = if (Test-Path $briefFile) { Get-Content $briefFile -Raw } else { "" }
                        if ($taskDesc) {
                            try {
                                $analysis = & $analyzeScript -TaskDescription $taskDesc -AgentsDir $agentsDir
                                if ($analysis -and $analysis.Confidence -ge 0.6) {
                                    Write-Log "INFO" "[$taskRef] On-the-fly analysis: role=$($analysis.SuggestedRole), caps=$($analysis.RequiredCapabilities -join ','), confidence=$($analysis.Confidence)"
                                    $pipelineArgs = @{
                                        AssignedRole         = $analysis.SuggestedRole
                                        RequiredCapabilities = $analysis.RequiredCapabilities
                                        OutputPath           = $roomLifecycleCheck
                                        AgentsDir            = $agentsDir
                                    }
                                    & $resolvePipeline @pipelineArgs
                                    # Reload lifecycle for this iteration
                                    $lifecycle = Get-Content $roomLifecycleCheck -Raw | ConvertFrom-Json
                                }
                            } catch {
                                Write-Log "WARN" "[$taskRef] Task analysis failed: $_. Using default lifecycle."
                            }
                        }
                    }
                }

                if ((Get-ActiveCount) -lt $maxConcurrent) {
                    # --- SKILL RESOLUTION: resolve skills from dashboard before spawning ---
                    Resolve-RoomSkills -RoomDir $roomDir -TaskRef $taskRef -AssignedRole $assignedRole
                    $nextState = if ($lifecycle -and $lifecycle.initial_state) { $lifecycle.initial_state } else { "engineering" }
                    Write-Log "INFO" "[$taskRef] Dependencies met. Transitioning to $nextState in $roomId..."
                    Write-RoomStatus $roomDir $nextState
                    Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                }
            }

            { $_ -in @('engineering', 'fixing') } {
                $allPassed = $false
                $allTerminal = $false
                $totalActive++

                # Track whether any PID is alive for deadlock detection
                # Scan ALL pid files in the room — the spawned role may differ from
                # the lifecycle state role (e.g. config says 'architect' but lifecycle
                # state says 'manager'), so checking only $baseRole.pid misses alive agents.
                $anyPidAlive = $false
                $anySpawnLock = $false
                $pidDir = Join-Path $roomDir "pids"
                if (Test-Path $pidDir) {
                    Get-ChildItem $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue | ForEach-Object {
                        if (Test-PidAlive $_.FullName) { $anyPidAlive = $true }
                    }
                    Get-ChildItem $pidDir -Filter "*.spawned_at" -ErrorAction SilentlyContinue | ForEach-Object {
                        $role = $_.BaseName  # e.g. "architect" from "architect.spawned_at"
                        if (Test-SpawnLock -RoomDir $roomDir -Role $role) { $anySpawnLock = $true }
                    }
                }
                if (-not $anyPidAlive -and -not $anySpawnLock) { $activeWithNoPid++ }

                # Check for state timeout
                if (Test-StateTimedOut $roomDir) {
                    Write-Log "ERROR" "[$taskRef] State '$status' timed out after ${stateTimeout}s."
                    Stop-RoomProcesses $roomDir
                    if ($retries -lt $maxRetries) {
                        ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                        & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body "Previous attempt timed out after ${stateTimeout}s. Please try again."
                        Write-RoomStatus $roomDir "fixing"
                        Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                    }
                    else {
                        Write-Log "ERROR" "[$taskRef] Max retries exceeded after timeout."
                        Write-RoomStatus $roomDir "failed-final"
                        Set-BlockedDescendants $taskRef
                    }
                    continue
                }

                $doneCount = Get-MsgCount $roomDir "done"
                $approveCount = if ($taskRef -eq 'PLAN-REVIEW') { Get-MsgCount $roomDir "plan-approve" } else { 0 }
                $expected = $retries + 1

                # --- Also check design-guidance for implicit approval (architect may post this instead of plan-approve) ---
                $guidanceCount = Get-MsgCount $roomDir "design-guidance"
                $guidanceApproval = $false
                if ($guidanceCount -gt 0 -and $approveCount -eq 0) {
                    $guidanceBody = Get-LatestBody $roomDir "design-guidance"
                    if ($guidanceBody -match 'plan-approve|signoff|APPROVED') {
                        $guidanceApproval = $true
                    }
                }

                if ($approveCount -gt 0 -or $guidanceApproval) {
                    Write-Log "INFO" "[$taskRef] Plan APPROVED via channel in $status state. Marking as passed."
                    Write-RoomStatus $roomDir "passed"
                    Handle-PlanApproval -TaskRef $taskRef
                }
                elseif ($doneCount -ge $expected) {
                    # Use current status (engineering or fixing) for lifecycle lookup
                    $nextState = if ($lifecycle -and $lifecycle.states -and $lifecycle.states.$status -and $lifecycle.states.$status.transitions.done) {
                        $lifecycle.states.$status.transitions.done
                    } else { "qa-review" }
                    Write-Log "INFO" "[$taskRef] Worker ($assignedRole) done in '$status'. Transitioning to $nextState..."
                    Write-RoomStatus $roomDir $nextState
                    if ($nextState -eq "qa-review") {
                        Start-WorkerJob -RoomDir $roomDir -Role 'qa' -Script $startQA -TaskRef $taskRef -SkipLockCheck
                    } elseif ($lifecycle -and $lifecycle.states.$nextState) {
                        # Spawn agent for the next custom lifecycle state
                        $nextDef = $lifecycle.states.$nextState
                        if ($nextDef.role -and (Test-Path $resolveRoleScript)) {
                            $nextResolved = & $resolveRoleScript -RoleName $nextDef.role -AgentsDir $agentsDir -WarRoomsDir $WarRoomsDir
                            Write-Log "INFO" "[$taskRef] Spawning '$($nextDef.role)' for lifecycle state '$nextState'..."
                            Start-WorkerJob -RoomDir $roomDir -Role ($nextDef.role -replace ':.*$','') -Script $nextResolved.Runner -TaskRef $taskRef -SkipLockCheck
                        } elseif (-not $nextDef.role) {
                            # No role defined for lifecycle state — fall back to assigned worker
                            Write-Log "WARN" "[$taskRef] Lifecycle state '$nextState' has no role defined. Spawning assigned worker '$assignedRole' as fallback."
                            Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                        }
                    }
                }
                else {
                    # Check if worker process is alive
                    $engPidFile = Join-Path $roomDir "pids" "$baseRole.pid"
                    # Backward compat: also check engineer.pid for rooms created before dynamic role support
                    if (-not (Test-Path $engPidFile)) {
                        $legacyPid = Join-Path $roomDir "pids" "engineer.pid"
                        if (Test-Path $legacyPid) { $engPidFile = $legacyPid }
                    }
                    $workerPidFile = $engPidFile

                    if ((Test-Path $workerPidFile) -and -not (Test-PidAlive $workerPidFile)) {
                        $errorCount = Get-MsgCount $roomDir "error"
                        if ($errorCount -gt 0) {
                            $errorBody = Get-LatestBody $roomDir "error"
                            Write-Log "ERROR" "[$taskRef] Worker ($assignedRole) error: $errorBody"
                            if ($retries -lt $maxRetries) {
                                Write-Log "INFO" "[$taskRef] Retrying (attempt $($retries + 1)/$maxRetries)..."
                                ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                                & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body "Previous attempt failed: $errorBody. Please try again."
                                Write-RoomStatus $roomDir "fixing"
                                Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                            }
                            else {
                                Write-Log "ERROR" "[$taskRef] Max retries exceeded. Marking as failed."
                                Write-RoomStatus $roomDir "failed-final"
                                Set-BlockedDescendants $taskRef
                            }
                        }
                        else {
                            # Worker process died but left a design-guidance or other message
                            if ($guidanceCount -gt 0) {
                                if ($baseRole -eq 'architect') {
                                    # Architect's design-guidance IS its completion signal — treat as done
                                    Write-Log "INFO" "[$taskRef] Architect review complete (design-guidance posted). Transitioning to next stage."
                                    $nextState = if ($lifecycle -and $lifecycle.states -and $lifecycle.states.$status -and $lifecycle.states.$status.transitions.done) {
                                        $lifecycle.states.$status.transitions.done
                                    } else { "qa-review" }
                                    Write-RoomStatus $roomDir $nextState
                                    if ($nextState -eq "qa-review") {
                                        Start-WorkerJob -RoomDir $roomDir -Role 'qa' -Script $startQA -TaskRef $taskRef -SkipLockCheck
                                    }
                                } else {
                                    Write-Log "INFO" "[$taskRef] Worker ($assignedRole) finished with guidance but no explicit verdict. Routing to triage."
                                    Write-RoomStatus $roomDir "manager-triage"
                                }
                            }
                            else {
                                Write-Log "ERROR" "[$taskRef] Worker ($assignedRole) died without posting any message."
                                if ($retries -lt $maxRetries) {
                                    Write-Log "INFO" "[$taskRef] Retrying (attempt $($retries + 1)/$maxRetries)..."
                                    ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                                    & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body "Worker process terminated unexpectedly. Please try again."
                                    Write-RoomStatus $roomDir "fixing"
                                    Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                                } else {
                                    Write-Log "ERROR" "[$taskRef] Max retries exceeded. Marking as failed."
                                    Write-RoomStatus $roomDir "failed-final"
                                    Set-BlockedDescendants $taskRef
                                }
                            }
                        }
                    }
                    elseif (-not (Test-Path $workerPidFile)) {
                        # --- No PID file at all: check if worker posted any response ---
                        $anyResponse = $doneCount + $guidanceCount + (Get-MsgCount $roomDir "error")
                        if ($anyResponse -gt 0) {
                            if ($guidanceCount -gt 0 -and $doneCount -eq 0) {
                                if ($baseRole -eq 'architect') {
                                    # Architect's design-guidance IS its completion signal
                                    Write-Log "INFO" "[$taskRef] Architect review complete (design-guidance posted, no PID). Transitioning to next stage."
                                    $nextState = if ($lifecycle -and $lifecycle.states -and $lifecycle.states.$status -and $lifecycle.states.$status.transitions.done) {
                                        $lifecycle.states.$status.transitions.done
                                    } else { "qa-review" }
                                    Write-RoomStatus $roomDir $nextState
                                    if ($nextState -eq "qa-review") {
                                        Start-WorkerJob -RoomDir $roomDir -Role 'qa' -Script $startQA -TaskRef $taskRef -SkipLockCheck
                                    }
                                } else {
                                    Write-Log "INFO" "[$taskRef] Worker ($assignedRole) posted guidance but no done/approve. Routing to triage."
                                    Write-RoomStatus $roomDir "manager-triage"
                                }
                            }
                            # else: done or error already handled above
                        }
                        elseif (Test-StateTimedOut $roomDir) {
                            Write-Log "ERROR" "[$taskRef] No PID file and state timed out. Worker ($assignedRole) may have failed to start."
                            if ($retries -lt $maxRetries) {
                                ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                                & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body "Worker process failed to start or timed out. Please try again."
                                Write-RoomStatus $roomDir "fixing"
                                Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                            } else {
                                Write-Log "ERROR" "[$taskRef] Max retries exceeded. Marking as failed."
                                Write-RoomStatus $roomDir "failed-final"
                                Set-BlockedDescendants $taskRef
                            }
                        }
                        elseif (-not (Test-SpawnLock -RoomDir $roomDir -Role $baseRole)) {
                            # No PID, no responses, spawn lock expired — worker died silently. Respawn it.
                            Write-Log "WARN" "[$taskRef] Worker ($assignedRole) has no PID and no responses. Respawning..."
                            Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                        }
                    }
                }
            }

            'qa-review' {
                $allPassed = $false
                $allTerminal = $false
                $totalActive++

                # Track PID for deadlock detection — scan all PIDs in room
                $anyPidAlive = $false; $anySpawnLock = $false
                $pidDir = Join-Path $roomDir "pids"
                if (Test-Path $pidDir) {
                    Get-ChildItem $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue | ForEach-Object {
                        if (Test-PidAlive $_.FullName) { $anyPidAlive = $true }
                    }
                    Get-ChildItem $pidDir -Filter "*.spawned_at" -ErrorAction SilentlyContinue | ForEach-Object {
                        if (Test-SpawnLock -RoomDir $roomDir -Role $_.BaseName) { $anySpawnLock = $true }
                    }
                }
                if (-not $anyPidAlive -and -not $anySpawnLock) { $activeWithNoPid++ }

                # Check for state timeout
                if (Test-StateTimedOut $roomDir) {
                    Write-Log "ERROR" "[$taskRef] QA review timed out after ${stateTimeout}s."
                    Stop-RoomProcesses $roomDir
                    if ($retries -lt $maxRetries) {
                        ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                        & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body "QA review timed out. Please review and fix."
                        Write-RoomStatus $roomDir "fixing"
                        Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                    }
                    else {
                        Write-RoomStatus $roomDir "failed-final"
                    }
                    continue
                }

                $passCount = Get-MsgCount $roomDir "pass"
                $approveCount = if ($taskRef -eq 'PLAN-REVIEW') { Get-MsgCount $roomDir "plan-approve" } else { 0 }
                if ($passCount -gt 0 -or $approveCount -gt 0) {
                    $nextState = if ($lifecycle -and $lifecycle.states -and $lifecycle.states.'qa-review' -and $lifecycle.states.'qa-review'.transitions.pass) {
                        $lifecycle.states.'qa-review'.transitions.pass
                    } else { "passed" }
                    Write-Log "INFO" "[$taskRef] QA PASSED or Plan APPROVED! Transitioning to $nextState."
                    Write-RoomStatus $roomDir $nextState
                    Handle-PlanApproval -TaskRef $taskRef
                }
                else {
                    $escalateCount = Get-MsgCount $roomDir "escalate"
                    $failCount = Get-MsgCount $roomDir "fail"
                    $rejectCount = if ($taskRef -eq 'PLAN-REVIEW') { Get-MsgCount $roomDir "plan-reject" } else { 0 }
                    $updateCount = if ($taskRef -eq 'PLAN-REVIEW') { Get-MsgCount $roomDir "plan-update" } else { 0 }
                    
                    if ($updateCount -gt 0) {
                        $updateBody = Get-LatestBody $roomDir "plan-update"
                        Write-Log "INFO" "[$taskRef] Manual plan update detected. Reloading $PlanFile..."
                        if ($updateBody.Trim()) {
                            $updateBody.Trim() | Out-File -FilePath $PlanFile -Encoding utf8
                        }
                        Write-RoomStatus $roomDir "pending"
                        continue
                    }

                    if ($escalateCount -gt 0 -or $failCount -gt 0 -or $rejectCount -gt 0) {
                        $feedback = if ($escalateCount -gt 0) {
                            Get-LatestBody $roomDir "escalate"
                        } elseif ($rejectCount -gt 0) {
                            Get-LatestBody $roomDir "plan-reject"
                        } else {
                            Get-LatestBody $roomDir "fail"
                        }
                        $triggerType = if ($escalateCount -gt 0) { "ESCALATE" } elseif ($rejectCount -gt 0) { "PLAN-REJECT" } else { "FAIL" }
                        Write-Log "INFO" "[$taskRef] QA $triggerType. Routing to manager triage..."
                        # Save triage input for analysis
                        $triageInputFile = Join-Path $roomDir "artifacts" "triage-input.md"
                        $artifactsDir = Join-Path $roomDir "artifacts"
                        if (-not (Test-Path $artifactsDir)) {
                            New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null
                        }
                        "# QA $triggerType Report`n`n$feedback" | Out-File -FilePath $triageInputFile -Encoding utf8 -Force
                        Write-RoomStatus $roomDir "manager-triage"
                    }
                    else {
                        # Check for QA error / process death
                        $errorCount = Get-MsgCount $roomDir "error"
                        if ($errorCount -gt 0) {
                            $errorBody = Get-LatestBody $roomDir "error"
                            Write-Log "WARN" "[$taskRef] QA error (verdict parse failure): $errorBody"
                            # Use separate qa_retries counter to prevent infinite QA retry loops
                            $qaRetries = if (Test-Path (Join-Path $roomDir "qa_retries")) {
                                [int](Get-Content (Join-Path $roomDir "qa_retries") -Raw).Trim()
                            } else { 0 }
                            if ($qaRetries -lt $maxQaRetries) {
                                ($qaRetries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "qa_retries") -Encoding utf8 -NoNewline
                                Write-Log "INFO" "[$taskRef] Re-running QA review (qa retry $($qaRetries + 1)/$maxQaRetries)..."
                                Write-RoomStatus $roomDir "qa-review"
                                Start-WorkerJob -RoomDir $roomDir -Role 'qa' -Script $startQA -TaskRef $taskRef -SkipLockCheck
                            }
                            else {
                                Write-Log "ERROR" "[$taskRef] QA retries exhausted ($maxQaRetries)."
                                if ($retries -lt $maxRetries) {
                                    Write-Log "WARN" "[$taskRef] Engineer retries not exhausted ($retries < $maxRetries). Rescuing to manager-triage."
                                    Write-RoomStatus $roomDir "manager-triage"
                                }
                                else {
                                    Write-Log "ERROR" "[$taskRef] Engineer retries also exhausted. Marking as failed-final."
                                    Write-RoomStatus $roomDir "failed-final"
                                    Set-BlockedDescendants $taskRef
                                }
                            }
                        }
                        else {
                            $qaPidFile = Join-Path $roomDir "pids" "qa.pid"
                            if (-not (Test-PidAlive $qaPidFile)) {
                                # Silent QA death or first time in qa-review (e.g. from transition)
                                Write-Log "INFO" "[$taskRef] Starting QA in $roomId..."
                                Start-WorkerJob -RoomDir $roomDir -Role 'qa' -Script $startQA -TaskRef $taskRef
                            }
                        }
                    }
                }
            }

            'manager-triage' {
                $allPassed = $false
                $allTerminal = $false
                $totalActive++

                # Classify the failure
                $feedback = ""
                $escalateCount = Get-MsgCount $roomDir "escalate"
                if ($escalateCount -gt 0) {
                    $feedback = Get-LatestBody $roomDir "escalate"
                } else {
                    $feedback = Get-LatestBody $roomDir "fail"
                    if (-not $feedback) {
                        $feedback = Get-LatestBody $roomDir "error"
                    }
                }

                $classification = Invoke-ManagerTriage -RoomDir $roomDir -QaFeedback $feedback
                
                # --- Unified Plan Negotiation: Handle feedback via AI expansion ---
                if ($taskRef -eq 'PLAN-REVIEW') {
                    Write-Log "INFO" "[$taskRef] Applying feedback via AI architect..."
                    $expandScript = Join-Path $agentsDir "plan" "Expand-Plan.ps1"
                    if (Test-Path $expandScript) {
                        $expandArgs = @("-NoProfile", "-NonInteractive", "-File", "`"$expandScript`"", "-PlanFile", "`"$PlanFile`"", "-OutFile", "`"$PlanFile`"", "-Feedback", "`"$($feedback -replace '"', '\"')`"", "-RoomDir", "`"$roomDir`"")
                        & pwsh @expandArgs
                        
                        if ($LASTEXITCODE -eq 0) {
                            Write-Log "INFO" "[$taskRef] Plan updated with feedback. Resetting to pending."
                            Write-RoomStatus $roomDir "pending"
                        } else {
                            Write-Log "ERROR" "[$taskRef] Failed to expand plan with feedback. ExitCode: $LASTEXITCODE"
                            Write-Log "WARN" "[$taskRef] AI expansion failed. Resetting to pending for manual review/update."
                            Write-RoomStatus $roomDir "pending"
                        }
                    } else {
                        Write-Log "ERROR" "[$taskRef] Expand-Plan.ps1 not found."
                        Write-RoomStatus $roomDir "failed-final"
                    }
                    continue
                }

                Write-Log "INFO" "[$taskRef] Triage classification: $classification"

                switch ($classification) {
                    'no-feedback' {
                        Write-Log "WARN" "[$taskRef] Triage with no feedback. Retrying initial state..."
                        if ($retries -lt $maxRetries) {
                            ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                            $retryState = if ($lifecycle -and $lifecycle.initial_state) { $lifecycle.initial_state } else { "engineering" }
                            Write-RoomStatus $roomDir $retryState
                            Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                        } else {
                            Write-Log "ERROR" "[$taskRef] Max retries exceeded (no feedback). Marking as failed."
                            Write-RoomStatus $roomDir "failed-final"
                            Set-BlockedDescendants $taskRef
                        }
                    }
                    'implementation-bug' {
                        if ($retries -lt $maxRetries) {
                            Write-Log "INFO" "[$taskRef] Implementation bug. Routing fix to engineer (retry $($retries + 1)/$maxRetries)..."
                            ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                            Write-TriageContext -RoomDir $roomDir -Classification $classification -QaFeedback $feedback -ManagerNotes "Classified as implementation bug. Engineer should fix the specific issues."
                            & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body $feedback
                            Write-RoomStatus $roomDir "fixing"
                            Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                        }
                        else {
                            Write-Log "ERROR" "[$taskRef] Max retries exceeded after triage. Marking as failed."
                            Write-RoomStatus $roomDir "failed-final"
                            Set-BlockedDescendants $taskRef
                        }
                    }
                    'design-issue' {
                        Write-Log "INFO" "[$taskRef] Design issue detected. Routing to architect..."
                        & $postMessage -RoomDir $roomDir -From "manager" -To "architect" -Type "design-review" -Ref $taskRef -Body "Design issue detected in $taskRef. QA feedback: $feedback"
                        Write-RoomStatus $roomDir "architect-review"
                        if (Test-Path $startArchitect) {
                            Start-WorkerJob -RoomDir $roomDir -Role 'architect' -Script $startArchitect -TaskRef $taskRef -SkipLockCheck
                        } else {
                            Write-Log "WARN" "[$taskRef] Start-Architect.ps1 not found. Falling back to engineer fix."
                            Write-TriageContext -RoomDir $roomDir -Classification $classification -QaFeedback $feedback -ManagerNotes "Design issue detected but architect unavailable. Engineer should attempt redesign."
                            if ($retries -lt $maxRetries) {
                                ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                                & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body $feedback
                                Write-RoomStatus $roomDir "fixing"
                                Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                            } else {
                                Write-RoomStatus $roomDir "failed-final"
                                Set-BlockedDescendants $taskRef
                            }
                        }
                    }
                    'plan-gap' {
                        Write-Log "INFO" "[$taskRef] Plan gap detected. Routing to architect for plan revision..."
                        & $postMessage -RoomDir $roomDir -From "manager" -To "architect" -Type "design-review" -Ref $taskRef -Body "Plan gap in $taskRef. Requirements may need updating. QA feedback: $feedback"
                        Write-RoomStatus $roomDir "architect-review"
                        if (Test-Path $startArchitect) {
                            Start-WorkerJob -RoomDir $roomDir -Role 'architect' -Script $startArchitect -TaskRef $taskRef -SkipLockCheck
                        } else {
                            Write-Log "WARN" "[$taskRef] Start-Architect.ps1 not found. Routing to plan-revision directly."
                            Write-RoomStatus $roomDir "plan-revision"
                        }
                    }
                }

                if ($classification -match '^subcommand-failure:(.+)$') {
                    $subcommand = $Matches[1]
                    $redesigns = if (Test-Path (Join-Path $roomDir "redesigns")) {
                        [int](Get-Content (Join-Path $roomDir "redesigns") -Raw).Trim()
                    } else { 0 }

                    if ($redesigns -lt $maxRedesigns) {
                        Write-Log "INFO" "[$taskRef] Subcommand failure detected ($subcommand). Routing to subcommand redesign (retry $($redesigns + 1)/$maxRedesigns)..."
                        ($redesigns + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "redesigns") -Encoding utf8 -NoNewline
                        Write-RoomStatus $roomDir "subcommand-redesign"
                        
                        $redesignScript = Join-Path $agentsDir "roles" "manager" "Redesign-Subcommand.ps1"
                        if (Test-Path $redesignScript) {
                            Write-SpawnLock -RoomDir $roomDir -Role $baseRole
                            Start-Job -ScriptBlock {
                                param($script, $room, $role, $sc, $feedback, $ref)
                                & $script -RoomDir $room -RoleName $role -SubcommandName $sc -ErrorContext $feedback -TaskRef $ref
                            } -ArgumentList $redesignScript, $roomDir, $baseRole, $subcommand, $feedback, $taskRef | Out-Null
                        } else {
                            Write-Log "ERROR" "[$taskRef] Redesign-Subcommand.ps1 not found. Failing."
                            Write-RoomStatus $roomDir "failed-final"
                        }
                    } else {
                        Write-Log "ERROR" "[$taskRef] Max subcommand redesigns exceeded ($maxRedesigns)."
                        Write-RoomStatus $roomDir "failed-final"
                        Set-BlockedDescendants $taskRef
                    }
                }
            }

            #BUG in this block
            'architect-review' {
                $allPassed = $false
                $allTerminal = $false
                $totalActive++

                # Track PID for deadlock detection — scan all PIDs in room
                $anyPidAlive = $false; $anySpawnLock = $false
                $pidDir = Join-Path $roomDir "pids"
                if (Test-Path $pidDir) {
                    Get-ChildItem $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue | ForEach-Object {
                        if (Test-PidAlive $_.FullName) { $anyPidAlive = $true }
                    }
                    Get-ChildItem $pidDir -Filter "*.spawned_at" -ErrorAction SilentlyContinue | ForEach-Object {
                        if (Test-SpawnLock -RoomDir $roomDir -Role $_.BaseName) { $anySpawnLock = $true }
                    }
                }
                if (-not $anyPidAlive -and -not $anySpawnLock) { $activeWithNoPid++ }

                # Check for state timeout
                if (Test-StateTimedOut $roomDir) {
                    Write-Log "ERROR" "[$taskRef] Architect review timed out. Falling back to engineer fix."
                    Stop-RoomProcesses $roomDir
                    $feedback = Get-LatestBody $roomDir "fail"
                    if (-not $feedback) { $feedback = Get-LatestBody $roomDir "escalate" }
                    if (-not $feedback) { $feedback = Get-LatestBody $roomDir "error" }
                    Write-TriageContext -RoomDir $roomDir -Classification 'design-issue' -QaFeedback $feedback -ManagerNotes "Architect review timed out. Engineer should attempt best-effort fix."
                    if ($retries -lt $maxRetries) {
                        ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                        & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body $feedback
                        Write-RoomStatus $roomDir "fixing"
                        Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                    } else {
                        Write-RoomStatus $roomDir "failed-final"
                        Set-BlockedDescendants $taskRef
                    }
                    continue
                }

                # Check for architect's design-guidance response
                $guidanceCount = Get-MsgCount $roomDir "design-guidance"
                if ($guidanceCount -gt 0) {
                    $guidance = Get-LatestBody $roomDir "design-guidance"
                    Write-Log "INFO" "[$taskRef] Architect guidance received."

                    # Parse recommendation: FIX, REDESIGN, or REPLAN
                    $recommendation = 'FIX'
                    if ($guidance -match 'RECOMMENDATION:\s*(FIX|REDESIGN|REPLAN)') {
                        $recommendation = $Matches[1].ToUpper()
                    }

                    $qaFeedback = Get-LatestBody $roomDir "fail"
                    if (-not $qaFeedback) { $qaFeedback = Get-LatestBody $roomDir "escalate" }
                    if (-not $qaFeedback) { $qaFeedback = Get-LatestBody $roomDir "error" }

                    switch ($recommendation) {
                        'FIX' {
                            Write-Log "INFO" "[$taskRef] Architect says FIX. Routing to engineer with guidance."
                            Write-TriageContext -RoomDir $roomDir -Classification 'design-issue' -QaFeedback $qaFeedback -ArchitectGuidance $guidance -ManagerNotes "Architect reviewed and recommends targeted fix."
                            if ($retries -lt $maxRetries) {
                                ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                                & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body $guidance
                                Write-RoomStatus $roomDir "fixing"
                                Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                            } else {
                                Write-RoomStatus $roomDir "failed-final"
                                Set-BlockedDescendants $taskRef
                            }
                        }
                        'REDESIGN' {
                            Write-Log "INFO" "[$taskRef] Architect says REDESIGN. Routing to engineer with design guidance."
                            Write-TriageContext -RoomDir $roomDir -Classification 'design-issue' -QaFeedback $qaFeedback -ArchitectGuidance $guidance -ManagerNotes "Architect recommends redesign. Engineer must follow architect's approach."
                            if ($retries -lt $maxRetries) {
                                ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                                & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body $guidance
                                Write-RoomStatus $roomDir "fixing"
                                Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                            } else {
                                Write-RoomStatus $roomDir "failed-final"
                                Set-BlockedDescendants $taskRef
                            }
                        }
                        'REPLAN' {
                            Write-Log "INFO" "[$taskRef] Architect says REPLAN. Transitioning to plan-revision."
                            Write-TriageContext -RoomDir $roomDir -Classification 'plan-gap' -QaFeedback $qaFeedback -ArchitectGuidance $guidance -ManagerNotes "Architect recommends plan revision. Brief will be updated."
                            Write-RoomStatus $roomDir "plan-revision"
                        }
                    }
                }
                else {
                    # Check if architect process is alive
                    $archPidFile = Join-Path $roomDir "pids" "architect.pid"
                    if ((Test-Path $archPidFile) -and -not (Test-PidAlive $archPidFile)) {
                        $archErrorCount = Get-MsgCount $roomDir "error"
                        Write-Log "WARN" "[$taskRef] Architect process died. Falling back to engineer fix."
                        $qaFeedback = Get-LatestBody $roomDir "fail"
                        if (-not $qaFeedback) { $qaFeedback = Get-LatestBody $roomDir "escalate" }
                        if (-not $qaFeedback) { $qaFeedback = Get-LatestBody $roomDir "error" }
                        Write-TriageContext -RoomDir $roomDir -Classification 'design-issue' -QaFeedback $qaFeedback -ManagerNotes "Architect review failed. Engineer should attempt best-effort fix."
                        if ($retries -lt $maxRetries) {
                            ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                            & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref $taskRef -Body $qaFeedback
                            Write-RoomStatus $roomDir "fixing"
                            Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                        } else {
                            Write-RoomStatus $roomDir "failed-final"
                            Set-BlockedDescendants $taskRef
                        }
                    }
                    elseif (-not (Test-Path $archPidFile) -and -not (Test-SpawnLock -RoomDir $roomDir -Role 'architect')) {
                        # No PID file and spawn lock expired — architect never started or was cleaned up. Respawn it.
                        Write-Log "WARN" "[$taskRef] Architect has no PID file. Respawning..."
                        if (Test-Path $startArchitect) {
                            Start-WorkerJob -RoomDir $roomDir -Role 'architect' -Script $startArchitect -TaskRef $taskRef -SkipLockCheck
                        } else {
                            Write-Log "WARN" "[$taskRef] Start-Architect.ps1 not found. Falling back to engineer fix."
                            $qaFeedback = Get-LatestBody $roomDir "fail"
                            if (-not $qaFeedback) { $qaFeedback = Get-LatestBody $roomDir "escalate" }
                            if (-not $qaFeedback) { $qaFeedback = "Architect unavailable." }
                            Write-TriageContext -RoomDir $roomDir -Classification 'design-issue' -QaFeedback $qaFeedback -ManagerNotes "Architect unavailable. Engineer should attempt best-effort fix."
                            if ($retries -lt $maxRetries) {
                                ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                                & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body $qaFeedback
                                Write-RoomStatus $roomDir "fixing"
                                Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                            } else {
                                Write-RoomStatus $roomDir "failed-final"
                                Set-BlockedDescendants $taskRef
                            }
                        }
                    }
                }
            }

            'plan-revision' {
                $allPassed = $false
                $allTerminal = $false
                $totalActive++

                # Update brief.md with triage context and architect guidance
                $briefFile = Join-Path $roomDir "brief.md"
                $triageFile = Join-Path $roomDir "artifacts" "triage-context.md"
                if (Test-Path $briefFile) {
                    $originalBrief = Get-Content $briefFile -Raw
                    $revisionNote = ""
                    if (Test-Path $triageFile) {
                        $triageContent = Get-Content $triageFile -Raw
                        $revisionNote = "`n`n---`n`n## Plan Revision Notes`n`n$triageContent"
                    }
                    $updatedBrief = $originalBrief + $revisionNote
                    $updatedBrief | Out-File -FilePath $briefFile -Encoding utf8 -Force
                    Write-Log "INFO" "[$taskRef] Brief updated with revision notes. Resetting to engineering."
                } else {
                    Write-Log "WARN" "[$taskRef] No brief.md found. Resetting to engineering anyway."
                }

                # Reset qa_retries for fresh QA cycle
                $qaRetriesFile = Join-Path $roomDir "qa_retries"
                if (Test-Path $qaRetriesFile) { Remove-Item $qaRetriesFile -Force }

                & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "plan-update" -Ref $taskRef -Body "Brief has been revised. Please re-read brief.md and implement accordingly."
                Write-RoomStatus $roomDir "engineering"
                Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
            }

            'passed' {
                # Good — this room is done
            }

            'subcommand-redesign' {
                $allPassed = $false
                $allTerminal = $false
                $totalActive++

                if (Test-StateTimedOut $roomDir) {
                    Write-Log "ERROR" "[$taskRef] Subcommand redesign timed out."
                    Write-RoomStatus $roomDir "failed-final"
                    continue
                }

                $redesignDone = Get-MsgCount $roomDir "redesign-done"
                if ($redesignDone -gt 0) {
                    Write-Log "INFO" "[$taskRef] Subcommand redesign complete. Retrying engineering."
                    Write-RoomStatus $roomDir "engineering"
                    & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "task" -Ref $taskRef -Body "Subcommand redesign complete. Please retry the task with updated subcommands."
                    Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                } else {
                    $redesignError = Get-MsgCount $roomDir "error"
                    if ($redesignError -gt 0) {
                        Write-Log "ERROR" "[$taskRef] Subcommand redesign failed."
                        Write-RoomStatus $roomDir "failed-final"
                    }
                }
            }

            'failed-final' {
                # Safety net: if retries not exhausted, an external agent may have
                # bypassed the manager (e.g., QA called warroom_update_status directly).
                # Rescue the room back to manager-triage so the normal flow can proceed.
                if ($retries -lt $maxRetries) {
                    $failFeedback = Get-LatestBody $roomDir "fail"
                    if (-not $failFeedback) { $failFeedback = Get-LatestBody $roomDir "error" }
                    if ($failFeedback) {
                        Write-Log "WARN" "[$taskRef] failed-final with retries=$retries < max=$maxRetries. Rescuing to manager-triage."
                        Write-RoomStatus $roomDir "manager-triage"
                        $allPassed = $false
                        $allTerminal = $false
                    }
                    else {
                        # No feedback messages — truly terminal
                        $allPassed = $false
                        $failedCount++
                    }
                }
                else {
                    $allPassed = $false
                    $failedCount++
                }
            }

            'blocked' {
                $allPassed = $false
                $failedCount++
            }

            default {
                # --- GENERIC LIFECYCLE-AWARE STATE HANDLER ---
                # Handles any custom state defined in lifecycle.json (e.g., security-review, schema-review)
                if ($lifecycle -and $lifecycle.states -and $lifecycle.states.$status) {
                    $customStateDef = $lifecycle.states.$status
                    $allPassed = $false
                    $allTerminal = $false
                    $totalActive++

                    # Track PID for deadlock detection — scan all PIDs in room
                    $anyPidAlive = $false; $anySpawnLock = $false
                    $pidDir = Join-Path $roomDir "pids"
                    if (Test-Path $pidDir) {
                        Get-ChildItem $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue | ForEach-Object {
                            if (Test-PidAlive $_.FullName) { $anyPidAlive = $true }
                        }
                        Get-ChildItem $pidDir -Filter "*.spawned_at" -ErrorAction SilentlyContinue | ForEach-Object {
                            if (Test-SpawnLock -RoomDir $roomDir -Role $_.BaseName) { $anySpawnLock = $true }
                        }
                    }
                    if (-not $anyPidAlive -and -not $anySpawnLock) { $activeWithNoPid++ }

                    # Check for state timeout
                    if (Test-StateTimedOut $roomDir) {
                        Write-Log "ERROR" "[$taskRef] Custom state '$status' timed out after ${stateTimeout}s."
                        Stop-RoomProcesses $roomDir
                        if ($customStateDef.transitions.fail) {
                            Write-RoomStatus $roomDir $customStateDef.transitions.fail
                        } elseif ($retries -lt $maxRetries) {
                            ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                            # Retry the SAME custom state with the correct role agent
                            Write-Log "WARN" "[$taskRef] Retrying custom state '$status' (attempt $($retries + 1)/$maxRetries)..."
                            Write-RoomStatus $roomDir $status
                            $stateRole = if ($customStateDef.role) { $customStateDef.role } else { $baseRole }
                            if (Test-Path $resolveRoleScript) {
                                $retryResolved = & $resolveRoleScript -RoleName $stateRole -AgentsDir $agentsDir -WarRoomsDir $WarRoomsDir
                                Start-WorkerJob -RoomDir $roomDir -Role ($stateRole -replace ':.*$','') -Script $retryResolved.Runner -TaskRef $taskRef -SkipLockCheck
                            } else {
                                Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                            }
                        } else {
                            Write-Log "ERROR" "[$taskRef] Max retries exceeded after custom state timeout."
                            Write-RoomStatus $roomDir "failed-final"
                            Set-BlockedDescendants $taskRef
                        }
                        continue
                    }

                    $stateRole = if ($customStateDef.role) { $customStateDef.role } else { $baseRole }
                    $stateBaseRole = $stateRole -replace ':.*$', ''

                    if ($customStateDef.type -eq 'review' -or $status -match '(review|audit|check|verify)') {
                        # --- REVIEW STATE: expects pass/fail/escalate ---
                        $passCount = Get-MsgCount $roomDir "pass"
                        $failCount = Get-MsgCount $roomDir "fail"
                        $escalateCount = Get-MsgCount $roomDir "escalate"

                        if ($passCount -gt 0) {
                            $nextState = if ($customStateDef.transitions.pass) { $customStateDef.transitions.pass } else { 'passed' }
                            Write-Log "INFO" "[$taskRef] Custom review '$status' by '$stateRole' PASSED. Transitioning to $nextState."
                            Write-RoomStatus $roomDir $nextState
                        }
                        elseif ($failCount -gt 0 -or $escalateCount -gt 0) {
                            $feedback = if ($escalateCount -gt 0) { Get-LatestBody $roomDir "escalate" } else { Get-LatestBody $roomDir "fail" }
                            $nextState = if ($customStateDef.transitions.fail) { $customStateDef.transitions.fail } else { 'manager-triage' }
                            Write-Log "INFO" "[$taskRef] Custom review '$status' by '$stateRole' FAILED. Transitioning to $nextState."
                            # Save triage input
                            $artifactsDir = Join-Path $roomDir "artifacts"
                            if (-not (Test-Path $artifactsDir)) { New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null }
                            "# $status Report`n`n$feedback" | Out-File -FilePath (Join-Path $artifactsDir "triage-input.md") -Encoding utf8 -Force
                            Write-RoomStatus $roomDir $nextState
                        }
                        else {
                            # Check if review agent is alive, spawn if needed
                            $reviewPidFile = Join-Path $roomDir "pids" "$stateBaseRole.pid"
                            if (-not (Test-PidAlive $reviewPidFile)) {
                                # Resolve the reviewer's runner script
                                if (Test-Path $resolveRoleScript) {
                                    $reviewResolved = & $resolveRoleScript -RoleName $stateRole -AgentsDir $agentsDir -WarRoomsDir $WarRoomsDir
                                    Write-Log "INFO" "[$taskRef] Starting '$stateRole' for custom review state '$status'..."
                                    Start-WorkerJob -RoomDir $roomDir -Role $stateBaseRole -Script $reviewResolved.Runner -TaskRef $taskRef
                                } else {
                                    Write-Log "WARN" "[$taskRef] Cannot resolve runner for '$stateRole'. Resolve-Role.ps1 not found."
                                }
                            }
                        }
                    }
                    else {
                        # --- WORKER STATE: expects done ---
                        $doneCount = Get-MsgCount $roomDir "done"
                        if ($doneCount -ge ($retries + 1)) {
                            $nextState = if ($customStateDef.transitions.done) { $customStateDef.transitions.done } else { 'qa-review' }
                            Write-Log "INFO" "[$taskRef] Custom worker '$status' by '$stateRole' done. Transitioning to $nextState."
                            Write-RoomStatus $roomDir $nextState

                            # If next state needs a different agent, resolve and spawn it
                            if ($lifecycle.states.$nextState) {
                                $nextDef = $lifecycle.states.$nextState
                                if ($nextDef.role -and $nextDef.role -ne $stateRole) {
                                    if (Test-Path $resolveRoleScript) {
                                        $nextResolved = & $resolveRoleScript -RoleName $nextDef.role -AgentsDir $agentsDir -WarRoomsDir $WarRoomsDir
                                        Write-Log "INFO" "[$taskRef] Auto-spawning '$($nextDef.role)' for state '$nextState'..."
                                        Start-WorkerJob -RoomDir $roomDir -Role ($nextDef.role -replace ':.*$','') -Script $nextResolved.Runner -TaskRef $taskRef -SkipLockCheck
                                    }
                                }
                            }
                        }
                        else {
                            # Check if worker is alive, spawn if needed
                            $workerPidFile = Join-Path $roomDir "pids" "$stateBaseRole.pid"
                            if (-not (Test-PidAlive $workerPidFile)) {
                                Write-Log "INFO" "[$taskRef] Starting '$stateRole' for custom worker state '$status'..."
                                Start-WorkerJob -RoomDir $roomDir -Role $stateBaseRole -Script $workerScript -TaskRef $taskRef
                            }
                        }
                    }
                }
                else {
                    Write-Log "WARN" "Unknown status '$status' for $roomId (no lifecycle definition found)"
                    $allPassed = $false
                    $allTerminal = $false
                }
            }
        }
    }

    # === Deadlock detection ===
    if ($totalActive -gt 0 -and $activeWithNoPid -eq $totalActive) {
        $stallCycles++
        if ($stallCycles -ge 12) {  # 12 cycles × 5s poll = 60s — enough for LLM API calls to complete
            Write-Log "WARN" "Deadlock detected: $totalActive rooms active but no PIDs alive for 2 cycles. Attempting recovery..."
            Get-ChildItem -Path $WarRoomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue | ForEach-Object {
                $rd = $_.FullName
                $ls = if (Test-Path (Join-Path $rd "status")) { (Get-Content (Join-Path $rd "status") -Raw).Trim() } else { "" }
                $lr = if (Test-Path (Join-Path $rd "retries")) { [int](Get-Content (Join-Path $rd "retries") -Raw).Trim() } else { 0 }
                $lt = if (Test-Path (Join-Path $rd "task-ref")) { (Get-Content (Join-Path $rd "task-ref") -Raw).Trim() } else { "UNKNOWN" }

                # --- Safety net: cap total deadlock recoveries per room ---
                $dlFile = Join-Path $rd "deadlock_recoveries"
                $dlCount = if (Test-Path $dlFile) { [int](Get-Content $dlFile -Raw).Trim() } else { 0 }
                if ($dlCount -ge 3) {
                    Write-Log "ERROR" "[$lt] Max deadlock recoveries (3) exceeded. Marking as failed."
                    Write-RoomStatus $rd "failed-final"
                    Set-BlockedDescendants $lt
                    return  # ForEach-Object uses 'return' to skip to next item
                }
                ($dlCount + 1).ToString() | Out-File -FilePath $dlFile -Encoding utf8 -NoNewline

                # Resolve the room's assigned role (not the stale $baseRole from the main loop)
                $dlRoomConfig = Join-Path $rd "config.json"
                $dlRole = "engineer"
                if (Test-Path $dlRoomConfig) {
                    $dlRc = Get-Content $dlRoomConfig -Raw | ConvertFrom-Json
                    if ($dlRc.assignment -and $dlRc.assignment.assigned_role) {
                        $dlRole = $dlRc.assignment.assigned_role -replace ':.*$', ''
                    }
                }

                if ($ls -in @('engineering', 'fixing')) {
                    if ($lr -lt $maxRetries) {
                        Write-Log "WARN" "[$lt] Deadlock recovery: restarting $dlRole via transition to fixing."
                        ($lr + 1).ToString() | Out-File -FilePath (Join-Path $rd "retries") -Encoding utf8 -NoNewline
                        & $postMessage -RoomDir $rd -From "manager" -To $dlRole -Type "fix" -Ref $lt -Body "Deadlock recovery: restarting $dlRole."
                        Write-RoomStatus $rd "fixing"
                        # Worker will be started by main loop in next iteration
                    }
                    else {
                        Write-Log "ERROR" "[$lt] Deadlock recovery: max retries exceeded."
                        Write-RoomStatus $rd "failed-final"
                        Set-BlockedDescendants $lt
                    }
                }
                elseif ($ls -eq 'qa-review') {
                    # Let the main loop handle restarting QA if it's dead
                    Write-Log "WARN" "[$lt] Deadlock recovery: QA process not running. Will be restarted by main loop."
                }
                elseif ($ls -eq 'manager-triage') {
                    # Triage is stateless — will re-process on next loop iteration
                    Write-Log "INFO" "[$lt] Deadlock recovery: will re-process manager-triage."
                }
                elseif ($ls -eq 'architect-review') {
                    # Let the main loop handle restarting architect
                    Write-Log "WARN" "[$lt] Deadlock recovery: architect review stalled. Will be restarted by main loop."
                }
            }
            $stallCycles = 0
        }
    }
    else {
        $stallCycles = 0
    }

    # === Release check ===
    if ($roomCount -gt 0 -and $allPassed) {
        Write-Host ""
        Write-Log "INFO" "All $roomCount rooms PASSED! Drafting release..."

        $draftScript = Join-Path $releaseDir "draft.sh"
        $draftOk = $true
        if (Test-Path $draftScript) {
            $draftOut = bash $draftScript $agentsDir 2>&1
            $draftOk = ($LASTEXITCODE -eq 0)
            if (-not $draftOk) { Write-Log "ERROR" "draft.sh failed: $draftOut" }
        }

        Write-Log "INFO" "Collecting signoffs..."
        $signoffScript = Join-Path $releaseDir "signoff.sh"
        $signoffOk = $false
        if ($draftOk -and (Test-Path $signoffScript)) {
            $signoffOut = bash $signoffScript $agentsDir 2>&1
            $signoffOk = ($LASTEXITCODE -eq 0)
            if (-not $signoffOk) { Write-Log "ERROR" "signoff.sh failed: $signoffOut" }
        }
        elseif (-not (Test-Path $signoffScript)) {
            $signoffOk = $true  # No signoff script means auto-approve
        }

        if ($signoffOk) {
            Write-Host ""
            Write-Host "============================================"
            Write-Log "INFO" "RELEASE COMPLETE! Release notes: $agentsDir/RELEASE.md"
            Write-Host "  Release notes: $agentsDir/RELEASE.md"
            Write-Host "============================================"
            Remove-Item $managerPidFile -Force -ErrorAction SilentlyContinue
            break
        }
        else {
            if (-not (Test-Path variable:script:signoffAttempts)) {
                $script:signoffAttempts = 0
            }
            $script:signoffAttempts++
            $maxSignoffAttempts = 3
            if ($script:signoffAttempts -ge $maxSignoffAttempts) {
                Write-Log "WARN" "Signoff rejected $maxSignoffAttempts times. Exiting with release pending manual review."
                Write-Host ""
                Write-Host "============================================"
                Write-Log "INFO" "RELEASE PENDING REVIEW: $agentsDir/RELEASE.md"
                Write-Host "  All rooms passed but signoff was not approved after $maxSignoffAttempts attempts."
                Write-Host "  Review RELEASE.md manually and re-run signoff."
                Write-Host "============================================"
                Remove-Item $managerPidFile -Force -ErrorAction SilentlyContinue
                break
            }
            Write-Log "ERROR" "Signoff failed (attempt $($script:signoffAttempts)/$maxSignoffAttempts). Continuing loop..."
        }
    }

    # === Exit on all-terminal (some failed/blocked) ===
    if ($roomCount -gt 0 -and -not $allPassed -and $allTerminal) {
        Write-Host ""
        $passedRooms = $roomCount - $failedCount
        Write-Log "ERROR" "All rooms terminal: $passedRooms passed, $failedCount failed/blocked. Exiting."
        Write-Log "INFO" "To resume: Start-Plan.ps1 -PlanFile <plan> -Resume"
        Remove-Item $managerPidFile -Force -ErrorAction SilentlyContinue
        break
    }

    # OPT-002: Time-based progress throttle (10s minimum interval)
    $nowEpoch = [int][double]::Parse((Get-Date -UFormat %s))
    if ($roomCount -gt 0 -and ($nowEpoch - $script:lastProgressUpdate) -ge 10) {
        $passedCount = 0
        $failedSummary = 0
        $blockedCount = 0
        Get-ChildItem -Path $WarRoomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue | ForEach-Object {
            $s2 = if (Test-Path (Join-Path $_.FullName "status")) { (Get-Content (Join-Path $_.FullName "status") -Raw).Trim() } else { "" }
            if ($s2 -eq 'passed') { $passedCount++ }
            if ($s2 -eq 'failed-final') { $failedSummary++ }
            if ($s2 -eq 'blocked') { $blockedCount++ }
        }
        Write-Log "INFO" "Progress: $passedCount/$roomCount passed, $failedSummary failed, $blockedCount blocked (iteration $iteration)"

        # Update progress file if available
        if (Test-Path $updateProgress) {
            try { & $updateProgress -WarRoomsDir $WarRoomsDir } catch { }
        }
        $script:lastProgressUpdate = $nowEpoch
    }

    Start-Sleep -Seconds $pollInterval
}

# --- Cleanup on exit ---
if ($script:shuttingDown) {
    Write-Log "INFO" "Shutting down all war-rooms..."
    Get-ChildItem -Path $WarRoomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-RoomProcesses $_.FullName
    }
    Remove-Item $managerPidFile -Force -ErrorAction SilentlyContinue
    Write-Log "INFO" "Shutdown complete."
}
