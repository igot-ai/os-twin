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
    if (Check-UV) {
        if (Test-Path $script:VenvDir) {
            Write-Ok "venv exists at $($script:VenvDir) (reusing)"
        }
        else {
            & uv venv $script:VenvDir --python 3.12 --quiet
            Write-Ok "venv at $($script:VenvDir) (Python 3.12)"
        }
    }
    else {
        $pyCmd = Check-Python
        if (Test-Path $script:VenvDir) {
            Write-Ok "venv exists at $($script:VenvDir) (reusing)"
        }
        else {
            if ($pyCmd) {
                & $pyCmd -m venv $script:VenvDir
                Write-Ok "venv at $($script:VenvDir)"
            }
            else {
                Write-Fail "No Python found — cannot create venv"
                throw "Python required for venv creation"
            }
        }
    }

    # Always sync requirements — even if the venv was reused.
    # Collect all requirements files that exist
    $reqArgs = @()

    $requirements = Join-Path $script:InstallDir ".agents\mcp\requirements.txt"
    if (Test-Path $requirements) { $reqArgs += @("-r", $requirements) }

    $dashReqs = Join-Path $script:InstallDir "dashboard\requirements.txt"
    if (Test-Path $dashReqs) { $reqArgs += @("-r", $dashReqs) }

    $memReqs = Join-Path $script:InstallDir ".agents\memory\requirements.txt"
    if (Test-Path $memReqs) { $reqArgs += @("-r", $memReqs) }

    # Install role-specific requirements
    $rolesDir = Join-Path $script:InstallDir ".agents\roles"
    if (Test-Path $rolesDir) {
        Get-ChildItem -Path $rolesDir -Directory | ForEach-Object {
            $roleReqs = Join-Path $_.FullName "requirements.txt"
            if (Test-Path $roleReqs) {
                $reqArgs += @("-r", $roleReqs)
            }
        }
    }

    if ($reqArgs.Count -eq 0) {
        Write-Warn "No requirements files found — skipping dependency sync"
    }
    else {
        Write-Step "Syncing all Python dependencies (single resolver pass)..."

        # Windows venv Python path
        $venvPython = Join-Path $script:VenvDir "Scripts\python.exe"

        if (Check-UV) {
            # Use CPU-only PyTorch index to avoid downloading ~2GB GPU builds.
            $uvArgs = @(
                "pip", "install", "--quiet", "--upgrade", "--prerelease=allow",
                "--python", $venvPython,
                "--extra-index-url", "https://download.pytorch.org/whl/cpu"
            ) + $reqArgs

            & uv @uvArgs
        }
        else {
            $venvPip = Join-Path $script:VenvDir "Scripts\pip.exe"
            $pipArgs = @(
                "install", "--quiet", "--upgrade",
                "--extra-index-url", "https://download.pytorch.org/whl/cpu"
            ) + $reqArgs

            & $venvPip @pipArgs
        }
        Write-Ok "All Python dependencies up to date"
    }
}
