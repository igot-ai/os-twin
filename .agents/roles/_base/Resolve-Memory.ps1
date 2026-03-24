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

            $domainVocabulary = @()
            $kbDir = Join-Path (Join-Path $agentsDir "memory") "knowledge"
            if (Test-Path $kbDir) {
                foreach ($kbFile in (Get-ChildItem $kbDir -Filter "*.yml" -ErrorAction SilentlyContinue)) {
                    $kbContent = Get-Content $kbFile.FullName -Raw -ErrorAction SilentlyContinue
                    if ($kbContent -and $kbContent -match 'domains:\s*\[(.+)\]') {
                        $domainVocabulary += @($Matches[1] -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ })
                    }
                }
                $domainVocabulary = @($domainVocabulary | Select-Object -Unique)
            }

            foreach ($dv in $domainVocabulary) {
                if ($briefText -match "\b$([regex]::Escape($dv.ToLower()))\b") {
                    $taskDomains += $dv
                }
            }
            $taskDomains = @($taskDomains | Select-Object -Unique)
        }
    }
}

# --- Working Memory ---
$safeRoleName = [System.IO.Path]::GetFileName($RoleName)
$roomId = if ($RoomDir) { Split-Path $RoomDir -Leaf } else { "" }
$workingFile = if ($roomId) {
    $roomSpecific = Join-Path $memoryDir "working" "$safeRoleName-$roomId.yml"
    if (Test-Path $roomSpecific) { $roomSpecific }
    else { Join-Path $memoryDir "working" "$safeRoleName.yml" }
} else { Join-Path $memoryDir "working" "$safeRoleName.yml" }

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
        $origin = 'discovery'

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
            elseif ($line -match '^\s*origin:\s*"?(.+?)"?\s*$') {
                $origin = $Matches[1]
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
            Origin      = $origin
            FilePath    = $file.FullName
        }
    }

    if ($knowledgeFacts.Count -gt 0) {
        $sorted = $knowledgeFacts | Sort-Object { $_.Confidence * $_.AccessCount } -Descending

        # Update access tracking for retrieved facts
        $today = (Get-Date).ToString("yyyy-MM-dd")
        foreach ($kf in $sorted) {
            try {
                $content = Get-Content $kf.FilePath -Raw
                $content = $content -replace 'last_accessed:\s*"[^"]*"', "last_accessed: `"$today`""
                $content = $content -replace 'access_count:\s*\d+', "access_count: $($kf.AccessCount + 1)"
                $content | Out-File -FilePath $kf.FilePath -Encoding utf8 -NoNewline -Force
            }
            catch { }
        }

        # Budget-aware fact selection (reserve 30% for session digests)
        $knowledgeBudget = [int]($maxChars * 0.7)
        $factLines = [System.Collections.Generic.List[string]]::new()
        $charCount = 0
        foreach ($kf in $sorted) {
            if ($kf.Origin -eq "qa-feedback") {
                $line = "- ⚠ $($kf.Fact) (from QA review, confidence: $($kf.Confidence))"
            }
            else {
                $line = "- $($kf.Fact) (confidence: $($kf.Confidence))"
            }
            if (($charCount + $line.Length + 1) -gt $knowledgeBudget) { break }
            $factLines.Add($line)
            $charCount += $line.Length + 1
        }
        if ($factLines.Count -gt 0) {
            $sections.Add("### Knowledge Base`n`n$($factLines -join "`n")")
        }
    }
}

# --- Recent Sessions ---
$sessionsDir = Join-Path $memoryDir "sessions"

if (Test-Path $sessionsDir) {
    $sessionDigests = @()

    foreach ($file in (Get-ChildItem $sessionsDir -Filter "*.yml" -ErrorAction SilentlyContinue)) {
        $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $content) { continue }

        $sDate = ""
        $sRoomId = ""
        $sRole = ""
        $sSummary = ""
        $sDomains = @()
        $sLearnings = @()
        $sMistakes = @()
        $currentList = $null

        foreach ($sline in ($content -split "`n")) {
            $sline = $sline.TrimEnd()
            if ($sline -match '^\s*date:\s*"?(.+?)"?\s*$') { $sDate = $Matches[1] }
            elseif ($sline -match '^\s*room_id:\s*"?(.+?)"?\s*$') { $sRoomId = $Matches[1] }
            elseif ($sline -match '^\s*agent_role:\s*"?(.+?)"?\s*$') { $sRole = $Matches[1] }
            elseif ($sline -match '^\s*summary:\s*"?(.+?)"?\s*$') { $sSummary = $Matches[1] }
            elseif ($sline -match '^\s*domain_tags:\s*\[(.+)\]') {
                $sDomains = @($Matches[1] -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ })
            }
            elseif ($sline -match '^\s*learnings:\s*\[\s*\]') { $currentList = $null }
            elseif ($sline -match '^\s*learnings:') { $currentList = 'learnings' }
            elseif ($sline -match '^\s*mistakes:\s*\[\s*\]') { $currentList = $null }
            elseif ($sline -match '^\s*mistakes:') { $currentList = 'mistakes' }
            elseif ($sline -match '^\s*(what_happened|decisions|session_id):') { $currentList = $null }
            elseif ($sline -match '^\s*-\s+"?(.+?)"?\s*$' -and $currentList) {
                switch ($currentList) {
                    'learnings' { $sLearnings += $Matches[1] }
                    'mistakes'  { $sMistakes += $Matches[1] }
                }
            }
        }

        if (-not $sSummary) { continue }

        $domainMatch = ($taskDomains.Count -eq 0)
        if (-not $domainMatch) {
            foreach ($d in $sDomains) {
                if ($taskDomains -contains $d) { $domainMatch = $true; break }
            }
        }
        if (-not $domainMatch) { continue }

        $sessionDigests += [PSCustomObject]@{
            Date      = $sDate
            RoomId    = $sRoomId
            Role      = $sRole
            Summary   = $sSummary
            Learnings = $sLearnings
            Mistakes  = $sMistakes
        }
    }

    if ($sessionDigests.Count -gt 0) {
        $sorted = $sessionDigests | Sort-Object Date -Descending | Select-Object -First 3

        $sessionBudget = [int]($maxChars * 0.3)
        $sessionLines = [System.Collections.Generic.List[string]]::new()
        $charCount = 0

        foreach ($sd in $sorted) {
            $line = "**$($sd.Date) -- $($sd.RoomId) ($($sd.Role))**: $($sd.Summary)"
            if ($sd.Learnings.Count -gt 0) {
                $line += "`n- Learned: $($sd.Learnings -join '; ')"
            }
            if ($sd.Mistakes.Count -gt 0) {
                $line += "`n- Mistakes: $($sd.Mistakes -join '; ')"
            }

            if (($charCount + $line.Length + 2) -gt $sessionBudget) { break }
            $sessionLines.Add($line)
            $charCount += $line.Length + 2
        }

        if ($sessionLines.Count -gt 0) {
            $sections.Add("### Recent Sessions`n`n$($sessionLines -join "`n`n")")
        }
    }
}

# --- Compose within budget ---
if ($sections.Count -eq 0) {
    return ''
}

$output = "## Agent Memory`n`n" + ($sections -join "`n`n")

Write-Output $output
