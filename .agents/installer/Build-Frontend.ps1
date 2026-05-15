# ──────────────────────────────────────────────────────────────────────────────
# Build-Frontend.ps1 — Unified frontend build function
#
# Provides: Build-Frontend
#
# Replaces the need for separate build functions with a single parameterized
# function that can build any frontend project.
#
# Requires: Lib.ps1, globals: $script:SourceDir, $script:ScriptDir
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_BuildFrontendPs1Loaded) { return }
$script:_BuildFrontendPs1Loaded = $true

function Build-Frontend {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$SubDir,
        [string]$Label
    )

    if (-not $Label) { $Label = $SubDir }

    # Locate the frontend directory relative to the source repo
    $feDir = ""
    $candidates = @(
        (Join-Path $script:SourceDir $SubDir),
        (Join-Path (Split-Path $script:ScriptDir -Parent) $SubDir),
        (Join-Path $script:ScriptDir $SubDir)
    )

    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c) -and (Test-Path (Join-Path $c "package.json"))) {
            $feDir = (Resolve-Path $c).Path
            break
        }
    }

    if (-not $feDir) {
        Write-Warn "$Label not found — skipping build"
        Write-Info "Expected at $SubDir\package.json"
        return
    }

    # Pick installed package manager (prefer bun for speed)
    $pm = ""
    foreach ($tool in @("bun", "pnpm", "npm", "yarn")) {
        if (Get-Command $tool -ErrorAction SilentlyContinue) {
            $pm = $tool
            break
        }
    }

    if (-not $pm) {
        Write-Warn "No package manager (bun/pnpm/npm/yarn) found — skipping $Label build"
        Write-Info "Install Node.js and a package manager to enable $Label"
        return
    }

    Write-Step "Building $Label ($pm) at $feDir..."
    $originalDir = Get-Location
    try {
        Set-Location $feDir

        # Install deps when node_modules is missing or stale relative to lockfile.
        # Freshness is checked against the lockfile that matches the selected PM so
        # that projects with multiple lockfiles (e.g. both bun.lock and pnpm-lock.yaml)
        # don't produce false staleness signals from the wrong tool's marker file.
        $needsInstall = $false
        if (-not (Test-Path "node_modules")) {
            $needsInstall = $true
        } elseif ($pm -eq "npm") {
            $marker = "node_modules/.package-lock.json"
            $lock   = "package-lock.json"
            $needsInstall = -not (Test-Path $marker) -or
                ((Test-Path $lock) -and (Get-Item $lock).LastWriteTime -gt (Get-Item $marker).LastWriteTime)
        } elseif ($pm -eq "pnpm") {
            $marker = "node_modules/.modules.yaml"
            $lock   = "pnpm-lock.yaml"
            $needsInstall = -not (Test-Path $marker) -or
                ((Test-Path $lock) -and (Get-Item $lock).LastWriteTime -gt (Get-Item $marker).LastWriteTime)
        } elseif ($pm -eq "bun") {
            $lock = if (Test-Path "bun.lockb") { "bun.lockb" } elseif (Test-Path "bun.lock") { "bun.lock" } else { $null }
            if ($lock) {
                $needsInstall = (Get-Item $lock).LastWriteTime -gt (Get-Item "node_modules").LastWriteTime
            } else {
                $needsInstall = $true
            }
        } else {
            # yarn or unknown — always install to be safe
            $needsInstall = $true
        }

        if ($needsInstall) {
            Write-Step "Installing npm dependencies..."
            & $pm install --frozen-lockfile 2>$null
            if ($LASTEXITCODE -ne 0) {
                & $pm install 2>$null
            }
        }

        & $pm run build
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "$Label build failed (exit code $LASTEXITCODE)"
            return
        }
        Write-Ok "$Label build complete"
    }
    catch {
        Write-Warn "$Label build failed: $_"
    }
    finally {
        Set-Location $originalDir
    }
}
