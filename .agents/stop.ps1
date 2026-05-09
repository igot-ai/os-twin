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
    [switch]$Force,

    [string]$Dir
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path $PSCommandPath -Parent
$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
$InstallDir = if ($Dir) {
    [System.IO.Path]::GetFullPath($Dir)
}
elseif ($env:OSTWIN_HOME) {
    [System.IO.Path]::GetFullPath($env:OSTWIN_HOME)
}
else {
    [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
}
$AgentsDir = if (Test-Path (Join-Path $InstallDir ".agents")) {
    Join-Path $InstallDir ".agents"
}
else {
    $ScriptDir
}
$ManagerPidFile = Join-Path $AgentsDir "manager.pid"
$DashboardPidFiles = @(
    (Join-Path $InstallDir "dashboard.pid"),
    (Join-Path $AgentsDir "dashboard.pid")
) | Select-Object -Unique
$ChannelPidFiles = @(
    (Join-Path $InstallDir "channels.pid"),
    (Join-Path $AgentsDir "channel.pid")
) | Select-Object -Unique
$WarroomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR } else { Join-Path $AgentsDir "war-rooms" }

# ─── Stop helpers ────────────────────────────────────────────────────────────

function Stop-PidFiles {
    param(
        [Parameter(Mandatory)]
        [string[]]$PidFiles,

        [Parameter(Mandatory)]
        [string]$Name
    )

    foreach ($pidFile in $PidFiles) {
        if (-not (Test-Path $pidFile)) { continue }

        $pidValue = (Get-Content $pidFile -Raw).Trim()
        try {
            $null = Get-Process -Id $pidValue -ErrorAction Stop
            Write-Host "[STOP] Stopping $Name (PID $pidValue)..."

            Stop-Process -Id $pidValue -ErrorAction SilentlyContinue

            for ($i = 0; $i -lt 5; $i++) {
                try { $null = Get-Process -Id $pidValue -ErrorAction Stop; Start-Sleep -Seconds 1 }
                catch { break }
            }

            try {
                $null = Get-Process -Id $pidValue -ErrorAction Stop
                Write-Host "[STOP] $Name still alive, force-killing..."
                Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
            }
            catch { }

            Write-Host "[STOP] $Name stopped."
        }
        catch {
            # Process not running
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

function Stop-Dashboard {
    Stop-PidFiles -PidFiles $DashboardPidFiles -Name "dashboard"
}

function Stop-Channels {
    Stop-PidFiles -PidFiles $ChannelPidFiles -Name "channels"
}

# Register cleanup — always stop dashboard on exit
try {
    # ─── Check for manager PID ────────────────────────────────────────────────

    if (-not (Test-Path $ManagerPidFile)) {
        Write-Host "[STOP] No manager running (no PID file)."
        Stop-Dashboard
        Stop-Channels
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
        Stop-Channels
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
            Stop-Channels
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
    # Dashboard and channels are always stopped on exit
    Stop-Dashboard
    Stop-Channels
}
