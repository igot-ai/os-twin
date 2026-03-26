<#
.SYNOPSIS
    Shows status of all war-rooms with optional JSON or live watch mode.

.DESCRIPTION
    Scans the war-rooms directory and displays status, retries, message count,
    active PIDs, goal completion, and last activity for each room.

    Replaces: war-rooms/status.sh

.PARAMETER WarRoomsDir
    Base directory to scan for war-rooms. Default: WARROOMS_DIR env or script dir.
.PARAMETER JsonOutput
    Output as JSON instead of formatted table.
.PARAMETER Watch
    Continuously refresh the display every few seconds.
.PARAMETER WatchInterval
    Seconds between refreshes in watch mode. Default: 3.
.PARAMETER ProjectDir
    Optional project directory (resolves war-rooms from project/.war-rooms).

.EXAMPLE
    ./Get-WarRoomStatus.ps1
    ./Get-WarRoomStatus.ps1 -JsonOutput
    ./Get-WarRoomStatus.ps1 -Watch
#>
[CmdletBinding()]
param(
    [string]$WarRoomsDir = '',
    [switch]$JsonOutput,
    [switch]$Watch,
    [int]$WatchInterval = 3,
    [string]$ProjectDir = ''
)

# --- Resolve war-rooms directory ---
if ($ProjectDir) {
    $WarRoomsDir = Join-Path $ProjectDir ".war-rooms"
}
if (-not $WarRoomsDir) {
    $WarRoomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR }
                   else { $PSScriptRoot }
}

function Get-StatusData {
    param([string]$BaseDir)

    $rooms = @()
    $summary = @{
        total       = 0
        pending     = 0
        engineering = 0
        developing  = 0
        optimize    = 0
        qa_review   = 0
        fixing      = 0
        passed      = 0
        failed      = 0
    }

    $roomDirs = Get-ChildItem -Path $BaseDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue
    foreach ($dir in $roomDirs) {
        $summary.total++
        $roomPath = $dir.FullName

        $status = if (Test-Path (Join-Path $roomPath "status")) {
            (Get-Content (Join-Path $roomPath "status") -Raw).Trim()
        } else { "unknown" }

        $taskRef = if (Test-Path (Join-Path $roomPath "task-ref")) {
            (Get-Content (Join-Path $roomPath "task-ref") -Raw).Trim()
        } else { "N/A" }

        $retries = if (Test-Path (Join-Path $roomPath "retries")) {
            (Get-Content (Join-Path $roomPath "retries") -Raw).Trim()
        } else { "0" }

        # Message count
        $msgCount = 0
        $lastActivity = "N/A"
        $channelFile = Join-Path $roomPath "channel.jsonl"
        if (Test-Path $channelFile) {
            $lines = Get-Content $channelFile | Where-Object { $_.Trim() }
            $msgCount = $lines.Count
            if ($msgCount -gt 0) {
                try {
                    $lastMsg = $lines[-1] | ConvertFrom-Json
                    $lastActivity = $lastMsg.ts
                }
                catch { }
            }
        }

        # Active PIDs
        $activePids = @()
        $pidDir = Join-Path $roomPath "pids"
        if (Test-Path $pidDir) {
            Get-ChildItem -Path $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue | ForEach-Object {
                $pidVal = (Get-Content $_.FullName -Raw).Trim()
                if ($pidVal -match '^\d+$') {
                    try {
                        $proc = Get-Process -Id ([int]$pidVal) -ErrorAction Stop
                        if ($proc) { $activePids += $pidVal }
                    }
                    catch { }
                }
            }
        }
        $pidStr = if ($activePids.Count -gt 0) { $activePids -join ',' } else { '-' }

        # Goal completion (from config.json)
        $goalsMet = 0
        $goalsTotal = 0
        $configFile = Join-Path $roomPath "config.json"
        if (Test-Path $configFile) {
            try {
                $roomConfig = Get-Content $configFile -Raw | ConvertFrom-Json
                $goalsTotal = $roomConfig.goals.definition_of_done.Count
            }
            catch { }
        }
        $goalVerifFile = Join-Path $roomPath "goal-verification.json"
        if (Test-Path $goalVerifFile) {
            try {
                $goalReport = Get-Content $goalVerifFile -Raw | ConvertFrom-Json
                $goalsMet = ($goalReport.goals | Where-Object { $_.status -eq "met" }).Count
            }
            catch { }
        }

        # Count by status
        switch ($status) {
            'pending'      { $summary.pending++ }
            'engineering'  { $summary.engineering++ }
            'developing'   { $summary.developing++ }
            'optimize'     { $summary.optimize++ }
            'qa-review'    { $summary.qa_review++ }
            'review'       { $summary.qa_review++ }
            'fixing'       { $summary.fixing++ }
            'passed'       { $summary.passed++ }
            'failed-final' { $summary.failed++ }
        }

        $rooms += [PSCustomObject]@{
            room_id       = $dir.Name
            task_ref      = $taskRef
            status        = $status
            retries       = [int]$retries
            messages      = $msgCount
            active_pids   = $pidStr
            goals         = "$goalsMet/$goalsTotal"
            last_activity = $lastActivity
        }
    }

    return @{
        rooms   = $rooms
        summary = $summary
    }
}

