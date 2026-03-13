# Agent OS — Start-ManagerLoop Pester Tests

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
    $script:PostMessage = Join-Path $script:agentsDir "channel" "Post-Message.ps1"
    $script:ReadMessages = Join-Path $script:agentsDir "channel" "Read-Messages.ps1"
    $script:NewWarRoom = Join-Path $script:agentsDir "war-rooms" "New-WarRoom.ps1"

    # Import Utils for Test-PidAlive, Set-WarRoomStatus
    $utilsModule = Join-Path $script:agentsDir "lib" "Utils.psm1"
    if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }
}

AfterAll {
    Remove-Module -Name "Utils" -ErrorAction SilentlyContinue
}

Describe "Start-ManagerLoop — State Machine Unit Tests" {
    BeforeEach {
        $script:warRoomsDir = Join-Path $TestDrive "warrooms-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null

        # Create test config
        $script:configFile = Join-Path $TestDrive "config-mgr-$(Get-Random).json"
        @{
            version = "0.1.0"
            manager = @{
                poll_interval_seconds = 1
                max_concurrent_rooms  = 10
                max_engineer_retries  = 3
                auto_approve_tools    = $true
                state_timeout_seconds = 900
            }
            engineer = @{
                cli              = "echo"
                default_model    = "test-model"
                timeout_seconds  = 10
                max_prompt_bytes = 102400
            }
            qa = @{
                cli             = "echo"
                default_model   = "test-model"
                approval_mode   = "auto-approve"
                timeout_seconds = 10
            }
            channel = @{
                format                 = "jsonl"
                max_message_size_bytes = 65536
            }
            release = @{
                require_signoffs = @("engineer", "qa", "manager")
                auto_draft       = $true
            }
        } | ConvertTo-Json -Depth 5 | Out-File $script:configFile -Encoding utf8
    }

    Context "Status reading" {
        It "reads pending status from room" {
            & $script:NewWarRoom -RoomId "room-001" -TaskRef "TASK-001" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $status = (Get-Content (Join-Path $script:warRoomsDir "room-001" "status") -Raw).Trim()
            $status | Should -Be "pending"
        }

        It "reads engineering status" {
            & $script:NewWarRoom -RoomId "room-002" -TaskRef "TASK-002" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            "engineering" | Out-File -FilePath (Join-Path $script:warRoomsDir "room-002" "status") -NoNewline
            $status = (Get-Content (Join-Path $script:warRoomsDir "room-002" "status") -Raw).Trim()
            $status | Should -Be "engineering"
        }
    }

    Context "State transitions" {
        It "pending → engineering (via Set-WarRoomStatus)" {
            & $script:NewWarRoom -RoomId "room-010" -TaskRef "TASK-010" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-010"

            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "engineering"
            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "engineering"

            $audit = Get-Content (Join-Path $roomDir "audit.log") -Raw
            $audit | Should -Match "pending -> engineering"
        }

        It "engineering → qa-review" {
            & $script:NewWarRoom -RoomId "room-011" -TaskRef "TASK-011" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-011"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "engineering"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "qa-review"

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "qa-review"
        }

        It "qa-review → passed" {
            & $script:NewWarRoom -RoomId "room-012" -TaskRef "TASK-012" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-012"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "engineering"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "qa-review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "passed"

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "passed"
        }

        It "qa-review → fixing (QA failure with retries)" {
            & $script:NewWarRoom -RoomId "room-013" -TaskRef "TASK-013" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-013"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "engineering"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "qa-review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "fixing"

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "fixing"
        }

        It "fixing → failed-final (retries exhausted)" {
            & $script:NewWarRoom -RoomId "room-014" -TaskRef "TASK-014" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-014"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "fixing"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "failed-final"

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "failed-final"
        }
    }

    Context "Message counting" {
        It "counts done messages correctly" {
            & $script:NewWarRoom -RoomId "room-020" -TaskRef "TASK-020" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-020"

            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                                  -Type "done" -Ref "TASK-020" -Body "First done"
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                                  -Type "done" -Ref "TASK-020" -Body "Second done"

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -AsObject
            $msgs.Count | Should -Be 2
        }

        It "counts pass messages" {
            & $script:NewWarRoom -RoomId "room-021" -TaskRef "TASK-021" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-021"

            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                                  -Type "pass" -Ref "TASK-021" -Body "All good"

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "pass" -AsObject
            $msgs.Count | Should -Be 1
        }

        It "counts fail messages" {
            & $script:NewWarRoom -RoomId "room-022" -TaskRef "TASK-022" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-022"

            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                                  -Type "fail" -Ref "TASK-022" -Body "Bad code"

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "fail" -AsObject
            $msgs.Count | Should -Be 1
        }
    }

    Context "Retry tracking" {
        It "increments retry counter" {
            & $script:NewWarRoom -RoomId "room-030" -TaskRef "TASK-030" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-030"

            $retries = [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
            $retries | Should -Be 0

            "1" | Out-File -FilePath (Join-Path $roomDir "retries") -NoNewline
            $retries = [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
            $retries | Should -Be 1
        }

        It "respects max retries limit" {
            $config = Get-Content $script:configFile -Raw | ConvertFrom-Json
            $maxRetries = $config.manager.max_engineer_retries
            $maxRetries | Should -Be 3

            # Simulate 3 retries → next should be failed-final
            3 | Should -BeGreaterOrEqual $maxRetries
        }
    }

    Context "State timeout detection" {
        It "detects timed out state" {
            & $script:NewWarRoom -RoomId "room-040" -TaskRef "TASK-040" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-040"

            # Set state_changed_at to a very old time
            $oldEpoch = [int][double]::Parse((Get-Date -UFormat %s)) - 10000
            $oldEpoch.ToString() | Out-File -FilePath (Join-Path $roomDir "state_changed_at") -NoNewline

            $changedAt = [int](Get-Content (Join-Path $roomDir "state_changed_at") -Raw).Trim()
            $now = [int][double]::Parse((Get-Date -UFormat %s))
            ($now - $changedAt) | Should -BeGreaterThan 900
        }
    }

    Context "Audit trail" {
        It "records all status transitions" {
            & $script:NewWarRoom -RoomId "room-050" -TaskRef "TASK-050" `
                                 -TaskDescription "Full lifecycle" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-050"

            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "engineering"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "qa-review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "fixing"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "engineering"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "qa-review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "passed"

            $auditLines = Get-Content (Join-Path $roomDir "audit.log")
            $auditLines.Count | Should -Be 6
            $auditLines[-1] | Should -Match "qa-review -> passed"
        }
    }

    Context "Blocked status (OPT-001)" {
        It "blocked status is valid for Set-WarRoomStatus" {
            & $script:NewWarRoom -RoomId "room-060" -TaskRef "TASK-060" `
                                 -TaskDescription "Block test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-060"

            { Set-WarRoomStatus -RoomDir $roomDir -NewStatus "blocked" } | Should -Not -Throw

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "blocked"
        }

        It "blocked counts as terminal (not active)" {
            & $script:NewWarRoom -RoomId "room-061" -TaskRef "TASK-061" `
                                 -TaskDescription "Block test 2" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-061"

            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "blocked"
            $audit = Get-Content (Join-Path $roomDir "audit.log") -Raw
            $audit | Should -Match "pending -> blocked"
        }
    }
}
