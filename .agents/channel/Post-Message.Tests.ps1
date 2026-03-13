# Agent OS — Post-Message Pester Tests

BeforeAll {
    $script:PostMessage = Join-Path $PSScriptRoot "Post-Message.ps1"
}

Describe "Post-Message" {
    BeforeEach {
        $script:roomDir = Join-Path $TestDrive "room-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:roomDir -Force | Out-Null
    }

    It "creates channel.jsonl if it doesn't exist" {
        $channelFile = Join-Path $script:roomDir "channel.jsonl"
        Test-Path $channelFile | Should -BeFalse

        & $script:PostMessage -RoomDir $script:roomDir -From "manager" -To "engineer" `
                              -Type "task" -Ref "TASK-001" -Body "Implement feature"

        Test-Path $channelFile | Should -BeTrue
    }

    It "writes valid JSON with all required fields" {
        & $script:PostMessage -RoomDir $script:roomDir -From "manager" -To "engineer" `
                              -Type "task" -Ref "TASK-001" -Body "Implement feature"

        $channelFile = Join-Path $script:roomDir "channel.jsonl"
        $lines = @(Get-Content $channelFile | Where-Object { $_.Trim() })
        $lines.Count | Should -Be 1

        $msg = $lines[0] | ConvertFrom-Json
        $msg.v | Should -Be 1
        $msg.from | Should -Be "manager"
        $msg.to | Should -Be "engineer"
        $msg.type | Should -Be "task"
        $msg.ref | Should -Be "TASK-001"
        $msg.body | Should -Be "Implement feature"
        $msg.ts.ToString("o") | Should -Match "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        $msg.id | Should -Not -BeNullOrEmpty
    }

    It "generates unique message IDs" {
        $id1 = & $script:PostMessage -RoomDir $script:roomDir -From "manager" -To "engineer" `
                                     -Type "task" -Ref "TASK-001" -Body "First"
        Start-Sleep -Milliseconds 10
        $id2 = & $script:PostMessage -RoomDir $script:roomDir -From "manager" -To "engineer" `
                                     -Type "task" -Ref "TASK-002" -Body "Second"
        $id1 | Should -Not -Be $id2
    }

    It "appends multiple messages to the same file" {
        & $script:PostMessage -RoomDir $script:roomDir -From "manager" -To "engineer" `
                              -Type "task" -Ref "TASK-001" -Body "First task"
        & $script:PostMessage -RoomDir $script:roomDir -From "engineer" -To "manager" `
                              -Type "done" -Ref "TASK-001" -Body "Completed"
        & $script:PostMessage -RoomDir $script:roomDir -From "manager" -To "qa" `
                              -Type "review" -Ref "TASK-001" -Body "Please review"

        $channelFile = Join-Path $script:roomDir "channel.jsonl"
        $lines = Get-Content $channelFile | Where-Object { $_.Trim() }
        $lines.Count | Should -Be 3
    }

    It "returns the message ID" {
        $msgId = & $script:PostMessage -RoomDir $script:roomDir -From "engineer" -To "manager" `
                                       -Type "done" -Ref "TASK-001" -Body "Done"
        $msgId | Should -Match "^engineer-done-"
    }

    It "truncates body exceeding max size" {
        # Create a config with small max
        $configFile = Join-Path $TestDrive "config.json"
        @{
            channel = @{ max_message_size_bytes = 50 }
        } | ConvertTo-Json -Depth 3 | Out-File $configFile -Encoding utf8

        $longBody = "x" * 200
        & $script:PostMessage -RoomDir $script:roomDir -From "manager" -To "engineer" `
                              -Type "task" -Ref "TASK-001" -Body $longBody `
                              -ConfigPath $configFile

        $channelFile = Join-Path $script:roomDir "channel.jsonl"
        $msg = (Get-Content $channelFile | Where-Object { $_.Trim() } | Select-Object -Last 1) | ConvertFrom-Json
        $msg.body | Should -Match "\[TRUNCATED:"
        $msg.body.Length | Should -BeLessThan 200
    }

    It "handles empty body" {
        & $script:PostMessage -RoomDir $script:roomDir -From "qa" -To "manager" `
                              -Type "pass" -Ref "TASK-001" -Body ""

        $channelFile = Join-Path $script:roomDir "channel.jsonl"
        $msg = (Get-Content $channelFile | Where-Object { $_.Trim() }) | ConvertFrom-Json
        $msg.body | Should -Be ""
    }

    It "validates message type with ValidateSet" {
        { & $script:PostMessage -RoomDir $script:roomDir -From "manager" -To "engineer" `
                                -Type "invalid-type" -Ref "TASK-001" -Body "test" } |
            Should -Throw
    }

    It "creates the room directory if it doesn't exist" {
        $newRoom = Join-Path $TestDrive "nonexistent-room-$(Get-Random)"
        & $script:PostMessage -RoomDir $newRoom -From "manager" -To "engineer" `
                              -Type "task" -Ref "TASK-001" -Body "Test"
        Test-Path $newRoom | Should -BeTrue
        Test-Path (Join-Path $newRoom "channel.jsonl") | Should -BeTrue
    }

    It "includes message ID format with from-type prefix" {
        $msgId = & $script:PostMessage -RoomDir $script:roomDir -From "qa" -To "manager" `
                                       -Type "fail" -Ref "TASK-001" -Body "Issues found"
        $msgId | Should -Match "^qa-fail-"
    }
}
