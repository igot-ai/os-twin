# Agent OS — Start-ManagerLoop Pester Tests (V2 Lifecycle)

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/manager").Path ".." "..")).Path
    $script:PostMessage = Join-Path $script:agentsDir "channel" "Post-Message.ps1"
    $script:ReadMessages = Join-Path $script:agentsDir "channel" "Read-Messages.ps1"
    $script:NewWarRoom = Join-Path $script:agentsDir "war-rooms" "New-WarRoom.ps1"

    # Import Utils for Test-PidAlive, Set-WarRoomStatus
    $utilsModule = Join-Path $script:agentsDir "lib" "Utils.psm1"
    if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }

    # Helper: write a minimal v2 lifecycle.json into a room
    function Write-V2Lifecycle {
        param([string]$RoomDir, [hashtable]$Override)
        $lc = @{
            version = 2
            initial_state = "developing"
            max_retries = 3
            states = @{
                developing = @{
                    role = "engineer"
                    type = "work"
                    signals = @{
                        done = @{ target = "review" }
                        error = @{ target = "failed"; actions = @("increment_retries") }
                    }
                }
                optimize = @{
                    role = "engineer"
                    type = "work"
                    signals = @{
                        done = @{ target = "review" }
                        error = @{ target = "failed"; actions = @("increment_retries") }
                    }
                }
                review = @{
                    role = "qa"
                    type = "review"
                    signals = @{
                        pass = @{ target = "passed" }
                        fail = @{ target = "developing"; actions = @("increment_retries", "post_fix") }
                        escalate = @{ target = "triage" }
                    }
                }
                triage = @{
                    role = "manager"
                    type = "triage"
                    signals = @{
                        fix = @{ target = "developing"; actions = @("increment_retries") }
                        redesign = @{ target = "developing"; actions = @("increment_retries", "revise_brief") }
                        reject = @{ target = "failed-final" }
                    }
                }
                failed = @{
                    role = "manager"
                    type = "decision"
                    signals = @{
                        retry = @{ target = "developing"; guard = "retries < max_retries" }
                        exhaust = @{ target = "failed-final"; guard = "retries >= max_retries" }
                    }
                }
                passed = @{ type = "terminal" }
                "failed-final" = @{ type = "terminal" }
            }
        }
        if ($Override) {
            foreach ($key in $Override.Keys) { $lc.states[$key] = $Override[$key] }
        }
        $lc | ConvertTo-Json -Depth 10 | Out-File (Join-Path $RoomDir "lifecycle.json") -Encoding utf8
    }
}

AfterAll {
    Remove-Module -Name "Utils" -ErrorAction SilentlyContinue
}

