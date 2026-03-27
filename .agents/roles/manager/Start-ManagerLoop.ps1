<#
.SYNOPSIS
    Manager orchestration loop — the brain of Agent OS.

.DESCRIPTION
    Monitors all war-rooms, routes work between engineers and QA,
    handles retries, deadlock detection, state timeouts, and release cycles.
    Runs continuously until all rooms pass or the process is terminated.

    Replaces: roles/manager/loop.sh

    V2 signal-based state-machine per room (lifecycle.json):
        pending → developing → review → passed
                  ↓ error        ↓ fail
                failed → triage → developing (retry)
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
        if ($s -notin @('pending', 'passed', 'failed-final', 'blocked', '')) { $count++ }
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

# === V2 LIFECYCLE HELPERS ===
function Find-LatestSignal {
    param([string]$RoomDir, [string[]]$ExpectedSignals)
    $changedAt = 0
    $changedFile = Join-Path $RoomDir "state_changed_at"
    if (Test-Path $changedFile) {
        $changedAt = [int](Get-Content $changedFile -Raw).Trim()
    }
    foreach ($sigType in $ExpectedSignals) {
        try {
            $msgs = & $readMessages -RoomDir $RoomDir -FilterType $sigType -Last 1 -AsObject
            if ($msgs -and $msgs.Count -gt 0) {
                $latest = $msgs[-1]
                $msgTs = 0
                if ($latest.ts) {
                    if ($latest.ts -match '^\d+$') { $msgTs = [int]$latest.ts }
                    elseif ($latest.ts -match '^\d{4}-') {
                        try { $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s)) } catch { }
                    }
                }
                if ($msgTs -ge $changedAt) { return $sigType }
            }
        } catch { }
    }
    return $null
}

