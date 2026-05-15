<#
.SYNOPSIS
    migrate-memory.ps1 — Move per-project .memory/ dirs to centralized store (Windows)

.DESCRIPTION
    PowerShell equivalent of scripts/migrate-memory.sh.

    For each project with a real .memory/ directory (not a junction/symlink):
      1. Look up the plan_id from the plan registry
      2. Move contents to <OSTWIN_HOME>\.ostwin\memory\<plan_id>\
      3. Replace .memory\ with a junction (or symlink if Developer Mode is on)

.PARAMETER DryRun
    Preview what would be migrated without making any changes.

.PARAMETER Target
    Migrate a single project directory instead of all projects under WORKINGDIR.

.EXAMPLE
    .\migrate-memory.ps1
    .\migrate-memory.ps1 -DryRun
    .\migrate-memory.ps1 -Target C:\Users\user\projects\myapp
#>

[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$Target
)

$ErrorActionPreference = "Stop"

# ── Resolve paths from env vars (no hardcodes) ───────────────────────────────

$OstwinHome = if ($env:OSTWIN_HOME) { $env:OSTWIN_HOME }
              else { Join-Path ($env:USERPROFILE ?? $HOME) ".ostwin" }

$MemoryBase = Join-Path $OstwinHome "memory"

# Locate plans dir: env var → walk up from script location
$PlansDir = $env:OSTWIN_PLANS_DIR
if (-not $PlansDir) {
    $search = $PSScriptRoot
    while ($search -and $search -ne (Split-Path $search -Parent)) {
        $candidate = Join-Path $search ".agents" "plans"
        if (Test-Path $candidate) { $PlansDir = $candidate; break }
        $search = Split-Path $search -Parent
    }
}

$WorkingDir = if ($env:OSTWIN_WORKINGDIR) { $env:OSTWIN_WORKINGDIR }
              else { Join-Path ($env:USERPROFILE ?? $HOME) "ostwin-workingdir" }

# ── Helper: resolve plan_id from registry ────────────────────────────────────

function Get-PlanId {
    param([string]$ProjectDir)

    if (-not $PlansDir -or -not (Test-Path $PlansDir)) { return "" }

    foreach ($meta in Get-ChildItem -Path $PlansDir -Filter "*.meta.json" -ErrorAction SilentlyContinue) {
        try {
            $data = Get-Content $meta.FullName -Raw | ConvertFrom-Json
            if ($data.working_dir -eq $ProjectDir) {
                return [System.IO.Path]::GetFileNameWithoutExtension($meta.Name) -replace '\.meta$', ''
            }
        } catch { continue }
    }
    return ""
}

# ── Helper: check if path is a reparse point (symlink or junction) ───────────

function Test-ReparsePoint {
    param([string]$Path)
    $item = Get-Item $Path -Force -ErrorAction SilentlyContinue
    return $item -and ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
}

# ── Helper: create a junction/symlink pointing central → project .memory ──────

function New-MemoryLink {
    param([string]$LinkPath, [string]$Target)

    # Try Developer-Mode symlink first; fall back to junction (no elevation needed)
    try {
        New-Item -ItemType SymbolicLink -Path $LinkPath -Target $Target -Force -ErrorAction Stop | Out-Null
        return
    } catch {}

    & cmd.exe /c "mklink /J `"$LinkPath`" `"$Target`"" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create junction from '$LinkPath' to '$Target'"
    }
}

# ── Core migration logic ─────────────────────────────────────────────────────

function Invoke-MigrateOne {
    param([string]$ProjectMemory)

    $projectDir = Split-Path $ProjectMemory -Parent
    $projectName = Split-Path $projectDir -Leaf

    # Skip if already a junction/symlink
    if (Test-ReparsePoint $ProjectMemory) {
        $target = (Get-Item $ProjectMemory -Force).Target
        Write-Host "  SKIP (already link): $ProjectMemory -> $target"
        return
    }

    # Skip empty directories
    $contents = Get-ChildItem -Path $ProjectMemory -ErrorAction SilentlyContinue
    if (-not $contents) {
        Write-Host "  SKIP (empty): $ProjectMemory"
        return
    }

    # Resolve plan_id
    $planId = Get-PlanId $projectDir
    if (-not $planId) {
        $planId = $projectName
        Write-Warning "  No plan registry entry for '$projectDir', using name '$planId'"
    }

    $centralDir = Join-Path $MemoryBase $planId

    if ($DryRun) {
        Write-Host "  DRY-RUN: $ProjectMemory -> $centralDir"
        return
    }

    Write-Host "  MIGRATE: $ProjectMemory -> $centralDir"

    if (-not (Test-Path $centralDir)) {
        New-Item -ItemType Directory -Path $centralDir -Force | Out-Null
    }

    # Copy contents to central store
    $robocopy = Get-Command robocopy -ErrorAction SilentlyContinue
    if ($robocopy) {
        & robocopy $ProjectMemory $centralDir /E /NFL /NDL /NJH /NJS /NP /R:1 /W:1 2>&1 | Out-Null
        if ($LASTEXITCODE -ge 8) {
            throw "robocopy failed with exit code $LASTEXITCODE — aborting to protect source at $ProjectMemory"
        }
    } else {
        Copy-Item -Path "$ProjectMemory\*" -Destination $centralDir -Recurse -Force
    }

    # Remove original directory and replace with link
    Remove-Item -Path $ProjectMemory -Recurse -Force
    New-MemoryLink -LinkPath $ProjectMemory -Target $centralDir

    Write-Host "  OK: link created"
}

# ── Entry point ───────────────────────────────────────────────────────────────

if (-not (Test-Path $MemoryBase)) {
    New-Item -ItemType Directory -Path $MemoryBase -Force | Out-Null
}

if ($Target) {
    $memDir = Join-Path $Target ".memory"
    if (Test-Path $memDir) {
        Invoke-MigrateOne $memDir
    } else {
        Write-Error "ERROR: '$memDir' does not exist"
        exit 1
    }
} else {
    if (-not (Test-Path $WorkingDir)) {
        Write-Warning "Working directory not found: $WorkingDir"
        Write-Host "Set `$env:OSTWIN_WORKINGDIR to override."
        exit 0
    }

    Write-Host "Scanning $WorkingDir for .memory directories..."
    $found = 0
    foreach ($project in Get-ChildItem -Path $WorkingDir -Directory -ErrorAction SilentlyContinue) {
        $memDir = Join-Path $project.FullName ".memory"
        if (Test-Path $memDir) {
            $found++
            Invoke-MigrateOne $memDir
        }
    }

    Write-Host ""
    Write-Host "Done. Processed $found directories."
    Write-Host "Centralized store: $MemoryBase"
    if (Test-Path $MemoryBase) {
        Get-ChildItem $MemoryBase | Format-Table Name, LastWriteTime -AutoSize
    }
}
