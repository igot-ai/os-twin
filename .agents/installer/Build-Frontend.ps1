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

        # Install deps if node_modules missing
        if (-not (Test-Path "node_modules")) {
            Write-Step "Installing npm dependencies..."
            try {
                & $pm install --frozen-lockfile 2>$null
            }
            catch {
                & $pm install
            }
        }

        & $pm run build
        Write-Ok "$Label build complete"
    }
    catch {
        Write-Warn "$Label build failed: $_"
    }
    finally {
        Set-Location $originalDir
    }
}
