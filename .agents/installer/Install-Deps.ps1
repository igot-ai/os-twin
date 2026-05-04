# ──────────────────────────────────────────────────────────────────────────────
# Install-Deps.ps1 — Dependency installers (Windows-specific)
#
# Provides: Install-UV, Install-Python, Install-Pwsh, Install-Node,
#           Install-OpenCode, Install-Pester
#
# Requires: Lib.ps1, Versions.ps1, Detect-OS.ps1 ($script:PkgMgr, $script:ARCH),
#           Check-Deps.ps1 (Check-UV, Check-OpenCode)
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_InstallDepsPs1Loaded) { return }
$script:_InstallDepsPs1Loaded = $true

# ─── uv ──────────────────────────────────────────────────────────────────────

function Install-UV {
    [CmdletBinding()]
    param()

    Write-Step "Installing uv (fast Python package manager)..."

    try {
        # Official uv installer for Windows
        $installScript = Invoke-RestMethod "https://astral.sh/uv/install.ps1"
        Invoke-Expression $installScript
    }
    catch {
        # Fallback: winget or direct download
        if ($script:PkgMgr -eq "winget") {
            & winget install --id astral-sh.uv --accept-package-agreements --accept-source-agreements 2>$null
        }
        elseif ($script:PkgMgr -eq "choco") {
            & choco install uv -y 2>$null
        }
        elseif ($script:PkgMgr -eq "scoop") {
            & scoop install uv 2>$null
        }
        else {
            Write-Fail "Cannot install uv: no supported method available"
            throw "uv installation failed"
        }
    }

    # Refresh PATH for current session
    $uvPaths = @(
        "$env:USERPROFILE\.local\bin",
        "$env:USERPROFILE\.cargo\bin",
        "$env:LOCALAPPDATA\uv"
    )
    foreach ($p in $uvPaths) {
        if ((Test-Path $p) -and $env:PATH -notlike "*$p*") {
            $env:PATH = "$p;$env:PATH"
        }
    }

    if (Check-UV) {
        $uvVer = (& uv --version 2>&1) -replace '[^0-9.]', '' | Select-Object -First 1
        Write-Ok "uv $uvVer installed"
    }
    else {
        Write-Fail "uv installation failed"
        throw "uv installation failed"
    }
}

# ─── Python ──────────────────────────────────────────────────────────────────

function Install-Python {
    [CmdletBinding()]
    param()

    $pyVer = $script:PythonInstallVersion
    if (-not $pyVer) { $pyVer = "3.12" }

    # Preferred: uv (manages its own Python installs)
    if (Check-UV) {
        Write-Step "Installing Python $pyVer via uv..."
        & uv python install $pyVer
        return
    }

    switch ($script:PkgMgr) {
        "winget" {
            Write-Step "Installing Python $pyVer via winget..."
            & winget install --id Python.Python.$([int][double]$pyVer) --accept-package-agreements --accept-source-agreements
        }
        "choco" {
            Write-Step "Installing Python $pyVer via Chocolatey..."
            & choco install python --version=$pyVer -y
        }
        "scoop" {
            Write-Step "Installing Python $pyVer via Scoop..."
            & scoop install python
        }
        default {
            # Direct download from python.org
            Write-Step "Installing Python $pyVer via direct download..."
            $archSuffix = if ($script:ARCH -eq "arm64") { "-arm64" } else { "-amd64" }
            $installerUrl = "https://www.python.org/ftp/python/${pyVer}.0/python-${pyVer}.0${archSuffix}.exe"
            $installerPath = "$env:TEMP\python-installer.exe"

            Write-Step "Downloading from $installerUrl..."
            Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing

            Write-Step "Running installer (quiet mode)..."
            Start-Process -FilePath $installerPath -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1" -Wait -NoNewWindow
            Remove-Item $installerPath -ErrorAction SilentlyContinue

            # Refresh PATH
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
        }
    }
}

# ─── PowerShell 7+ ──────────────────────────────────────────────────────────

