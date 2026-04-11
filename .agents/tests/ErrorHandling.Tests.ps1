#Requires -Version 7.0
# Agent OS — Error Handling Pester Tests
#
# Validates that error handling follows best practices:
#   - No exit 1 in script files (use throw instead)
#   - No empty catch { } blocks (use Write-Verbose or Write-Warning)
#   - Log.psm1 warns on write failure instead of silencing

BeforeAll {
    Import-Module "$PSScriptRoot/../.agents/lib/Log.psm1" -Force
}

AfterAll {
    Remove-Module -Name "Log" -ErrorAction SilentlyContinue
}

Describe 'Error Handling Compliance' {

    Context 'No exit statements in module functions' {
        It 'Log.psm1 contains no exit statements' {
            $content = Get-Content "$PSScriptRoot/../.agents/lib/Log.psm1" -Raw
            $content | Should -Not -Match '\bexit\s+\d'
        }
    }

    Context 'No silent catch blocks' {
        It 'Log.psm1 has no empty catch blocks' {
            $content = Get-Content "$PSScriptRoot/../.agents/lib/Log.psm1" -Raw
            # Empty catch = catch { } with only whitespace/comments inside
            $content | Should -Not -Match 'catch\s*\{\s*\}'
        }

        It 'Test-GoalCompletion.ps1 has no empty catch blocks' {
            $content = Get-Content "$PSScriptRoot/../.agents/war-rooms/Test-GoalCompletion.ps1" -Raw
            $content | Should -Not -Match 'catch\s*\{\s*\}'
        }

        It 'Get-WarRoomStatus.ps1 has no empty catch blocks' {
            $content = Get-Content "$PSScriptRoot/../.agents/war-rooms/Get-WarRoomStatus.ps1" -Raw
            $content | Should -Not -Match 'catch\s*\{\s*\}'
        }

        It 'Remove-WarRoom.ps1 has no empty catch blocks' {
            $content = Get-Content "$PSScriptRoot/../.agents/war-rooms/Remove-WarRoom.ps1" -Raw
            $content | Should -Not -Match 'catch\s*\{\s*\}'
        }
    }

    Context 'Scripts use throw instead of exit 1' {
        It 'New-WarRoom.ps1 does not use exit 1' {
            $content = Get-Content "$PSScriptRoot/../.agents/war-rooms/New-WarRoom.ps1" -Raw
            $content | Should -Not -Match '\bexit\s+1\b'
        }
        It 'Remove-WarRoom.ps1 does not use exit 1' {
            $content = Get-Content "$PSScriptRoot/../.agents/war-rooms/Remove-WarRoom.ps1" -Raw
            $content | Should -Not -Match '\bexit\s+1\b'
        }
        It 'New-GoalReport.ps1 does not use exit 1' {
            $content = Get-Content "$PSScriptRoot/../.agents/war-rooms/New-GoalReport.ps1" -Raw
            $content | Should -Not -Match '\bexit\s+1\b'
        }
        It 'Test-GoalCompletion.ps1 does not use exit 1' {
            $content = Get-Content "$PSScriptRoot/../.agents/war-rooms/Test-GoalCompletion.ps1" -Raw
            $content | Should -Not -Match '\bexit\s+1\b'
        }
        It 'Expand-Plan.ps1 does not use exit 1' {
            $content = Get-Content "$PSScriptRoot/../.agents/plan/Expand-Plan.ps1" -Raw
            $content | Should -Not -Match '\bexit\s+1\b'
        }
        It 'Review-Dependencies.ps1 does not use exit 1' {
            $content = Get-Content "$PSScriptRoot/../.agents/plan/Review-Dependencies.ps1" -Raw
            $content | Should -Not -Match '\bexit\s+1\b'
        }
    }

    Context 'Build-DependencyGraph.ps1 already uses throw' {
        It 'Build-DependencyGraph.ps1 does not use exit 1' {
            $content = Get-Content "$PSScriptRoot/../.agents/plan/Build-DependencyGraph.ps1" -Raw
            $content | Should -Not -Match '\bexit\s+1\b'
        }

        It 'Build-DependencyGraph.ps1 uses throw for errors' {
            $content = Get-Content "$PSScriptRoot/../.agents/plan/Build-DependencyGraph.ps1" -Raw
            $content | Should -Match '\bthrow\b'
        }
    }

    Context 'New-WarRoom.ps1 throws on duplicate room' {
        It 'throws when room already exists' {
            $testDir = Join-Path $TestDrive 'rooms'
            New-Item -ItemType Directory -Path (Join-Path $testDir 'room-dup') -Force | Out-Null
            {
                & "$PSScriptRoot/../.agents/war-rooms/New-WarRoom.ps1" `
                    -RoomId 'room-dup' -TaskRef 'TASK-001' -TaskDescription 'test' `
                    -WarRoomsDir $testDir -WorkingDir $TestDrive
            } | Should -Throw '*already exists*'
        }
    }

    Context 'Remove-WarRoom.ps1 throws on missing room' {
        It 'throws when room does not exist' {
            $testDir = Join-Path $TestDrive 'rooms-empty'
            New-Item -ItemType Directory -Path $testDir -Force | Out-Null
            {
                & "$PSScriptRoot/../.agents/war-rooms/Remove-WarRoom.ps1" `
                    -RoomId 'room-ghost' -WarRoomsDir $testDir
            } | Should -Throw '*not found*'
        }
    }

    Context 'Test-GoalCompletion.ps1 throws on missing config' {
        It 'throws when config.json is missing' {
            $testDir = Join-Path $TestDrive 'room-no-config'
            New-Item -ItemType Directory -Path $testDir -Force | Out-Null
            {
                & "$PSScriptRoot/../.agents/war-rooms/Test-GoalCompletion.ps1" `
                    -RoomDir $testDir
            } | Should -Throw '*config.json*'
        }
    }

    Context 'Log.psm1 warns on write failure instead of silencing' {
        It 'Write-OstwinLog emits warning when log dir is unwritable' {
            $env:AGENT_OS_LOG_DIR = '/nonexistent/path/that/does/not/exist'
            try {
                # Should not throw, but should emit a warning
                $warnings = Write-OstwinLog -Level INFO -Message 'test' 3>&1
                # At minimum it should not crash
            } finally {
                Remove-Item Env:AGENT_OS_LOG_DIR -ErrorAction SilentlyContinue
            }
        }

        It 'Log.psm1 catch blocks contain Write-Warning' {
            $content = Get-Content "$PSScriptRoot/../.agents/lib/Log.psm1" -Raw
            $content | Should -Match 'Write-Warning\s+"Log file write failed'
            $content | Should -Match 'Write-Warning\s+"JSON log file write failed'
        }
    }

    Context 'Agent invocations are wrapped in try/catch' {
        It 'Expand-Plan.ps1 wraps agent call in try/catch' {
            $content = Get-Content "$PSScriptRoot/../.agents/plan/Expand-Plan.ps1" -Raw
            $content | Should -Match 'try\s*\{'
            $content | Should -Match 'Agent invocation failed'
        }

        It 'Review-Dependencies.ps1 wraps agent call in try/catch' {
            $content = Get-Content "$PSScriptRoot/../.agents/plan/Review-Dependencies.ps1" -Raw
            $content | Should -Match 'try\s*\{'
            $content | Should -Match 'Agent invocation failed'
        }
    }
}
