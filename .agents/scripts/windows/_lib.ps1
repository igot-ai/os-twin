# _lib.ps1 — Shared validation and helpers for Windows automation scripts
# Dot-source: . "$PSScriptRoot\_lib.ps1"
# Requires: PowerShell 5.1+ on Windows

# ── OS validation ────────────────────────────────────────────────────────────
# Works on both PS 5.1 (where $IsWindows doesn't exist) and PS 7+ (cross-platform)
function Assert-Windows {
    $onWindows = $false
    if ($PSVersionTable.PSVersion.Major -le 5) {
        # PS 5.1 only runs on Windows
        $onWindows = $true
    } elseif ($PSVersionTable.PSVersion.Major -ge 6) {
        $onWindows = $IsWindows
    }
    if (-not $onWindows) {
        Write-Error "This script requires Windows. Use the macOS scripts on darwin."
        exit 1
    }
}

# ── Safe Add-Type (idempotent) ───────────────────────────────────────────────
# Checks if a type already exists before calling Add-Type to avoid reflection
# cache errors in long-running sessions.
function Add-TypeSafe {
    param(
        [string]$TypeName,
        [string]$TypeDefinition
    )
    if (-not ([System.Management.Automation.PSTypeName]$TypeName).Type) {
        Add-Type -TypeDefinition $TypeDefinition -ErrorAction Stop
    }
}

# ── Input validation ─────────────────────────────────────────────────────────

function Assert-NonEmpty {
    param([string]$Value, [string]$Label = "value")
    if ([string]::IsNullOrWhiteSpace($Value)) {
        Write-Error "Missing required argument: $Label"
        exit 1
    }
}

function Assert-UInt {
    param([string]$Value, [string]$Label = "value")
    if (-not [uint32]::TryParse($Value, [ref]$null)) {
        Write-Error "$Label must be a non-negative integer, got: '$Value'"
        exit 1
    }
}

Assert-Windows
