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
$workingFile = Join-Path $memoryDir "working" "$RoleName.yml"
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
    $workingNotes = Get-Content $workingFile -Raw -ErrorAction SilentlyContinue
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

# --- Build LLM prompt ---
$extractionPrompt = @"
You are extracting reusable knowledge from an AI agent's work session.

Given the agent's output and notes, extract atomic facts useful in future sessions.

Focus on:
- Non-obvious codebase conventions discovered
- Mistakes made and the correct approach
- Environment/config gotchas
- Patterns specific to this project

Do NOT extract:
- Obvious things derivable from reading the code
- Task-specific details that won't generalize
- Temporary state or in-progress work

Output ONLY valid YAML (no markdown fences, no explanation):
facts:
  - fact: "description"
    domains: ["domain1", "domain2"]

If nothing worth extracting, output:
facts: []

--- AGENT OUTPUT ---
$agentOutput

--- WORKING NOTES ---
$workingNotes

--- ROOM BRIEF ---
$briefContent
"@

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
        $currentFact = @{ fact = $Matches[1]; domains = @() }
    }
    elseif ($line -match '^\s*-\s+fact:\s*(.+)') {
        if ($currentFact) { $facts += $currentFact }
        $currentFact = @{ fact = $Matches[1].Trim().Trim('"').Trim("'"); domains = @() }
    }
    elseif ($line -match '^\s*domains:\s*\[(.+)\]' -and $currentFact) {
        $currentFact.domains = @($Matches[1] -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ })
    }
}
if ($currentFact) { $facts += $currentFact }

if ($facts.Count -eq 0) {
    Write-Verbose "No facts extracted from session."
    return
}

# --- Merge facts into Knowledge Base ---
$roomName = Split-Path $RoomDir -Leaf
$today = (Get-Date).ToString("yyyy-MM-dd")

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
        $newConfidence = [Math]::Min(0.99, $matched.confidence + 0.1)
        $newAccessCount = $matched.access_count + 1
        $content = Get-Content $matched.file -Raw
        $content = $content -replace 'confidence:\s*[\d.]+', "confidence: $newConfidence"
        $content = $content -replace 'access_count:\s*\d+', "access_count: $newAccessCount"
        $content = $content -replace 'last_accessed:\s*".+?"', "last_accessed: `"$today`""
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

        $yamlOut = @"
fact: "$($fact.fact)"
source: "$roomName"
domains: [$domainsYaml]
confidence: 0.7
created: "$today"
last_accessed: "$today"
access_count: 1
"@
        $yamlOut | Out-File -FilePath $filePath -Encoding utf8 -NoNewline -Force
        Write-Verbose "Created new fact: $filePath"
    }
}

# --- Clear working memory ---
if (Test-Path $workingFile) {
    Remove-Item $workingFile -Force -ErrorAction SilentlyContinue
}

Write-Verbose "Memory consolidation complete: $($facts.Count) fact(s) processed."