function Show-FormattedStatus {
    param($Data)

    Write-Host ""
    Write-Host "=== Ostwin War-Room Dashboard ===" -ForegroundColor Cyan
    Write-Host ""

    if ($Data.summary.total -eq 0) {
        Write-Host "  No war-rooms found." -ForegroundColor DarkGray
        Write-Host ""
        return
    }

    # Header
    $fmt = "  {0,-12} {1,-10} {2,-14} {3,-8} {4,-6} {5,-8} {6,-10} {7}"
    Write-Host ($fmt -f "ROOM", "REF", "STATUS", "RETRIES", "MSGS", "GOALS", "PIDS", "LAST ACTIVITY") -ForegroundColor White
    Write-Host ($fmt -f "----", "---", "------", "-------", "----", "-----", "----", "-------------") -ForegroundColor DarkGray

    foreach ($room in $Data.rooms) {
        $statusColor = switch ($room.status) {
            'pending'      { 'DarkGray' }
            'engineering'  { 'Yellow' }
            'developing'   { 'Yellow' }
            'optimize'     { 'DarkYellow' }
            'qa-review'    { 'Cyan' }
            'review'       { 'Cyan' }
            'fixing'       { 'DarkYellow' }
            'passed'       { 'Green' }
            'failed-final' { 'Red' }
            'failed'       { 'Red' }
            'triage'       { 'Magenta' }
            default        { 'White' }
        }

        $line = $fmt -f $room.room_id, $room.task_ref, $room.status, $room.retries, $room.messages, $room.goals, $room.active_pids, $room.last_activity
        Write-Host $line -ForegroundColor $statusColor
    }

    $s = $Data.summary
    $active = $s.engineering + $s.developing + $s.optimize
    Write-Host ""
    Write-Host "  Summary: $($s.total) total | $($s.pending) pending | $active active | $($s.qa_review) review | $($s.fixing) fixing | $($s.passed) passed | $($s.failed) failed" -ForegroundColor White
    Write-Host ""
}

# --- Main execution ---
if ($Watch) {
    while ($true) {
        Clear-Host
        $data = Get-StatusData -BaseDir $WarRoomsDir
        Show-FormattedStatus -Data $data
        Start-Sleep -Seconds $WatchInterval
    }
}
else {
    $data = Get-StatusData -BaseDir $WarRoomsDir

    if ($JsonOutput) {
        $data | ConvertTo-Json -Depth 5
    }
    else {
        Show-FormattedStatus -Data $data
    }
}
