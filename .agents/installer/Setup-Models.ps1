# ──────────────────────────────────────────────────────────────────────────────
# Setup-Models.ps1 — Model catalog initialization
#
# Provides: Setup-Models
#
# Requires: Lib.ps1, globals: $script:InstallDir, $script:VenvDir
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_SetupModelsPs1Loaded) { return }
$script:_SetupModelsPs1Loaded = $true

function Setup-Models {
    [CmdletBinding()]
    param()

    $configuredModelsPath = Join-Path $script:InstallDir ".agents" "configured_models.json"
    
    if (Test-Path $configuredModelsPath) {
        Write-Ok "Models catalog already exists at $configuredModelsPath"
        return
    fi

    Write-Step "Initializing models catalog from models.dev..."

    # Ensure we use the venv python
    $pyCmd = Join-Path $script:VenvDir "bin" "python.exe"
    if (-not (Test-Path $pyCmd)) {
        $pyCmd = Join-Path $script:VenvDir "Scripts" "python.exe"
    }
    if (-not (Test-Path $pyCmd)) {
        $pyCmd = "python"
    }

    # Call the dashboard's loader to bootstrap the file.
    # We set PYTHONPATH to include the project root so 'dashboard' is importable.
    $env:PYTHONPATH = $script:InstallDir
    try {
        $cmd = "& '$pyCmd' -c 'from dashboard.lib.settings.models_dev_loader import load_models_on_startup; load_models_on_startup()'"
        Invoke-Expression $cmd 2>$null
        if (Test-Path $configuredModelsPath) {
            Write-Ok "Models catalog initialized at $configuredModelsPath"
            return
        }
    } catch {
        # Fallback to direct download
    }

    # Last-ditch effort: use Invoke-WebRequest to at least get the raw catalog
    $modelsDevUrl = "https://models.dev/api.json"
    $opencodeDir = Join-Path $HOME ".local\share\opencode"
    try {
        if (-not (Test-Path $opencodeDir)) {
            New-Item -ItemType Directory -Path $opencodeDir -Force | Out-Null
        }
        Invoke-WebRequest -Uri $modelsDevUrl -OutFile $configuredModelsPath -ErrorAction Stop
        
        # Feed to both files in both locations
        $projectRawPath = Join-Path (Split-Path $configuredModelsPath) "models_dev_raw.json"
        $opencodeConfigPath = Join-Path $opencodeDir "configured_models.json"
        $opencodeRawPath = Join-Path $opencodeDir "models_dev_raw.json"
        
        Copy-Item $configuredModelsPath $projectRawPath -Force
        Copy-Item $configuredModelsPath $opencodeConfigPath -Force
        Copy-Item $configuredModelsPath $opencodeRawPath -Force
        
        Write-Warn "Models catalog downloaded as raw JSON to multiple locations (Python loader failed)"
    } catch {
        Write-Warn "Failed to initialize models catalog — dashboard will fetch it on startup"
    }
}
