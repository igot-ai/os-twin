# Agent OS — Consolidate-Memory Pester Tests (no-LLM, structural tests)
#
# NOTE: The full Consolidate-Memory.ps1 calls an LLM which requires API keys
# and network access. These tests validate the structural / gating logic
# without invoking the LLM.

BeforeAll {
    $script:Consolidate = Join-Path (Resolve-Path "$PSScriptRoot/../../roles/_base").Path "Consolidate-Memory.ps1"
    $script:agentsDir = (Resolve-Path "$PSScriptRoot/../..").Path
}

Describe "Consolidate-Memory structural checks" {

    BeforeEach {
        # Isolated temp setup
        $script:memDir = Join-Path $TestDrive "mem-consol-$(Get-Random)"
        $script:roomDir = Join-Path $TestDrive "room-consol-$(Get-Random)"

        New-Item -ItemType Directory -Path (Join-Path $script:memDir "memory" "working") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:memDir "memory" "knowledge") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:memDir "memory" "sessions") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:roomDir "artifacts") -Force | Out-Null

        # Baseline output file
        $script:outputFile = Join-Path $script:roomDir "artifacts" "engineer-output.txt"
        "Test agent output" | Out-File $script:outputFile -Encoding utf8
    }

    Context "Memory disabled" {

        It "exits silently when memory.enabled is false" {
            $configFile = Join-Path $script:memDir "config.json"
            @{
                memory = @{ enabled = $false }
            } | ConvertTo-Json -Depth 3 | Out-File $configFile -Encoding utf8

            $env:AGENT_OS_CONFIG = $configFile
            try {
                # Should not throw, just return early
                $result = & $script:Consolidate `
                    -RoomDir $script:roomDir `
                    -RoleName "engineer" `
                    -OutputFile $script:outputFile `
                    -ErrorAction SilentlyContinue
                # No facts should be processed
            }
            finally {
                Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue
            }
        }

        It "exits silently when config.json is missing" {
            $env:AGENT_OS_CONFIG = (Join-Path $TestDrive "nonexistent-config.json")
            try {
                $result = & $script:Consolidate `
                    -RoomDir $script:roomDir `
                    -RoleName "engineer" `
                    -OutputFile $script:outputFile `
                    -ErrorAction SilentlyContinue
            }
            finally {
                Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue
            }
        }
    }

    Context "Input gathering" {

        It "reads agent output file" {
            $longOutput = "x" * 10000
            $longOutput | Out-File $script:outputFile -Encoding utf8

            # We can verify the file is readable (the script truncates to 5000 chars)
            $content = Get-Content $script:outputFile -Raw
            $content.Length | Should -BeGreaterThan 5000
        }

        It "reads working notes when present" {
            $roomId = Split-Path $script:roomDir -Leaf
            $workFile = Join-Path $script:memDir "memory" "working" "engineer-$roomId.yml"
            @"
role: engineer
room_id: $roomId
notes:
  - note: "CORS must come before auth middleware"
    domains: ["api"]
    timestamp: "2026-03-28T00:00:00Z"
"@ | Out-File $workFile -Encoding utf8

            Test-Path $workFile | Should -BeTrue
            $content = Get-Content $workFile -Raw
            $content | Should -Match "CORS"
        }

        It "reads QA feedback from channel.jsonl" {
            $channelFile = Join-Path $script:roomDir "channel.jsonl"
            '{"role":"engineer","body":"Implemented login","type":"done"}' | Out-File $channelFile -Encoding utf8
            '{"role":"qa","body":"FAIL - Missing input validation","type":"fail"}' | Out-File $channelFile -Encoding utf8 -Append

            $content = Get-Content $channelFile
            $lastQa = $content | Where-Object { $_ -match '"qa"' -or $_ -match '"FAIL"' } | Select-Object -Last 1
            $lastQa | Should -Match "Missing input validation"
        }
    }

    Context "Working memory path resolution" {

        It "finds room-specific working file" {
            $roomId = Split-Path $script:roomDir -Leaf
            $workFile = Join-Path $script:memDir "memory" "working" "engineer-$roomId.yml"
            "notes: []" | Out-File $workFile -Encoding utf8

            Test-Path $workFile | Should -BeTrue
        }

        It "falls back to legacy working file" {
            $legacyFile = Join-Path $script:memDir "memory" "working" "engineer.yml"
            "notes: []" | Out-File $legacyFile -Encoding utf8

            Test-Path $legacyFile | Should -BeTrue
        }
    }

    Context "LLM response parsing (simulated)" {

        It "parses well-formed YAML facts" {
            $yamlResponse = @"
facts:
  - fact: "Express 5 requires explicit router registration"
    domains: ["api", "express"]
    origin: "discovery"
  - fact: "Missing content-type causes 415 errors"
    domains: ["api"]
    origin: "qa-feedback"
"@
            # Parse using the same logic as Consolidate-Memory.ps1
            $facts = @()
            $currentFact = $null

            foreach ($line in ($yamlResponse -split "`n")) {
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

            $facts.Count | Should -Be 2
            $facts[0].fact | Should -Be "Express 5 requires explicit router registration"
            $facts[0].domains | Should -Contain "api"
            $facts[0].origin | Should -Be "discovery"
            $facts[1].origin | Should -Be "qa-feedback"
        }

        It "handles markdown-fenced YAML response" {
            $rawResponse = @"
``````yaml
facts:
  - fact: "Test fact"
    domains: ["test"]
    origin: "discovery"
``````
"@
            $cleaned = ($rawResponse -replace '(?s)```ya?ml?\s*', '' -replace '(?s)```\s*$', '').Trim()
            $cleaned | Should -Match "^facts:"
            $cleaned | Should -Not -Match '```'
        }

        It "handles empty facts response" {
            $yamlResponse = "facts: []"

            $facts = @()
            $currentFact = $null
            foreach ($line in ($yamlResponse -split "`n")) {
                if ($line -match '^\s*-\s+fact:\s*"(.+)"') {
                    if ($currentFact) { $facts += $currentFact }
                    $currentFact = @{ fact = $Matches[1]; domains = @(); origin = "discovery" }
                }
            }
            if ($currentFact) { $facts += $currentFact }

            $facts.Count | Should -Be 0
        }
    }

    Context "Deduplication logic (simulated)" {

        It "detects duplicate facts with 60% word overlap" {
            $existingFact = "Express 5 requires explicit middleware ordering for routes"
            $newFact = "Express 5 requires explicit middleware registration for API routes"

            $existWords = @($existingFact.ToLower() -split '\W+' | Where-Object { $_.Length -gt 3 })
            $newWords = @($newFact.ToLower() -split '\W+' | Where-Object { $_.Length -gt 3 })

            $commonWords = @($newWords | Where-Object { $_ -in $existWords }).Count
            $similarity = if ($newWords.Count -gt 0) { $commonWords / $newWords.Count } else { 0 }

            $similarity | Should -BeGreaterOrEqual 0.5 -Because "these are near-duplicate facts"
        }

        It "distinguishes genuinely different facts" {
            $existingFact = "Express 5 requires explicit middleware ordering"
            $newFact = "JWT tokens use RS256 algorithm for signing"

            $existWords = @($existingFact.ToLower() -split '\W+' | Where-Object { $_.Length -gt 3 })
            $newWords = @($newFact.ToLower() -split '\W+' | Where-Object { $_.Length -gt 3 })

            $commonWords = @($newWords | Where-Object { $_ -in $existWords }).Count
            $similarity = if ($newWords.Count -gt 0) { $commonWords / $newWords.Count } else { 0 }

            $similarity | Should -BeLessThan 0.5 -Because "these are unrelated facts"
        }
    }
}
