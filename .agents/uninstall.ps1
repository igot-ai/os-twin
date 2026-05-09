<#
.SYNOPSIS
    Agent OS (Ostwin) — Uninstaller (PowerShell port of uninstall.sh)

.DESCRIPTION
    Cleanly removes ostwin from the system.

.PARAMETER Yes
    Non-interactive — remove without prompting.

.PARAMETER Dir
    Remove from custom location (default: ~/.ostwin).
#>
[CmdletBinding()]
param(
    [Alias('y')]
    [switch]$Yes,

    [string]$Dir
)

$ErrorActionPreference = "Stop"

$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
$InstallDir = if ($Dir) { $Dir } else { Join-Path $HomeDir ".ostwin" }
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)

function Stop-InstallProcesses {
    $stopScript = Join-Path $InstallDir ".agents\stop.ps1"
    if (Test-Path $stopScript) {
        Write-Host "  Stopping running Ostwin services..."
        $oldOstwinHome = $env:OSTWIN_HOME
        try {
            $env:OSTWIN_HOME = $InstallDir
            if (Get-Command pwsh -ErrorAction SilentlyContinue) {
                & pwsh -NoProfile -ExecutionPolicy Bypass -File $stopScript -Force -Dir $InstallDir 2>$null
            }
            else {
                & powershell -NoProfile -ExecutionPolicy Bypass -File $stopScript -Force -Dir $InstallDir 2>$null
            }
        }
        catch {
            Write-Warning "  Could not stop all Ostwin services cleanly: $_"
        }
        finally {
            $env:OSTWIN_HOME = $oldOstwinHome
        }
    }

    if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
        try {
            $needle = $InstallDir.ToLowerInvariant()
            $helpers = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
                $cmdLine = if ($_.CommandLine) { $_.CommandLine } else { "" }
                $cmd = $cmdLine.ToLowerInvariant()
                $cmd.Contains($needle) -and (
                    $cmd.Contains("sync-skills.ps1") -or
                    $cmd.Contains("dashboard/api.py") -or
                    $cmd.Contains("dashboard\api.py") -or
                    $cmd.Contains("bot/src/index.ts") -or
                    $cmd.Contains("bot\src\index.ts")
                )
            }
            foreach ($proc in $helpers) {
                try {
                    Write-Host "  Stopping helper process PID $($proc.ProcessId)..."
                    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
                }
                catch { }
            }
        }
        catch {
            Write-Warning "  Could not scan helper processes: $_"
        }
    }
}

Write-Host ""
Write-Host "  Ostwin -- Uninstaller"
Write-Host ""

if (-not (Test-Path $InstallDir -PathType Container)) {
    Write-Host "  Ostwin not found at $InstallDir"
    Write-Host "  Nothing to remove."
    exit 0
}

Write-Host "  Will remove: $InstallDir"
Write-Host ""

if (-not $Yes) {
    $answer = Read-Host "  ? Are you sure? [y/N]"
    if ($answer -notmatch '^[Yy]') {
        Write-Host "  Cancelled."
        exit 0
    }
}

# ─── Remove deepagents-cli if installed via uv ───────────────────────────────

if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "  Removing deepagents-cli from uv tools..."
    & uv tool uninstall deepagents-cli 2>$null
}

# ─── Note about Pester module ────────────────────────────────────────────────

if (Get-Command pwsh -ErrorAction SilentlyContinue) {
    Write-Host "  Note: Pester module left in place (shared PowerShell module)"
}

# ─── Stop running services before deleting files ────────────────────────────

Stop-InstallProcesses

# ─── Remove installation directory ──────────────────────────────────────────

Write-Host "  Removing $InstallDir..."
if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
    & cmd.exe /c "rd /s /q `"$InstallDir`"" 2>&1
    if (Test-Path $InstallDir) {
        Remove-Item -Path $InstallDir -Recurse -Force -ErrorAction Stop
    }
}
else {
    Remove-Item -Path $InstallDir -Recurse -Force -ErrorAction Stop
}
Write-Host "    [OK] Files removed"

# ─── Clean PATH from User environment (Windows) ─────────────────────────────

if ($IsWindows -or ($env:OS -eq "Windows_NT")) {
    # Clean from Windows User PATH
    try {
        $userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
        if ($userPath -and $userPath -match "ostwin") {
            $parts = $userPath -split ";" | Where-Object { $_ -notmatch "ostwin" }
            $newPath = $parts -join ";"
            [System.Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
            Write-Host "    [OK] PATH entry removed from User environment"
        }
    }
    catch {
        Write-Warning "  Could not clean PATH from registry: $_"
    }
}
else {
    # On macOS/Linux, clean shell RC files
    foreach ($rcFile in @(
        (Join-Path $HomeDir ".zshrc"),
        (Join-Path $HomeDir ".bashrc"),
        (Join-Path $HomeDir ".profile"),
        (Join-Path $HomeDir ".config" "fish" "config.fish")
    )) {
        if ((Test-Path $rcFile) -and (Select-String -Path $rcFile -Pattern "ostwin" -Quiet -ErrorAction SilentlyContinue)) {
            Write-Host "  Cleaning $rcFile..."
            $lines = Get-Content $rcFile | Where-Object { $_ -notmatch '# Ostwin CLI' -and $_ -notmatch 'ostwin' }
            $lines | Set-Content -Path $rcFile
            Write-Host "    [OK] PATH entry removed"
        }
    }
}

Write-Host ""
Write-Host "  Uninstall complete."
Write-Host ""
Write-Host "  Note: API keys (GOOGLE_API_KEY, etc.) are not removed."
Write-Host "  Note: Project .agents/ directories are not affected."
Write-Host ""
