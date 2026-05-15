# ──────────────────────────────────────────────────────────────────────────────
# Lib.ps1 — Shared utility functions for the Ostwin Windows installer
#
# Provides: colors, formatting helpers (Write-Header, Write-Ok, Write-Warn,
#           Write-Fail, Write-Info, Write-Step), interactive prompt (Ask-User),
#           and semantic version comparison (Compare-VersionGte).
#
# Usage:  . "$PSScriptRoot\installer\Lib.ps1"
#
# This module has NO side effects when sourced — it only defines functions.
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_LibPs1Loaded) { return }
$script:_LibPs1Loaded = $true

# ─── Output helpers ──────────────────────────────────────────────────────────

function Write-Header {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Message)
    Write-Host ""
    Write-Host "  $Message" -ForegroundColor Blue
}

function Write-Ok {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "    [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "    [WARN] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "    [FAIL] $Message" -ForegroundColor Red
}

function Write-Info {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "    $Message" -ForegroundColor DarkGray
}

function Write-Step {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Message)
    Write-Host "  → $Message" -ForegroundColor Cyan
}

# ─── Interactive prompt ──────────────────────────────────────────────────────
# Returns $true if AutoYes is set or user answers Y/y.

function Ask-User {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Prompt)

    if ($script:AutoYes) {
        return $true
    }

    Write-Host -NoNewline "    ? $Prompt [Y/n] " -ForegroundColor Yellow
    $answer = Read-Host
    if ([string]::IsNullOrWhiteSpace($answer) -or $answer -match '^[Yy]') {
        return $true
    }
    return $false
}

# ─── Venv executable resolution ─────────────────────────────────────────────
# Resolves the Python or pip binary inside a venv, cross-platform.
# Windows layout: Scripts/python.exe   Unix layout: bin/python

function Get-VenvPython {
    param([Parameter(Mandatory)][string]$VenvDir)
    foreach ($rel in @("Scripts/python.exe", "bin/python3", "bin/python")) {
        $p = Join-Path $VenvDir $rel
        if (Test-Path $p) { return $p }
    }
    return "python"
}

function Get-VenvPip {
    param([Parameter(Mandatory)][string]$VenvDir)
    foreach ($rel in @("Scripts/pip.exe", "bin/pip3", "bin/pip")) {
        $p = Join-Path $VenvDir $rel
        if (Test-Path $p) { return $p }
    }
    return "pip"
}

# ─── Version comparison ─────────────────────────────────────────────────────
# Returns $true if $Current >= $Minimum (semantic version comparison).

function Compare-VersionGte {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Current,
        [Parameter(Mandatory)][string]$Minimum
    )

    try {
        # Normalize: strip leading 'v', keep only digits and dots
        $Current = $Current -replace '^v', ''
        $Minimum = $Minimum -replace '^v', ''

        $currentVer = [version]$Current
        $minimumVer = [version]$Minimum
        return $currentVer -ge $minimumVer
    }
    catch {
        # Fallback: simple string comparison
        return $Current -ge $Minimum
    }
}
