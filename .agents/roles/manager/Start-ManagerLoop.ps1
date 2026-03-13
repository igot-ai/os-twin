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

# === MAIN LOOP ===
$iteration = 0
$stallCycles = 0

while (-not $script:shuttingDown) {
    $iteration++

    $roomCount = 0
    $allPassed = $true
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
                if ((Get-ActiveCount) -lt $maxConcurrent) {
                    Write-Log "INFO" "[$taskRef] Spawning engineer in $roomId..."
                    Write-RoomStatus $roomDir "engineering"
                    Start-Job -ScriptBlock {
                        param($script, $room)
                        & $script -RoomDir $room
                    } -ArgumentList $startEngineer, $roomDir | Out-Null
                }
            }

            { $_ -in @('engineering', 'fixing') } {
                $allPassed = $false
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
                    $failCount = Get-MsgCount $roomDir "fail"
                    if ($failCount -gt 0) {
                        $feedback = Get-LatestBody $roomDir "fail"
                        if ($retries -lt $maxRetries) {
                            Write-Log "INFO" "[$taskRef] QA FAILED. Routing feedback to engineer (retry $($retries + 1)/$maxRetries)..."
                            ($retries + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -Encoding utf8 -NoNewline
                            & $postMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref $taskRef -Body $feedback
                            Write-RoomStatus $roomDir "fixing"
                            Start-Job -ScriptBlock {
                                param($script, $room)
                                & $script -RoomDir $room
                            } -ArgumentList $startEngineer, $roomDir | Out-Null
                        }
                        else {
                            Write-Log "ERROR" "[$taskRef] Max retries exceeded after QA failure. Marking as failed."
                            Write-RoomStatus $roomDir "failed-final"
                        }
                    }
                    else {
                        # Check for QA error / process death
                        $errorCount = Get-MsgCount $roomDir "error"
                        if ($errorCount -gt 0) {
                            $errorBody = Get-LatestBody $roomDir "error"
                            Write-Log "WARN" "[$taskRef] QA error (verdict parse failure): $errorBody"
                            if ($retries -lt $maxRetries) {
                                Write-Log "INFO" "[$taskRef] Re-running QA review..."
                                Write-RoomStatus $roomDir "qa-review"
                                Start-Job -ScriptBlock {
                                    param($script, $room)
                                    & $script -RoomDir $room
                                } -ArgumentList $startQA, $roomDir | Out-Null
                            }
                            else {
                                Write-RoomStatus $roomDir "failed-final"
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

            'passed' {
                # Good — this room is done
            }

            'failed-final' {
                $allPassed = $false
            }

            default {
                Write-Log "WARN" "Unknown status '$status' for $roomId"
                $allPassed = $false
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

                if ($ls -in @('engineering', 'fixing')) {
                    if ($lr -lt $maxRetries) {
                        ($lr + 1).ToString() | Out-File -FilePath (Join-Path $rd "retries") -Encoding utf8 -NoNewline
                        & $postMessage -RoomDir $rd -From "manager" -To "engineer" -Type "fix" -Ref $lt -Body "Deadlock recovery: restarting engineer."
                        Write-RoomStatus $rd "fixing"
                        Start-Job -ScriptBlock { param($s, $r); & $s -RoomDir $r } -ArgumentList $startEngineer, $rd | Out-Null
                    }
                    else {
                        Write-RoomStatus $rd "failed-final"
                    }
                }
                elseif ($ls -eq 'qa-review') {
                    Write-RoomStatus $rd "qa-review"
                    Start-Job -ScriptBlock { param($s, $r); & $s -RoomDir $r } -ArgumentList $startQA, $rd | Out-Null
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
        if (Test-Path $draftScript) {
            bash $draftScript $agentsDir 2>&1 | Out-Null
        }

        Write-Log "INFO" "Collecting signoffs..."
        $signoffScript = Join-Path $releaseDir "signoff.sh"
        $signoffOk = $false
        if (Test-Path $signoffScript) {
            bash $signoffScript $agentsDir 2>&1 | Out-Null
            $signoffOk = ($LASTEXITCODE -eq 0)
        }
        else {
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
            Write-Log "ERROR" "Signoff failed. Continuing loop..."
        }
    }

    # Status summary every 10 iterations
    if ($iteration % 10 -eq 0 -and $roomCount -gt 0) {
        $passedCount = 0
        $failedCount = 0
        Get-ChildItem -Path $WarRoomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue | ForEach-Object {
            $s2 = if (Test-Path (Join-Path $_.FullName "status")) { (Get-Content (Join-Path $_.FullName "status") -Raw).Trim() } else { "" }
            if ($s2 -eq 'passed') { $passedCount++ }
            if ($s2 -eq 'failed-final') { $failedCount++ }
        }
        Write-Log "INFO" "Progress: $passedCount/$roomCount passed, $failedCount failed (iteration $iteration)"
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
