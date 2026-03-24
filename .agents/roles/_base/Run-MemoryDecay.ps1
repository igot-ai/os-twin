<#
.SYNOPSIS
    Decays stale knowledge facts and prunes old session digests.

.DESCRIPTION
    Applies exponential decay to knowledge facts based on last access time
    and access frequency. Facts below retention threshold are moved to
    memory/pruned/. Session digests older than max_session_age_days are deleted.
#>
[CmdletBinding()]
param()

$agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..") -ErrorAction SilentlyContinue).Path
$memoryDir = Join-Path $agentsDir "memory"
$knowledgeDir = Join-Path $memoryDir "knowledge"
$sessionsDir = Join-Path $memoryDir "sessions"

# --- Load config ---
$configPath = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG }
              else { Join-Path $agentsDir "config.json" }

$decayConstant = 7.0
$retentionThreshold = 0.2
$maxSessionAgeDays = 30

if (Test-Path $configPath) {
    try {
        $config = Get-Content $configPath -Raw | ConvertFrom-Json
        if ($config.memory.decay_constant) { $decayConstant = [double]$config.memory.decay_constant }
        if ($config.memory.retention_threshold) { $retentionThreshold = [double]$config.memory.retention_threshold }
        if ($config.memory.max_session_age_days) { $maxSessionAgeDays = [int]$config.memory.max_session_age_days }
    }
    catch { }
}

$today = Get-Date

# --- Decay knowledge facts ---
if (Test-Path $knowledgeDir) {
    $prunedDir = Join-Path $memoryDir "pruned"

    foreach ($file in (Get-ChildItem $knowledgeDir -Filter "*.yml" -ErrorAction SilentlyContinue)) {
        $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $content) { continue }

        $lastAccessed = $null
        $accessCount = 1

        if ($content -match 'last_accessed:\s*"(\d{4}-\d{2}-\d{2})"') {
            try { $lastAccessed = [datetime]::ParseExact($Matches[1], "yyyy-MM-dd", $null) }
            catch { }
        }
        if ($content -match 'access_count:\s*(\d+)') {
            $accessCount = [int]$Matches[1]
        }

        if (-not $lastAccessed) { continue }

        $daysSince = ($today - $lastAccessed).Days
        if ($daysSince -lt 0) { $daysSince = 0 }

        $retention = [Math]::Exp(-$daysSince / ($accessCount * $decayConstant))

        if ($retention -lt $retentionThreshold) {
            if (-not (Test-Path $prunedDir)) {
                New-Item -ItemType Directory -Path $prunedDir -Force | Out-Null
            }
            $dest = Join-Path $prunedDir $file.Name
            Move-Item $file.FullName $dest -Force
            Write-Verbose "Pruned fact: $($file.Name) (retention=$([Math]::Round($retention, 3)), days=$daysSince, access=$accessCount)"
        }
    }
}

# --- Prune old session digests ---
if (Test-Path $sessionsDir) {
    foreach ($file in (Get-ChildItem $sessionsDir -Filter "*.yml" -ErrorAction SilentlyContinue)) {
        $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $content) { continue }

        $sessionDate = $null
        if ($content -match 'date:\s*"(\d{4}-\d{2}-\d{2})"') {
            try { $sessionDate = [datetime]::ParseExact($Matches[1], "yyyy-MM-dd", $null) }
            catch { }
        }

        if (-not $sessionDate) { continue }

        $age = ($today - $sessionDate).Days
        if ($age -gt $maxSessionAgeDays) {
            Remove-Item $file.FullName -Force
            Write-Verbose "Deleted old session digest: $($file.Name) (age=$age days)"
        }
    }
}
