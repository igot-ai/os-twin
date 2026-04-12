<#
.SYNOPSIS
    Agent OS — Graceful Shutdown (PowerShell port of stop.sh)

.DESCRIPTION
    Stops the running manager loop, dashboard, and all child agent processes.

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
$DashboardPidFile = Join-Path $AgentsDir "dashboard.pid"
$WarroomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR } else { Join-Path $AgentsDir "war-rooms" }

# ─── Stop Dashboard ──────────────────────────────────────────────────────────

function Stop-Dashboard {
    if (-not (Test-Path $DashboardPidFile)) { return }

    $dashPid = (Get-Content $DashboardPidFile -Raw).Trim()
    try {
        $proc = Get-Process -Id $dashPid -ErrorAction Stop
        Write-Host "[STOP] Stopping dashboard (PID $dashPid)..."

        # Graceful stop attempt
        Stop-Process -Id $dashPid -ErrorAction SilentlyContinue

        # Wait up to 5s for graceful shutdown (tunnel cleanup needs time)
        for ($i = 0; $i -lt 5; $i++) {
            try { $null = Get-Process -Id $dashPid -ErrorAction Stop; Start-Sleep -Seconds 1 }
            catch { break }
        }

        # Force kill if still alive
        try {
            $null = Get-Process -Id $dashPid -ErrorAction Stop
            Write-Host "[STOP] Dashboard still alive, force-killing..."
            Stop-Process -Id $dashPid -Force -ErrorAction SilentlyContinue
        }
        catch { }

        Write-Host "[STOP] Dashboard stopped."
    }
    catch {
        # Process not running
    }
    Remove-Item $DashboardPidFile -Force -ErrorAction SilentlyContinue
}

# Register cleanup — always stop dashboard on exit
try {
    # ─── Check for manager PID ────────────────────────────────────────────────

    if (-not (Test-Path $ManagerPidFile)) {
        Write-Host "[STOP] No manager running (no PID file)."
        Stop-Dashboard
        exit 0
    }

    $managerPid = (Get-Content $ManagerPidFile -Raw).Trim()

    # Check if manager process is alive
    $managerAlive = $false
    try {
        $null = Get-Process -Id $managerPid -ErrorAction Stop
        $managerAlive = $true
    }
    catch { }

    if (-not $managerAlive) {
        Write-Host "[STOP] Manager PID $managerPid not running. Cleaning up PID file."
        Remove-Item $ManagerPidFile -Force -ErrorAction SilentlyContinue
        Stop-Dashboard
        exit 0
    }

    # ─── Graceful shutdown ────────────────────────────────────────────────────

    Write-Host "[STOP] Sending stop signal to manager (PID $managerPid)..."
    Stop-Process -Id $managerPid -ErrorAction SilentlyContinue

    # Wait up to 10 seconds for graceful shutdown
    for ($i = 0; $i -lt 10; $i++) {
        try {
            $null = Get-Process -Id $managerPid -ErrorAction Stop
            Start-Sleep -Seconds 1
        }
        catch {
            Write-Host "[STOP] Manager stopped gracefully."
            Remove-Item $ManagerPidFile -Force -ErrorAction SilentlyContinue
            Stop-Dashboard
            exit 0
        }
    }

    # ─── Force kill if still alive ────────────────────────────────────────────

    $stillAlive = $false
    try { $null = Get-Process -Id $managerPid -ErrorAction Stop; $stillAlive = $true } catch { }

    if ($stillAlive) {
        if ($Force) {
            Write-Host "[STOP] Force-killing manager (PID $managerPid)..."
            Stop-Process -Id $managerPid -Force -ErrorAction SilentlyContinue

            # Kill any remaining agent processes in war-rooms
            if (Test-Path $WarroomsDir) {
                foreach ($pidFile in Get-ChildItem -Path $WarroomsDir -Filter "*.pid" -Recurse -ErrorAction SilentlyContinue) {
                    $agentPid = (Get-Content $pidFile.FullName -Raw).Trim()
                    try { Stop-Process -Id $agentPid -Force -ErrorAction SilentlyContinue } catch { }
                    Remove-Item $pidFile.FullName -Force -ErrorAction SilentlyContinue
                }
            }

            Remove-Item $ManagerPidFile -Force -ErrorAction SilentlyContinue
            Write-Host "[STOP] Force shutdown complete."
        }
        else {
            Write-Error "[STOP] Manager still running after 10s. Use -Force to kill."
            exit 1
        }
    }
}
finally {
    # Dashboard is always stopped on exit
    Stop-Dashboard
}
