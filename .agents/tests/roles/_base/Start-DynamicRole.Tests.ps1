# Agent OS — Start-DynamicRole Pester Tests

BeforeAll {
    $script:StartDynamicRole = Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/_base").Path "Start-DynamicRole.ps1"
}

Describe "Start-DynamicRole - Evaluator Logic" {
    BeforeEach {
        $script:tempDir = Join-Path $TestDrive "test-dynamic-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:tempDir -Force | Out-Null
        
        $script:mockInvokeAgent = Join-Path $script:tempDir "Mock-InvokeAgent.ps1"
        $script:mockPostMessage = Join-Path $script:tempDir "Mock-PostMessage.ps1"
        $script:mockGetRoleDef = Join-Path $script:tempDir "Mock-GetRoleDef.ps1"
        $script:postMessageArgsFile = Join-Path $script:tempDir "postMessageArgs.json"
        $script:invokeAgentArgsFile = Join-Path $script:tempDir "invokeAgentArgs.json"

        # Mock Post-Message
        @"
param(`$RoomDir, `$From, `$To, `$Type, `$Ref, `$Body)
@{
    RoomDir = `$RoomDir
    From = `$From
    To = `$To
    Type = `$Type
    Ref = `$Ref
    Body = `$Body
} | ConvertTo-Json -Depth 5 | Out-File `"$($script:postMessageArgsFile.Replace('\', '\\'))`"
"@ | Out-File $script:mockPostMessage -Encoding utf8

        # Mock Get-RoleDef (returns evaluator type)
        @"
param(`$RoleName, `$RolePath)
return @{
    InstanceType = 'evaluator'
}
"@ | Out-File $script:mockGetRoleDef -Encoding utf8
        
        # Setup Room
        $script:roomDir = Join-Path $script:tempDir "room-001"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:roomDir "pids") -Force | Out-Null
        
        @"
{ "assignment": { "assigned_role": "evaluator-role" } }
"@ | Out-File (Join-Path $script:roomDir "config.json") -Encoding utf8
        "TASK-001" | Out-File (Join-Path $script:roomDir "task-ref") -NoNewline
    }

    It "Parses VERDICT: FAIL and strips noise" {
        @"
[CmdletBinding()]
param(`$RoomDir, `$RoleName, `$Prompt, `$TimeoutSeconds, `$InstanceId, `$WorkingDir, `$Model, `$ModelIsExplicit)
return @{
    ExitCode = 0
    TimedOut = `$false
    Output = "🔧 Calling tool: some tool`nVERDICT: FAIL`nThis failed because reasons.`n✓ Task completed"
}
"@ | Out-File $script:mockInvokeAgent -Encoding utf8

        & $script:StartDynamicRole -RoomDir $script:roomDir `
            -OverrideInvokeAgent $script:mockInvokeAgent `
            -OverridePostMessage $script:mockPostMessage `
            -OverrideGetRoleDef $script:mockGetRoleDef

        $args = Get-Content $script:postMessageArgsFile -Raw | ConvertFrom-Json
        $args.Type | Should -Be "fail"
        $args.Body | Should -Match "This failed because reasons."
        $args.Body | Should -Not -Match "🔧 Calling tool"
        $args.Body | Should -Not -Match "✓ Task completed"
    }
    
    It "Parses VERDICT: DONE and preserves clean text" {
        @"
[CmdletBinding()]
param(`$RoomDir, `$RoleName, `$Prompt, `$TimeoutSeconds, `$InstanceId, `$WorkingDir, `$Model, `$ModelIsExplicit)
return @{
    ExitCode = 0
    TimedOut = `$false
    Output = "Here is some text.`nVERDICT: DONE`nTests passed successfully."
}
"@ | Out-File $script:mockInvokeAgent -Encoding utf8

        & $script:StartDynamicRole -RoomDir $script:roomDir `
            -OverrideInvokeAgent $script:mockInvokeAgent `
            -OverridePostMessage $script:mockPostMessage `
            -OverrideGetRoleDef $script:mockGetRoleDef

        $args = Get-Content $script:postMessageArgsFile -Raw | ConvertFrom-Json
        $args.Type | Should -Be "done"
        $args.Body | Should -Match "Here is some text."
        $args.Body | Should -Match "Tests passed successfully."
        $args.Body | Should -Match "VERDICT: DONE"
    }

    It "Defaults to FAIL if VERDICT is not present" {
        @"
[CmdletBinding()]
param(`$RoomDir, `$RoleName, `$Prompt, `$TimeoutSeconds, `$InstanceId, `$WorkingDir, `$Model, `$ModelIsExplicit)
return @{
    ExitCode = 0
    TimedOut = `$false
    Output = "Just some random output."
}
"@ | Out-File $script:mockInvokeAgent -Encoding utf8

        & $script:StartDynamicRole -RoomDir $script:roomDir `
            -OverrideInvokeAgent $script:mockInvokeAgent `
            -OverridePostMessage $script:mockPostMessage `
            -OverrideGetRoleDef $script:mockGetRoleDef

        $args = Get-Content $script:postMessageArgsFile -Raw | ConvertFrom-Json
        $args.Type | Should -Be "fail"
        $args.Body | Should -Be "Just some random output."
    }

    It "prefers lifecycle state role over assigned_role when no RoleName override is provided" {
        @"
{
  "assignment": { "assigned_role": "frontend-engineer" }
}
"@ | Out-File (Join-Path $script:roomDir "config.json") -Encoding utf8

        @"
{
  "version": 2,
  "initial_state": "developing",
  "states": {
    "developing": { "role": "frontend-engineer", "type": "work", "signals": { "done": { "target": "backend-engineer" } } },
    "backend-engineer": { "role": "backend-engineer", "type": "work", "signals": { "done": { "target": "review" } } }
  }
}
"@ | Out-File (Join-Path $script:roomDir "lifecycle.json") -Encoding utf8
        "backend-engineer" | Out-File (Join-Path $script:roomDir "status") -NoNewline

        @"
[CmdletBinding()]
param(`$RoomDir, `$RoleName, `$Prompt, `$TimeoutSeconds, `$InstanceId, `$WorkingDir, `$Model, `$ModelIsExplicit)
@{
    RoomDir = `$RoomDir
    RoleName = `$RoleName
    TimeoutSeconds = `$TimeoutSeconds
} | ConvertTo-Json -Depth 5 | Out-File `"$($script:invokeAgentArgsFile.Replace('\', '\\'))`"
return @{
    ExitCode = 0
    TimedOut = `$false
    Output = "VERDICT: DONE`nBackend work complete."
}
"@ | Out-File $script:mockInvokeAgent -Encoding utf8

        & $script:StartDynamicRole -RoomDir $script:roomDir `
            -OverrideInvokeAgent $script:mockInvokeAgent `
            -OverridePostMessage $script:mockPostMessage `
            -OverrideGetRoleDef $script:mockGetRoleDef

        $postArgs = Get-Content $script:postMessageArgsFile -Raw | ConvertFrom-Json
        $invokeArgs = Get-Content $script:invokeAgentArgsFile -Raw | ConvertFrom-Json

        $invokeArgs.RoleName | Should -Be "backend-engineer"
        $postArgs.From | Should -Be "backend-engineer"
        $postArgs.Type | Should -Be "done"
    }
}

Describe "Start-DynamicRole - Model explicitness" {
    BeforeEach {
        $script:tempDir = Join-Path $TestDrive "test-dynamic-model-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:tempDir -Force | Out-Null

        $script:mockInvokeAgent = Join-Path $script:tempDir "Mock-InvokeAgent.ps1"
        $script:mockPostMessage = Join-Path $script:tempDir "Mock-PostMessage.ps1"
        $script:mockGetRoleDef = Join-Path $script:tempDir "Mock-GetRoleDef.ps1"
        $script:invokeAgentArgsFile = Join-Path $script:tempDir "invokeAgentArgs.json"

        @"
param(`$RoomDir, `$From, `$To, `$Type, `$Ref, `$Body)
"@ | Out-File $script:mockPostMessage -Encoding utf8

        @"
param(`$RoleName, `$RolePath)
return @{
    InstanceType = 'worker'
    Model = 'claude-3-5-sonnet-20241022'
}
"@ | Out-File $script:mockGetRoleDef -Encoding utf8

        $script:roomDir = Join-Path $script:tempDir "room-001"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:roomDir "pids") -Force | Out-Null

        @"
{ "assignment": { "assigned_role": "test-engineer" } }
"@ | Out-File (Join-Path $script:roomDir "config.json") -Encoding utf8
        "TASK-001" | Out-File (Join-Path $script:roomDir "task-ref") -NoNewline

        @"
[CmdletBinding()]
param(`$RoomDir, `$RoleName, `$Prompt, `$TimeoutSeconds, `$InstanceId, `$WorkingDir, `$Model, `$ModelIsExplicit)
@{
    RoomDir = `$RoomDir
    RoleName = `$RoleName
    Model = `$Model
    ModelIsExplicit = `$ModelIsExplicit
} | ConvertTo-Json -Depth 5 | Out-File `"$($script:invokeAgentArgsFile.Replace('\', '\\'))`"
return @{
    ExitCode = 0
    TimedOut = `$false
    Output = "done"
}
"@ | Out-File $script:mockInvokeAgent -Encoding utf8
    }

    It "treats seeded room model as advisory when config_override.model is absent" {
        @"
{
  "role": "test-engineer",
  "instance_id": "001",
  "display_name": "test-engineer #001",
  "model": "claude-3-5-sonnet-20241022",
  "status": "pending",
  "config_override": {}
}
"@ | Out-File (Join-Path $script:roomDir "test-engineer_001.json") -Encoding utf8

        & $script:StartDynamicRole -RoomDir $script:roomDir `
            -OverrideInvokeAgent $script:mockInvokeAgent `
            -OverridePostMessage $script:mockPostMessage `
            -OverrideGetRoleDef $script:mockGetRoleDef

        $invokeArgs = Get-Content $script:invokeAgentArgsFile -Raw | ConvertFrom-Json
        $invokeArgs.Model | Should -Be "claude-3-5-sonnet-20241022"
        [bool]$invokeArgs.ModelIsExplicit | Should -BeFalse
    }

    It "treats config_override.model as an explicit model override" {
        @"
{
  "role": "test-engineer",
  "instance_id": "001",
  "display_name": "test-engineer #001",
  "model": "claude-3-5-sonnet-20241022",
  "status": "pending",
  "config_override": {
    "model": "claude-3-5-sonnet-20241022"
  }
}
"@ | Out-File (Join-Path $script:roomDir "test-engineer_001.json") -Encoding utf8

        & $script:StartDynamicRole -RoomDir $script:roomDir `
            -OverrideInvokeAgent $script:mockInvokeAgent `
            -OverridePostMessage $script:mockPostMessage `
            -OverrideGetRoleDef $script:mockGetRoleDef

        $invokeArgs = Get-Content $script:invokeAgentArgsFile -Raw | ConvertFrom-Json
        $invokeArgs.Model | Should -Be "claude-3-5-sonnet-20241022"
        $invokeArgs.ModelIsExplicit | Should -BeTrue
    }
}
