<#
.SYNOPSIS
    clawhub-install.ps1 — Install skills from the ClawHub public registry
    (PowerShell port of clawhub-install.sh)

.DESCRIPTION
    Manages skills from the ClawHub public registry.

.PARAMETER Action
    Command: install, search, update, remove, list.

.PARAMETER Arguments
    Remaining arguments (slug, query, etc.).
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Action,

    [Parameter(Position = 1, ValueFromRemainingArguments)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"

# ─── Configuration ───────────────────────────────────────────────────────────

$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
$OstwinHome = if ($env:OSTWIN_HOME) { $env:OSTWIN_HOME } else { Join-Path $HomeDir ".ostwin" }
$ClawHubUrl = if ($env:CLAWHUB_URL) { $env:CLAWHUB_URL } else { "https://clawhub.ai" }
$ClawHubApi = "${ClawHubUrl}/api/v1"
$SkillsDir = Join-Path $OstwinHome ".agents" "skills"
$LockFile = Join-Path $SkillsDir ".clawhub-lock.json"

# ─── Helpers ─────────────────────────────────────────────────────────────────

function Write-Ok   { param([string]$Msg) Write-Host "  [OK] $Msg" }
function Write-Warn { param([string]$Msg) Write-Host "  [WARN] $Msg" }
function Write-Fail { param([string]$Msg) Write-Host "  [FAIL] $Msg" }
function Write-Info { param([string]$Msg) Write-Host "  $Msg" }
function Write-Step { param([string]$Msg) Write-Host "  -> $Msg" }

function Ensure-Dirs {
    if (-not (Test-Path $SkillsDir)) { New-Item -ItemType Directory -Path $SkillsDir -Force | Out-Null }
    $lockDir = Split-Path $LockFile -Parent
    if (-not (Test-Path $lockDir)) { New-Item -ItemType Directory -Path $lockDir -Force | Out-Null }
    if (-not (Test-Path $LockFile)) {
        '{"skills":{}}' | Set-Content -Path $LockFile -Encoding UTF8
    }
}

function Get-LockEntry {
    param([string]$Slug)
    try {
        $lock = Get-Content $LockFile -Raw | ConvertFrom-Json
        $skills = $lock.skills
        if ($skills.PSObject.Properties[$Slug]) {
            return $skills.$Slug
        }
    }
    catch { }
    return $null
}

function Set-LockEntry {
    param([string]$Slug, [string]$Version, [string]$SourceUrl)
    try {
        $lock = Get-Content $LockFile -Raw | ConvertFrom-Json
    }
    catch {
        $lock = [PSCustomObject]@{ skills = [PSCustomObject]@{} }
    }
    if (-not $lock.skills) { $lock | Add-Member -NotePropertyName "skills" -NotePropertyValue ([PSCustomObject]@{}) -Force }

    $entry = [PSCustomObject]@{
        version      = $Version
        source       = $SourceUrl
        installed_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    }
    if ($lock.skills.PSObject.Properties[$Slug]) {
        $lock.skills.$Slug = $entry
    }
    else {
        $lock.skills | Add-Member -NotePropertyName $Slug -NotePropertyValue $entry -Force
    }
    $lock | ConvertTo-Json -Depth 5 | Set-Content -Path $LockFile -Encoding UTF8
}

function Remove-LockEntry {
    param([string]$Slug)
    try {
        $lock = Get-Content $LockFile -Raw | ConvertFrom-Json
        if ($lock.skills.PSObject.Properties[$Slug]) {
            $lock.skills.PSObject.Properties.Remove($Slug)
            $lock | ConvertTo-Json -Depth 5 | Set-Content -Path $LockFile -Encoding UTF8
        }
    }
    catch { }
}

function Invoke-DashboardSync {
    $syncScript = Join-Path $OstwinHome "sync-skills.ps1"
    if (-not (Test-Path $syncScript)) {
        $syncScript = Join-Path $OstwinHome "sync-skills.sh"
    }
    # Try project-local
    $agentsDir = Join-Path (Get-Location).Path ".agents"
    if (Test-Path $agentsDir) {
        $localSync = Join-Path $agentsDir "sync-skills.ps1"
        if (Test-Path $localSync) { $syncScript = $localSync }
        elseif (Test-Path (Join-Path $agentsDir "sync-skills.sh")) { $syncScript = Join-Path $agentsDir "sync-skills.sh" }
    }

    if (Test-Path $syncScript) {
        Write-Info "Syncing with dashboard..."
        $env:OSTWIN_HOME = $OstwinHome
        if ($syncScript -match '\.ps1$') {
            & pwsh -NoProfile -File $syncScript 2>$null
        }
        else {
            if (Get-Command bash -ErrorAction SilentlyContinue) {
                & bash $syncScript 2>$null
            }
        }
    }
}

function Get-JsonField {
    param([PSObject]$Data, [string]$Field, [string]$Default = "")
    if ($Data.PSObject.Properties[$Field]) { return $Data.$Field }
    return $Default
}

# ─── Command: install ────────────────────────────────────────────────────────

function Invoke-Install {
    param([string]$Slug)
    if (-not $Slug) {
        Write-Fail "Usage: ostwin skills install <slug>"
        Write-Host "  Example: ostwin skills install steipete/web-search"
        exit 1
    }

    Ensure-Dirs

    Write-Host ""
    Write-Host "  ClawHub Install"
    Write-Host ""

    # 1. Fetch skill metadata
    Write-Step "Fetching metadata for '$Slug'..."
    try {
        $metaResponse = Invoke-RestMethod -Uri "${ClawHubApi}/skills/${Slug}" -TimeoutSec 15 -ErrorAction Stop
    }
    catch {
        Write-Fail "Skill '$Slug' not found on ClawHub."
        Write-Info "Try: ostwin skills search <keyword>"
        exit 1
    }

    # Parse version and name
    $skill = if ($metaResponse.PSObject.Properties['version']) { $metaResponse } else { $metaResponse.skill ?? $metaResponse }
    $version = Get-JsonField $skill "latestVersion" (Get-JsonField $skill "version" "unknown")
    if ($version -is [PSObject]) { $version = Get-JsonField $version "version" (Get-JsonField $version "semver" "unknown") }
    $name = Get-JsonField $skill "name" (Get-JsonField $skill "slug" $Slug)
    $description = Get-JsonField $skill "description" ""
    if ($description.Length -gt 80) { $description = $description.Substring(0, 80) }

    Write-Info "$name v$version"
    if ($description) { Write-Info $description }

    # Check if already installed
    $existing = Get-LockEntry -Slug $Slug
    if ($existing) {
        $existingVersion = $existing.version
        if ($existingVersion -eq $version) {
            Write-Ok "Already installed at v$version"
            exit 0
        }
        Write-Warn "Upgrading from v$existingVersion to v$version"
    }

    # 2. Download the skill archive
    Write-Step "Downloading..."
    $tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) "ostwin-skill-$([guid]::NewGuid().ToString('N').Substring(0,8))"
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
    $zipFile = Join-Path $tmpDir "skill.zip"

    $downloadUrl = "${ClawHubApi}/download?slug=${Slug}"
    try {
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipFile -TimeoutSec 60 -ErrorAction Stop
    }
    catch {
        # Fallback: version-specific download
        $downloadUrl = "${ClawHubApi}/download?slug=${Slug}&version=${version}"
        try {
            Invoke-WebRequest -Uri $downloadUrl -OutFile $zipFile -TimeoutSec 60 -ErrorAction Stop
        }
        catch {
            Write-Fail "Failed to download skill '$Slug'."
            Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
            exit 1
        }
    }

    if (-not (Test-Path $zipFile) -or (Get-Item $zipFile).Length -eq 0) {
        Write-Fail "Downloaded file is empty."
        Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
        exit 1
    }

    # 3. Extract
    Write-Step "Extracting..."
    $extractDir = Join-Path $tmpDir "extract"
    New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

    try {
        Expand-Archive -Path $zipFile -DestinationPath $extractDir -Force -ErrorAction Stop
    }
    catch {
        # Try tar for gzip
        try {
            & tar -xzf $zipFile -C $extractDir 2>$null
            if ($LASTEXITCODE -ne 0) { throw "tar failed" }
        }
        catch {
            Write-Fail "Failed to extract archive."
            Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
            exit 1
        }
    }

    # Find SKILL.md
    $skillMd = Get-ChildItem -Path $extractDir -Filter "SKILL.md" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $skillMd) {
        Write-Fail "No SKILL.md found in the downloaded package."
        Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
        exit 1
    }
    $skillSourceDir = $skillMd.DirectoryName

    # 4. Install to global skills directory
    $skillDirName = ($Slug -split '/')[-1]
    $destDir = Join-Path $SkillsDir $skillDirName

    if (Test-Path $destDir) { Remove-Item $destDir -Recurse -Force }
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    Copy-Item -Path "$skillSourceDir\*" -Destination $destDir -Recurse -Force -ErrorAction SilentlyContinue

    # 5. Write origin.json
    $origin = [PSCustomObject]@{
        source       = "clawhub"
        slug         = $Slug
        version      = $version
        registry_url = "${ClawHubUrl}/skills/${Slug}"
        installed_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
    }
    $origin | ConvertTo-Json -Depth 3 | Set-Content -Path (Join-Path $destDir "origin.json") -Encoding UTF8

    # 6. Update lockfile
    Set-LockEntry -Slug $Slug -Version $version -SourceUrl "${ClawHubUrl}/skills/${Slug}"

    # 7. Cleanup
    Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue

    Write-Ok "Installed '$name' v$version -> $destDir"
    Write-Host ""

    # 8. Sync with dashboard
    Invoke-DashboardSync
}

