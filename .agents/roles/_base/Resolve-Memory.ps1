<#
.SYNOPSIS
    Retrieves relevant agent memories and composes them into a prompt section.

.DESCRIPTION
    Reads working memory and knowledge base YAML files from .agents/memory/,
    filters and ranks facts, then returns a formatted markdown section
    suitable for injection into the system prompt.

.PARAMETER RoomDir
    War-room directory path (used for domain context extraction).
.PARAMETER RoleName
    Agent role name (determines which working memory file to read).
.PARAMETER MaxTokens
    Approximate token budget for the composed output (~4 chars per token).

.OUTPUTS
    [string] Markdown-formatted memory section, or empty string if no memories exist.

.EXAMPLE
    $mem = ./Resolve-Memory.ps1 -RoomDir "./war-rooms/room-001" -RoleName "engineer"
#>
[CmdletBinding()]
param(
    [string]$RoomDir = '',
    [Parameter(Mandatory)]
    [string]$RoleName,
    [int]$MaxTokens = 2000
)

$agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
$memoryDir = Join-Path $agentsDir "memory"

if (-not (Test-Path $memoryDir)) {
    return ''
}

$maxChars = $MaxTokens * 4
$sections = [System.Collections.Generic.List[string]]::new()

# --- Extract task domains from war-room context ---
$taskDomains = @()

if ($RoomDir -and (Test-Path $RoomDir)) {
    $configFile = Join-Path $RoomDir "config.json"
    if (Test-Path $configFile) {
        try {
            $roomConfig = Get-Content $configFile -Raw | ConvertFrom-Json
            if ($roomConfig.domains) {
                $taskDomains = @($roomConfig.domains)
            }
        }
        catch { }
    }

    if ($taskDomains.Count -eq 0) {
        $briefFile = Join-Path $RoomDir "brief.md"
        if (Test-Path $briefFile) {
            $briefText = (Get-Content $briefFile -Raw).ToLower()
            $domainKeywords = @{
                'api'        = 'api'
                'database'   = 'database'
                'auth'       = 'auth'
                'frontend'   = 'frontend'
                'backend'    = 'backend'
                'webhook'    = 'webhook'
                'payment'    = 'payment'
                'stripe'     = 'payment'
                'deploy'     = 'deployment'
                'ci/cd'      = 'deployment'
                'test'       = 'testing'
                'security'   = 'security'
            }
            foreach ($kw in $domainKeywords.Keys) {
                if ($briefText -match [regex]::Escape($kw)) {
                    $taskDomains += $domainKeywords[$kw]
                }
            }
            $taskDomains = @($taskDomains | Select-Object -Unique)
        }
    }
}

# --- Working Memory ---
$safeRoleName = [System.IO.Path]::GetFileName($RoleName)
$workingFile = Join-Path $memoryDir "working" "$safeRoleName.yml"

if (Test-Path $workingFile) {
    $lines = Get-Content $workingFile
    $notes = @()
    $inNote = $false
    $currentNote = ''

    foreach ($line in $lines) {
        if ($line -match '^\s*-\s+note:\s*"?(.+?)"?\s*$') {
            if ($inNote -and $currentNote) {
                $notes += $currentNote
            }
            $currentNote = $Matches[1]
            $inNote = $true
        }
        elseif ($line -match '^\s*-\s+note:\s*$') {
            if ($inNote -and $currentNote) {
                $notes += $currentNote
            }
            $currentNote = ''
            $inNote = $true
        }
        elseif ($inNote -and $line -match '^\s*-\s') {
            if ($currentNote) {
                $notes += $currentNote
            }
            $currentNote = ''
            $inNote = $false
        }
    }
    if ($inNote -and $currentNote) {
        $notes += $currentNote
    }

    if ($notes.Count -gt 0) {
        $noteLines = ($notes | ForEach-Object { "- $_" }) -join "`n"
        $sections.Add("### Working Notes`n`n$noteLines")
    }
}

# --- Knowledge Base ---
$knowledgeDir = Join-Path $memoryDir "knowledge"

if (Test-Path $knowledgeDir) {
    $knowledgeFacts = @()

    foreach ($file in (Get-ChildItem $knowledgeDir -Filter "*.yml")) {
        $lines = Get-Content $file.FullName
        $fact = ''
        $confidence = 0.5
        $accessCount = 1
        $domains = @()

        foreach ($line in $lines) {
            if ($line -match '^\s*fact:\s*"?(.+?)"?\s*$') {
                $fact = $Matches[1]
            }
            elseif ($line -match '^\s*confidence:\s*([0-9.]+)') {
                $confidence = [double]$Matches[1]
            }
            elseif ($line -match '^\s*access_count:\s*(\d+)') {
                $accessCount = [int]$Matches[1]
            }
            elseif ($line -match '^\s*domains:\s*\[(.+)\]') {
                $domains = $Matches[1] -split ',\s*' | ForEach-Object { $_.Trim().Trim("'", '"') }
            }
        }

        if (-not $fact) { continue }

        $matched = $false
        if ($taskDomains.Count -eq 0) {
            $matched = $true
        }
        else {
            foreach ($d in $domains) {
                if ($taskDomains -contains $d) {
                    $matched = $true
                    break
                }
            }
        }

        if (-not $matched) { continue }

        $knowledgeFacts += [PSCustomObject]@{
            Fact        = $fact
            Confidence  = $confidence
            AccessCount = $accessCount
            FilePath    = $file.FullName
        }
    }

    if ($knowledgeFacts.Count -gt 0) {
        $sorted = $knowledgeFacts | Sort-Object { $_.Confidence * $_.AccessCount } -Descending
        $factLines = ($sorted | ForEach-Object {
            "- $($_.Fact) (confidence: $($_.Confidence), used $($_.AccessCount) times)"
        }) -join "`n"
        $sections.Add("### Knowledge Base`n`n$factLines")
    }
}

# --- Compose within budget ---
if ($sections.Count -eq 0) {
    return ''
}

$output = "## Agent Memory`n`n" + ($sections -join "`n`n")

if ($output.Length -gt $maxChars) {
    $output = $output.Substring(0, $maxChars - 3) + "..."
}

Write-Output $output
