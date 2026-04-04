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
$helpersModule = Join-Path $scriptDir "ManagerLoop-Helpers.psm1"
if (Test-Path $logModule) { Import-Module $logModule -Force }
if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }
if (Test-Path $helpersModule) { Import-Module $helpersModule -Force }

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

# --- Inject runtime context into ManagerLoop-Helpers module ---
# All helper functions are defined in ManagerLoop-Helpers.psm1 (imported above).
# Set-ManagerLoopContext binds runtime paths and config so they remain testable.
if (Get-Command Set-ManagerLoopContext -ErrorAction SilentlyContinue) {
    Set-ManagerLoopContext -Context @{
        agentsDir        = $agentsDir
        WarRoomsDir      = $WarRoomsDir
        dagFile          = $dagFile
        hasDag           = $hasDag
        dagCache         = $script:dagCache
        dagMtime         = $script:dagMtime
        config           = $config
        stateTimeout     = $stateTimeout
        maxRetries       = $maxRetries
        postMessage      = $postMessage
        readMessages     = $readMessages
        dashboardBaseUrl = $dashboardBaseUrl
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
                    # Sync config.json assigned_role with the initial state's role
                    $initDef = if ($lifecycle -and $lifecycle.states -and $lifecycle.states.$nextState) { $lifecycle.states.$nextState } else { $null }
                    if ($initDef -and $initDef.role) {
                        $initBaseRole = $initDef.role -replace ':.*$', ''
                        $rcFile = Join-Path $roomDir "config.json"
                        if (Test-Path $rcFile) {
                            $rc = Get-Content $rcFile -Raw | ConvertFrom-Json
                            if ($rc.assignment) {
                                $rc.assignment.assigned_role = $initBaseRole
                                if ($rc.PSObject.Properties['jit_role_id']) { $rc.PSObject.Properties.Remove('jit_role_id') }
                                $rc | ConvertTo-Json -Depth 10 | Out-File -FilePath $rcFile -Encoding utf8
                            }
                        }
                    }
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
                            # Guard: only fire Handle-PlanApproval once per plan
                            $planApprovedFlag = Join-Path $WarRoomsDir ".plan_approved_$($taskRef -replace '[^a-zA-Z0-9-]','')" 
                            if ($taskRef -eq 'PLAN-REVIEW' -and -not (Test-Path $planApprovedFlag)) {
                                Handle-PlanApproval -TaskRef $taskRef
                                "1" | Out-File -FilePath $planApprovedFlag -Encoding utf8 -NoNewline
                            }
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
                                $restartState = if ($lifecycle.initial_state) { $lifecycle.initial_state } else { 'developing' }
                                Write-RoomStatus $roomDir $restartState
                                # LEAK-6 fix: re-resolve role from the restart state, not the timed-out state
                                $restartStateDef = $lifecycle.states.$restartState
                                $restartRole = if ($restartStateDef -and $restartStateDef.role) { $restartStateDef.role } else { $baseRole }
                                $restartBaseRole = $restartRole -replace ':.*$', ''
                                if (Test-Path $resolveRoleScript) {
                                    $restartResolved = & $resolveRoleScript -RoleName $restartRole -AgentsDir $agentsDir -WarRoomsDir $WarRoomsDir
                                    Start-WorkerJob -RoomDir $roomDir -Role $restartBaseRole -Script $restartResolved.Runner -TaskRef $taskRef -SkipLockCheck
                                } else {
                                    Start-WorkerJob -RoomDir $roomDir -Role $restartBaseRole -Script $workerScript -TaskRef $taskRef -SkipLockCheck
                                }
                            } else {
                                Write-RoomStatus $roomDir 'failed-final'
                                Set-BlockedDescendants $taskRef
                            }
                            continue
                        }

                        # PLAN-REVIEW shortcut — check all signal types the architect may post
                        if ($taskRef -eq 'PLAN-REVIEW') {
                            $passCount    = Get-MsgCount $roomDir "pass"
                            $approveCount = Get-MsgCount $roomDir "plan-approve"
                            $doneCount    = Get-MsgCount $roomDir "done"
                            $failCount    = Get-MsgCount $roomDir "fail"
                            $errorCount   = Get-MsgCount $roomDir "error"

                            Write-Log "DEBUG" "[$taskRef] PLAN-REVIEW shortcut: pass=$passCount approve=$approveCount done=$doneCount fail=$failCount error=$errorCount"

                            # Log latest message bodies for debugging
                            if ($passCount -gt 0) {
                                $passBody = Get-LatestBody $roomDir "pass"
                                $passPreview = if ($passBody.Length -gt 200) { $passBody.Substring(0, 200) + '...' } else { $passBody }
                                Write-Log "DEBUG" "[$taskRef] Latest pass body: $passPreview"
                            }
                            if ($failCount -gt 0) {
                                $failBody = Get-LatestBody $roomDir "fail"
                                $failPreview = if ($failBody.Length -gt 200) { $failBody.Substring(0, 200) + '...' } else { $failBody }
                                Write-Log "DEBUG" "[$taskRef] Latest fail body: $failPreview"
                            }
                            if ($doneCount -gt 0) {
                                $doneBody = Get-LatestBody $roomDir "done"
                                $donePreview = if ($doneBody.Length -gt 200) { $doneBody.Substring(0, 200) + '...' } else { $doneBody }
                                Write-Log "DEBUG" "[$taskRef] Latest done body: $donePreview"
                            }
                            if ($errorCount -gt 0) {
                                $errBody = Get-LatestBody $roomDir "error"
                                $errPreview = if ($errBody.Length -gt 200) { $errBody.Substring(0, 200) + '...' } else { $errBody }
                                Write-Log "DEBUG" "[$taskRef] Latest error body: $errPreview"
                            }

                            # Check for approval: pass signal, plan-approve signal, or done with approval keyword
                            $approved = $false
                            if ($passCount -gt 0 -or $approveCount -gt 0) {
                                $approved = $true
                                Write-Log "DEBUG" "[$taskRef] Approved via pass/plan-approve signal"
                            } elseif ($doneCount -gt 0) {
                                $doneBody = Get-LatestBody $roomDir "done"
                                if ($doneBody -match 'plan-approve|signoff|APPROVED|VERDICT:\s*PASS') {
                                    $approved = $true
                                    Write-Log "DEBUG" "[$taskRef] Approved via done body keyword match"
                                } else {
                                    Write-Log "DEBUG" "[$taskRef] done body did NOT match approval keywords"
                                }
                            } else {
                                Write-Log "DEBUG" "[$taskRef] No pass/approve/done signals — shortcut cannot decide"
                            }

                            if ($approved) {
                                $planApprovedFlag = Join-Path $WarRoomsDir ".plan_approved_$($taskRef -replace '[^a-zA-Z0-9-]','')"
                                Write-Log "INFO" "[$taskRef] Plan APPROVED. Transitioning to passed."
                                Write-RoomStatus $roomDir 'passed'
                                if (-not (Test-Path $planApprovedFlag)) {
                                    Handle-PlanApproval -TaskRef $taskRef
                                    "1" | Out-File -FilePath $planApprovedFlag -Encoding utf8 -NoNewline
                                }
                                continue
                            }

                            # Handle architect VERDICT: REJECT via fail signal or done body
                            if ($failCount -gt 0) {
                                $rejectBody = Get-LatestBody $roomDir "fail"
                                Write-Log "WARN" "[$taskRef] Plan REJECTED by architect."
                                & $postMessage -RoomDir $roomDir -From "manager" -To "architect" `
                                               -Type "plan-reject" -Ref $taskRef -Body $rejectBody
                            } elseif ($doneCount -gt 0) {
                                $rejectBody = Get-LatestBody $roomDir "done"
                                if ($rejectBody -match 'VERDICT:\s*REJECT') {
                                    Write-Log "WARN" "[$taskRef] Plan REJECTED by architect."
                                    & $postMessage -RoomDir $roomDir -From "manager" -To "architect" `
                                                   -Type "plan-reject" -Ref $taskRef -Body $rejectBody
                                }
                            }
                        }

                        # Signal detection — lifecycle-driven (derives signals + sender from lifecycle.json)
                        $matchedSignal = Find-LatestSignal -RoomDir $roomDir -Lifecycle $lifecycle -StateName $status

                        if ($matchedSignal) {
                            $transitionDef = $v2StateDef.signals.$matchedSignal
                            $targetState = $transitionDef.target
                            $actions = @()
                            if ($transitionDef.actions) { $actions = @($transitionDef.actions) }

                            Write-Log "INFO" "[$taskRef] V2 signal '$matchedSignal' in '$status' -> '$targetState'."
                            # Resolve the TARGET state's role so post_fix delivers to the fixer,
                            # not the current state's reviewer/worker.
                            $targetDef = $lifecycle.states.$targetState
                            $targetRoleForActions = if ($targetDef -and $targetDef.role) {
                                $targetDef.role -replace ':.*$', ''
                            } else { $baseRole }
                            Invoke-SignalActions -RoomDir $roomDir -Actions $actions -TaskRef $taskRef -BaseRole $targetRoleForActions
                            Write-RoomStatus $roomDir $targetState

                            # Reset crash-respawn counter on successful transition
                            $crashFile = Join-Path $roomDir "crash_respawns"
                            Remove-Item $crashFile -Force -ErrorAction SilentlyContinue

                            # Sync config.json assigned_role with the target state's role
                            $trDef = $lifecycle.states.$targetState
                            if ($trDef -and $trDef.role) {
                                $trBaseRole = $trDef.role -replace ':.*$', ''
                                $rcFile = Join-Path $roomDir "config.json"
                                if (Test-Path $rcFile) {
                                    $rc = Get-Content $rcFile -Raw | ConvertFrom-Json
                                    if ($rc.assignment) {
                                        $rc.assignment.assigned_role = $trBaseRole
                                        if ($rc.PSObject.Properties['jit_role_id']) { $rc.PSObject.Properties.Remove('jit_role_id') }
                                        $rc | ConvertTo-Json -Depth 10 | Out-File -FilePath $rcFile -Encoding utf8
                                    }
                                }
                            }

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
                            if ($stateRole -and $v2StateDef.type -notin @('triage', 'decision')) {
                                $stateBaseRole = $stateRole -replace ':.*$', ''
                                $statePidFile = Join-Path $roomDir "pids" "$stateBaseRole.pid"
                                $pidAlive = Test-PidAlive $statePidFile
                                $spawnLocked = Test-SpawnLock -RoomDir $roomDir -Role $stateBaseRole
                                Write-Log "INFO" "[$taskRef] No signal matched. role='$stateBaseRole' pidAlive=$pidAlive spawnLocked=$spawnLocked status='$status'"
                                if (-not $pidAlive -and -not $spawnLocked) {
                                    # Guard: check if a signal is pending but hasn't been processed yet.
                                    $pendingSignalCheck = Find-LatestSignal -RoomDir $roomDir -Lifecycle $lifecycle -StateName $status
                                    if ($pendingSignalCheck) {
                                        Write-Log "DEBUG" "[$taskRef] Signal '$pendingSignalCheck' pending in '$status' — skipping re-spawn."
                                    } else {
                                        # --- Crash-respawn guard ---
                                        # If the agent keeps dying without posting any signal,
                                        # cap consecutive crash-respawns to prevent infinite loops.
                                        $crashFile = Join-Path $roomDir "crash_respawns"
                                        $crashCount = if (Test-Path $crashFile) { [int](Get-Content $crashFile -Raw).Trim() } else { 0 }
                                        $crashCount++
                                        $maxCrashRespawns = 3
                                        if ($crashCount -gt $maxCrashRespawns) {
                                            Write-Log "ERROR" "[$taskRef] Agent '$stateRole' crashed $crashCount times in '$status' without producing a signal. Marking as failed."
                                            Write-RoomStatus $roomDir "failed"
                                            # Reset the crash counter for the next lifecycle attempt
                                            Remove-Item $crashFile -Force -ErrorAction SilentlyContinue
                                        } else {
                                            $crashCount.ToString() | Out-File -FilePath $crashFile -Encoding utf8 -NoNewline
                                            Write-Log "DEBUG" "[$taskRef] No pending signal, no PID, no lock — will re-spawn '$stateRole' (crash $crashCount/$maxCrashRespawns)."
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

                # Risk 6 fix: Resolve role from lifecycle state, not config.json.
                # Multi-role lifecycles (e.g. reporting.role=reporter) need the state's role.
                $dlLifecycleFile = Join-Path $rd "lifecycle.json"
                $dlLifecycle = if (Test-Path $dlLifecycleFile) { Get-Content $dlLifecycleFile -Raw | ConvertFrom-Json } else { $null }
                $dlStateDef = if ($dlLifecycle -and $dlLifecycle.states -and $dlLifecycle.states.$ls) { $dlLifecycle.states.$ls } else { $null }

                $dlRole = "engineer"
                if ($dlStateDef -and $dlStateDef.role) {
                    $dlRole = ($dlStateDef.role -replace ':.*$', '')
                } else {
                    $dlRoomConfig = Join-Path $rd "config.json"
                    if (Test-Path $dlRoomConfig) {
                        $dlRc = Get-Content $dlRoomConfig -Raw | ConvertFrom-Json
                        if ($dlRc.assignment -and $dlRc.assignment.assigned_role) {
                            $dlRole = $dlRc.assignment.assigned_role -replace ':.*$', ''
                        }
                    }
                }

                if ($dlStateDef -and $dlStateDef.type -in @('work', 'review', 'triage')) {
                    $restartState = if ($dlLifecycle.initial_state) { $dlLifecycle.initial_state } else { 'developing' }

                    # LEAK-7 fix: check for pending signals before deadlock reset
                    $dlPendingSignal = $null
                    if ($dlLifecycle) {
                        $dlPendingSignal = Find-LatestSignal -RoomDir $rd -Lifecycle $dlLifecycle -StateName $ls
                    }
                    if ($dlPendingSignal) {
                        Write-Log "INFO" "[$lt] Deadlock recovery: signal '$dlPendingSignal' pending — skipping reset."
                        return  # Let normal signal detection handle it next iteration
                    }

                    # Risk 2 fix: Clean stale PIDs before transition (prevents double retry increment)
                    Stop-RoomProcesses $rd

                    # Risk 3+4 fix: DO NOT increment retries here.
                    # Retries should only be incremented by lifecycle signal actions (e.g. increment_retries on QA fail).
                    # Incrementing retries during deadlock recovery corrupts the done-count gate (Risk 3)
                    # and compounds into QA cascade deadlocks (Risk 4).
                    # Exhaustion is handled by the deadlock_recoveries cap (line 1113), not by lifecycle retries.

                    # Risk 6 fix: Resolve restart state's role from lifecycle for correct runner
                    $restartStateDef = if ($dlLifecycle.states.$restartState) { $dlLifecycle.states.$restartState } else { $null }
                    $dlRestartRole = if ($restartStateDef -and $restartStateDef.role) { ($restartStateDef.role -replace ':.*$', '') } else { $dlRole }

                    Write-Log "WARN" "[$lt] Deadlock recovery ($($dlCount+1)/3): restarting $dlRestartRole via $restartState."
                    & $postMessage -RoomDir $rd -From "manager" -To $dlRestartRole -Type "fix" -Ref $lt -Body "Deadlock recovery: restarting $dlRestartRole."
                    Write-RoomStatus $rd $restartState

                    # Risk 2 fix: Spawn worker immediately (don't rely on next iteration's respawn branch)
                    $dlResolveRole = Join-Path $agentsDir "roles" "_base" "Resolve-Role.ps1"
                    if (Test-Path $dlResolveRole) {
                        $dlResolved = & $dlResolveRole -RoleName ($restartStateDef.role) -AgentsDir $agentsDir -WarRoomsDir $WarRoomsDir
                        Start-WorkerJob -RoomDir $rd -Role $dlRestartRole -Script $dlResolved.Runner -TaskRef $lt -SkipLockCheck
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
