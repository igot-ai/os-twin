<#
.SYNOPSIS
    sync-skills.ps1 — Scan OSTWIN_HOME for SKILL.md files and register them
    with the dashboard vector store. (PowerShell port of sync-skills.sh)

.DESCRIPTION
    Scans the global skills directory for SKILL.md files and registers them
    with the dashboard API. Can also install skills from a source directory.

.PARAMETER InstallFrom
    Copy skills from a project directory into ~/.ostwin/.agents/skills/ first.

.PARAMETER Port
    Dashboard port (default: 3366).

.PARAMETER Home
    Override OSTWIN_HOME (default: ~/.ostwin).
#>
[CmdletBinding()]
param(
    [string]$InstallFrom,

    [int]$Port = 3366,

    [string]$Home
)

$ErrorActionPreference = "Stop"

# ─── Configuration ───────────────────────────────────────────────────────────

$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
$OstwinHome = if ($Home) { $Home }
              elseif ($env:OSTWIN_HOME) { $env:OSTWIN_HOME }
              else { Join-Path $HomeDir ".ostwin" }
$DashboardPort = if ($env:DASHBOARD_PORT) { [int]$env:DASHBOARD_PORT } else { $Port }
$DashboardUrl = "http://localhost:${DashboardPort}"
$OstwinApiKey = $env:OSTWIN_API_KEY

# Load .env
$envFile = Join-Path $OstwinHome ".env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#') -or $trimmed -notmatch '=') { continue }
        $eqIdx = $trimmed.IndexOf('=')
        $key = $trimmed.Substring(0, $eqIdx).Trim()
        $val = $trimmed.Substring($eqIdx + 1).Trim().Trim('"').Trim("'")
        if ($key -and -not [System.Environment]::GetEnvironmentVariable($key, 'Process')) {
            [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
        }
    }
    $OstwinApiKey = $env:OSTWIN_API_KEY
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

function Write-Ok   { param([string]$Msg) Write-Host "    [OK] $Msg" }
function Write-Warn { param([string]$Msg) Write-Host "    [WARN] $Msg" }
function Write-Fail { param([string]$Msg) Write-Host "    [FAIL] $Msg" }
function Write-Info { param([string]$Msg) Write-Host "    $Msg" }
function Write-Step { param([string]$Msg) Write-Host "  -> $Msg" }

function Get-SkillMeta {
    param([string]$SkillMdPath)
    $result = @{ name = ""; description = ""; tags = "[]" }
    $content = Get-Content $SkillMdPath -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return $result }

    # Parse YAML frontmatter
    if ($content -match '(?ms)^---\s*\n(.*?)\n---') {
        $yaml = $Matches[1]
        if ($yaml -match '(?m)^name:\s*[''"]?([^''"}\n]+)[''"]?') {
            $result.name = $Matches[1].Trim()
        }
        if ($yaml -match '(?m)^description:\s*[''"]?([^''"}\n]+)[''"]?') {
            $result.description = $Matches[1].Trim()
        }
        if ($yaml -match '(?m)^tags:\s*(.+)') {
            $result.tags = $Matches[1].Trim()
        }
    }
    return $result
}

function Get-AuthHeaders {
    $headers = @{ "Content-Type" = "application/json" }
    if ($OstwinApiKey) { $headers["X-API-Key"] = $OstwinApiKey }
    return $headers
}

# ─── Install skills from a project directory ────────────────────────────────

