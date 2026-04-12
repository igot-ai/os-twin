# ──────────────────────────────────────────────────────────────────────────────
# Start-Dashboard.ps1 — Dashboard launch, health check, tunnel detection
#
# Provides: Start-Dashboard, Publish-Skills
#
# Requires: Lib.ps1, Check-Deps.ps1,
#           globals: $script:InstallDir, $script:VenvDir,
#                    $script:DashboardPort, $script:OstwinApiKey
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_StartDashboardPs1Loaded) { return }
$script:_StartDashboardPs1Loaded = $true

function Start-Dashboard {
    [CmdletBinding()]
    param()

    $dashboardApi = Join-Path $script:InstallDir "dashboard\api.py"
    if (-not (Test-Path $dashboardApi)) {
        Write-Warn "Dashboard not found — skipping auto-start"
        Write-Info "Re-run: .\install.ps1 -SourceDir C:\path\to\agent-os"
        return
    }

    # Stop any existing process on the dashboard port
    try {
        $existingProcs = Get-NetTCPConnection -LocalPort $script:DashboardPort -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        if ($existingProcs) {
            Write-Step "Stopping existing process on :$($script:DashboardPort)..."
            foreach ($pid in $existingProcs) {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            }
            Start-Sleep -Seconds 1
        }
    }
    catch {
        # Get-NetTCPConnection may not be available — continue
    }

    # Load .env so the dashboard process inherits API keys
    $envFile = Join-Path $script:InstallDir ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
                [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
            }
        }
    }

    $logsDir = Join-Path $script:InstallDir "logs"
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    }

    Write-Step "Starting dashboard on http://localhost:$($script:DashboardPort)..."

    $venvPython = Join-Path $script:VenvDir "Scripts\python.exe"
    $logFile = Join-Path $logsDir "dashboard.log"

    # Start dashboard via Start-Process -NoNewWindow for PID tracking
    $dashProcess = Start-Process -FilePath $venvPython `
        -ArgumentList "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "$($script:DashboardPort)", "--project-dir", "$($script:InstallDir)" `
        -WorkingDirectory (Join-Path $script:InstallDir "dashboard") `
        -NoNewWindow -PassThru `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError (Join-Path $logsDir "dashboard-error.log")

    $dashPid = $dashProcess.Id
    $pidFile = Join-Path $script:InstallDir "dashboard.pid"
    Set-Content -Path $pidFile -Value $dashPid -NoNewline

    # Read OSTWIN_API_KEY for auth headers
    $script:OstwinApiKey = $env:OSTWIN_API_KEY
    if (-not $script:OstwinApiKey) {
        $script:OstwinApiKey = ""
    }

    # Health-check: poll /api/status up to 60s
    Write-Step "Waiting for dashboard to be healthy (up to 60s)..."
    $dashOk = $false
    for ($i = 1; $i -le 60; $i++) {
        try {
            $headers = @{}
            if ($script:OstwinApiKey) {
                $headers["X-API-Key"] = $script:OstwinApiKey
            }
            $response = Invoke-RestMethod -Uri "http://localhost:$($script:DashboardPort)/api/status" `
                -Headers $headers -TimeoutSec 2 -ErrorAction Stop
            $dashOk = $true
            break
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }

    if ($dashOk) {
        Write-Ok "Dashboard healthy at http://localhost:$($script:DashboardPort) (PID $dashPid)"
        Check-Tunnel
    }
    else {
        Write-Warn "Dashboard did not respond in 60s — check $logFile"
        Write-Info "Start manually: $venvPython -m uvicorn api:app --port $($script:DashboardPort)"
    }
}

function Publish-Skills {
    [CmdletBinding()]
    param()

    Write-Header "9b. Publishing skills to backend"

    $syncScript = Join-Path $script:InstallDir ".agents\sync-skills.sh"
    $syncScriptPs1 = Join-Path $script:InstallDir ".agents\sync-skills.ps1"

    if (Test-Path $syncScriptPs1) {
        $env:OSTWIN_HOME = $script:InstallDir
        $env:DASHBOARD_PORT = $script:DashboardPort
        & pwsh -NoProfile -File $syncScriptPs1 --install-from (Join-Path $script:InstallDir ".agents")
    }
    elseif ((Test-Path $syncScript) -and (Get-Command bash -ErrorAction SilentlyContinue)) {
        $env:OSTWIN_HOME = $script:InstallDir
        $env:DASHBOARD_PORT = $script:DashboardPort
        & bash $syncScript --install-from (Join-Path $script:InstallDir ".agents")
    }
    else {
        Write-Warn "sync-skills script not found — skipping skill sync"
    }
}

# ─── Internal helpers ────────────────────────────────────────────────────────

function Check-Tunnel {
    [CmdletBinding()]
    param()

    $tunnelUrl = ""
    $tunnelError = ""

    try {
        $headers = @{}
        if ($script:OstwinApiKey) {
            $headers["X-API-Key"] = $script:OstwinApiKey
        }
        $tunnelJson = Invoke-RestMethod -Uri "http://localhost:$($script:DashboardPort)/api/tunnel/status" `
            -Headers $headers -TimeoutSec 5 -ErrorAction Stop

        if ($tunnelJson.url) { $tunnelUrl = $tunnelJson.url }
        if ($tunnelJson.error) { $tunnelError = $tunnelJson.error }
    }
    catch { }

    if ($tunnelUrl) {
        Write-Ok "Tunnel active: $tunnelUrl"
        $script:TunnelUrl = $tunnelUrl
    }
    elseif ($tunnelError) {
        Write-Warn "Tunnel failed: $tunnelError"
    }
    elseif (-not $env:NGROK_AUTHTOKEN) {
        Write-Info "Tunnel not configured — set NGROK_AUTHTOKEN in ~\.ostwin\.env to enable port forwarding"
    }
    else {
        Write-Warn "Tunnel not active — check dashboard logs"
    }
}