# ─── Command: search ─────────────────────────────────────────────────────────

function Invoke-Search {
    param([string]$Query)
    if (-not $Query) {
        Write-Fail "Usage: ostwin skills search <query>"
        exit 1
    }

    Write-Host ""
    Write-Host "  ClawHub Search: $Query"
    Write-Host ""

    $encodedQuery = [System.Uri]::EscapeDataString($Query)
    try {
        $response = Invoke-RestMethod -Uri "${ClawHubApi}/search?q=${encodedQuery}" -TimeoutSec 15 -ErrorAction Stop
    }
    catch {
        Write-Fail "Search failed. ClawHub may be unreachable."
        exit 1
    }

    $results = if ($response -is [array]) { $response } else { $response.results ?? $response.skills ?? @() }

    if (-not $results -or $results.Count -eq 0) {
        Write-Host "  No results found."
        exit 0
    }

    $count = [Math]::Min(20, $results.Count)
    for ($i = 0; $i -lt $count; $i++) {
        $r = $results[$i]
        $slug = Get-JsonField $r "slug" (Get-JsonField $r "name" "?")
        $desc = Get-JsonField $r "description" ""
        if ($desc.Length -gt 60) { $desc = $desc.Substring(0, 60) }
        $ver = Get-JsonField $r "version" (Get-JsonField $r "latestVersion" "")
        if ($ver -is [PSObject]) { $ver = Get-JsonField $ver "version" (Get-JsonField $ver "semver" "") }
        $verStr = if ($ver) { " v$ver" } else { "" }
        Write-Host ("  {0,-35}{1,-10}  {2}" -f $slug, $verStr, $desc)
    }
    Write-Host ""
}

