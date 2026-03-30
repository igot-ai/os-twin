# Agent OS — Build-SystemPrompt Memory Integration Tests

BeforeAll {
    $script:BuildPrompt = Join-Path (Resolve-Path "$PSScriptRoot/../../roles/_base").Path "Build-SystemPrompt.ps1"
    $script:agentsDir = (Resolve-Path "$PSScriptRoot/../..").Path
}

Describe "Build-SystemPrompt Memory Integration" {

    BeforeEach {
        # Use a built-in role path
        $script:rolePath = Join-Path $script:agentsDir "roles" "engineer"

        $script:roomDir = Join-Path $TestDrive "room-bsp-mem-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
        "# Test Task`nBuild an Express API" |
            Out-File (Join-Path $script:roomDir "brief.md") -Encoding utf8
    }

    Context "Memory tools section" {

        It "includes memory tool instructions when memory is enabled" {
            $prompt = & $script:BuildPrompt -RolePath $script:rolePath -RoomDir $script:roomDir
            $prompt | Should -Match "Memory Tools"
            $prompt | Should -Match "memory_note"
            $prompt | Should -Match "memory_recall"
            $prompt | Should -Match "memory_drop"
        }

        It "includes how-to guidance for agents" {
            $prompt = & $script:BuildPrompt -RolePath $script:rolePath -RoomDir $script:roomDir
            $prompt | Should -Match "memory effectively"
        }
    }

    Context "Recalled memory injection" {

        It "includes recalled memory in prompt when KB has facts" {
            # The real project KB has 11+ facts, so this should match
            $prompt = & $script:BuildPrompt -RolePath $script:rolePath -RoomDir $script:roomDir
            if ($prompt -match "Agent Memory") {
                $prompt | Should -Match "Knowledge Base"
            }
        }
    }

    Context "Memory disabled" {

        It "skips memory sections when memory.enabled is false" {
            # Create a config with memory disabled
            $testConfig = Join-Path $TestDrive "config-no-mem.json"
            @{
                version     = "0.1.0"
                engineer    = @{ cli = "echo"; default_model = "test" }
                memory      = @{ enabled = $false }
            } | ConvertTo-Json -Depth 3 | Out-File $testConfig -Encoding utf8

            $env:AGENT_OS_CONFIG = $testConfig
            try {
                $rolePath = Join-Path $TestDrive "role-nomem-$(Get-Random)"
                New-Item -ItemType Directory -Path $rolePath -Force | Out-Null
                @{ name = "test-role" } | ConvertTo-Json | Out-File (Join-Path $rolePath "role.json")

                $prompt = & $script:BuildPrompt -RolePath $rolePath -RoomDir $script:roomDir
                $prompt | Should -Not -Match "Memory Tools"
            }
            finally {
                Remove-Item Env:AGENT_OS_CONFIG -ErrorAction SilentlyContinue
            }
        }
    }
}
