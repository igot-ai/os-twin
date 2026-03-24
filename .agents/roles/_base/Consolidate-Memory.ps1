<#
.SYNOPSIS
    Consolidates agent session memory into the Knowledge Base.

.DESCRIPTION
    Runs after an agent session ends. Gathers session inputs (agent output,
    working notes, room context), calls an LLM to extract atomic facts,
    merges facts into the Knowledge Base, and clears working memory.

.PARAMETER RoomDir
    Path to the war-room directory.
.PARAMETER RoleName
    Agent role name (engineer, qa, architect, etc.).
.PARAMETER OutputFile
    Path to the agent's captured output file.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RoomDir,

    [Parameter(Mandatory)]
    [string]$RoleName,

    [Parameter(Mandatory)]
    [string]$OutputFile
)

# --- Resolve paths ---
$agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..") -ErrorAction SilentlyContinue).Path
$memoryDir = Join-Path $agentsDir "memory"
$roomId = Split-Path $RoomDir -Leaf
$workingFile = Join-Path $memoryDir "working" "$RoleName-$roomId.yml"
if (-not (Test-Path $workingFile)) {
    $legacyFile = Join-Path $memoryDir "working" "$RoleName.yml"
    if (Test-Path $legacyFile) { $workingFile = $legacyFile }
}
$knowledgeDir = Join-Path $memoryDir "knowledge"

# --- Check if memory is enabled ---
$configPath = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG }
              else { Join-Path $agentsDir "config.json" }

if (-not (Test-Path $configPath)) { return }

$config = Get-Content $configPath -Raw | ConvertFrom-Json
if (-not $config.memory -or -not $config.memory.enabled) { return }

# --- Ensure knowledge dir exists ---
if (-not (Test-Path $knowledgeDir)) {
    New-Item -ItemType Directory -Path $knowledgeDir -Force | Out-Null
}

# --- Gather inputs ---
$agentOutput = ""
if (Test-Path $OutputFile) {
    $agentOutput = Get-Content $OutputFile -Raw -ErrorAction SilentlyContinue
    if ($agentOutput.Length -gt 5000) {
        $agentOutput = $agentOutput.Substring($agentOutput.Length - 5000)
    }
}

$workingNotes = ""
if (Test-Path $workingFile) {
    $rawNotes = Get-Content $workingFile -Raw -ErrorAction SilentlyContinue
    if ($rawNotes) {
        $formattedNotes = @()
        $currentNote = ""
        $currentDomains = @()
        foreach ($wline in ($rawNotes -split "`n")) {
            if ($wline -match '^\s*-\s+note:\s*"?(.+?)"?\s*$') {
                if ($currentNote) {
                    $tag = if ($currentDomains.Count -gt 0) { "[domains: $($currentDomains -join ', ')] " } else { "" }
                    $formattedNotes += "${tag}$currentNote"
                }
                $currentNote = $Matches[1]
                $currentDomains = @()
            }
            elseif ($wline -match '^\s*domains:\s*\[(.+)\]' -and $currentNote) {
                $currentDomains = @($Matches[1] -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ })
            }
        }
        if ($currentNote) {
            $tag = if ($currentDomains.Count -gt 0) { "[domains: $($currentDomains -join ', ')] " } else { "" }
            $formattedNotes += "${tag}$currentNote"
        }
        $workingNotes = if ($formattedNotes.Count -gt 0) { $formattedNotes -join "`n" } else { $rawNotes }
    }
}

$briefContent = ""
$briefFile = Join-Path $RoomDir "brief.md"
if (Test-Path $briefFile) {
    $briefContent = Get-Content $briefFile -Raw -ErrorAction SilentlyContinue
}

if (-not $agentOutput -and -not $workingNotes) {
    Write-Verbose "No session data to consolidate."
    return
}