# ─── Command: list ───────────────────────────────────────────────────────────

function Invoke-List {
    Ensure-Dirs

    Write-Host ""
    Write-Host "  Installed ClawHub Skills"
    Write-Host ""

    try {
        $lock = Get-Content $LockFile -Raw | ConvertFrom-Json
    }
    catch {
        Write-Host "  No skills installed from ClawHub."
        exit 0
    }

    $skills = $lock.skills
    if (-not $skills -or $skills.PSObject.Properties.Count -eq 0) {
        Write-Host "  No skills installed from ClawHub."
        exit 0
    }

    foreach ($prop in $skills.PSObject.Properties | Sort-Object Name) {
        $slug = $prop.Name
        $info = $prop.Value
        $ver = if ($info.version) { $info.version } else { "?" }
        $installedAt = if ($info.installed_at) { $info.installed_at } else { "?" }
        $dirName = if ($slug -match '/') { ($slug -split '/')[-1] } else { $slug }
        $exists = if (Test-Path (Join-Path $SkillsDir $dirName)) { "[OK]" } else { "[X]" }
        Write-Host ("  $exists {0,-35}  v{1,-10}  {2}" -f $slug, $ver, $installedAt)
    }
    Write-Host ""
}

# ─── Command: update ─────────────────────────────────────────────────────────

