# ──────────────────────────────────────────────────────────────────────────────
# Setup-Venv.ps1 — Python virtual environment creation and dependency sync
#
# Provides: Setup-Venv
#
# Two-phase dependency strategy (mirrors setup-venv.sh):
#   Phase 1: `uv sync --project dashboard/` — uses pyproject.toml + uv.lock
#   Phase 2: `uv pip install -r` — supplementary reqs (mcp, memory, roles)
#
# Requires: Lib.ps1, Check-Deps.ps1 (Check-UV, Check-Python),
#           globals: $script:InstallDir, $script:VenvDir
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_SetupVenvPs1Loaded) { return }
$script:_SetupVenvPs1Loaded = $true

function Setup-Venv {
    [CmdletBinding()]
    param()

    Write-Step "Setting up Python virtual environment..."

    # Pin to Python 3.12 — some deps lack cp313 wheels
    # Check for valid venv (pyvenv.cfg must exist, not just the directory)
    $venvValid = (Test-Path $script:VenvDir) -and (Test-Path (Join-Path $script:VenvDir "pyvenv.cfg"))

    if (Check-UV) {
        if ($venvValid) {
            Write-Ok "venv exists at $($script:VenvDir) (reusing)"
        }
        else {
            if (Test-Path $script:VenvDir) { & cmd.exe /c "rd /s /q `"$($script:VenvDir)`"" 2>$null }
            & uv venv $script:VenvDir --python 3.12 --quiet 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $script:VenvDir "pyvenv.cfg"))) {
                Write-Fail "Failed to create venv at $($script:VenvDir)"
                throw "uv venv failed (exit code $LASTEXITCODE)"
            }
            Write-Ok "venv at $($script:VenvDir) (Python 3.12)"
        }
    }
    else {
        $pyCmd = Check-Python
        if ($venvValid) {
            Write-Ok "venv exists at $($script:VenvDir) (reusing)"
        }
        else {
            if (Test-Path $script:VenvDir) { & cmd.exe /c "rd /s /q `"$($script:VenvDir)`"" 2>$null }
            if ($pyCmd) {
                & $pyCmd -m venv $script:VenvDir
                if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $script:VenvDir "pyvenv.cfg"))) {
                    Write-Fail "Failed to create venv at $($script:VenvDir)"
                    throw "python -m venv failed (exit code $LASTEXITCODE)"
                }
                Write-Ok "venv at $($script:VenvDir)"
            }
            else {
                Write-Fail "No Python found — cannot create venv"
                throw "Python required for venv creation"
            }
        }
    }

    # ── Phase 1: Dashboard project (uv sync with lockfile) ─────────────────
    # Uses pyproject.toml + uv.lock for reproducible, locked installs.
    # This replaces the old dashboard/requirements.txt approach.
    $dashProject = Join-Path $script:InstallDir "dashboard"
    $dashPyproject = Join-Path $dashProject "pyproject.toml"

    if ((Check-UV) -and (Test-Path $dashPyproject)) {
        Write-Step "Syncing dashboard dependencies (uv sync -> pyproject.toml)..."

        $logsDir = Join-Path $script:InstallDir "logs"
        if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
        $uvLog = Join-Path $logsDir "uv-install.log"

        $uvExe = (Get-Command uv).Source

        # Build uv sync args
        $uvSyncArgs = @(
            "sync",
            "--project", "`"$dashProject`"",
            "--no-install-project"
        )

        # Use the lockfile as-is when present (--frozen skips the resolver entirely,
        # giving fast, reproducible installs). Fall back to plain sync which re-resolves.
        $uvLock = Join-Path $dashProject "uv.lock"
        if (Test-Path $uvLock) {
            $uvSyncArgs += "--frozen"
        }

        # Include dev extras (pytest, ruff, etc.) so tests work out of the box
        $uvSyncArgs += "--all-extras"

        # CPU-only PyTorch to avoid the ~2GB GPU download
        $uvSyncArgs += @("--extra-index-url", "https://download.pytorch.org/whl/cpu")
        $uvSyncArgs += @("--index-strategy", "unsafe-best-match")
        $uvSyncArgs += "--quiet"

        $uvArgStr = $uvSyncArgs -join " "

        # UV_PROJECT_ENVIRONMENT tells uv sync to install into the shared venv
        # instead of creating a project-local .venv inside dashboard/
        $batFile = Join-Path $logsDir "_uv-sync.cmd"
        $batContent = "@echo off`r`nset UV_PROJECT_ENVIRONMENT=$($script:VenvDir)`r`n`"$uvExe`" $uvArgStr >`"$uvLog`" 2>&1"
        [System.IO.File]::WriteAllText($batFile, $batContent, [System.Text.UTF8Encoding]::new($false))

        $proc = Start-Process -FilePath "cmd.exe" `
            -ArgumentList "/c", "`"$batFile`"" `
            -WindowStyle Hidden -Wait -PassThru

        if ($proc.ExitCode -ne 0) {
            Write-Warn "uv sync failed (exit $($proc.ExitCode)) — falling back to pip"
            if (Test-Path $uvLog) {
                Write-Host "--- BEGIN uv-install.log ---" -ForegroundColor Gray
                Get-Content $uvLog | ForEach-Object { Write-Host $_ -ForegroundColor Gray }
                Write-Host "--- END uv-install.log ---" -ForegroundColor Gray
            }
            # Fallback: try uv pip install from pyproject.toml deps directly
            Setup-Venv-PipFallback
        }
        else {
            Write-Ok "Dashboard deps synced from pyproject.toml"
        }
    }
    else {
        # No uv or no pyproject.toml — use pip fallback
        Setup-Venv-PipFallback
    }

    # ── Phase 2: Supplementary requirements (mcp, memory, roles) ───────────
    # These aren't part of the dashboard project, so they stay as pip installs.
    $reqPaths = @()

    $requirements = Join-Path $script:InstallDir ".agents\mcp\requirements.txt"
    if (Test-Path $requirements) { $reqPaths += $requirements }

    # NOTE: dashboard/requirements.txt is intentionally NOT included here.
    # Dashboard deps are handled in Phase 1 via uv sync / pyproject.toml.

    $memReqs = Join-Path $script:InstallDir ".agents\memory\requirements.txt"
    if (Test-Path $memReqs) { $reqPaths += $memReqs }

    # Install role-specific requirements
    $rolesDir = Join-Path $script:InstallDir ".agents\roles"
    if (Test-Path $rolesDir) {
        Get-ChildItem -Path $rolesDir -Directory | ForEach-Object {
            $roleReqs = Join-Path $_.FullName "requirements.txt"
            if (Test-Path $roleReqs) {
                $reqPaths += $roleReqs
            }
        }
    }

    if ($reqPaths.Count -eq 0) {
        Write-Info "No supplementary requirements found — skipping"
    }
    else {
        Write-Step "Installing supplementary Python dependencies (mcp, memory, roles)..."

        # Build -r args
        $reqArgs = @()
        $reqArgsCmd = @()
        foreach ($rp in $reqPaths) {
            $reqArgs += @("-r", $rp)
            $reqArgsCmd += @("-r", "`"$rp`"")
        }

        $venvPython = Get-VenvPython $script:VenvDir

        if (Check-UV) {
            $uvExe = (Get-Command uv).Source
            $uvArgs = @(
                "pip", "install", "--no-progress", "--upgrade", "--prerelease=if-necessary",
                "--python", "`"$venvPython`"",
                "--extra-index-url", "https://download.pytorch.org/whl/cpu"
            ) + $reqArgsCmd
            $uvArgStr = $uvArgs -join " "

            $logsDir = Join-Path $script:InstallDir "logs"
            if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
            $uvLog = Join-Path $logsDir "uv-install.log"
            $batFile = Join-Path $logsDir "_uv-install.cmd"
            $batContent = "@echo off`r`n`"$uvExe`" $uvArgStr >`"$uvLog`" 2>&1"
            [System.IO.File]::WriteAllText($batFile, $batContent, [System.Text.UTF8Encoding]::new($false))

            $proc = Start-Process -FilePath "cmd.exe" `
                -ArgumentList "/c", "`"$batFile`"" `
                -WindowStyle Hidden -Wait -PassThru

            if ($proc.ExitCode -ne 0) {
                Write-Fail "uv pip install failed (exit $($proc.ExitCode))"
                if (Test-Path $uvLog) {
                    Write-Host "--- BEGIN uv-install.log ---" -ForegroundColor Gray
                    Get-Content $uvLog | ForEach-Object { Write-Host $_ -ForegroundColor Gray }
                    Write-Host "--- END uv-install.log ---" -ForegroundColor Gray
                }
                throw "Supplementary dependency installation failed"
            }
        }
        else {
            $venvPip = Get-VenvPip $script:VenvDir
            $pipArgs = @(
                "install", "--quiet", "--upgrade",
                "--extra-index-url", "https://download.pytorch.org/whl/cpu"
            ) + $reqArgs

            & $venvPip @pipArgs
            if ($LASTEXITCODE -ne 0) {
                Write-Fail "pip install failed (exit $LASTEXITCODE)"
                throw "Supplementary dependency installation failed"
            }
        }
        Write-Ok "Supplementary dependencies up to date"
    }
}