function Install-FromDir {
    param([string]$SourceDir)
    $destBase = Join-Path $OstwinHome ".agents" "skills"
    $copied = 0

    Write-Step "Scanning $SourceDir for SKILL.md files..."

    $skillMds = Get-ChildItem -Path $SourceDir -Filter "SKILL.md" -Recurse -File -ErrorAction SilentlyContinue

    foreach ($skillMd in $skillMds) {
        $skillDir = $skillMd.DirectoryName
        $skillName = Split-Path $skillDir -Leaf

        # Skip nested SKILL.md files (parent already has one)
        $isNested = $false
        $parentDir = Split-Path $skillDir -Parent
        while ($parentDir -and $parentDir -ne $SourceDir -and $parentDir -ne [System.IO.Path]::GetPathRoot($parentDir)) {
            if (Test-Path (Join-Path $parentDir "SKILL.md")) {
                $isNested = $true
                break
            }
            $parentDir = Split-Path $parentDir -Parent
        }
        if ($isNested) { continue }

        $meta = Get-SkillMeta -SkillMdPath $skillMd.FullName
        if ($meta.name) { $skillName = $meta.name }

        # Determine role and category from path
        $relPath = $skillDir.Substring($SourceDir.Length).TrimStart('\', '/')

        $destDir = ""
        if ($relPath -match 'roles/([^/\\]+)/([^/\\]+)$') {
            $role = $Matches[1]
            $destDir = Join-Path $destBase "roles" $role $skillName
        }
        elseif ($relPath -match 'global/([^/\\]+)$') {
            $destDir = Join-Path $destBase "global" $skillName
        }
        else {
            # Fallback: infer from tags
            $firstTag = ""
            if ($meta.tags -match '^\[(.+)\]$') {
                $firstTag = ($Matches[1] -split ',')[0].Trim().Trim('"', "'")
            }
            if ($firstTag) {
                $destDir = Join-Path $destBase "roles" $firstTag $skillName
            }
            else {
                $destDir = Join-Path $destBase "global" $skillName
            }
        }

        if (-not $destDir) {
            Write-Warn "Could not determine destination for $($skillMd.FullName) -- skipping"
            continue
        }

        # Skip if source and destination are the same
        $resolvedSrc = (Resolve-Path $skillDir -ErrorAction SilentlyContinue).Path
        if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
        $resolvedDst = (Resolve-Path $destDir -ErrorAction SilentlyContinue).Path
        if ($resolvedSrc -eq $resolvedDst) {
            Write-Info "  $skillName (already in place)"
            $copied++
            continue
        }

        # Copy the entire skill directory
        if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
        Copy-Item -Path "$skillDir\*" -Destination $destDir -Recurse -Force -ErrorAction SilentlyContinue
        if ($LASTEXITCODE -ne 0 -or -not $?) {
            Copy-Item -Path "$skillDir\." -Destination $destDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        $relDest = $destDir.Substring($OstwinHome.Length).TrimStart('\', '/')
        Write-Info "  $skillName -> $relDest"
        $copied++
    }

    if ($copied -gt 0) {
        Write-Ok "$copied skill(s) copied to $destBase"
    }
    else {
        Write-Warn "No SKILL.md files found in $SourceDir"
    }
}

# ─── Sync home skills with dashboard API ─────────────────────────────────────

function Sync-HomeSkills {
    $skillsBase = Join-Path $OstwinHome ".agents" "skills"
    Write-Step "Scanning $skillsBase for SKILL.md files..."

    $total = 0
    $installed = 0
    $failed = 0
    $skipped = 0
    $seenPaths = @{}
    $headers = Get-AuthHeaders

    $searchDirs = @(
        (Join-Path $skillsBase "roles"),
        (Join-Path $skillsBase "global")
    ) | Where-Object { Test-Path $_ }

    foreach ($searchDir in $searchDirs) {
        $skillMds = Get-ChildItem -Path $searchDir -Filter "SKILL.md" -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' -and $_.FullName -notmatch '[\\/]node_modules[\\/]' -and $_.FullName -notmatch '[\\/]__pycache__[\\/]' }

        foreach ($skillMd in $skillMds) {
            $realPath = (Resolve-Path $skillMd.FullName -ErrorAction SilentlyContinue).Path ?? $skillMd.FullName
            if ($seenPaths.ContainsKey($realPath)) {
                $skipped++
                continue
            }
            $seenPaths[$realPath] = $true

            $skillDir = $skillMd.DirectoryName
            $skillName = Split-Path $skillDir -Leaf

            $meta = Get-SkillMeta -SkillMdPath $skillMd.FullName
            if ($meta.name) { $skillName = $meta.name }

            $total++

            # Install via API
            $payload = @{
                path        = $skillDir
                name        = $meta.name
                description = $meta.description
                tags        = $meta.tags
            } | ConvertTo-Json -Compress

            try {
                $result = Invoke-RestMethod -Uri "${DashboardUrl}/api/skills/install" `
                    -Method POST -Headers $headers -Body $payload -TimeoutSec 10 -ErrorAction Stop
                $installed++
            }
            catch {
                $failed++
                Write-Info "  X $skillName"
            }
        }
    }

    if ($total -eq 0) {
        Write-Warn "No SKILL.md files found in $skillsBase"
        return
    }

    Write-Ok "$installed/$total skill(s) registered via API"
    if ($skipped -gt 0) {
        Write-Info "$skipped duplicate path(s) skipped"
    }
    if ($failed -gt 0) {
        Write-Warn "$failed skill(s) failed -- dashboard may not be reachable"
    }

    # Final sync to ensure vector store is consistent
    Write-Step "Finalizing vector store sync..."
    try {
        $syncResult = Invoke-RestMethod -Uri "${DashboardUrl}/api/skills/sync" `
            -Method POST -Headers $headers -TimeoutSec 15 -ErrorAction Stop
        $syncedCount = if ($syncResult.synced_count) { $syncResult.synced_count } else { 0 }
        Write-Ok "Vector store synced ($syncedCount updated)"
    }
    catch {
        Write-Warn "Vector store sync returned empty -- store may be unavailable"
    }
}

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "  Skills Sync"
Write-Host ""

# If --install-from was specified, copy skills first
if ($InstallFrom) {
    # Resolve to absolute path
    if (-not [System.IO.Path]::IsPathRooted($InstallFrom)) {
        $InstallFrom = (Resolve-Path $InstallFrom -ErrorAction Stop).Path
    }
    if (-not (Test-Path $InstallFrom -PathType Container)) {
        Write-Fail "Source directory not found: $InstallFrom"
        exit 1
    }
    Install-FromDir -SourceDir $InstallFrom
    Write-Host ""
}

# Always sync home skills with the dashboard
Sync-HomeSkills
Write-Host ""
