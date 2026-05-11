# ──────────────────────────────────────────────────────────────────────────────
# Orchestrate-Deps.ps1 — Dependency check & install orchestration (step 2)
#
# Provides: Invoke-DependencyOrchestration
#
# This mirrors _orchestrate-deps.sh — handles the branching logic for
# -DashboardOnly vs full install.
#
# Requires: Check-Deps.ps1, Install-Deps.ps1, Lib.ps1,
#           globals: $script:DashboardOnly, $script:AutoYes
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_OrchestrateDepsPs1Loaded) { return }
$script:_OrchestrateDepsPs1Loaded = $true

function Ensure-Pnpm {
    [CmdletBinding()]
    param()

    $targetPnpm = if ($script:PnpmInstallVersion) { $script:PnpmInstallVersion } else { "10.26.0" }
    $script:PnpmExecutable = "pnpm"
    $script:PnpmArguments = @()
    $currentPnpm = $null
    if (Get-Command pnpm -ErrorAction SilentlyContinue) {
        try {
            $currentPnpm = (& pnpm --version 2>$null | Select-Object -First 1).ToString().Trim()
        }
        catch { }
    }

    if ($currentPnpm -and $currentPnpm -eq $targetPnpm) {
        Write-Ok "pnpm $currentPnpm"
        return $true
    }

    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npmCmd) {
        Write-Warn "npm not found — cannot install pinned pnpm $targetPnpm"
        return $false
    }

    if ($currentPnpm) {
        Write-Step "Switching pnpm from $currentPnpm to pinned $targetPnpm..."
    }
    else {
        Write-Step "Installing pnpm $targetPnpm..."
    }

    & npm install -g "pnpm@$targetPnpm" 2>$null | Out-Null

    $resolvedPnpm = $null
    if (Get-Command pnpm -ErrorAction SilentlyContinue) {
        try {
            $resolvedPnpm = (& pnpm --version 2>$null | Select-Object -First 1).ToString().Trim()
        }
        catch { }
    }

    if ($resolvedPnpm -and $resolvedPnpm -eq $targetPnpm) {
        $script:PnpmExecutable = "pnpm"
        $script:PnpmArguments = @()
        Write-Ok "pnpm $resolvedPnpm"
        return $true
    }

    if (Get-Command npx -ErrorAction SilentlyContinue) {
        $script:PnpmExecutable = "npx"
        $script:PnpmArguments = @("-y", "pnpm@$targetPnpm")
        if ($resolvedPnpm) {
            Write-Warn "Pinned pnpm $targetPnpm was requested, but pnpm $resolvedPnpm is still on PATH — using npx fallback"
        }
        else {
            Write-Warn "Pinned pnpm $targetPnpm was requested, but pnpm is not on PATH — using npx fallback"
        }
        return $true
    }

    if ($resolvedPnpm) {
        Write-Warn "Pinned pnpm $targetPnpm was requested, but pnpm $resolvedPnpm is available and npx fallback is unavailable"
    }
    else {
        Write-Warn "Pinned pnpm $targetPnpm was requested, but pnpm is still not available and npx fallback is unavailable"
    }
    return $false
}

