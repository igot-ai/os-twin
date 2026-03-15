<#
.SYNOPSIS
    Tears down a war-room: kills processes, optionally archives, then removes.

.DESCRIPTION
    Gracefully shuts down all tracked processes in a war-room, optionally archives
    the channel log and config.json, then removes the room directory.

    Replaces: war-rooms/teardown.sh

.PARAMETER RoomId
    War-room identifier (e.g. room-001).
.PARAMETER Archive
    If set, copies channel.jsonl and config.json to an archive directory before removal.
.PARAMETER Force
    If set, uses SIGKILL immediately instead of graceful SIGTERM.
.PARAMETER WarRoomsDir
    Base directory for war-rooms. Default: WARROOMS_DIR env var or script directory.

.EXAMPLE
    ./Remove-WarRoom.ps1 -RoomId "room-001"
    ./Remove-WarRoom.ps1 -RoomId "room-001" -Archive
    ./Remove-WarRoom.ps1 -RoomId "room-001" -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RoomId,

    [switch]$Archive,
    [switch]$Force,

    [string]$WarRoomsDir = ''
)

# --- Resolve war-rooms directory ---
if (-not $WarRoomsDir) {
    $WarRoomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR }
                   else { $PSScriptRoot }
}

$roomDir = Join-Path $WarRoomsDir $RoomId

if (-not (Test-Path $roomDir)) {
    Write-Error "War-room '$RoomId' not found at $roomDir"
    exit 1
}

Write-Output "[TEARDOWN] Shutting down war-room '$RoomId'..."

# --- 1. Kill all tracked processes ---
$pidDir = Join-Path $roomDir "pids"
if (Test-Path $pidDir) {
    Get-ChildItem -Path $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue | ForEach-Object {
        $pidVal = (Get-Content $_.FullName -Raw).Trim()
        if ($pidVal -match '^\d+$') {
            $processId = [int]$pidVal
            try {
                $proc = Get-Process -Id $processId -ErrorAction Stop
                if ($proc) {
                    Write-Output "  Stopping PID $processId..."
                    if ($Force) {
                        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
                    }
                    else {
                        # Graceful: try SIGTERM equivalent, then force after 2 seconds
                        Stop-Process -Id $processId -ErrorAction SilentlyContinue
                    }
                }
            }
            catch {
                # Process already dead — ignore
            }
        }
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    }
}

# --- 2. Wait briefly for graceful shutdown ---
if (-not $Force) {
    Start-Sleep -Seconds 2

    # Force kill any remaining
    if (Test-Path $pidDir) {
        Get-ChildItem -Path $pidDir -Filter "*.pid" -ErrorAction SilentlyContinue | ForEach-Object {
            $pidVal = (Get-Content $_.FullName -Raw).Trim()
            if ($pidVal -match '^\d+$') {
                try {
                    Stop-Process -Id ([int]$pidVal) -Force -ErrorAction SilentlyContinue
                }
                catch { }
            }
            Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
        }
    }
}

# --- 3. Archive if requested ---
if ($Archive) {
    $archiveDir = Join-Path $WarRoomsDir ".archives"
    New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $archivePrefix = "$RoomId-$timestamp"

    # Archive channel log
    $channelFile = Join-Path $roomDir "channel.jsonl"
    if (Test-Path $channelFile) {
        $archiveFile = Join-Path $archiveDir "$archivePrefix.jsonl"
        Copy-Item $channelFile $archiveFile
        Write-Output "  Archived channel to: $archiveFile"
    }

    # Archive config.json (goal contract)
    $configFile = Join-Path $roomDir "config.json"
    if (Test-Path $configFile) {
        $archiveConfig = Join-Path $archiveDir "$archivePrefix-config.json"
        Copy-Item $configFile $archiveConfig
        Write-Output "  Archived config to: $archiveConfig"
    }

    # Archive goal-verification.json if it exists
    $goalFile = Join-Path $roomDir "goal-verification.json"
    if (Test-Path $goalFile) {
        $archiveGoal = Join-Path $archiveDir "$archivePrefix-goals.json"
        Copy-Item $goalFile $archiveGoal
        Write-Output "  Archived goal report to: $archiveGoal"
    }

    # Archive audit.log if it exists
    $auditFile = Join-Path $roomDir "audit.log"
    if (Test-Path $auditFile) {
        $archiveAudit = Join-Path $archiveDir "$archivePrefix-audit.log"
        Copy-Item $auditFile $archiveAudit
    }
}

# --- 4. Remove room directory ---
Remove-Item $roomDir -Recurse -Force

Write-Output "[TEARDOWN] War-room '$RoomId' removed."
