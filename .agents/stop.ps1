<#
.SYNOPSIS
    Agent OS — Graceful Shutdown (cross-platform PowerShell)

.DESCRIPTION
    Stops the running manager loop, dashboard, and all child agent processes.
    Uses three strategies in order:
      1. Stop-Process on manager (graceful — it cleans up its own children)
      2. Process-tree kill via recursive child enumeration
      3. Force-kill all tracked PIDs (with -Force)

.PARAMETER Force
    Force-kill processes that don't respond to graceful shutdown.
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path $PSCommandPath -Parent
$AgentsDir = $ScriptDir
$ManagerPidFile = Join-Path $AgentsDir "manager.pid"
$ManagerPgidFile = Join-Path $AgentsDir "manager.pgid"
$DashboardPidFile = Join-Path $AgentsDir "dashboard.pid"
$WarroomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR } else { Join-Path $AgentsDir "war-rooms" }

function Stop-ProcessTree { # Kill a process and all its descendants (depth-first)
    param([int]$TargetPid)
    if ($IsLinux -or $IsMacOS) {
        $childPids = @()
        try { $childPids = (pgrep -P $TargetPid 2>$null) -split "`n" | Where-Object { $_ -match '^\d+$' } } catch { }
        foreach ($cp in $childPids) { Stop-ProcessTree -TargetPid ([int]$cp) }
    } else {
        try {
            Get-CimInstance Win32_Process -Filter "ParentProcessId=$TargetPid" -ErrorAction SilentlyContinue | ForEach-Object {
                Stop-ProcessTree -TargetPid $_.ProcessId
            }
        } catch { }
    }
    try { Stop-Process -Id $TargetPid -Force -ErrorAction SilentlyContinue } catch { }
}

function Stop-Dashboard {
    if (-not (Test-Path $DashboardPidFile)) { return }
    $dashPid = (Get-Content $DashboardPidFile -Raw).Trim()
    if ($dashPid -notmatch '^\d+$') { Remove-Item $DashboardPidFile -Force -ErrorAction SilentlyContinue; return }
    try {
        $null = Get-Process -Id $dashPid -ErrorAction Stop
        Write-Host "[STOP] Stopping dashboard (PID $dashPid)..."
        Stop-Process -Id $dashPid -ErrorAction SilentlyContinue
        for ($i = 0; $i -lt 5; $i++) {
            try { $null = Get-Process -Id $dashPid -ErrorAction Stop; Start-Sleep -Seconds 1 } catch { break }
        }
        try { $null = Get-Process -Id $dashPid -ErrorAction Stop; Write-Host "[STOP] Dashboard still alive, force-killing..."; Stop-Process -Id $dashPid -Force -ErrorAction SilentlyContinue } catch { }
        Write-Host "[STOP] Dashboard stopped."
    } catch { }
    Remove-Item $DashboardPidFile -Force -ErrorAction SilentlyContinue
}

function Stop-AllRoomPids { # Kill every PID recorded in war-room pid files + their trees
    param([switch]$ForceKill)
    if (-not (Test-Path $WarroomsDir)) { return }
    foreach ($pidFile in Get-ChildItem -Path $WarroomsDir -Filter "*.pid" -Recurse -ErrorAction SilentlyContinue) {
        $agentPid = (Get-Content $pidFile.FullName -Raw -ErrorAction SilentlyContinue)
        if ($agentPid) { $agentPid = $agentPid.Trim() }
        if ($agentPid -match '^\d+$') {
            $intPid = [int]$agentPid
            if (Get-Process -Id $intPid -ErrorAction SilentlyContinue) {
                Stop-ProcessTree -TargetPid $intPid
            }
        }
        Remove-Item $pidFile.FullName -Force -ErrorAction SilentlyContinue
    }
    Get-ChildItem -Path $WarroomsDir -Filter "*.spawned_at" -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}

function Remove-PidFiles {
    Remove-Item $ManagerPidFile -Force -ErrorAction SilentlyContinue
    Remove-Item $ManagerPgidFile -Force -ErrorAction SilentlyContinue
}

try {
    if (-not (Test-Path $ManagerPidFile)) {
        Write-Host "[STOP] No manager PID file. Sweeping for orphaned room processes..."
        Stop-AllRoomPids
        Remove-PidFiles
        Stop-Dashboard
        exit 0
    }

    $managerPid = (Get-Content $ManagerPidFile -Raw).Trim()
    $managerAlive = $false
    try { $null = Get-Process -Id $managerPid -ErrorAction Stop; $managerAlive = $true } catch { }

    if (-not $managerAlive) {
        Write-Host "[STOP] Manager PID $managerPid not running. Sweeping orphaned processes..."
        Stop-AllRoomPids
        Remove-PidFiles
        Stop-Dashboard
        exit 0
    }

    # --- Strategy 1: graceful stop (manager cleans up its own children) ---
    Write-Host "[STOP] Sending stop signal to manager (PID $managerPid)..."
    Stop-Process -Id $managerPid -ErrorAction SilentlyContinue

    for ($i = 0; $i -lt 10; $i++) {
        try { $null = Get-Process -Id $managerPid -ErrorAction Stop; Start-Sleep -Seconds 1 }
        catch {
            Write-Host "[STOP] Manager stopped gracefully."
            Stop-AllRoomPids
            Remove-PidFiles
            Stop-Dashboard
            exit 0
        }
    }

    # --- Strategy 2: process-tree kill ---
    Write-Host "[STOP] Manager still alive after 10s. Killing process tree..."
    Stop-ProcessTree -TargetPid ([int]$managerPid)
    Stop-AllRoomPids
    Start-Sleep -Seconds 2

    $stillAlive = $false
    try { $null = Get-Process -Id $managerPid -ErrorAction Stop; $stillAlive = $true } catch { }

    if (-not $stillAlive) {
        Write-Host "[STOP] Process tree killed."
        Remove-PidFiles
        Stop-Dashboard
        exit 0
    }

    # --- Strategy 3: force-kill (requires -Force) ---
    if ($Force) {
        Write-Host "[STOP] Force-killing remaining processes..."
        if (($IsLinux -or $IsMacOS) -and (Test-Path $ManagerPgidFile)) { # PGID group kill on Unix
            $pgid = (Get-Content $ManagerPgidFile -Raw -ErrorAction SilentlyContinue)
            if ($pgid) { $pgid = $pgid.Trim() }
            if ($pgid -match '^\d+$') {
                Write-Host "[STOP]   Killing process group $pgid..."
                bash -c "kill -9 -- -$pgid" 2>$null
            }
        }
        Stop-ProcessTree -TargetPid ([int]$managerPid)
        Stop-AllRoomPids -ForceKill
        try { Stop-Process -Id $managerPid -Force -ErrorAction SilentlyContinue } catch { }
        Remove-PidFiles
        Write-Host "[STOP] Force shutdown complete."
    } else {
        Write-Error "[STOP] Still alive. Use -Force to kill the entire tree."
        exit 1
    }
} finally {
    Stop-Dashboard
}
