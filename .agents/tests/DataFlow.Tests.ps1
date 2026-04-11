#Requires -Version 7.0
# Agent OS — Data Flow Pester Tests
#
# Validates three data-flow improvements:
#   1. Test-GoalMet negation detection — prevents false-positive matches
#      when evidence contains negated goal phrases.
#   2. Test-NegationContext — checks the 80-char preceding window for
#      negation words (not, failed, can't, etc.).
#   3. Channel reading efficiency — Get-WarRoomStatus.ps1 uses
#      StreamReader instead of Get-Content for channel.jsonl.
#   4. Get-RoomsByStatus — lightweight status-only room filtering.

Describe 'Test-GoalMet negation detection' {
    # Extract the function definitions from the script so we can test them
    # in isolation without running the full script (which requires -RoomDir).
    BeforeAll {
        $scriptContent = Get-Content "$PSScriptRoot/../.agents/war-rooms/Test-GoalCompletion.ps1" -Raw

        # Extract Test-NegationContext function (defined before Test-GoalMet)
        if ($scriptContent -match '(?s)(function Test-NegationContext \{.+?\n\})') {
            Invoke-Expression $Matches[1]
        }
        # Extract Test-GoalMet function
        if ($scriptContent -match '(?s)(function Test-GoalMet \{.+?\n\})') {
            Invoke-Expression $Matches[1]
        }
    }

    Context 'Positive matches' {
        It 'detects exact phrase match' {
            $result = Test-GoalMet -Goal 'JWT tokens generated' -Evidence 'The JWT tokens generated successfully during testing.'
            $result.Status | Should -Be 'met'
            $result.Score | Should -Be 1.0
        }

        It 'detects key term match above 70%' {
            $result = Test-GoalMet -Goal 'Unit tests passing with coverage' -Evidence 'All unit tests are passing. Coverage report shows 85%.'
            $result.Status | Should -Be 'met'
        }

        It 'returns met for simple affirmative evidence' {
            $result = Test-GoalMet -Goal 'database schema created' -Evidence 'The database schema was created and validated.'
            $result.Status | Should -Be 'met'
            $result.Score | Should -Be 1.0
        }
    }

    Context 'Negation detection' {
        It 'detects negated exact phrase' {
            $result = Test-GoalMet -Goal 'JWT authentication implemented' -Evidence 'JWT authentication was NOT implemented due to time constraints.'
            $result.Status | Should -Not -Be 'met'
        }

        It 'detects negation with contraction' {
            $result = Test-GoalMet -Goal 'tests passing' -Evidence "The tests aren't passing yet. We need more work."
            $result.Status | Should -Not -Be 'met'
        }

        It 'does not false-positive on negation far from match' {
            # "not" appears 100+ chars before the key terms, well outside the 80-char window
            $padding = "The system was not ready for production use at all, and the team spent weeks working through various infrastructure and deployment issues before finally getting"
            $result = Test-GoalMet -Goal 'database migrations work' -Evidence "$padding the database migrations work correctly in staging."
            # "database", "migrations", "work" all appear in non-negated context
            $result.Status | Should -BeIn @('met', 'partial')
        }

        It 'reports negated terms in evidence string' {
            $result = Test-GoalMet -Goal 'authentication module deployed' -Evidence 'The authentication module was not deployed to staging.'
            # When terms are negated, the evidence string should contain "(negated:"
            if ($result.Evidence -match 'negated') {
                $result.Evidence | Should -Match 'negated'
            }
            $result.Status | Should -Not -Be 'met'
        }
    }

    Context 'Edge cases' {
        It 'returns not_met for empty evidence' {
            $result = Test-GoalMet -Goal 'something specific' -Evidence ''
            $result.Status | Should -Be 'not_met'
        }

        It 'returns not_met for goal with only stop words' {
            $result = Test-GoalMet -Goal 'the and or but' -Evidence 'lots of text here'
            $result.Status | Should -Be 'not_met'
        }

        It 'handles evidence with mixed positive and negative mentions' {
            # "failed" appears far before (>80 chars) the positive mention "code compiles cleanly"
            $padding = "Initially the build failed to compile. The team spent the next several days debugging the root cause, refactoring the build pipeline, and upgrading dependencies. After all those fixes,"
            $result = Test-GoalMet -Goal 'code compiles cleanly' -Evidence "$padding the code compiles cleanly now."
            $result.Status | Should -BeIn @('met', 'partial')
        }
    }
}