function Invoke-SignalActions {
    param([string]$RoomDir, [string[]]$Actions, [string]$TaskRef, [string]$BaseRole)
    foreach ($action in $Actions) {
        switch ($action) {
            'increment_retries' {
                $retriesFile = Join-Path $RoomDir "retries"
                $r = if (Test-Path $retriesFile) { [int](Get-Content $retriesFile -Raw).Trim() } else { 0 }
                ($r + 1).ToString() | Out-File -FilePath $retriesFile -Encoding utf8 -NoNewline
            }
            'post_fix' {
                $feedback = Get-LatestBody $RoomDir "fail"
                if (-not $feedback) { $feedback = Get-LatestBody $RoomDir "escalate" }
                if (-not $feedback) { $feedback = Get-LatestBody $RoomDir "error" }
                if ($feedback) {
                    & $postMessage -RoomDir $RoomDir -From "manager" -To $BaseRole -Type "fix" -Ref $TaskRef -Body $feedback
                }
            }
            'revise_brief' {
                $briefFile = Join-Path $RoomDir "brief.md"
                $triageFile = Join-Path $RoomDir "artifacts" "triage-context.md"
                if ((Test-Path $briefFile) -and (Test-Path $triageFile)) {
                    $originalBrief = Get-Content $briefFile -Raw
                    $triageContent = Get-Content $triageFile -Raw
                    $updatedBrief = $originalBrief + "`n`n---`n`n## Plan Revision Notes`n`n$triageContent"
                    $updatedBrief | Out-File -FilePath $briefFile -Encoding utf8 -Force
                }
                $qaRetriesFile = Join-Path $RoomDir "qa_retries"
                if (Test-Path $qaRetriesFile) { Remove-Item $qaRetriesFile -Force }
            }
        }
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
            $null = & $buildDagScript -WarRoomsDir $WarRoomsDir
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
                    $nextState = if ($lifecycle -and $lifecycle.initial_state) { $lifecycle.initial_state } else { "developing" }
                    Write-Log "INFO" "[$taskRef] Dependencies met. Transitioning to $nextState in $roomId..."
                    Write-RoomStatus $roomDir $nextState
                    Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                }
            }

            # === V2 SIGNAL-BASED STATE HANDLER ===
            # All non-pending states are handled via lifecycle.json signals
            default {
                $v2StateDef = if ($lifecycle -and $lifecycle.states -and $lifecycle.states.$status) { $lifecycle.states.$status } else { $null }
                $v2MaxRetries = if ($lifecycle -and $lifecycle.max_retries) { $lifecycle.max_retries } else { $maxRetries }

                if (-not $v2StateDef) {
                    # Unknown state with no lifecycle definition
                    Write-Log "WARN" "[$taskRef] Unknown state '$status' in $roomId (no lifecycle definition)"
                    $allPassed = $false; $allTerminal = $false
                    continue
                }

                switch ($v2StateDef.type) {
                    'terminal' {
                        if ($status -eq 'passed') {
                            Handle-PlanApproval -TaskRef $taskRef
                        } elseif ($status -eq 'failed-final') {
                            if ($retries -lt $v2MaxRetries) {
                                $failFeedback = Get-LatestBody $roomDir "fail"
                                if (-not $failFeedback) { $failFeedback = Get-LatestBody $roomDir "error" }
                                if ($failFeedback) {
                                    Write-Log "WARN" "[$taskRef] failed-final with retries=$retries < max=$v2MaxRetries. Rescuing to triage."
                                    Write-RoomStatus $roomDir "triage"
                                    $allPassed = $false; $allTerminal = $false
                                } else {
                                    $allPassed = $false; $failedCount++
                                }
                            } else {
                                $allPassed = $false; $failedCount++
                            }
                            Set-BlockedDescendants $taskRef
                        } else {
                            # blocked or other terminal
                            $allPassed = $false; $failedCount++
                        }
                    }
                    'decision' {
                        $allPassed = $false; $allTerminal = $false; $totalActive++
                        if ($retries -lt $v2MaxRetries) {
                            Write-Log "INFO" "[$taskRef] Decision: retries ($retries) < max ($v2MaxRetries). Retrying."
                            Write-RoomStatus $roomDir $v2StateDef.signals.retry.target
                        } else {
                            Write-Log "ERROR" "[$taskRef] Decision: retries exhausted. Failing."
                            Write-RoomStatus $roomDir $v2StateDef.signals.exhaust.target
                            Set-BlockedDescendants $taskRef
                        }
                    }
                    { $_ -in @('work', 'review', 'triage') } {
                        $allPassed = $false; $allTerminal = $false; $totalActive++

                        # PID tracking for deadlock detection
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

                        # State timeout
                        if (Test-StateTimedOut $roomDir) {
                            Write-Log "ERROR" "[$taskRef] V2 state '$status' timed out after ${stateTimeout}s."
                            Stop-RoomProcesses $roomDir
                            if ($retries -lt $v2MaxRetries) {
                                ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                                & $postMessage -RoomDir $roomDir -From "manager" -To $baseRole -Type "fix" -Ref $taskRef -Body "State '$status' timed out. Please try again."
                                Write-RoomStatus $roomDir ($lifecycle.initial_state)
                                Start-WorkerJob -RoomDir $roomDir -Role $baseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                            } else {
                                Write-RoomStatus $roomDir 'failed-final'
                                Set-BlockedDescendants $taskRef
                            }
                            continue
                        }

                        # PLAN-REVIEW shortcut
                        if ($taskRef -eq 'PLAN-REVIEW') {
                            $approveCount = Get-MsgCount $roomDir "plan-approve"
                            $doneCount = Get-MsgCount $roomDir "done"
                            $doneApproval = $false
                            if ($doneCount -gt 0 -and $approveCount -eq 0) {
                                $doneBody = Get-LatestBody $roomDir "done"
                                if ($doneBody -match 'plan-approve|signoff|APPROVED') { $doneApproval = $true }
                            }
                            if ($approveCount -gt 0 -or $doneApproval) {
                                Write-Log "INFO" "[$taskRef] Plan APPROVED. Transitioning to passed."
                                Write-RoomStatus $roomDir 'passed'
                                Handle-PlanApproval -TaskRef $taskRef
                                continue
                            }
                        }

                        # Signal detection
                        $expectedSignals = @($v2StateDef.signals.PSObject.Properties.Name)
                        $matchedSignal = Find-LatestSignal $roomDir $expectedSignals

                        if ($matchedSignal) {
                            $transitionDef = $v2StateDef.signals.$matchedSignal
                            $targetState = $transitionDef.target
                            $actions = @()
                            if ($transitionDef.actions) { $actions = @($transitionDef.actions) }

                            Write-Log "INFO" "[$taskRef] V2 signal '$matchedSignal' in '$status' -> '$targetState'."
                            Invoke-SignalActions -RoomDir $roomDir -Actions $actions -TaskRef $taskRef -BaseRole $baseRole
                            Write-RoomStatus $roomDir $targetState

                            # Spawn target state's role agent
                            $targetDef = $lifecycle.states.$targetState
                            if ($targetDef -and $targetDef.role -and $targetDef.type -in @('work', 'review')) {
                                $targetRole = $targetDef.role
                                $targetBaseRole = $targetRole -replace ':.*$', ''
                                if (Test-Path $resolveRoleScript) {
                                    $targetResolved = & $resolveRoleScript -RoleName $targetRole -AgentsDir $agentsDir -WarRoomsDir $WarRoomsDir
                                    Start-WorkerJob -RoomDir $roomDir -Role $targetBaseRole -Script $targetResolved.Runner -TaskRef $taskRef -SkipLockCheck
                                } else {
                                    Start-WorkerJob -RoomDir $roomDir -Role $targetBaseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                                }
                            }
                        }
                        else {
                            # No signal — ensure worker/reviewer is alive
                            $stateRole = $v2StateDef.role
                            if ($stateRole -and $v2StateDef.type -ne 'triage') {
                                $stateBaseRole = $stateRole -replace ':.*$', ''
                                $statePidFile = Join-Path $roomDir "pids" "$stateBaseRole.pid"
                                if (-not (Test-PidAlive $statePidFile) -and -not (Test-SpawnLock -RoomDir $roomDir -Role $stateBaseRole)) {
                                    if (Test-Path $resolveRoleScript) {
                                        $stateResolved = & $resolveRoleScript -RoleName $stateRole -AgentsDir $agentsDir -WarRoomsDir $WarRoomsDir
                                        Write-Log "INFO" "[$taskRef] Spawning '$stateRole' for '$status'."
                                        Start-WorkerJob -RoomDir $roomDir -Role $stateBaseRole -Script $stateResolved.Runner -TaskRef $taskRef
                                    } else {
                                        Start-WorkerJob -RoomDir $roomDir -Role $stateBaseRole -Script $workerScript -TaskRef $taskRef
                                    }
                                }
                            }
                        }
                    }
                    default {
                        Write-Log "WARN" "[$taskRef] Unknown lifecycle type '$($v2StateDef.type)' for state '$status'"
                        $allPassed = $false; $allTerminal = $false
                    }
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

                # --- Skip rooms in terminal states (already completed or failed) ---
                if ($ls -in @('passed', 'failed-final', 'blocked', '')) {
                    return  # ForEach-Object: skip this room
                }

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

                # V2 lifecycle: use lifecycle.json to determine recovery
                $dlLifecycleFile = Join-Path $rd "lifecycle.json"
                $dlLifecycle = if (Test-Path $dlLifecycleFile) { Get-Content $dlLifecycleFile -Raw | ConvertFrom-Json } else { $null }
                $dlStateDef = if ($dlLifecycle -and $dlLifecycle.states -and $dlLifecycle.states.$ls) { $dlLifecycle.states.$ls } else { $null }

                if ($dlStateDef -and $dlStateDef.type -in @('work', 'review', 'triage')) {
                    $dlMaxRetries = if ($dlLifecycle.max_retries) { $dlLifecycle.max_retries } else { $maxRetries }
                    $restartState = if ($dlLifecycle.initial_state) { $dlLifecycle.initial_state } else { 'developing' }
                    if ($lr -lt $dlMaxRetries) {
                        Write-Log "WARN" "[$lt] Deadlock recovery: restarting $dlRole via transition to $restartState."
                        ($lr + 1).ToString() | Out-File -FilePath (Join-Path $rd "retries") -Encoding utf8 -NoNewline
                        & $postMessage -RoomDir $rd -From "manager" -To $dlRole -Type "fix" -Ref $lt -Body "Deadlock recovery: restarting $dlRole."
                        Write-RoomStatus $rd $restartState
                    } else {
                        Write-Log "ERROR" "[$lt] Deadlock recovery: max retries exceeded."
                        Write-RoomStatus $rd "failed-final"
                        Set-BlockedDescendants $lt
                    }
                } else {
                    Write-Log "WARN" "[$lt] Deadlock recovery: state '$ls' not recoverable. Skipping."
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
