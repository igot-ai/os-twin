# Setup-WindowsEnvironment.ps1
# Configures Windows for native UTF-8 support to run Agent OS without code changes
# Run with: powershell -ExecutionPolicy Bypass -File .agents\Setup-WindowsEnvironment.ps1 -AutoFix

[CmdletBinding()]
param(
    [switch]$AutoFix,
    [switch]$CheckOnly,
    [switch]$SetConsoleOnly
)

$ErrorActionPreference = "Stop"

# Colors for output (ASCII-only to avoid issues before UTF-8 is set)
function Write-Info { param([string]$Message) Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok { param([string]$Message) Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn { param([string]$Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }
function Write-Step { param([string]$Message) Write-Host "" ; Write-Host "=== $Message ===" -ForegroundColor White }

Write-Step "Agent OS - Windows UTF-8 Environment Setup"
Write-Info "This script configures Windows for UTF-8 support to run Agent OS"
Write-Info "without requiring changes to the codebase."
Write-Host ""

# Check current Windows version
$osInfo = Get-CimInstance -ClassName Win32_OperatingSystem
$windowsVersion = [System.Environment]::OSVersion.Version
$isWindows10OrLater = ($windowsVersion.Major -eq 10 -and $windowsVersion.Build -ge 10240) -or ($windowsVersion.Major -gt 10)
$supportsUtf8SystemLocale = ($windowsVersion.Major -eq 10 -and $windowsVersion.Build -ge 18362) -or ($windowsVersion.Major -gt 10)

Write-Info "Detected: $($osInfo.Caption) (Build $($windowsVersion.Build))"

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warn "Not running as Administrator. Some fixes require admin privileges."
    Write-Warn "Right-click PowerShell and select 'Run as Administrator' to apply all fixes."
    Write-Host ""
}

# Check current code page
$currentCodePage = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage" -Name "OEMCP" -ErrorAction SilentlyContinue).OEMCP
$currentAcp = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage" -Name "ACP" -ErrorAction SilentlyContinue).ACP

Write-Info "Current Console Code Page: $currentCodePage (65001 = UTF-8)"
Write-Info "Current Windows Code Page: $currentAcp (65001 = UTF-8)"

# Check PowerShell version
$psVersion = $PSVersionTable.PSVersion
Write-Info "PowerShell Version: $($psVersion.Major).$($psVersion.Minor)"

if ($psVersion.Major -ge 7) {
    Write-Ok "PowerShell 7+ detected - UTF-8 support is native!"
}

Write-Host ""

# Diagnostic: Show what UTF-8 characters look like currently
Write-Step "UTF-8 Display Test"
Write-Info "The following line shows how UTF-8 characters currently display:"
Write-Host "Test characters: — – ─ │ ┌ ┐ ▶ ⚠ ✅ ❌ 🔑"
Write-Host ""
Write-Info "If you see garbled characters or '?' symbols, UTF-8 is not properly configured."
Write-Host ""

# If CheckOnly, exit here
if ($CheckOnly) {
    Write-Info "Check-only mode. Exiting without making changes."
    exit 0
}

# Apply fixes
if ($AutoFix -or $SetConsoleOnly) {
    Write-Step "Applying UTF-8 Configuration"

    # Fix 1: Set console code page for current session
    Write-Info "Setting console code page to UTF-8 (65001)..."
    try {
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        [Console]::InputEncoding = [System.Text.Encoding]::UTF8
        $OutputEncoding = [System.Text.Encoding]::UTF8

        # Also try to set system-wide console
        if ($isAdmin) {
            $consoleKey = "HKLM:\SOFTWARE\Microsoft\Command Processor"
            if (-not (Test-Path $consoleKey)) {
                New-Item -Path $consoleKey -Force | Out-Null
            }
            Set-ItemProperty -Path $consoleKey -Name "Autorun" -Value "chcp 65001 >nul" -ErrorAction SilentlyContinue
        }

        Write-Ok "Console encoding set to UTF-8"
    }
    catch {
        Write-Error "Failed to set console encoding: $_"
    }

    # Fix 2: Set system locale to UTF-8 (requires admin and restart)
    if ($AutoFix -and $isAdmin -and $supportsUtf8SystemLocale) {
        Write-Info "Configuring system-wide UTF-8 locale (requires restart)..."
        try {
            $codePageKey = "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage"

            # Backup current values
            $backupFile = "$env:TEMP\CodePage_Backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').reg"
            reg export "HKLM\SYSTEM\CurrentControlSet\Control\Nls\CodePage" $backupFile /y 2>$null
            Write-Info "Registry backup saved to: $backupFile"

            # Set UTF-8 code pages
            Set-ItemProperty -Path $codePageKey -Name "ACP" -Value "65001" -Type String
            Set-ItemProperty -Path $codePageKey -Name "OEMCP" -Value "65001" -Type String
            Set-ItemProperty -Path $codePageKey -Name "MACCP" -Value "65001" -Type String

            Write-Ok "System locale configured for UTF-8"
            Write-Warn "RESTART REQUIRED for system-wide changes to take effect!"
        }
        catch {
            Write-Error "Failed to set system locale: $_"
        }
    }
    elseif ($AutoFix -and -not $isAdmin) {
        Write-Warn "Skipping system-wide UTF-8 locale (requires Administrator)"
        Write-Warn "Run as Administrator to enable permanent UTF-8 support."
    }
    elseif ($AutoFix -and -not $supportsUtf8SystemLocale) {
        Write-Warn "System-wide UTF-8 locale not supported on Windows builds before 1903"
        Write-Info "Use PowerShell 7 or the install.bat wrapper for UTF-8 support."
    }

    # Fix 3: Create persistent profile settings
    Write-Info "Configuring PowerShell profile for UTF-8..."
    try {
        $profileDir = Split-Path -Parent $PROFILE
        if (-not (Test-Path $profileDir)) {
            New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
        }

        $utf8Config = @'
# UTF-8 Configuration for Agent OS
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
'@

        if (Test-Path $PROFILE) {
            $existingContent = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
            if ($existingContent -notmatch "UTF-8 Configuration for Agent OS") {
                Add-Content -Path $PROFILE -Value "`n`n$utf8Config" -Encoding UTF8
                Write-Ok "Added UTF-8 settings to PowerShell profile"
            }
            else {
                Write-Ok "UTF-8 settings already in PowerShell profile"
            }
        }
        else {
            Set-Content -Path $PROFILE -Value $utf8Config -Encoding UTF8
            Write-Ok "Created PowerShell profile with UTF-8 settings"
        }
    }
    catch {
        Write-Error "Failed to configure PowerShell profile: $_"
    }

    # Fix 4: Create install.bat wrapper for immediate use
    Write-Info "Creating install.bat wrapper for immediate UTF-8 support..."
    try {
        $installBatPath = Join-Path (Get-Location) "install.bat"

        $batLines = @(
            "@echo off",
            ":: Agent OS Windows Installer Wrapper",
            ":: This batch file ensures UTF-8 encoding before running the install script",
            "",
            "title Agent OS Installer",
            "",
            "echo ============================================================",
            "echo  Agent OS - Windows Installer with UTF-8 Support",
            "echo ============================================================",
            "echo.",
            "",
            ":: Check if running from the correct directory",
            "if not exist `.`\.agents\install.ps1` (",
            "    echo ERROR: install.ps1 not found!",
            "    echo Please run this batch file from the os-twin root directory.",
            "    echo Current directory: %CD%",
            "    pause",
            "    exit /b 1",
            ")",
            "",
            ":: Set UTF-8 code page for this console session",
            "echo [Step 1/3] Setting UTF-8 code page for this session...",
            "chcp 65001 >nul 2>&1",
            "if %ERRORLEVEL% NEQ 0 (",
            "    echo WARNING: Could not set UTF-8 code page. Will try to continue anyway.",
            ") else (",
            "    echo          Code page set to 65001 (UTF-8)",
            ")",
            "",
            ":: Check PowerShell availability",
            "echo.",
            "echo [Step 2/3] Checking PowerShell...",
            "powershell -Command `"exit 0`" >nul 2>&1",
            "if %ERRORLEVEL% NEQ 0 (",
            "    echo ERROR: PowerShell is not available or not in PATH.",
            "    echo Please install PowerShell and try again.",
            "    pause",
            "    exit /b 1",
            ")",
            "echo          PowerShell is available",
            "",
            ":: Launch the installer with UTF-8 encoding",
            "echo.",
            "echo [Step 3/3] Launching Agent OS Installer...",
            "echo          This may take a few minutes...",
            "echo.",
            "",
            ":: Set UTF-8 and run the installer directly",
            "powershell -NoProfile -ExecutionPolicy Bypass -Command \"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; & '.\.agents\install.ps1' %*\"",
            "",
            "set INSTALL_RESULT=%ERRORLEVEL%",
            "",
            "echo.",
            "echo ============================================================",
            "",
            "if %INSTALL_RESULT% EQU 0 (",
            "    echo  Installation completed successfully!",
            "    echo.",
            "    echo  You can now use the 'ostwin' command from a new terminal.",
            "    echo  Start a new PowerShell window and run: ostwin --help",
            ") else (",
            "    echo  Installation failed with error code: %INSTALL_RESULT%",
            "    echo.",
            "    echo  Troubleshooting:",
            "    echo  1. Make sure you're running as Administrator",
            "    echo  2. Check the error messages above",
            "    echo  3. See SETUP-WINDOWS.md for detailed help",
            "    echo.",
            "    echo  For persistent UTF-8 support, run:",
            "    echo    powershell -ExecutionPolicy Bypass -File .agents\Setup-WindowsEnvironment.ps1 -AutoFix",
            ")",
            "",
            "echo ============================================================",
            "echo.",
            "pause",
            "exit /b %INSTALL_RESULT%"
        )

        $batContent = $batLines -join "`r`n"
        Set-Content -Path $installBatPath -Value $batContent -Encoding ASCII
        Write-Ok "Created install.bat - use this to run the installer without system changes"
    }
    catch {
        Write-Error "Failed to create install.bat: $_"
    }

    Write-Host ""
    Write-Step "Setup Complete"

    if ($supportsUtf8SystemLocale -and $isAdmin) {
        Write-Ok "Configuration applied successfully!"
        Write-Warn "IMPORTANT: Restart your computer for system-wide UTF-8 to take effect."
        Write-Host ""
        Write-Info "After restart, you can run: .\install.ps1"
        Write-Info "Or use immediately (before restart): .\install.bat"
    }
    else {
        Write-Ok "Per-session configuration applied!"
        Write-Host ""
        Write-Info "Use: .\install.bat (recommended - handles UTF-8 automatically)"
        Write-Info "Or run: powershell -ExecutionPolicy Bypass -File .\.agents\install.ps1"
    }
}
else {
    Write-Host ""
    Write-Info "No changes made. Use -AutoFix to apply UTF-8 configuration."
    Write-Host ""
    Write-Info "Examples:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .agents\Setup-WindowsEnvironment.ps1 -AutoFix"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .agents\Setup-WindowsEnvironment.ps1 -SetConsoleOnly"
}

Write-Host ""
Write-Info "For more information, see: SETUP-WINDOWS.md"
