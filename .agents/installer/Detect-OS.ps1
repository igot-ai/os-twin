# ──────────────────────────────────────────────────────────────────────────────
# Detect-OS.ps1 — Windows platform detection
#
# Sets: $script:OS, $script:WinVersion, $script:WinBuild,
#       $script:ARCH, $script:PkgMgr
#
# Usage:  . "$PSScriptRoot\Detect-OS.ps1"
#         Detect-WindowsOS
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_DetectOSPs1Loaded) { return }
$script:_DetectOSPs1Loaded = $true

function Detect-WindowsOS {
    [CmdletBinding()]
    param()

    # Verify we are actually on Windows
    if ($IsLinux -or $IsMacOS) {
        Write-Fail "This installer is for Windows only. Use install.sh for macOS/Linux."
        throw "Unsupported OS: not Windows"
    }

    # On Windows PowerShell 5.1, $IsWindows may not exist (it's implicit)
    if ($null -ne (Get-Variable -Name IsWindows -ErrorAction SilentlyContinue) -and -not $IsWindows) {
        Write-Fail "This installer is for Windows only."
        throw "Unsupported OS: not Windows"
    }

    $script:OS = "windows"

    # Architecture detection
    $arch = $env:PROCESSOR_ARCHITECTURE
    switch ($arch) {
        "AMD64"  { $script:ARCH = "x64" }
        "ARM64"  { $script:ARCH = "arm64" }
        "x86"    { $script:ARCH = "x86" }
        default  { $script:ARCH = $arch.ToLower() }
    }

    # Windows version detection
    $osInfo = [System.Environment]::OSVersion.Version
    $script:WinBuild = $osInfo.Build

    if ($osInfo.Build -ge 22000) {
        $script:WinVersion = "11"
    }
    elseif ($osInfo.Build -ge 10240) {
        $script:WinVersion = "10"
    }
    else {
        $script:WinVersion = "$($osInfo.Major).$($osInfo.Minor)"
        Write-Warn "Windows version $($script:WinVersion) detected. Windows 10+ recommended."
    }

    # Package manager detection (priority: winget > choco > scoop)
    $script:PkgMgr = ""
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $script:PkgMgr = "winget"
    }
    elseif (Get-Command choco -ErrorAction SilentlyContinue) {
        $script:PkgMgr = "choco"
    }
    elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
        $script:PkgMgr = "scoop"
    }

    # Developer Mode detection (needed for symlinks without elevation)
    $script:DevModeEnabled = $false
    try {
        $regPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock"
        $devMode = Get-ItemProperty -Path $regPath -Name AllowDevelopmentWithoutDevLicense -ErrorAction SilentlyContinue
        if ($devMode -and $devMode.AllowDevelopmentWithoutDevLicense -eq 1) {
            $script:DevModeEnabled = $true
        }
    }
    catch {
        # Registry key may not exist — not in dev mode
    }
}