function Invoke-Update {
    param([string]$Target)

    $updateAll = ($Target -eq "--all")

    Ensure-Dirs

    Write-Host ""
    Write-Host "  ClawHub Update"
    Write-Host ""

    $slugsToUpdate = @()

    if ($updateAll) {
        try {
            $lock = Get-Content $LockFile -Raw | ConvertFrom-Json
            $slugsToUpdate = @($lock.skills.PSObject.Properties.Name)
        }
        catch { }
    }
    elseif ($Target) {
        $slugsToUpdate = @($Target)
    }
    else {
        Write-Fail "Usage: ostwin skills update <slug> | --all"
        exit 1
    }

    if ($slugsToUpdate.Count -eq 0) {
        Write-Info "No ClawHub skills installed."
        exit 0
    }

    $updated = 0
    foreach ($slug in $slugsToUpdate) {
        Write-Step "Checking $slug..."

        try {
            $meta = Invoke-RestMethod -Uri "${ClawHubApi}/skills/${slug}" -TimeoutSec 15 -ErrorAction Stop
        }
        catch {
            Write-Warn "Could not fetch metadata for '$slug'. Skipping."
            continue
        }

        $skill = if ($meta.PSObject.Properties['version']) { $meta } else { $meta.skill ?? $meta }
        $remoteVersion = Get-JsonField $skill "latestVersion" (Get-JsonField $skill "version" "unknown")
        if ($remoteVersion -is [PSObject]) { $remoteVersion = Get-JsonField $remoteVersion "version" (Get-JsonField $remoteVersion "semver" "unknown") }

        $existing = Get-LockEntry -Slug $slug
        $localVersion = if ($existing) { $existing.version } else { "unknown" }

        if ($remoteVersion -eq $localVersion) {
            Write-Info "$slug is up to date (v$localVersion)"
            continue
        }

        Write-Info "$slug`: v$localVersion -> v$remoteVersion"
        Invoke-Install -Slug $slug
        $updated++
    }

    if ($updated -eq 0) {
        Write-Ok "All skills are up to date."
    }
    else {
        Write-Ok "Updated $updated skill(s)."
    }
    Write-Host ""
}

# ─── Command: remove ─────────────────────────────────────────────────────────

function Invoke-Remove {
    param([string]$Slug)
    if (-not $Slug) {
        Write-Fail "Usage: ostwin skills remove <slug>"
        exit 1
    }

    Ensure-Dirs

    Write-Host ""
    Write-Host "  ClawHub Remove"
    Write-Host ""

    $skillDirName = ($Slug -split '/')[-1]
    $destDir = Join-Path $SkillsDir $skillDirName

    if (Test-Path $destDir) {
        Remove-Item $destDir -Recurse -Force
        Write-Ok "Removed directory: $destDir"
    }
    else {
        Write-Warn "Skill directory not found: $destDir"
    }

    Remove-LockEntry -Slug $Slug
    Write-Ok "Removed '$Slug' from lockfile."
    Write-Host ""

    Invoke-DashboardSync
}

# ─── Help ────────────────────────────────────────────────────────────────────

function Show-ClawHubHelp {
    Write-Host @"
ClawHub Skill Installer -- Install skills from the ClawHub public registry

Usage:
  clawhub-install.ps1 <command> [args]

Commands:
  install <slug>           Install a skill by its ClawHub slug (e.g. steipete/web-search)
  search  <query>          Search the ClawHub registry
  update  [--all|<slug>]   Update installed skills to latest versions
  remove  <slug>           Remove an installed skill
  list                     Show installed ClawHub skills

Environment:
  OSTWIN_HOME    Override install dir   (default: ~/.ostwin)
  CLAWHUB_URL    Override registry URL  (default: https://clawhub.ai)
"@
}

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

$firstArg = if ($Arguments -and $Arguments.Count -gt 0) { $Arguments[0] } else { "" }
$restArgs = if ($Arguments -and $Arguments.Count -gt 1) { $Arguments[1..($Arguments.Count - 1)] } else { @() }

switch ($Action) {
    "install" { Invoke-Install -Slug $firstArg }
    "search"  { Invoke-Search -Query $firstArg }
    "update"  { Invoke-Update -Target $firstArg }
    "remove"  { Invoke-Remove -Slug $firstArg }
    "list"    { Invoke-List }
    { $_ -in @("-h", "--help", "help") } { Show-ClawHubHelp }
    ""        { Show-ClawHubHelp; exit 1 }
    default   {
        Write-Fail "Unknown command: $Action"
        Show-ClawHubHelp
        exit 1
    }
}