# --- Extract QA feedback from channel ---
$qaFeedback = ""
$channelFile = Join-Path $RoomDir "channel.jsonl"
if (Test-Path $channelFile) {
    $lastQaMsg = $null
    foreach ($jsonLine in (Get-Content $channelFile -ErrorAction SilentlyContinue)) {
        if (-not $jsonLine.Trim()) { continue }
        try {
            $msg = $jsonLine | ConvertFrom-Json
            if ($msg.role -eq "qa" -or $jsonLine -match '"PASS"' -or $jsonLine -match '"FAIL"') {
                $lastQaMsg = $jsonLine
            }
        }
        catch { }
    }
    if ($lastQaMsg) {
        $qaFeedback = $lastQaMsg
        if ($qaFeedback.Length -gt 2000) {
            $qaFeedback = $qaFeedback.Substring(0, 2000)
        }
    }
}

# --- Build LLM prompt ---
$extractionPrompt = @"
You are extracting reusable knowledge from an AI agent's work session.

Given the agent's output and notes, extract atomic facts useful in future sessions.

Focus on:
- Non-obvious codebase conventions discovered
- Mistakes made and the correct approach
- Environment/config gotchas
- Patterns specific to this project

Mark facts derived from QA feedback or mistake corrections with `origin: qa-feedback`. Other facts should have `origin: discovery`.

Separately identify any mistakes and the correct approach. These are high-value learnings — mark them with origin: qa-feedback.

Do NOT extract:
- Obvious things derivable from reading the code
- Task-specific details that won't generalize
- Temporary state or in-progress work

Output ONLY valid YAML (no markdown fences, no explanation):
facts:
  - fact: "description"
    domains: ["domain1", "domain2"]
    origin: "discovery"

If nothing worth extracting, output:
facts: []

--- AGENT OUTPUT ---
$agentOutput

--- WORKING NOTES ---
$workingNotes

--- ROOM BRIEF ---
$briefContent
"@

if ($qaFeedback) {
    $extractionPrompt += @"

--- QA FEEDBACK (HIGH PRIORITY — facts from this section should use origin: qa-feedback) ---
$qaFeedback
"@
}

# --- Resolve agent CLI (same pattern as Invoke-Agent.ps1) ---
$agentCmd = ""
if ($config.memory.consolidation_cli) {
    $agentCmd = $config.memory.consolidation_cli
}
if (-not $agentCmd) {
    $localAgent = Join-Path $agentsDir "bin" "agent"
    if (Test-Path $localAgent) {
        $agentCmd = $localAgent
    }
    elseif ($config.$RoleName.cli -and $config.$RoleName.cli -ne "cli") {
        $agentCmd = $config.$RoleName.cli
    }
    else {
        $agentCmd = "deepagents"
    }
}

$consolidationModel = if ($config.memory.consolidation_model) { $config.memory.consolidation_model }
                      else { "gemini-3-flash-preview" }

# --- Validate shell-interpolated values ---
if ($agentCmd -notmatch '^[a-zA-Z0-9_./-]+$') {
    Write-Warning "Memory consolidation aborted: invalid agent command '$agentCmd'"
    return
}
if ($consolidationModel -notmatch '^[a-zA-Z0-9._-]+$') {
    Write-Warning "Memory consolidation aborted: invalid model name '$consolidationModel'"
    return
}

# --- Call LLM ---
$llmResponse = ""
$promptFile = $null
try {
    $promptFile = [System.IO.Path]::GetTempFileName()
    $extractionPrompt | Out-File -FilePath $promptFile -Encoding utf8 -NoNewline -Force
    $safePrompt = $promptFile -replace "'", "'\''"

    $llmResponse = bash -c "$agentCmd -n `"`$(cat '$safePrompt')`" --model $consolidationModel --quiet 2>/dev/null" 2>$null
}
catch {
    Write-Warning "Memory consolidation LLM call failed: $($_.Exception.Message)"
    return
}
finally {
    if ($promptFile) { Remove-Item $promptFile -Force -ErrorAction SilentlyContinue }
}

if (-not $llmResponse) {
    Write-Verbose "No LLM response received for memory consolidation."
    return
}

# --- Parse YAML response ---
$yamlContent = ($llmResponse -replace '(?s)```ya?ml?\s*', '' -replace '(?s)```\s*$', '').Trim()

