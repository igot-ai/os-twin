# Agent OS — Run-MemoryDecay Pester Tests
#
# Run-MemoryDecay.ps1 resolves its memory directory from $PSScriptRoot (the real
# .agents/ dir), so we cannot redirect it to a temp dir. Instead, we:
#   1. Test the retention/positive cases (recent facts, high-access facts) using
#      temp files written to the REAL knowledge/ dir, then clean up.
#   2. Validate the Ebbinghaus decay formula inline.
#   3. Test session digest pruning by writing to the REAL sessions/ dir, then clean up.

BeforeAll {
    $script:RunDecay = Join-Path (Resolve-Path "$PSScriptRoot/../../roles/_base").Path "Run-MemoryDecay.ps1"
    $script:agentsDir = (Resolve-Path "$PSScriptRoot/../..").Path
    $script:knowledgeDir = Join-Path $script:agentsDir "memory" "knowledge"
    $script:sessionsDir = Join-Path $script:agentsDir "memory" "sessions"
    $script:prunedDir = Join-Path $script:agentsDir "memory" "pruned"
}

Describe "Run-MemoryDecay" {

    Context "Ebbinghaus decay formula" {

        It "computes correct retention for fresh facts" {
            # retention = e^(-0 / (5 * 7.0)) = e^0 = 1.0
            $daysSince = 0
            $accessCount = 5
            $decayConstant = 7.0
            $retention = [Math]::Exp(-$daysSince / ($accessCount * $decayConstant))
            $retention | Should -Be 1.0
        }

        It "computes correct retention for moderately old facts" {
            # retention = e^(-14 / (3 * 7.0)) = e^(-0.667) ≈ 0.513
            $daysSince = 14
            $accessCount = 3
            $decayConstant = 7.0
            $retention = [Math]::Exp(-$daysSince / ($accessCount * $decayConstant))
            [Math]::Round($retention, 2) | Should -Be 0.51
        }

        It "computes very low retention for ancient, low-access facts" {
            # retention = e^(-60 / (1 * 7.0)) = e^(-8.57) ≈ 0.0002
            $daysSince = 60
            $accessCount = 1
            $decayConstant = 7.0
            $retention = [Math]::Exp(-$daysSince / ($accessCount * $decayConstant))
            $retention | Should -BeLessThan 0.2 -Because "should be below prune threshold"
        }

        It "high access count compensates for age" {
            # retention = e^(-20 / (50 * 7.0)) = e^(-0.057) ≈ 0.944
            $daysSince = 20
            $accessCount = 50
            $decayConstant = 7.0
            $retention = [Math]::Exp(-$daysSince / ($accessCount * $decayConstant))
            $retention | Should -BeGreaterThan 0.2 -Because "high access count prevents pruning"
        }
    }

    Context "Knowledge fact retention (live)" {

        It "retains recently-accessed facts" {
            $today = (Get-Date).ToString("yyyy-MM-dd")
            $testFile = Join-Path $script:knowledgeDir "test-fresh-fact-pester.yml"
            try {
                @"
fact: "Pester test fresh fact should survive decay"
source: "pester-test"
source_role: "test"
domains: ["test"]
origin: "discovery"
confidence: 0.9
created: "$today"
last_accessed: "$today"
access_count: 5
"@ | Out-File $testFile -Encoding utf8

                & $script:RunDecay -Verbose

                Test-Path $testFile | Should -BeTrue -Because "fresh facts should not be pruned"
            }
            finally {
                Remove-Item $testFile -Force -ErrorAction SilentlyContinue
            }
        }

        It "retains high-access-count facts even when somewhat old" {
            $oldDate = (Get-Date).AddDays(-20).ToString("yyyy-MM-dd")
            $testFile = Join-Path $script:knowledgeDir "test-reinforced-fact-pester.yml"
            try {
                @"
fact: "Pester test reinforced fact with many accesses"
source: "pester-test"
source_role: "test"
domains: ["test"]
origin: "qa-feedback"
confidence: 0.95
created: "2025-01-01"
last_accessed: "$oldDate"
access_count: 50
"@ | Out-File $testFile -Encoding utf8

                & $script:RunDecay -Verbose

                Test-Path $testFile | Should -BeTrue -Because "high access count prevents decay"
            }
            finally {
                Remove-Item $testFile -Force -ErrorAction SilentlyContinue
            }
        }

        It "prunes very old, rarely-accessed facts" {
            $testFile = Join-Path $script:knowledgeDir "test-stale-fact-pester.yml"
            $prunedFile = Join-Path $script:prunedDir "test-stale-fact-pester.yml"
            try {
                @"
fact: "Pester test ancient stale fact that must be pruned"
source: "pester-test"
source_role: "test"
domains: ["test"]
origin: "discovery"
confidence: 0.5
created: "2024-01-01"
last_accessed: "2024-01-01"
access_count: 1
"@ | Out-File $testFile -Encoding utf8

                & $script:RunDecay -Verbose

                Test-Path $testFile | Should -BeFalse -Because "ancient fact should be pruned"
                Test-Path $prunedFile | Should -BeTrue -Because "pruned fact moved to pruned/"
            }
            finally {
                Remove-Item $testFile -Force -ErrorAction SilentlyContinue
                Remove-Item $prunedFile -Force -ErrorAction SilentlyContinue
            }
        }

        It "skips facts without last_accessed date" {
            $testFile = Join-Path $script:knowledgeDir "test-nodate-fact-pester.yml"
            try {
                @"
fact: "Pester test fact with no date"
source: "pester-test"
domains: ["test"]
confidence: 0.5
access_count: 1
"@ | Out-File $testFile -Encoding utf8

                & $script:RunDecay -Verbose

                Test-Path $testFile | Should -BeTrue -Because "no date means skip"
            }
            finally {
                Remove-Item $testFile -Force -ErrorAction SilentlyContinue
            }
        }
    }

    Context "Session digest pruning (live)" {

        It "retains recent session digests" {
            $recentDate = (Get-Date).AddDays(-5).ToString("yyyy-MM-dd")
            $testFile = Join-Path $script:sessionsDir "pester-test-recent-session.yml"
            try {
                @"
session_id: "pester-test-recent"
room_id: "room-pester"
agent_role: "test"
date: "$recentDate"
summary: "Recent pester test session should be kept"
what_happened: []
"@ | Out-File $testFile -Encoding utf8

                & $script:RunDecay -Verbose

                Test-Path $testFile | Should -BeTrue -Because "5-day-old digest is within 30-day limit"
            }
            finally {
                Remove-Item $testFile -Force -ErrorAction SilentlyContinue
            }
        }

        It "deletes session digests older than 30 days" {
            $oldDate = (Get-Date).AddDays(-45).ToString("yyyy-MM-dd")
            $testFile = Join-Path $script:sessionsDir "pester-test-old-session.yml"
            try {
                @"
session_id: "pester-test-old"
room_id: "room-pester"
agent_role: "test"
date: "$oldDate"
summary: "Old pester test session should be deleted"
what_happened: []
"@ | Out-File $testFile -Encoding utf8

                & $script:RunDecay -Verbose

                Test-Path $testFile | Should -BeFalse -Because "45-day-old digest exceeds 30-day limit"
            }
            finally {
                Remove-Item $testFile -Force -ErrorAction SilentlyContinue
            }
        }

        It "retains session digest at exactly 30 days (boundary)" {
            $boundaryDate = (Get-Date).AddDays(-30).ToString("yyyy-MM-dd")
            $testFile = Join-Path $script:sessionsDir "pester-test-boundary-session.yml"
            try {
                @"
session_id: "pester-test-boundary"
room_id: "room-pester"
agent_role: "test"
date: "$boundaryDate"
summary: "Boundary pester test session"
what_happened: []
"@ | Out-File $testFile -Encoding utf8

                & $script:RunDecay -Verbose

                # At exactly 30 days: age == 30, threshold is > 30, so kept
                Test-Path $testFile | Should -BeTrue -Because "exactly 30 days is NOT > 30"
            }
            finally {
                Remove-Item $testFile -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