function Install-Pwsh {
    [CmdletBinding()]
    param()

    $pwshVer = $script:PwshInstallVersion
    if (-not $pwshVer) { $pwshVer = "7.4.7" }

    switch ($script:PkgMgr) {
        "winget" {
            Write-Step "Installing PowerShell $pwshVer via winget..."
            & winget install --id Microsoft.PowerShell --accept-package-agreements --accept-source-agreements
        }
        "choco" {
            Write-Step "Installing PowerShell $pwshVer via Chocolatey..."
            & choco install powershell-core -y
        }
        default {
            # Direct MSI install from GitHub
            Write-Step "Installing PowerShell $pwshVer via direct download..."
            $archSuffix = switch ($script:ARCH) {
                "arm64" { "win-arm64" }
                "x64"   { "win-x64" }
                default { "win-x64" }
            }
            $msiUrl = "https://github.com/PowerShell/PowerShell/releases/download/v${pwshVer}/PowerShell-${pwshVer}-${archSuffix}.msi"
            $msiPath = "$env:TEMP\PowerShell-installer.msi"

            Write-Step "Downloading from $msiUrl..."
            Invoke-WebRequest -Uri $msiUrl -OutFile $msiPath -UseBasicParsing

            Write-Step "Running MSI installer..."
            Start-Process msiexec.exe -ArgumentList "/i", $msiPath, "/quiet", "/norestart" -Wait -NoNewWindow
            Remove-Item $msiPath -ErrorAction SilentlyContinue
            Write-Ok "PowerShell $pwshVer installed"
        }
    }
}

# ─── Node.js ─────────────────────────────────────────────────────────────────

function Install-Node {
    [CmdletBinding()]
    param()

    $nodeVer = $script:NodeVersion
    if (-not $nodeVer) { $nodeVer = "v25.8.1" }
    # Strip the leading 'v' for download URL
    $nodeVerClean = $nodeVer -replace '^v', ''

    switch ($script:PkgMgr) {
        "winget" {
            Write-Step "Installing Node.js via winget..."
            & winget install --id OpenJS.NodeJS --accept-package-agreements --accept-source-agreements
        }
        "choco" {
            Write-Step "Installing Node.js via Chocolatey..."
            & choco install nodejs -y
        }
        "scoop" {
            Write-Step "Installing Node.js via Scoop..."
            & scoop install nodejs
        }
        default {
            Write-Step "Installing Node.js $nodeVer via direct download..."
            $archSuffix = switch ($script:ARCH) {
                "arm64" { "arm64" }
                "x64"   { "x64" }
                default { "x64" }
            }
            $zipUrl = "https://nodejs.org/dist/${nodeVer}/node-${nodeVer}-win-${archSuffix}.zip"
            $zipPath = "$env:TEMP\node.zip"
            $nodeDir = "$env:LOCALAPPDATA\node"

            Write-Step "Downloading from $zipUrl..."
            Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing

            if (Test-Path $nodeDir) { Remove-Item $nodeDir -Recurse -Force }
            New-Item -ItemType Directory -Path $nodeDir -Force | Out-Null

            Write-Step "Extracting Node.js..."
            Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
            $extracted = Join-Path $env:TEMP "node-${nodeVer}-win-${archSuffix}"
            Copy-Item -Path "$extracted\*" -Destination $nodeDir -Recurse -Force
            Remove-Item $zipPath -ErrorAction SilentlyContinue
            Remove-Item $extracted -Recurse -ErrorAction SilentlyContinue

            # Add to PATH for current session
            if ($env:PATH -notlike "*$nodeDir*") {
                $env:PATH = "$nodeDir;$env:PATH"
            }
            Write-Ok "Node.js $nodeVer installed to $nodeDir"
        }
    }

    # Refresh PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + $env:PATH
}

# ─── opencode ────────────────────────────────────────────────────────────────

