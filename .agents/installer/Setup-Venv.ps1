# ──────────────────────────────────────────────────────────────────────────────
# Setup-Venv.ps1 — Python virtual environment creation and dependency sync
#
# Provides: Setup-Venv
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

    # Always sync requirements — even if the venv was reused.
    # Collect all requirement file paths (unquoted).
    # Quoting for .cmd bat files is done at the point of use, not here,
    # because PowerShell native calls (pip.exe) need raw paths.
    $reqPaths = @()

    $requirements = Join-Path $script:InstallDir ".agents\mcp\requirements.txt"
    if (Test-Path $requirements) { $reqPaths += $requirements }

    $dashReqs = Join-Path $script:InstallDir "dashboard\requirements.txt"
    if (Test-Path $dashReqs) { $reqPaths += $dashReqs }

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

    # Build -r args: raw for PowerShell splatting, quoted for .cmd string
    $reqArgs = @()       # for native pip.exe (PowerShell handles quoting)
    $reqArgsCmd = @()    # for .cmd bat file (needs explicit quotes)
    foreach ($rp in $reqPaths) {
        $reqArgs += @("-r", $rp)
        $reqArgsCmd += @("-r", "`"$rp`"")
    }

    if ($reqPaths.Count -eq 0) {
        Write-Warn "No requirements files found — skipping dependency sync"
    }
    else {
        Write-Step "Syncing all Python dependencies (single resolver pass)..."

        # Windows venv Python path
        $venvPython = Join-Path $script:VenvDir "Scripts\python.exe"

        if (Check-UV) {
            # Use CPU-only PyTorch index to avoid downloading ~2GB GPU builds.
            # Run via bat file to fully isolate uv's console progress output on Windows
            $uvExe = (Get-Command uv).Source
            $uvArgs = @(
                "pip", "install", "--quiet", "--upgrade", "--prerelease=allow",
                "--python", "`"$venvPython`"",
                "--extra-index-url", "https://download.pytorch.org/whl/cpu"
            ) + $reqArgsCmd
            $uvArgStr = $uvArgs -join " "

            $logsDir = Join-Path $script:InstallDir "logs"
            if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
            $uvLog = Join-Path $logsDir "uv-install.log"
            $batFile = Join-Path $logsDir "_uv-install.cmd"
            Set-Content -Path $batFile -Value "@echo off`r`n`"$uvExe`" $uvArgStr >`"$uvLog`" 2>&1" -Encoding ASCII

            $proc = Start-Process -FilePath "cmd.exe" `
                -ArgumentList "/c", "`"$batFile`"" `
                -WindowStyle Hidden -Wait -PassThru

            if ($proc.ExitCode -ne 0) {
                Write-Fail "uv pip install failed (exit $($proc.ExitCode)) — check $uvLog"
                throw "Python dependency installation failed"
            }
        }
        else {
            $venvPip = Join-Path $script:VenvDir "Scripts\pip.exe"
            $pipArgs = @(
                "install", "--quiet", "--upgrade",
                "--extra-index-url", "https://download.pytorch.org/whl/cpu"
            ) + $reqArgs

            & $venvPip @pipArgs
            if ($LASTEXITCODE -ne 0) {
                Write-Fail "pip install failed (exit $LASTEXITCODE)"
                throw "Python dependency installation failed"
            }
        }
        Write-Ok "All Python dependencies up to date"
    }
}
