# ──────────────────────────────────────────────────────────────────────────────
# Versions.ps1 — Centralized version constants for the Ostwin Windows installer
#
# All hard-coded version strings live here. Modules dot-source this file
# instead of embedding version literals.
#
# Usage:  . "$PSScriptRoot\Versions.ps1"
# ──────────────────────────────────────────────────────────────────────────────

if ($script:_VersionsPs1Loaded) { return }
$script:_VersionsPs1Loaded = $true

# Python
$script:MinPythonVersion   = "3.10"
$script:PythonInstallVersion = "3.12"

# PowerShell
$script:MinPwshVersion     = "7"
$script:PwshInstallVersion = "7.4.7"

# Node.js
$script:NodeVersion        = "v25.8.1"

# pnpm
$script:PnpmInstallVersion = "10.26.0"