function Install-OpenCode {
    [CmdletBinding()]
    param()

    Write-Step "Installing opencode..."
    $installed = $false

    switch ($script:PkgMgr) {
        "winget" {
            $output = & winget install --id AnomalyCo.opencode --accept-package-agreements --accept-source-agreements 2>&1
            if ($LASTEXITCODE -eq 0) {
                $installed = $true
            }
            else {
                Write-Warn "winget install failed: $output"
            }
        }
        "choco" {
            $output = & choco install opencode -y 2>&1
            if ($LASTEXITCODE -eq 0) {
                $installed = $true
            }
            else {
                Write-Warn "choco install failed: $output"
            }
        }
    }

    # Fallback: official install script
    if (-not $installed) {
        try {
            Write-Step "Trying official install script..."
            $installScript = Invoke-RestMethod "https://opencode.ai/install.ps1"
            Invoke-Expression $installScript
            $installed = $true
        }
        catch {
            Write-Warn "opencode install script failed: $_"
            if (Check-Node) {
                Write-Step "Trying npm install..."
                & npm install -g opencode 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $installed = $true
                }
            }
        }
    }

    # Refresh PATH from system
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "Machine")

    # Add common install locations to PATH
    $opencodePaths = @(
        "$env:LOCALAPPDATA\opencode",
        "$env:APPDATA\npm",
        "$env:USERPROFILE\.local\bin",
        "$env:USERPROFILE\.cargo\bin"
    )
    foreach ($p in $opencodePaths) {
        if ((Test-Path $p) -and $env:PATH -notlike "*$p*") {
            $env:PATH = "$p;$env:PATH"
        }
    }

    if (Check-OpenCode) {
        $ocVer = (& opencode --version 2>&1) -replace '[^0-9.]', '' | Select-Object -First 1
        if (-not $ocVer) { $ocVer = "installed" }
        Write-Ok "opencode $ocVer installed"
    }
    else {
        Write-Fail "opencode installed but not in PATH"
        Write-Info "Restart your terminal or run: . `$PROFILE"
        throw "opencode not available in PATH — installation cannot continue"
    }
}

# ─── ngrok ───────────────────────────────────────────────────────────────────

function Install-Ngrok {
    [CmdletBinding()]
    param()

    # Already installed?
    if (Get-Command ngrok -ErrorAction SilentlyContinue) {
        $ngrokVer = (& ngrok version 2>&1) -replace '[^0-9.]', '' | Select-Object -First 1
        Write-Ok "ngrok $ngrokVer already installed"
        return
    }

    Write-Step "Installing ngrok..."

    # 1st choice: winget (from Microsoft Store source)
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Step "Installing ngrok via winget (Microsoft Store)..."
        & winget install ngrok -s msstore --accept-package-agreements --accept-source-agreements 2>$null
        # Refresh PATH
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + $env:PATH
        if (Get-Command ngrok -ErrorAction SilentlyContinue) {
            $ngrokVer = (& ngrok version 2>&1) -replace '[^0-9.]', '' | Select-Object -First 1
            Write-Ok "ngrok $ngrokVer installed via winget"
            return
        }
        Write-Warn "winget install returned but ngrok not found in PATH — trying fallback..."
    }

    # 2nd choice: scoop
    if (Get-Command scoop -ErrorAction SilentlyContinue) {
        Write-Step "Installing ngrok via scoop..."
        & scoop install ngrok 2>$null
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + $env:PATH
        if (Get-Command ngrok -ErrorAction SilentlyContinue) {
            $ngrokVer = (& ngrok version 2>&1) -replace '[^0-9.]', '' | Select-Object -First 1
            Write-Ok "ngrok $ngrokVer installed via scoop"
            return
        }
        Write-Warn "scoop install returned but ngrok not found in PATH"
    }

    # No supported method
    Write-Host ""
    Write-Fail "Cannot install ngrok: neither winget nor scoop is available."
    Write-Host "    Please install a package manager first:" -ForegroundColor Yellow
    Write-Host "      • winget — comes with Windows 10/11 App Installer (recommended)" -ForegroundColor Yellow
    Write-Host "        https://learn.microsoft.com/windows/package-manager/winget/" -ForegroundColor DarkGray
    Write-Host "      • scoop  — https://scoop.sh" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    Then re-run the installer, or install ngrok manually:" -ForegroundColor Yellow
    Write-Host "      https://ngrok.com/download" -ForegroundColor DarkGray
    Write-Host ""
}

# ─── Pester (PowerShell test framework) ──────────────────────────────────────

