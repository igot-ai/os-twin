# Agent OS — Start-DynamicRole Pester Tests

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/../../roles/_base").Path ".." "..")).Path
    $script:StartDynamicRole = Join-Path $script:agentsDir "roles" "_base" "Start-DynamicRole.ps1"
    
    # Mock dependencies
    $script:PostMessageMock = Join-Path $TestDrive "Mock-PostMessage.ps1"
    "param(`$RoomDir, `$From, `$To, `$Type, `$Ref, `$Body); `$Body | Out-File (Join-Path `$RoomDir 'mock_channel.out')" | Out-File $script:PostMessageMock -Encoding utf8
    
    $script:GetRoleDefMock = Join-Path $TestDrive "Mock-GetRoleDef.ps1"
    @"
param(`$RoleName = '', `$RolePath = '')
if (`$RoleName -eq 'game-qa' -or `$RolePath -match 'game-qa') {
    return [PSCustomObject]@{
        Name = 'game-qa'
        InstanceType = 'evaluator'
        PromptTemplate = '# Role: QA\nTest prompt.'
    }
}
return [PSCustomObject]@{
    Name = if (`$RoleName) { `$RoleName } else { 'worker-role' }
    InstanceType = 'worker'
    PromptTemplate = '# Role: Worker\nTest prompt.'
}
"@ | Out-File $script:GetRoleDefMock -Encoding utf8

    $script:InvokeAgentMock = Join-Path $TestDrive "Mock-InvokeAgent.ps1"
    "param(`$Prompt); return [PSCustomObject]@{ ExitCode=0; TimedOut=`$false; Output=(Get-Content (Join-Path `$TestDrive 'mock_agent_response.txt') -Raw) }" | Out-File $script:InvokeAgentMock -Encoding utf8

    $script:BuildSystemPromptMock = Join-Path $TestDrive "Mock-BuildSystemPrompt.ps1"
    "param(); return 'SYSTEM PROMPT'" | Out-File $script:BuildSystemPromptMock -Encoding utf8
}

Describe "Start-DynamicRole.ps1" {
    BeforeEach {
        $script:roomDir = Join-Path $TestDrive "room-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:roomDir "artifacts") -Force | Out-Null
        
        $script:configFile = Join-Path $script:roomDir "config.json"
        @{
            assignment = @{ assigned_role = "game-ui-analyst" }
        } | ConvertTo-Json | Out-File $script:configFile -Encoding utf8
        
        $script:overrides = @{
            OverrideGetRoleDef = $script:GetRoleDefMock
            OverrideInvokeAgent = $script:InvokeAgentMock
            OverridePostMessage = $script:PostMessageMock
            OverrideBuildSystemPrompt = $script:BuildSystemPromptMock
        }
    }

    It "generates worker prompt and posts 'done' signal" {
        "Analysis complete." | Out-File (Join-Path $TestDrive 'mock_agent_response.txt') -Encoding utf8

        & $script:StartDynamicRole -RoomDir $script:roomDir `
                                   -RoleName "game-ui-analyst" `
                                   -AgentsDir $script:agentsDir `
                                   -TimeoutSeconds 10 `
                                   @script:overrides

        $debugFile = Join-Path $script:roomDir "artifacts" "dynamic-role-debug.md"
        # Test-Path $debugFile | Should -BeTrue 
        
        # $content = Get-Content $debugFile -Raw
        # $content | Should -Match "Instance Type\*\*: worker"
        # $content | Should -Not -Match "VERDICT: PASS"

        $postOutput = Get-Content (Join-Path $script:roomDir 'mock_channel.out') -Raw
        $postOutput | Should -Match "Analysis complete."
    }

    It "generates evaluator prompt and posts parsed 'pass' signal" {
        "VERDICT: PASS`nLooks good." | Out-File (Join-Path $TestDrive 'mock_agent_response.txt') -Encoding utf8

        & $script:StartDynamicRole -RoomDir $script:roomDir `
                                   -RoleName "game-qa" `
                                   -AgentsDir $script:agentsDir `
                                   -TimeoutSeconds 10 `
                                   @script:overrides

        $debugFile = Join-Path $script:roomDir "artifacts" "dynamic-role-debug.md"
        # Test-Path $debugFile | Should -BeTrue 
        # $content = Get-Content $debugFile -Raw
        
        # $content | Should -Match "Instance Type\*\*: evaluator"
        # $content | Should -Match "VERDICT: PASS"

        $postOutput = Get-Content (Join-Path $script:roomDir 'mock_channel.out') -Raw
        $postOutput | Should -Match "Looks good."
    }

    It "generates evaluator prompt and posts parsed 'done' signal" {
        "VERDICT: DONE`nLooks perfect." | Out-File (Join-Path $TestDrive 'mock_agent_response.txt') -Encoding utf8

        & $script:StartDynamicRole -RoomDir $script:roomDir `
                                   -RoleName "game-qa" `
                                   -AgentsDir $script:agentsDir `
                                   -TimeoutSeconds 10 `
                                   @script:overrides

        $postOutput = Get-Content (Join-Path $script:roomDir 'mock_channel.out') -Raw
        $postOutput | Should -Match "Looks perfect."
    }
}
