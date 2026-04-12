# ──────────────────────────────────────────────────────────────────────────────
# Setup-Path.ps1 — PATH configuration for Windows
#
# Provides: Setup-Path
#
# Writes to:
#   1. $PROFILE (PowerShell profile) — so new shells see the ostwin bin dir
#   2. User PATH environment variable — so CMD/Explorer/other apps see it too
#
# Requires: Lib.ps1, globals: $script:InstallDir
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_SetupPathPs1Loaded) { return }
$script:_SetupPathPs1Loaded = $true

function Setup-Path {
    [CmdletBinding()]
    param()

    Write-Step "Configuring PATH..."

    $binDir = Join-Path $script:InstallDir ".agents\bin"

    # 1. Add to User PATH environment variable (persistent, works across all shells)
    $currentUserPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
    if ($currentUserPath -and $currentUserPath -like "*$binDir*") {
        Write-Ok "PATH already contains $binDir (User environment)"
    }
    else {
        if ($currentUserPath) {
            $newPath = "$binDir;$currentUserPath"
        }
        else {
            $newPath = $binDir
        }
        [System.Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-Ok "Added $binDir to User PATH environment variable"
    }

    # 2. Add to PowerShell $PROFILE (so 'ostwin' works in new PS sessions)
    $profilePath = $PROFILE
    if ($profilePath) {
        $profileDir = Split-Path $profilePath -Parent
        if (-not (Test-Path $profileDir)) {
            New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
        }

        if (-not (Test-Path $profilePath)) {
            # Create profile if it doesn't exist
            New-Item -ItemType File -Path $profilePath -Force | Out-Null
        }

        $profileContent = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue
        if ($profileContent -and $profileContent -like "*ostwin*") {
            Write-Ok "PATH already configured in `$PROFILE"
        }
        else {
            $pathLine = @"

# Ostwin CLI (Agent OS)
`$env:PATH = "$binDir;`$env:PATH"
"@
            Add-Content -Path $profilePath -Value $pathLine
            Write-Ok "Added to PATH in `$PROFILE ($profilePath)"
        }
    }

    # 3. Export for current session
    if ($env:PATH -notlike "*$binDir*") {
        $env:PATH = "$binDir;$env:PATH"
    }
}