function Install-PesterModule {
    [CmdletBinding()]
    param()

    Write-Step "Installing Pester (PowerShell test framework)..."

    $installed = Get-Module -ListAvailable Pester | Where-Object { $_.Version.Major -ge 5 }
    if ($installed) {
        Write-Ok "Pester $($installed.Version) already installed"
    }
    else {
        try {
            Install-Module -Name Pester -Force -Scope CurrentUser -SkipPublisherCheck -ErrorAction Stop
            $ver = (Get-Module -ListAvailable Pester | Select-Object -First 1).Version
            Write-Ok "Pester $ver installed"
        }
        catch {
            Write-Warn "Pester installation failed (non-critical): $_"
        }
    }
}

# ─── Helper: Select Obscura release asset ─────────────────────────────────────

function _Select-ObscuraAsset {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [object]$Release,

        [Parameter(Mandatory = $true)]
        [string]$AssetPattern
    )

    $assets = $Release.assets
    foreach ($asset in $assets) {
        if ($asset.name -match $AssetPattern) {
            return $asset
        }
    }
    return $null
}

# ─── Obscura (headless browser for MCP) ───────────────────────────────────────

function Install-Obscura {
    [CmdletBinding()]
    param()

    # Already installed?
    $obscuraPath = Check-Obscura
    if ($obscuraPath) {
        $ver = Get-ObscuraVersionSafe -Path $obscuraPath
        Write-Ok "obscura $ver ($obscuraPath)"
        return
    }

    Write-Step "Installing Obscura (headless browser for MCP)..."

    # Only support Windows x64 for now
    if ($script:ARCH -notin @("x64", "amd64")) {
        Write-Warn "Obscura binary not available for architecture: $($script:ARCH)"
        Write-Info "Install manually from: https://github.com/h4ckf0r0day/obscura/releases"
        return
    }

    # Ensure install directory exists
    $binDir = Join-Path $script:InstallDir ".agents\bin"
    if (-not (Test-Path $binDir)) {
        New-Item -ItemType Directory -Path $binDir -Force | Out-Null
    }

    # Create unique temp directory for this install
    $tempDir = Join-Path $env:TEMP "ostwin-obscura-$(New-Guid)"
    $zipPath = Join-Path $tempDir "obscura.zip"
    $extractDir = Join-Path $tempDir "extract"

    try {
        # Fetch latest release info from GitHub API
        Write-Step "Fetching latest Obscura release..."
        $releaseUrl = "https://api.github.com/repos/h4ckf0r0day/obscura/releases/latest"
        $headers = @{
            "Accept" = "application/vnd.github.v3+json"
            "User-Agent" = "Ostwin-Installer"
        }
        $release = Invoke-RestMethod -Uri $releaseUrl -Headers $headers -UseBasicParsing

        # Find Windows x64 asset
        $asset = _Select-ObscuraAsset -Release $release -AssetPattern "obscura-x86_64-windows\.zip"
        if (-not $asset) {
            Write-Warn "Could not find obscura-x86_64-windows.zip in latest release"
            Write-Info "Available assets: $($release.assets.name -join ', ')"
            return
        }

        $downloadUrl = $asset.browser_download_url
        Write-Step "Downloading from $downloadUrl..."

        # Create unique temp directory
        New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
        New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

        # Download to unique temp path
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing

        # Extract
        Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

        # Find obscura.exe in extracted content
        $obscuraExe = Get-ChildItem -Path $extractDir -Filter "obscura.exe" -Recurse | Select-Object -First 1
        if (-not $obscuraExe) {
            Write-Warn "obscura.exe not found in downloaded archive"
            return
        }

        # Copy to install location
        $destPath = Join-Path $binDir "obscura.exe"
        Copy-Item -Path $obscuraExe.FullName -Destination $destPath -Force

        # Add to PATH for current session
        if ($env:PATH -notlike "*$binDir*") {
            $env:PATH = "$binDir;$env:PATH"
        }

        # Verify
        $ver = Get-ObscuraVersionSafe -Path $destPath
        Write-Ok "obscura $ver installed to $destPath"
    }
    catch {
        Write-Warn "Failed to install Obscura: $_"
        Write-Info "Install manually from: https://github.com/h4ckf0r0day/obscura/releases"
    }
    finally {
        # Cleanup temp directory
        if (Test-Path $tempDir) {
            Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
