# ──────────────────────────────────────────────────────────────────────────────
# Setup-Models.ps1 — Model catalog initialization
#
# Provides: Setup-Models
#
# Requires: Lib.ps1, globals: $script:InstallDir, $script:VenvDir
#
# Usage:
#   Setup-Models            # Only fetch if configured_models.json is missing
#   Setup-Models -Force     # Always fetch latest (used on first-time install)
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_SetupModelsPs1Loaded) { return }
$script:_SetupModelsPs1Loaded = $true

function Setup-Models {
    [CmdletBinding()]
    param(
        [switch]$Force
    )

    $configuredModelsPath = Join-Path $script:InstallDir ".agents" "configured_models.json"
    $rawModelsPath = Join-Path $script:InstallDir ".agents" "models_dev_raw.json"
    
    if ((Test-Path $configuredModelsPath) -and -not $Force) {
        Write-Ok "Models catalog already exists at $configuredModelsPath"
        return
    }

    if ($Force) {
        Write-Step "First-time install detected — fetching latest models catalog from models.dev..."
    } else {
        Write-Step "Initializing models catalog from models.dev..."
    }

    # Ensure directories exist
    $parentDir = Split-Path $configuredModelsPath
    if (-not (Test-Path $parentDir)) {
        New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
    }

    # ── Try Python loader first ──────────────────────────────────────────────
    $pyCmd = Join-Path $script:VenvDir "bin" "python.exe"
    if (-not (Test-Path $pyCmd)) {
        $pyCmd = Join-Path $script:VenvDir "Scripts" "python.exe"
    }
    if (-not (Test-Path $pyCmd)) {
        $pyCmd = "python"
    }

    $env:PYTHONPATH = $script:InstallDir
    try {
        $cmd = "& '$pyCmd' -c 'from dashboard.lib.settings.models_dev_loader import load_models_on_startup; load_models_on_startup()'"
        Invoke-Expression $cmd 2>$null
        if (Test-Path $configuredModelsPath) {
            Write-Ok "Models catalog initialized at $configuredModelsPath"
            return
        }
    } catch {
        # Fall through to direct download
    }

    # ── Fallback: direct download ────────────────────────────────────────────
    $modelsDevUrl = "https://models.dev/api.json"
    try {
        Invoke-WebRequest -Uri $modelsDevUrl -OutFile $rawModelsPath -ErrorAction Stop
        
        # Distribute to local locations
        Copy-Item $rawModelsPath $configuredModelsPath -Force
        
        Write-Warn "Models catalog downloaded as raw JSON (Python loader unavailable)"
    } catch {
        Write-Warn "Failed to initialize models catalog — dashboard will fetch it on startup"
    }
}