# ── Fallback: install dashboard deps via pip when uv sync unavailable ────────
function Setup-Venv-PipFallback {
    [CmdletBinding()]
    param()

    # Try pyproject.toml deps as a pip install, or fall back to requirements.txt
    $dashProject = Join-Path $script:InstallDir "dashboard"
    $dashReqs = Join-Path $dashProject "requirements.txt"
    $dashPyproject = Join-Path $dashProject "pyproject.toml"

    $venvPython = Get-VenvPython $script:VenvDir

    # Prefer installing the project metadata (picks up pyproject.toml deps)
    if (Check-UV) {
        if (Test-Path $dashPyproject) {
            Write-Step "Installing dashboard deps via uv pip (from pyproject.toml)..."
            $uvExe = (Get-Command uv).Source
            $logsDir = Join-Path $script:InstallDir "logs"
            if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
            $uvLog = Join-Path $logsDir "uv-install.log"
            $batFile = Join-Path $logsDir "_uv-pip-fallback.cmd"
            $uvArgStr = "pip install --no-progress --upgrade --prerelease=if-necessary --python `"$venvPython`" --extra-index-url https://download.pytorch.org/whl/cpu `"$dashProject`""
            $batContent = "@echo off`r`n`"$uvExe`" $uvArgStr >`"$uvLog`" 2>&1"
            [System.IO.File]::WriteAllText($batFile, $batContent, [System.Text.UTF8Encoding]::new($false))

            $proc = Start-Process -FilePath "cmd.exe" `
                -ArgumentList "/c", "`"$batFile`"" `
                -WindowStyle Hidden -Wait -PassThru
            if ($proc.ExitCode -eq 0) {
                Write-Ok "Dashboard deps installed (pip fallback)"
                return
            }
            Write-Warn "uv pip install from pyproject.toml failed — trying requirements.txt"
        }
        if (Test-Path $dashReqs) {
            Write-Step "Installing dashboard deps via uv pip (from requirements.txt)..."
            $uvExe = (Get-Command uv).Source
            $logsDir = Join-Path $script:InstallDir "logs"
            if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
            $uvLog = Join-Path $logsDir "uv-install.log"
            $batFile = Join-Path $logsDir "_uv-pip-fallback.cmd"
            $uvArgStr = "pip install --no-progress --upgrade --prerelease=if-necessary --python `"$venvPython`" --extra-index-url https://download.pytorch.org/whl/cpu -r `"$dashReqs`""
            $batContent = "@echo off`r`n`"$uvExe`" $uvArgStr >`"$uvLog`" 2>&1"
            [System.IO.File]::WriteAllText($batFile, $batContent, [System.Text.UTF8Encoding]::new($false))

            $proc = Start-Process -FilePath "cmd.exe" `
                -ArgumentList "/c", "`"$batFile`"" `
                -WindowStyle Hidden -Wait -PassThru
            if ($proc.ExitCode -ne 0) {
                Write-Fail "pip fallback failed"
                throw "Dashboard dependency installation failed"
            }
            Write-Ok "Dashboard deps installed (pip fallback from requirements.txt)"
        }
        else {
            Write-Warn "No dashboard dependency source found — skipping"
        }
    }
    else {
        # No uv at all — use raw pip
        $venvPip = Get-VenvPip $script:VenvDir
        if (Test-Path $dashReqs) {
            Write-Step "Installing dashboard deps via pip (from requirements.txt)..."
            & $venvPip install --quiet --upgrade --extra-index-url https://download.pytorch.org/whl/cpu -r $dashReqs
            if ($LASTEXITCODE -ne 0) {
                Write-Fail "pip install failed"
                throw "Dashboard dependency installation failed"
            }
            Write-Ok "Dashboard deps installed (pip)"
        }
        else {
            Write-Warn "No dashboard requirements.txt found — skipping"
        }
    }
}
