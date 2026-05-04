<#
.SYNOPSIS
    Ostwin — Web Dashboard Launcher (PowerShell port of dashboard.sh)

.DESCRIPTION
    Starts the FastAPI web dashboard for monitoring war-rooms.

.PARAMETER Port
    Server port (default: 3366)

.PARAMETER ProjectDir
    Project to monitor (default: current directory)

.PARAMETER Background
    Run in background (write PID to dashboard.pid)

.PARAMETER Help
    Show help text.
#>
[CmdletBinding()]
param(
    [int]$Port = 3366,

    [string]$ProjectDir = (Get-Location).Path,

    [switch]$Background,

    [Alias('h')]
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Usage: dashboard.ps1 [-Port PORT] [-ProjectDir PATH] [-Background]"
    Write-Host "  -Port PORT         Server port (default: 3366)"
    Write-Host "  -ProjectDir PATH   Project to monitor (default: current directory)"
    Write-Host "  -Background        Run in background (write PID to dashboard.pid)"
    exit 0
}

$ScriptDir = Split-Path $PSCommandPath -Parent
$AgentsDir = $ScriptDir

# ─── Resolve Python ──────────────────────────────────────────────────────────

$PythonCmd = $null
$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }

# Local .venv
$localVenvPy = Join-Path $AgentsDir ".venv" "Scripts" "python.exe"
$localVenvPyUnix = Join-Path $AgentsDir ".venv" "bin" "python"
# Global ostwin venv
$globalVenvPy = Join-Path $HomeDir ".ostwin" ".venv" "Scripts" "python.exe"
$globalVenvPyUnix = Join-Path $HomeDir ".ostwin" ".venv" "bin" "python"

if (Test-Path $localVenvPy) { $PythonCmd = $localVenvPy }
elseif (Test-Path $localVenvPyUnix) { $PythonCmd = $localVenvPyUnix }
elseif (Test-Path $globalVenvPy) { $PythonCmd = $globalVenvPy }
elseif (Test-Path $globalVenvPyUnix) { $PythonCmd = $globalVenvPyUnix }
elseif (Get-Command python3 -ErrorAction SilentlyContinue) { $PythonCmd = "python3" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $PythonCmd = "python" }
else {
    Write-Error "[ERROR] Python not found."
    exit 1
}

# ─── Resolve dashboard directory ─────────────────────────────────────────────

$DashboardDir = ""
$candidateInside = Join-Path $AgentsDir "dashboard"
$candidateSibling = Join-Path (Split-Path $AgentsDir -Parent) "dashboard"

if (Test-Path $candidateInside -PathType Container) {
    $DashboardDir = $candidateInside
}
elseif (Test-Path $candidateSibling -PathType Container) {
    $DashboardDir = $candidateSibling
}

$apiPy = if ($DashboardDir) { Join-Path $DashboardDir "api.py" } else { "" }
if (-not $DashboardDir -or -not (Test-Path $apiPy)) {
    Write-Error "[ERROR] Web dashboard not found."
    Write-Host "  Looked in:" -ForegroundColor Red
    Write-Host "    $candidateInside\api.py"
    Write-Host "    $candidateSibling\api.py"
    Write-Host ""
    Write-Host "  If installed via 'ostwin init', re-run init to copy the dashboard."
    Write-Host "  If running from source, ensure dashboard/api.py exists alongside .agents/."
    exit 1
}

# ─── Check Python dependencies ───────────────────────────────────────────────

$depCheck = & $PythonCmd -c "import fastapi, uvicorn" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "[ERROR] Missing Python dependencies."
    Write-Host "  Install with: pip install fastapi uvicorn"
    exit 1
}

# ─── Resolve project dir to absolute path ────────────────────────────────────

$ProjectDir = (Resolve-Path $ProjectDir -ErrorAction Stop).Path

# ─── Build frontend if source is newer than output ───────────────────────────

$feDir = Join-Path $DashboardDir "fe"
$feOut = Join-Path $feDir "out"
if ((Test-Path $feDir) -and (Test-Path (Join-Path $feDir "package.json"))) {
    $needsBuild = $false
    if (-not (Test-Path $feOut)) {
        $needsBuild = $true
    }
    else {
        $srcFiles = Get-ChildItem -Path (Join-Path $feDir "src") -Recurse -File -ErrorAction SilentlyContinue
        $outTime = (Get-Item $feOut).LastWriteTime
        if ($srcFiles | Where-Object { $_.LastWriteTime -gt $outTime } | Select-Object -First 1) {
            $needsBuild = $true
        }
    }

    if ($needsBuild) {
        Write-Host "[DASHBOARD] Building frontend..."
        Push-Location $feDir
        try {
            & npm install --silent 2>$null
            & npm run build 2>&1
        }
        catch {
            Write-Warning "[WARN] Frontend build failed -- serving with stale assets"
        }
        finally { Pop-Location }
    }
}

# ─── Launch dashboard ────────────────────────────────────────────────────────

$PidFile = Join-Path $AgentsDir "dashboard.pid"

# Set UTF-8 environment for Python on Windows (prevents encoding errors with non-ASCII paths)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

if ($Background) {
    $dashLogDir = Join-Path $HomeDir ".ostwin" "dashboard"
    if (-not (Test-Path $dashLogDir)) { New-Item -ItemType Directory -Path $dashLogDir -Force | Out-Null }

    Write-Host "[DASHBOARD] Starting in background on http://localhost:${Port}"
    Write-Host "  Project: $ProjectDir"

    $stdoutLog = Join-Path $dashLogDir "stdout.log"

    $proc = Start-Process -FilePath $PythonCmd `
        -ArgumentList "api.py", "--port", $Port, "--project-dir", $ProjectDir `
        -WorkingDirectory $DashboardDir `
        -NoNewWindow -PassThru `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError (Join-Path $dashLogDir "stderr.log")

    $proc.Id | Set-Content -Path $PidFile
    Write-Host "  PID: $($proc.Id)"
    Write-Host "  Logs: $dashLogDir\debug.log (debug) | stdout.log (raw)"

    # Check for ngrok tunnel after dashboard starts
    Start-Sleep -Seconds 3
    try {
        $tunnelStatus = Invoke-RestMethod -Uri "http://localhost:${Port}/api/tunnel/status" -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($tunnelStatus.url) {
            Write-Host "  Tunnel: $($tunnelStatus.url)"
        }
    }
    catch { }
}
else {
    Write-Host "[DASHBOARD] Starting web dashboard on http://localhost:${Port}"
    Write-Host "  Project: $ProjectDir"
    Write-Host "  War-rooms: $ProjectDir\.war-rooms"
    Write-Host "  Press Ctrl+C to stop."
    Write-Host ""

    $PID | Set-Content -Path $PidFile

    Push-Location $DashboardDir
    try {
        & $PythonCmd api.py --port $Port --project-dir $ProjectDir
    }
    finally { Pop-Location }
}