function Invoke-DependencyOrchestration {
    [CmdletBinding()]
    param()

    if ($script:DashboardOnly) {
        Write-Header "2. Checking dependencies (dashboard-only — minimal)"

        # PowerShell version (we're already running)
        $psVer = "$($PSVersionTable.PSVersion.Major).$($PSVersionTable.PSVersion.Minor)"
        Write-Ok "PowerShell $psVer"

        # uv
        if (-not (Check-UV)) {
            Install-UV
        }

        # Python
        $script:PythonCmd = Check-Python
        if (-not $script:PythonCmd) {
            Install-Python
            $script:PythonCmd = Check-Python
            if (-not $script:PythonCmd) {
                Write-Fail "Python required for dashboard"
                throw "Python installation failed"
            }
        }
        Write-Ok "Python $($script:PythonVersion) ($($script:PythonCmd))"

        # Node.js
        if (-not (Check-Node)) {
            Install-Node
        }
        if (Check-Node) {
            $nodeVer = (& node --version 2>&1) | Select-Object -First 1
            Write-Ok "Node.js $nodeVer"

            $null = Ensure-Pnpm
            if (-not (Get-Command clawhub -ErrorAction SilentlyContinue)) {
                if (Get-Command npm -ErrorAction SilentlyContinue) {
                    Write-Step "Installing clawhub CLI..."
                    & npm install -g clawhub 2>$null
                }
            }
        }
        else {
            Write-Fail "Node.js required for dashboard"
            throw "Node.js installation failed"
        }
    }
    else {
        Write-Header "2. Checking dependencies"

        # PowerShell version
        $psVer = "$($PSVersionTable.PSVersion.Major).$($PSVersionTable.PSVersion.Minor)"
        Write-Ok "PowerShell $psVer"

        # uv
        if (Check-UV) {
            $uvVer = (& uv --version 2>&1) -replace '[^0-9.]', '' | Select-Object -First 1
            Write-Ok "uv $uvVer"
        }
        else {
            Write-Warn "uv not found"
            if (Ask-User "Install uv? (recommended — fast Python package manager)") {
                Install-UV
            }
            else {
                Write-Info "Skipping uv — will use pip fallback"
            }
        }

        # Python
        $script:PythonCmd = Check-Python
        if ($script:PythonCmd) {
            Write-Ok "Python $($script:PythonVersion) ($($script:PythonCmd))"
        }
        else {
            Write-Warn "Python $($script:MinPythonVersion)+ not found"
            if (Ask-User "Install Python?") {
                Install-Python
                $script:PythonCmd = Check-Python
                if ($script:PythonCmd) {
                    Write-Ok "Python $($script:PythonVersion) installed"
                }
                else {
                    Write-Fail "Python installation failed"
                    throw "Python $($script:MinPythonVersion)+ is required"
                }
            }
            else {
                Write-Fail "Python $($script:MinPythonVersion)+ is required"
                throw "Python is required"
            }
        }

        # opencode
        if (Check-OpenCode) {
            $ocVer = (& opencode --version 2>&1) -replace '[^0-9.]', '' | Select-Object -First 1
            if (-not $ocVer) { $ocVer = "installed" }
            Write-Ok "opencode $ocVer"
        }
        elseif ($script:SkipOptional) {
            Write-Warn "opencode not found (skipped — SkipOptional)"
        }
        else {
            Install-OpenCode
        }

        # Node.js
        if (Check-Node) {
            $nodeVer = (& node --version 2>&1) | Select-Object -First 1
            Write-Ok "Node.js $nodeVer"

            $null = Ensure-Pnpm
            if (-not (Get-Command clawhub -ErrorAction SilentlyContinue)) {
                if (Get-Command npm -ErrorAction SilentlyContinue) {
                    Write-Step "Installing clawhub CLI..."
                    & npm install -g clawhub 2>$null
                }
            }
        }
        else {
            Write-Warn "Node.js not found"
            if (Ask-User "Install Node.js? (required for Dashboard UI)") {
                Install-Node
                if (Check-Node) {
                    $nodeVer = (& node --version 2>&1) | Select-Object -First 1
                    Write-Ok "Node.js $nodeVer installed"

                    $null = Ensure-Pnpm
                    if (-not (Get-Command clawhub -ErrorAction SilentlyContinue)) {
                        if (Get-Command npm -ErrorAction SilentlyContinue) {
                            Write-Step "Installing clawhub CLI..."
                            & npm install -g clawhub 2>$null
                        }
                    }
                }
                else {
                    Write-Warn "Node.js installation failed"
                }
            }
            else {
                Write-Warn "Skipping Node.js — dashboard UI will not be built"
            }
        }
    }
}