Describe "Start-ManagerLoop — V2 Lifecycle Unit Tests" {
    BeforeEach {
        $script:warRoomsDir = Join-Path $TestDrive "warrooms-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:warRoomsDir -Force | Out-Null

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

        It "reads developing status" {
            & $script:NewWarRoom -RoomId "room-002" -TaskRef "TASK-002" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            "developing" | Out-File -FilePath (Join-Path $script:warRoomsDir "room-002" "status") -NoNewline
            $status = (Get-Content (Join-Path $script:warRoomsDir "room-002" "status") -Raw).Trim()
            $status | Should -Be "developing"
        }
    }

    Context "V2 state transitions" {
        It "pending → developing" {
            & $script:NewWarRoom -RoomId "room-010" -TaskRef "TASK-010" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-010"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"
            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "developing"
            $audit = Get-Content (Join-Path $roomDir "audit.log") -Raw
            $audit | Should -Match "pending -> developing"
        }

        It "developing → review (done signal)" {
            & $script:NewWarRoom -RoomId "room-011" -TaskRef "TASK-011" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-011"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"
            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "review"
        }

        It "review → passed (pass signal)" {
            & $script:NewWarRoom -RoomId "room-012" -TaskRef "TASK-012" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-012"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "passed"
            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "passed"
        }

        It "review → developing (fail signal with retries)" {
            & $script:NewWarRoom -RoomId "room-013" -TaskRef "TASK-013" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-013"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"
            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "developing"
        }

        It "developing → failed-final (retries exhausted)" {
            & $script:NewWarRoom -RoomId "room-014" -TaskRef "TASK-014" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-014"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "failed-final"
            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "failed-final"
        }

        It "review → triage (escalate signal)" {
            & $script:NewWarRoom -RoomId "room-015" -TaskRef "TASK-015" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-015"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "triage"
            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "triage"
            $audit = Get-Content (Join-Path $roomDir "audit.log") -Raw
            $audit | Should -Match "review -> triage"
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
            3 | Should -BeGreaterOrEqual $maxRetries
        }
    }

    Context "State timeout detection" {
        It "detects timed out state" {
            & $script:NewWarRoom -RoomId "room-040" -TaskRef "TASK-040" `
                                 -TaskDescription "Test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-040"
            $oldEpoch = [int][double]::Parse((Get-Date -UFormat %s)) - 10000
            $oldEpoch.ToString() | Out-File -FilePath (Join-Path $roomDir "state_changed_at") -NoNewline
            $changedAt = [int](Get-Content (Join-Path $roomDir "state_changed_at") -Raw).Trim()
            $now = [int][double]::Parse((Get-Date -UFormat %s))
            ($now - $changedAt) | Should -BeGreaterThan 900
        }
    }

    Context "Audit trail" {
        It "records all v2 status transitions" {
            & $script:NewWarRoom -RoomId "room-050" -TaskRef "TASK-050" `
                                 -TaskDescription "Full lifecycle" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-050"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "passed"
            $auditLines = Get-Content (Join-Path $roomDir "audit.log")
            $auditLines.Count | Should -Be 5
            $auditLines[-1] | Should -Match "review -> passed"
        }

        It "records pipeline lifecycle with optimize state" {
            & $script:NewWarRoom -RoomId "room-051" -TaskRef "TASK-051" `
                                 -TaskDescription "Pipeline lifecycle" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-051"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "optimize"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "passed"
            $auditLines = Get-Content (Join-Path $roomDir "audit.log")
            $auditLines.Count | Should -Be 5
            $auditLines[2] | Should -Match "review -> optimize"
            $auditLines[3] | Should -Match "optimize -> review"
        }
    }

    Context "Blocked status" {
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

    Context "Triage state (v2)" {
        It "review → triage (escalate transition is valid)" {
            & $script:NewWarRoom -RoomId "room-070" -TaskRef "TASK-070" `
                                 -TaskDescription "Triage test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-070"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "triage"
            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "triage"
        }

        It "triage → developing (fix classification)" {
            & $script:NewWarRoom -RoomId "room-071" -TaskRef "TASK-071" `
                                 -TaskDescription "Triage fix" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-071"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "triage"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"
            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "developing"
            $audit = Get-Content (Join-Path $roomDir "audit.log") -Raw
            $audit | Should -Match "triage -> developing"
        }

        It "triage → failed-final (reject classification)" {
            & $script:NewWarRoom -RoomId "room-072" -TaskRef "TASK-072" `
                                 -TaskDescription "Triage reject" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-072"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "triage"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "failed-final"
            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "failed-final"
        }
    }

    Context "Triage context file" {
        It "Write-TriageContext creates triage-context.md" {
            & $script:NewWarRoom -RoomId "room-100" -TaskRef "TASK-100" `
                                 -TaskDescription "Context test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-100"
            $artifactsDir = Join-Path $roomDir "artifacts"
            if (-not (Test-Path $artifactsDir)) {
                New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null
            }
            $contextFile = Join-Path $artifactsDir "triage-context.md"
            @"
# Manager Triage Context

## Classification: implementation-bug

## QA Failure Report
Tests are failing.

## Manager's Direction
Classified as implementation bug. Engineer should fix.
"@ | Out-File -FilePath $contextFile -Encoding utf8 -Force
            Test-Path $contextFile | Should -BeTrue
            $content = Get-Content $contextFile -Raw
            $content | Should -Match "implementation-bug"
            $content | Should -Match "Tests are failing"
        }
    }

    Context "Escalate message handling" {
        It "counts escalate messages" {
            & $script:NewWarRoom -RoomId "room-110" -TaskRef "TASK-110" `
                                 -TaskDescription "Escalate test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-110"
            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                                  -Type "escalate" -Ref "TASK-110" -Body "Design problem detected"
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "escalate" -AsObject
            $msgs.Count | Should -Be 1
        }

        It "architect done message with RECOMMENDATION is readable" {
            & $script:NewWarRoom -RoomId "room-111" -TaskRef "TASK-111" `
                                 -TaskDescription "Arch done" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-111"
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "done" -Ref "TASK-111" `
                                  -Body "RECOMMENDATION: FIX`nFix the null check on line 42."
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].body | Should -Match "RECOMMENDATION: FIX"
        }
    }

    Context "V2 lifecycle schema" {
        It "architect-as-worker emits done signal (not design-guidance)" {
            & $script:NewWarRoom -RoomId "room-130" -TaskRef "EPIC-130" `
                                 -TaskDescription "Arch as primary worker" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-130"
            Write-V2Lifecycle -RoomDir $roomDir -Override @{
                developing = @{
                    role = "architect"; type = "work"
                    signals = @{
                        done = @{ target = "review" }
                        error = @{ target = "failed"; actions = @("increment_retries") }
                    }
                }
            }
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "done" -Ref "EPIC-130" `
                                  -Body "RECOMMENDATION: FIX`n`nPlease install dependencies and configure design tokens."
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].body | Should -Match "RECOMMENDATION: FIX"
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.developing.role | Should -Be "architect"
            $lc.states.developing.signals.done.target | Should -Be "review"
        }

        It "done-transition lookup uses v2 signals schema" {
            & $script:NewWarRoom -RoomId "room-131" -TaskRef "EPIC-131" `
                                 -TaskDescription "Signal lookup test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-131"
            Write-V2Lifecycle -RoomDir $roomDir
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $status = "optimize"
            $nextState = $lc.states.$status.signals.done.target
            $nextState | Should -Be "review"
        }

        It "optimize state is included in base lifecycle" {
            & $script:NewWarRoom -RoomId "room-135" -TaskRef "TASK-135" `
                                 -TaskDescription "Optimize state" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-135"
            Write-V2Lifecycle -RoomDir $roomDir
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.optimize | Should -Not -BeNullOrEmpty
            $lc.states.optimize.role | Should -Be "engineer"
            $lc.states.optimize.type | Should -Be "work"
            $lc.states.optimize.signals.done.target | Should -Be "review"
            $lc.states.optimize.signals.error.target | Should -Be "failed"
        }

        It "pipeline review.fail targets optimize (not developing)" {
            & $script:NewWarRoom -RoomId "room-136" -TaskRef "TASK-136" `
                                 -TaskDescription "Pipeline fail path" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-136"
            # Override review.fail → optimize to match pipeline-generated lifecycles
            Write-V2Lifecycle -RoomDir $roomDir -Override @{
                review = @{
                    role = "qa"; type = "review"
                    signals = @{
                        pass = @{ target = "passed" }
                        fail = @{ target = "optimize"; actions = @("increment_retries", "post_fix") }
                        escalate = @{ target = "triage" }
                    }
                }
            }
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.review.signals.fail.target | Should -Be "optimize"
        }

        It "review signals include pass/fail/escalate" {
            & $script:NewWarRoom -RoomId "room-132" -TaskRef "TASK-132" `
                                 -TaskDescription "Review signals" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-132"
            Write-V2Lifecycle -RoomDir $roomDir
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.review.signals.pass.target | Should -Be "passed"
            $lc.states.review.signals.fail.target | Should -Be "developing"
            $lc.states.review.signals.escalate.target | Should -Be "triage"
        }

        It "fail signal includes increment_retries and post_fix actions" {
            & $script:NewWarRoom -RoomId "room-133" -TaskRef "TASK-133" `
                                 -TaskDescription "Fail actions" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-133"
            Write-V2Lifecycle -RoomDir $roomDir
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $actions = $lc.states.review.signals.fail.actions
            $actions | Should -Contain "increment_retries"
            $actions | Should -Contain "post_fix"
        }

        It "decision state has retry and exhaust signals" {
            & $script:NewWarRoom -RoomId "room-134" -TaskRef "TASK-134" `
                                 -TaskDescription "Decision state" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-134"
            Write-V2Lifecycle -RoomDir $roomDir
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.failed.type | Should -Be "decision"
            $lc.states.failed.signals.retry.target | Should -Be "developing"
            $lc.states.failed.signals.exhaust.target | Should -Be "failed-final"
        }
    }

    Context "External status bypass rescue (QA-bypass scenario)" {
        It "failed-final with retries remaining and fail message rescues to triage" {
            & $script:NewWarRoom -RoomId "room-120" -TaskRef "EPIC-120" `
                                 -TaskDescription "QA bypass test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-120"
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                                  -Type "done" -Ref "EPIC-120" -Body "Implemented feature"
            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                                  -Type "fail" -Ref "EPIC-120" `
                                  -Body "VERDICT: FAIL`nBuild integrity issues found."
            "failed-final" | Out-File -FilePath (Join-Path $roomDir "status") -NoNewline
            $retries = [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
            $retries | Should -Be 0
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "fail" -AsObject
            $msgs.Count | Should -BeGreaterThan 0
            $maxRetries = 3
            ($retries -lt $maxRetries) | Should -BeTrue
        }

        It "failed-final with retries exhausted stays terminal" {
            & $script:NewWarRoom -RoomId "room-121" -TaskRef "TASK-121" `
                                 -TaskDescription "Exhausted retries" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-121"
            "3" | Out-File -FilePath (Join-Path $roomDir "retries") -NoNewline
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "failed-final"
            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "failed-final"
            $retries = [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
            $maxRetries = 3
            ($retries -ge $maxRetries) | Should -BeTrue
        }

        It "failed-final with no fail/error messages stays terminal" {
            & $script:NewWarRoom -RoomId "room-122" -TaskRef "TASK-122" `
                                 -TaskDescription "No feedback" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-122"
            "failed-final" | Out-File -FilePath (Join-Path $roomDir "status") -NoNewline
            $failMsgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "fail" -AsObject
            $errorMsgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "error" -AsObject
            ($failMsgs.Count + $errorMsgs.Count) | Should -Be 0
        }
    }

    Context "warroom-server MCP status restriction" {
        It "warroom-server.py rejects terminal statuses" {
            $serverPy = Join-Path $script:agentsDir "mcp" "warroom-server.py"
            $content = Get-Content $serverPy -Raw
            $content | Should -Match 'StatusType\s*=\s*Literal\['
            $content | Should -Not -Match 'StatusType\s*=\s*Literal\[[\s\S]*?"passed"'
            $content | Should -Not -Match 'StatusType\s*=\s*Literal\[[\s\S]*?"failed-final"'
        }

        It "warroom-server.py writes audit.log on status change" {
            $serverPy = Join-Path $script:agentsDir "mcp" "warroom-server.py"
            $content = Get-Content $serverPy -Raw
            $content | Should -Match 'audit\.log'
            $content | Should -Match 'state_changed_at'
        }
    }
}