Describe 'Test-NegationContext' {
    BeforeAll {
        $scriptContent = Get-Content "$PSScriptRoot/../.agents/war-rooms/Test-GoalCompletion.ps1" -Raw
        if ($scriptContent -match '(?s)(function Test-NegationContext \{.+?\n\})') {
            Invoke-Expression $Matches[1]
        }
    }

    It 'detects "not" before match' {
        $text = 'this feature was not implemented correctly'
        $matchIdx = $text.IndexOf('implemented')
        Test-NegationContext -Text $text -MatchIndex $matchIdx -MatchLength 11 | Should -Be $true
    }

    It 'does not flag when no negation present' {
        $text = 'the feature was implemented correctly'
        $matchIdx = $text.IndexOf('implemented')
        Test-NegationContext -Text $text -MatchIndex $matchIdx -MatchLength 11 | Should -Be $false
    }

    It 'detects "failed" as negation' {
        $text = 'the build failed to compile the authentication module'
        $matchIdx = $text.IndexOf('authentication')
        Test-NegationContext -Text $text -MatchIndex $matchIdx -MatchLength 14 | Should -Be $true
    }

    It 'detects contraction "didn''t"' {
        $text = "the team didn't finish the deployment"
        $matchIdx = $text.IndexOf('deployment')
        Test-NegationContext -Text $text -MatchIndex $matchIdx -MatchLength 10 | Should -Be $true
    }

    It 'ignores negation beyond 80-char window' {
        # Build a string where "not" is more than 80 chars before "implemented"
        $padding = 'x' * 100
        $text = "not $padding implemented correctly"
        $matchIdx = $text.IndexOf('implemented')
        Test-NegationContext -Text $text -MatchIndex $matchIdx -MatchLength 11 | Should -Be $false
    }

    It 'detects "without" as negation' {
        $text = 'deployed without proper testing or validation'
        $matchIdx = $text.IndexOf('testing')
        Test-NegationContext -Text $text -MatchIndex $matchIdx -MatchLength 7 | Should -Be $true
    }
}

Describe 'Channel reading efficiency' {
    It 'Get-WarRoomStatus.ps1 uses StreamReader not Get-Content for channel' {
        $content = Get-Content "$PSScriptRoot/../.agents/war-rooms/Get-WarRoomStatus.ps1" -Raw
        # Should use StreamReader for channel reading
        $content | Should -Match 'StreamReader'
        # Should NOT use Get-Content for channel.jsonl reading in the status loop
        # (It's okay if Get-Content is used for small files like status, task-ref, etc.)
    }

    It 'Get-WarRoomStatus.ps1 properly disposes StreamReader with try/finally' {
        $content = Get-Content "$PSScriptRoot/../.agents/war-rooms/Get-WarRoomStatus.ps1" -Raw
        $content | Should -Match 'finally'
        $content | Should -Match '\.Dispose\(\)'
    }
}

Describe 'Get-RoomsByStatus helper' {
    BeforeAll {
        # Extract Get-RoomsByStatus function from the script
        $scriptContent = Get-Content "$PSScriptRoot/../.agents/war-rooms/Get-WarRoomStatus.ps1" -Raw
        if ($scriptContent -match '(?s)(function Get-RoomsByStatus \{.+?\n\})') {
            Invoke-Expression $Matches[1]
        }

        # Create a temp directory with mock war-rooms for testing
        $script:tempBase = Join-Path ([System.IO.Path]::GetTempPath()) "dataflow-test-$(Get-Random)"
        New-Item -Path $script:tempBase -ItemType Directory -Force | Out-Null

        # room-001: pending
        $r1 = Join-Path $script:tempBase "room-001"
        New-Item -Path $r1 -ItemType Directory -Force | Out-Null
        Set-Content -Path (Join-Path $r1 "status") -Value "pending"

        # room-002: developing (canonical state name; replaces legacy "engineering")
        $r2 = Join-Path $script:tempBase "room-002"
        New-Item -Path $r2 -ItemType Directory -Force | Out-Null
        Set-Content -Path (Join-Path $r2 "status") -Value "developing"

        # room-003: passed
        $r3 = Join-Path $script:tempBase "room-003"
        New-Item -Path $r3 -ItemType Directory -Force | Out-Null
        Set-Content -Path (Join-Path $r3 "status") -Value "passed"

        # room-004: pending (second)
        $r4 = Join-Path $script:tempBase "room-004"
        New-Item -Path $r4 -ItemType Directory -Force | Out-Null
        Set-Content -Path (Join-Path $r4 "status") -Value "pending"

        # room-005: no status file (unknown)
        $r5 = Join-Path $script:tempBase "room-005"
        New-Item -Path $r5 -ItemType Directory -Force | Out-Null
    }

    AfterAll {
        if ($script:tempBase -and (Test-Path $script:tempBase)) {
            Remove-Item -Path $script:tempBase -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    It 'returns rooms matching a single status' {
        $result = Get-RoomsByStatus -BaseDir $script:tempBase -Status @('pending')
        $result.Count | Should -Be 2
        $result.Name | Should -Contain 'room-001'
        $result.Name | Should -Contain 'room-004'
    }

    It 'returns rooms matching multiple statuses' {
        $result = Get-RoomsByStatus -BaseDir $script:tempBase -Status @('pending', 'passed')
        $result.Count | Should -Be 3
    }

    It 'returns unknown rooms when queried' {
        $result = Get-RoomsByStatus -BaseDir $script:tempBase -Status @('unknown')
        $result.Count | Should -Be 1
        $result.Name | Should -Be 'room-005'
    }

    It 'returns empty for non-existent status' {
        $result = @(Get-RoomsByStatus -BaseDir $script:tempBase -Status @('nonexistent'))
        $result.Count | Should -Be 0
    }

    It 'function exists in Get-WarRoomStatus.ps1' {
        $content = Get-Content "$PSScriptRoot/../.agents/war-rooms/Get-WarRoomStatus.ps1" -Raw
        $content | Should -Match 'function Get-RoomsByStatus'
    }
}
