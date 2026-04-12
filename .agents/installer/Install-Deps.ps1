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

    switch ($script:PkgMgr) {
        "winget" {
            & winget install --id AnomalyCo.opencode --accept-package-agreements --accept-source-agreements 2>$null
        }
        "choco" {
            & choco install opencode -y 2>$null
        }
        default {
            # Official install script
            try {
                $installScript = Invoke-RestMethod "https://opencode.ai/install.ps1"
                Invoke-Expression $installScript
            }
            catch {
                Write-Warn "opencode install script failed — trying npm..."
                if (Check-Node) {
                    & npm install -g opencode 2>$null
                }
                else {
                    Write-Warn "Cannot install opencode: no supported method available"
                    return
                }
            }
        }
    }

    # Refresh PATH and verify
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + $env:PATH
    if (Check-OpenCode) {
        $ocVer = (& opencode --version 2>&1) -replace '[^0-9.]', '' | Select-Object -First 1
        if (-not $ocVer) { $ocVer = "installed" }
        Write-Ok "opencode $ocVer installed"
    }
    else {
        Write-Warn "opencode installed but not in PATH yet — restart your terminal"
    }
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
