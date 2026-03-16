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
    [string]$WarRoomsDir = ''
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
$maxQaRetries = 2
$script:lastProgressUpdate = 0
$script:dagCache = $null
$script:dagMtime = $null

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
    # --- Classification: keyword matching ---
    $designKeywords = 'architecture|design|scope|interface|contract|api-design|redesign|structural'
    $planKeywords   = 'specification|acceptance criteria|definition of done|brief|missing requirement|requirements|out of scope'
    if ($QaFeedback -match $designKeywords) {
        return 'design-issue'
    }
    if ($QaFeedback -match $planKeywords) {
        return 'plan-gap'
    }
    # --- Heuristic: repeated failure (same feedback ≥60% word overlap) ---
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

# === MAIN LOOP ===
$iteration = 0
$stallCycles = 0

while (-not $script:shuttingDown) {
    $iteration++

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
        } else { "UNKNOWN" }

        $retries = if (Test-Path (Join-Path $roomDir "retries")) {
            [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
        } else { 0 }

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

                if ((Get-ActiveCount) -lt $maxConcurrent) {
                    Write-Log "INFO" "[$taskRef] Dependencies met. Spawning engineer in $roomId..."
                    Write-RoomStatus $roomDir "engineering"
                    Start-Job -ScriptBlock {
                        param($script, $room)
                        & $script -RoomDir $room
                    } -ArgumentList $startEngineer, $roomDir | Out-Null
                }
            }

            { $_ -in @('engineering', 'fixing') } {
                $allPassed = $false
                $allTerminal = $false
                $totalActive++

                # Check for state timeout
                if (Test-StateTimedOut $roomDir) {
                    Write-Log "ERROR" "[$taskRef] State '$status' timed out after ${stateTimeout}s."
                    Stop-RoomProcesses $roomDir
                    if ($retries -lt $maxRetries) {
                        ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                        & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref $taskRef -Body "Previous attempt timed out after ${stateTimeout}s. Please try again."
                        Write-RoomStatus $roomDir "fixing"
                        Start-Job -ScriptBlock {
                            param($script, $room)
                            & $script -RoomDir $room
                        } -ArgumentList $startEngineer, $roomDir | Out-Null
                    }
                    else {
                        Write-Log "ERROR" "[$taskRef] Max retries exceeded after timeout."
                        Write-RoomStatus $roomDir "failed-final"
                        Set-BlockedDescendants $taskRef
                    }
                    continue
                }

                $doneCount = Get-MsgCount $roomDir "done"
                $expected = $retries + 1

                if ($doneCount -ge $expected) {
                    Write-Log "INFO" "[$taskRef] Engineer done. Routing to QA..."
                    Write-RoomStatus $roomDir "qa-review"
                    Start-Job -ScriptBlock {
                        param($script, $room)
                        & $script -RoomDir $room
                    } -ArgumentList $startQA, $roomDir | Out-Null
                }
                else {
                    # Check if engineer process died
                    $engPidFile = Join-Path $roomDir "pids" "engineer.pid"
                    if ((Test-Path $engPidFile) -and -not (Test-PidAlive $engPidFile)) {
                        $errorCount = Get-MsgCount $roomDir "error"
                        if ($errorCount -gt 0) {
                            $errorBody = Get-LatestBody $roomDir "error"
                            Write-Log "ERROR" "[$taskRef] Engineer error: $errorBody"
                            if ($retries -lt $maxRetries) {
                                Write-Log "INFO" "[$taskRef] Retrying (attempt $($retries + 1)/$maxRetries)..."
                                ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                                & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref $taskRef -Body "Previous attempt failed: $errorBody. Please try again."
                                Write-RoomStatus $roomDir "fixing"
                                Start-Job -ScriptBlock {
                                    param($script, $room)
                                    & $script -RoomDir $room
                                } -ArgumentList $startEngineer, $roomDir | Out-Null
                            }
                            else {
                                Write-Log "ERROR" "[$taskRef] Max retries exceeded. Marking as failed."
                                Write-RoomStatus $roomDir "failed-final"
                                Set-BlockedDescendants $taskRef
                            }
                        }
                        else {
                            $activeWithNoPid++
                        }
                    }
                }
            }

            'qa-review' {
                $allPassed = $false
                $allTerminal = $false
                $totalActive++

                # Check for state timeout
                if (Test-StateTimedOut $roomDir) {
                    Write-Log "ERROR" "[$taskRef] QA review timed out after ${stateTimeout}s."
                    Stop-RoomProcesses $roomDir
                    if ($retries -lt $maxRetries) {
                        ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                        & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref $taskRef -Body "QA review timed out. Please review and fix."
                        Write-RoomStatus $roomDir "fixing"
                        Start-Job -ScriptBlock {
                            param($script, $room)
                            & $script -RoomDir $room
                        } -ArgumentList $startEngineer, $roomDir | Out-Null
                    }
                    else {
                        Write-RoomStatus $roomDir "failed-final"
                    }
                    continue
                }

                $passCount = Get-MsgCount $roomDir "pass"
                if ($passCount -gt 0) {
                    Write-Log "INFO" "[$taskRef] QA PASSED! Room $roomId complete."
                    Write-RoomStatus $roomDir "passed"
                }
                else {
                    # Check for QA escalation first (design/scope issue)
                    $escalateCount = Get-MsgCount $roomDir "escalate"
                    $failCount = Get-MsgCount $roomDir "fail"
                    if ($escalateCount -gt 0 -or $failCount -gt 0) {
                        $feedback = if ($escalateCount -gt 0) {
                            Get-LatestBody $roomDir "escalate"
                        } else {
                            Get-LatestBody $roomDir "fail"
                        }
                        $triggerType = if ($escalateCount -gt 0) { "ESCALATE" } else { "FAIL" }
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
                                Start-Job -ScriptBlock {
                                    param($script, $room)
                                    & $script -RoomDir $room
                                } -ArgumentList $startQA, $roomDir | Out-Null
                            }
                            else {
                                Write-Log "ERROR" "[$taskRef] QA retries exhausted ($maxQaRetries). Marking as failed."
                                Write-RoomStatus $roomDir "failed-final"
                                Set-BlockedDescendants $taskRef
                            }
                        }
                        else {
                            $qaPidFile = Join-Path $roomDir "pids" "qa.pid"
                            if ((Test-Path $qaPidFile) -and -not (Test-PidAlive $qaPidFile)) {
                                Write-Log "WARN" "[$taskRef] QA process died without verdict. Treating as error."
                                & $postMessage -RoomDir $roomDir -From "qa" -To "manager" -Type "error" -Ref $taskRef -Body "QA process terminated without verdict"
                            }
                            else {
                                $activeWithNoPid++
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
                }

                $classification = Invoke-ManagerTriage -RoomDir $roomDir -QaFeedback $feedback
                Write-Log "INFO" "[$taskRef] Triage classification: $classification"

                switch ($classification) {
                    'implementation-bug' {
                        if ($retries -lt $maxRetries) {
                            Write-Log "INFO" "[$taskRef] Implementation bug. Routing fix to engineer (retry $($retries + 1)/$maxRetries)..."
                            ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                            Write-TriageContext -RoomDir $roomDir -Classification $classification -QaFeedback $feedback -ManagerNotes "Classified as implementation bug. Engineer should fix the specific issues."
                            & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref $taskRef -Body $feedback
                            Write-RoomStatus $roomDir "fixing"
                            Start-Job -ScriptBlock {
                                param($script, $room)
                                & $script -RoomDir $room
                            } -ArgumentList $startEngineer, $roomDir | Out-Null
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
                            Start-Job -ScriptBlock {
                                param($script, $room)
                                & $script -RoomDir $room
                            } -ArgumentList $startArchitect, $roomDir | Out-Null
                        } else {
                            Write-Log "WARN" "[$taskRef] Start-Architect.ps1 not found. Falling back to engineer fix."
                            Write-TriageContext -RoomDir $roomDir -Classification $classification -QaFeedback $feedback -ManagerNotes "Design issue detected but architect unavailable. Engineer should attempt redesign."
                            if ($retries -lt $maxRetries) {
                                ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                                & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref $taskRef -Body $feedback
                                Write-RoomStatus $roomDir "fixing"
                                Start-Job -ScriptBlock {
                                    param($script, $room)
                                    & $script -RoomDir $room
                                } -ArgumentList $startEngineer, $roomDir | Out-Null
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
                            Start-Job -ScriptBlock {
                                param($script, $room)
                                & $script -RoomDir $room
                            } -ArgumentList $startArchitect, $roomDir | Out-Null
                        } else {
                            Write-Log "WARN" "[$taskRef] Start-Architect.ps1 not found. Routing to plan-revision directly."
                            Write-RoomStatus $roomDir "plan-revision"
                        }
                    }
                }
            }

            'architect-review' {
                $allPassed = $false
                $allTerminal = $false
                $totalActive++

                # Check for state timeout
                if (Test-StateTimedOut $roomDir) {
                    Write-Log "ERROR" "[$taskRef] Architect review timed out. Falling back to engineer fix."
                    Stop-RoomProcesses $roomDir
                    $feedback = Get-LatestBody $roomDir "fail"
                    if (-not $feedback) { $feedback = Get-LatestBody $roomDir "escalate" }
                    Write-TriageContext -RoomDir $roomDir -Classification 'design-issue' -QaFeedback $feedback -ManagerNotes "Architect review timed out. Engineer should attempt best-effort fix."
                    if ($retries -lt $maxRetries) {
                        ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                        & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref $taskRef -Body $feedback
                        Write-RoomStatus $roomDir "fixing"
                        Start-Job -ScriptBlock {
                            param($script, $room)
                            & $script -RoomDir $room
                        } -ArgumentList $startEngineer, $roomDir | Out-Null
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

                    switch ($recommendation) {
                        'FIX' {
                            Write-Log "INFO" "[$taskRef] Architect says FIX. Routing to engineer with guidance."
                            Write-TriageContext -RoomDir $roomDir -Classification 'design-issue' -QaFeedback $qaFeedback -ArchitectGuidance $guidance -ManagerNotes "Architect reviewed and recommends targeted fix."
                            if ($retries -lt $maxRetries) {
                                ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                                & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref $taskRef -Body $guidance
                                Write-RoomStatus $roomDir "fixing"
                                Start-Job -ScriptBlock {
                                    param($script, $room)
                                    & $script -RoomDir $room
                                } -ArgumentList $startEngineer, $roomDir | Out-Null
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
                                & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref $taskRef -Body $guidance
                                Write-RoomStatus $roomDir "fixing"
                                Start-Job -ScriptBlock {
                                    param($script, $room)
                                    & $script -RoomDir $room
                                } -ArgumentList $startEngineer, $roomDir | Out-Null
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
                    # Check if architect process died
                    $archPidFile = Join-Path $roomDir "pids" "architect.pid"
                    if ((Test-Path $archPidFile) -and -not (Test-PidAlive $archPidFile)) {
                        $archErrorCount = Get-MsgCount $roomDir "error"
                        Write-Log "WARN" "[$taskRef] Architect process died. Falling back to engineer fix."
                        $qaFeedback = Get-LatestBody $roomDir "fail"
                        if (-not $qaFeedback) { $qaFeedback = Get-LatestBody $roomDir "escalate" }
                        Write-TriageContext -RoomDir $roomDir -Classification 'design-issue' -QaFeedback $qaFeedback -ManagerNotes "Architect review failed. Engineer should attempt best-effort fix."
                        if ($retries -lt $maxRetries) {
                            ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                            & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref $taskRef -Body $qaFeedback
                            Write-RoomStatus $roomDir "fixing"
                            Start-Job -ScriptBlock {
                                param($script, $room)
                                & $script -RoomDir $room
                            } -ArgumentList $startEngineer, $roomDir | Out-Null
                        } else {
                            Write-RoomStatus $roomDir "failed-final"
                            Set-BlockedDescendants $taskRef
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

                & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "plan-update" -Ref $taskRef -Body "Brief has been revised. Please re-read brief.md and implement accordingly."
                Write-RoomStatus $roomDir "engineering"
                Start-Job -ScriptBlock {
                    param($script, $room)
                    & $script -RoomDir $room
                } -ArgumentList $startEngineer, $roomDir | Out-Null
            }

            'passed' {
                # Good — this room is done
            }

            'failed-final' {
                $allPassed = $false
                $failedCount++
            }

            'blocked' {
                $allPassed = $false
                $failedCount++  # counts toward terminal
            }

            default {
                Write-Log "WARN" "Unknown status '$status' for $roomId"
                $allPassed = $false
                $allTerminal = $false
            }
        }
    }

    # === Deadlock detection ===
    if ($totalActive -gt 0 -and $activeWithNoPid -eq $totalActive) {
        $stallCycles++
        if ($stallCycles -ge 2) {
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

                if ($ls -in @('engineering', 'fixing')) {
                    if ($lr -lt $maxRetries) {
                        ($lr + 1).ToString() | Out-File -FilePath (Join-Path $rd "retries") -Encoding utf8 -NoNewline
                        & $postMessage -RoomDir $rd -From "manager" -To "engineer" -Type "fix" -Ref $lt -Body "Deadlock recovery: restarting engineer."
                        Write-RoomStatus $rd "fixing"
                        Start-Job -ScriptBlock { param($s, $r); & $s -RoomDir $r } -ArgumentList $startEngineer, $rd | Out-Null
                    }
                    else {
                        Write-RoomStatus $rd "failed-final"
                        Set-BlockedDescendants $lt
                    }
                }
                elseif ($ls -eq 'qa-review') {
                    # Route to manager-triage so manager handles QA failure through normal flow
                    Write-Log "WARN" "[$lt] Deadlock recovery: QA process died. Routing to manager triage."
                    & $postMessage -RoomDir $rd -From "qa" -To "manager" -Type "error" -Ref $lt -Body "QA process terminated without verdict (deadlock recovery)"
                    Write-RoomStatus $rd "manager-triage"
                }
                elseif ($ls -eq 'manager-triage') {
                    # Triage is stateless — will re-process on next loop iteration
                    Write-Log "INFO" "[$lt] Deadlock recovery: will re-process manager-triage."
                }
                elseif ($ls -eq 'architect-review') {
                    Write-Log "WARN" "[$lt] Deadlock recovery: architect review stalled. Falling back to engineer fix."
                    if ($lr -lt $maxRetries) {
                        ($lr + 1).ToString() | Out-File -FilePath (Join-Path $rd "retries") -Encoding utf8 -NoNewline
                        & $postMessage -RoomDir $rd -From "manager" -To "engineer" -Type "fix" -Ref $lt -Body "Architect review stalled during deadlock recovery. Please attempt fix."
                        Write-RoomStatus $rd "fixing"
                        Start-Job -ScriptBlock { param($s, $r); & $s -RoomDir $r } -ArgumentList $startEngineer, $rd | Out-Null
                    } else {
                        Write-RoomStatus $rd "failed-final"
                        Set-BlockedDescendants $lt
                    }
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