$facts = @()
$currentFact = $null

foreach ($line in ($yamlContent -split "`n")) {
    $line = $line.TrimEnd()

    if ($line -match '^\s*-\s+fact:\s*"(.+)"') {
        if ($currentFact) { $facts += $currentFact }
        $currentFact = @{ fact = $Matches[1]; domains = @(); origin = "discovery" }
    }
    elseif ($line -match '^\s*-\s+fact:\s*(.+)') {
        if ($currentFact) { $facts += $currentFact }
        $currentFact = @{ fact = $Matches[1].Trim().Trim('"').Trim("'"); domains = @(); origin = "discovery" }
    }
    elseif ($line -match '^\s*domains:\s*\[(.+)\]' -and $currentFact) {
        $currentFact.domains = @($Matches[1] -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ })
    }
    elseif ($line -match '^\s*origin:\s*"?(.+?)"?\s*$' -and $currentFact) {
        $currentFact.origin = $Matches[1]
    }
}
if ($currentFact) { $facts += $currentFact }

if ($facts.Count -eq 0) {
    Write-Verbose "No facts extracted from session."
}

$roomName = Split-Path $RoomDir -Leaf
$today = (Get-Date).ToString("yyyy-MM-dd")

# --- Merge facts into Knowledge Base (skip if no facts) ---
if ($facts.Count -gt 0) {

# Load existing knowledge for dedup
$existingFacts = @()
Get-ChildItem $knowledgeDir -Filter "*.yml" -ErrorAction SilentlyContinue | ForEach-Object {
    $content = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
    if ($content) {
        $ef = @{ file = $_.FullName; fact = ""; domains = @(); confidence = 0.7; access_count = 1 }
        if ($content -match 'fact:\s*"(.+)"') { $ef.fact = $Matches[1] }
        elseif ($content -match 'fact:\s*(.+)') { $ef.fact = $Matches[1].Trim().Trim('"') }
        if ($content -match 'domains:\s*\[(.+)\]') {
            $ef.domains = @($Matches[1] -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ })
        }
        if ($content -match 'confidence:\s*([\d.]+)') { $ef.confidence = [double]$Matches[1] }
        if ($content -match 'access_count:\s*(\d+)') { $ef.access_count = [int]$Matches[1] }
        $existingFacts += $ef
    }
}

foreach ($fact in $facts) {
    $matched = $null
    $factWords = @($fact.fact.ToLower() -split '\W+' | Where-Object { $_.Length -gt 3 })

    foreach ($ef in $existingFacts) {
        if (-not $ef.fact) { continue }

        $domainOverlap = @($fact.domains | Where-Object { $_ -in $ef.domains }).Count
        if ($domainOverlap -eq 0 -and $fact.domains.Count -gt 0 -and $ef.domains.Count -gt 0) { continue }

        $efWords = @($ef.fact.ToLower() -split '\W+' | Where-Object { $_.Length -gt 3 })
        $commonWords = @($factWords | Where-Object { $_ -in $efWords }).Count
        $similarity = if ($factWords.Count -gt 0) { $commonWords / $factWords.Count } else { 0 }

        if ($similarity -ge 0.5) {
            $matched = $ef
            break
        }
    }

    if ($matched) {
        $boost = if ($fact.origin -eq "qa-feedback") { 0.15 } else { 0.1 }
        $newConfidence = [Math]::Min(0.99, $matched.confidence + $boost)
        $newAccessCount = $matched.access_count + 1
        $content = Get-Content $matched.file -Raw
        $content = $content -replace 'confidence:\s*[\d.]+', "confidence: $newConfidence"
        $content = $content -replace 'access_count:\s*\d+', "access_count: $newAccessCount"
        $content = $content -replace 'last_accessed:\s*".+?"', "last_accessed: `"$today`""
        if ($fact.origin -eq "qa-feedback" -and $content -notmatch 'origin:') {
            $content += "`norigin: `"qa-feedback`""
        }
        $content | Out-File -FilePath $matched.file -Encoding utf8 -NoNewline -Force
        Write-Verbose "Updated existing fact: $($matched.file)"
    }
    else {
        $domain = if ($fact.domains.Count -gt 0) { $fact.domains[0] } else { "general" }
        $slugWords = @($fact.fact.ToLower() -split '\W+' | Where-Object { $_.Length -gt 2 } | Select-Object -First 5)
        $slug = ($domain + "-" + ($slugWords -join "-")) -replace '[^a-z0-9\-]', ''
        $slug = $slug.Substring(0, [Math]::Min($slug.Length, 80))

        $filePath = Join-Path $knowledgeDir "$slug.yml"
        $counter = 1
        while (Test-Path $filePath) {
            $filePath = Join-Path $knowledgeDir "$slug-$counter.yml"
            $counter++
        }

        $domainsYaml = ($fact.domains | ForEach-Object { "`"$_`"" }) -join ", "
        $factOrigin = if ($fact.origin) { $fact.origin } else { "discovery" }
        $factConfidence = if ($factOrigin -eq "qa-feedback") { 0.85 } else { 0.7 }

        $yamlOut = @"
fact: "$($fact.fact)"
source: "$roomName"
source_role: "$RoleName"
domains: [$domainsYaml]
origin: "$factOrigin"
confidence: $factConfidence
created: "$today"
last_accessed: "$today"
access_count: 1
"@
        $yamlOut | Out-File -FilePath $filePath -Encoding utf8 -NoNewline -Force
        Write-Verbose "Created new fact: $filePath"
    }
}
} # end if ($facts.Count -gt 0)

# --- Generate session digest ---
$digestEnabled = $true
if ($config.memory.PSObject.Properties['session_digest_enabled'] -and -not $config.memory.session_digest_enabled) {
    $digestEnabled = $false
}

if ($digestEnabled) {
    try {
        $sessionsDir = Join-Path $memoryDir "sessions"
        if (-not (Test-Path $sessionsDir)) {
            New-Item -ItemType Directory -Path $sessionsDir -Force | Out-Null
        }

        $allDomains = @($facts | ForEach-Object { $_.domains } | ForEach-Object { $_ } | Where-Object { $_ } | Select-Object -Unique)
        $domainsForPrompt = if ($allDomains.Count -gt 0) { $allDomains -join ", " } else { "general" }

        $digestPrompt = @"
You are generating a concise session digest from an AI agent's work session.

Given the agent output, working notes, and brief below, produce a structured YAML digest.
Output ONLY valid YAML (no markdown fences, no explanation):

summary: "one-line summary"
what_happened:
  - "bullet 1"
  - "bullet 2"
decisions:
  - "decision 1"
learnings:
  - "learning 1"
mistakes:
  - "mistake 1"

If a section has no items, output an empty list (e.g. mistakes: []).

--- AGENT OUTPUT ---
$agentOutput

--- WORKING NOTES ---
$workingNotes

--- ROOM BRIEF ---
$briefContent
"@

        $digestPromptFile = $null
        try {
            $digestPromptFile = [System.IO.Path]::GetTempFileName()
            $digestPrompt | Out-File -FilePath $digestPromptFile -Encoding utf8 -NoNewline -Force
            $safeDigestPrompt = $digestPromptFile -replace "'", "'\''"

            $digestResponse = bash -c "$agentCmd -n `"`$(cat '$safeDigestPrompt')`" --model $consolidationModel --quiet 2>/dev/null" 2>$null
        }
        finally {
            if ($digestPromptFile) { Remove-Item $digestPromptFile -Force -ErrorAction SilentlyContinue }
        }

        $digestLog = Join-Path $memoryDir "digest-debug.log"
        "[$today $roomId $RoleName] agentCmd=$agentCmd model=$consolidationModel responseLen=$($digestResponse.Length)" | Out-File -FilePath $digestLog -Encoding utf8 -Append
        if (-not $digestResponse) {
            "[$today $roomId $RoleName] ERROR: Empty digest response" | Out-File -FilePath $digestLog -Encoding utf8 -Append
        }

        if ($digestResponse) {
            $digestYaml = ($digestResponse -replace '(?s)```ya?ml?\s*', '' -replace '(?s)```\s*$', '').Trim()

            $summary = ""
            $whatHappened = @()
            $decisions = @()
            $learnings = @()
            $mistakes = @()
            $currentList = $null

            foreach ($dline in ($digestYaml -split "`n")) {
                $dline = $dline.TrimEnd()
                if ($dline -match '^\s*summary:\s*"?(.+?)"?\s*$') {
                    $summary = $Matches[1]
                    $currentList = $null
                }
                elseif ($dline -match '^\s*what_happened:\s*\[\s*\]') { $currentList = $null }
                elseif ($dline -match '^\s*what_happened:') { $currentList = 'what_happened' }
                elseif ($dline -match '^\s*decisions:\s*\[\s*\]') { $currentList = $null }
                elseif ($dline -match '^\s*decisions:') { $currentList = 'decisions' }
                elseif ($dline -match '^\s*learnings:\s*\[\s*\]') { $currentList = $null }
                elseif ($dline -match '^\s*learnings:') { $currentList = 'learnings' }
                elseif ($dline -match '^\s*mistakes:\s*\[\s*\]') { $currentList = $null }
                elseif ($dline -match '^\s*mistakes:') { $currentList = 'mistakes' }
                elseif ($dline -match '^\s*-\s+"?(.+?)"?\s*$' -and $currentList) {
                    $item = $Matches[1]
                    switch ($currentList) {
                        'what_happened' { $whatHappened += $item }
                        'decisions'     { $decisions += $item }
                        'learnings'     { $learnings += $item }
                        'mistakes'      { $mistakes += $item }
                    }
                }
            }

            "[$today $roomId $RoleName] parsed summary='$summary' what=$($whatHappened.Count) learn=$($learnings.Count) mistake=$($mistakes.Count)" | Out-File -FilePath $digestLog -Encoding utf8 -Append
            if ($summary) {
                $digestDate = (Get-Date).ToString("yyyyMMdd")
                $digestFileName = "$digestDate-$roomId-$RoleName.yml"
                $digestFile = Join-Path $sessionsDir $digestFileName

                $domainsYamlDigest = ($allDomains | ForEach-Object { "`"$_`"" }) -join ", "
                $fmtList = { param($items) if ($items.Count -eq 0) { "[]" } else { "`n" + (($items | ForEach-Object { "  - `"$_`"" }) -join "`n") } }

                $digestOut = @"
session_id: "$roomId-$RoleName-$today"
room_id: "$roomId"
agent_role: "$RoleName"
date: "$today"
domain_tags: [$domainsYamlDigest]
summary: "$summary"
what_happened: $(& $fmtList $whatHappened)
decisions: $(& $fmtList $decisions)
learnings: $(& $fmtList $learnings)
mistakes: $(& $fmtList $mistakes)
"@
                $digestOut | Out-File -FilePath $digestFile -Encoding utf8 -NoNewline -Force
                Write-Verbose "Session digest written: $digestFile"
            }
        }
    }
    catch {
        "[$today $roomId $RoleName] EXCEPTION: $($_.Exception.Message)" | Out-File -FilePath (Join-Path $memoryDir "digest-debug.log") -Encoding utf8 -Append
        Write-Warning "Session digest generation failed: $($_.Exception.Message)"
    }
}

# --- Clear working memory ---
if (Test-Path $workingFile) {
    Remove-Item $workingFile -Force -ErrorAction SilentlyContinue
}

Write-Verbose "Memory consolidation complete: $($facts.Count) fact(s) processed."

# --- Run memory decay ---
$decayScript = Join-Path $PSScriptRoot "Run-MemoryDecay.ps1"
if (Test-Path $decayScript) {
    try { & $decayScript -ErrorAction SilentlyContinue }
    catch { Write-Warning "Memory decay failed: $($_.Exception.Message)" }
}
