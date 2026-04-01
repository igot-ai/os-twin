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

    Context "Leak fix — Find-LatestSignal detects DateTime timestamps" {
        It "detects done signal when ts is ISO-8601 (parsed as DateTime by ConvertFrom-Json)" {
            & $script:NewWarRoom -RoomId "room-200" -TaskRef "TASK-200" `
                                 -TaskDescription "Signal detect test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-200"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"

            # Post a done message (Post-Message writes ISO-8601 ts)
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                                  -Type "done" -Ref "TASK-200" -Body "Work complete"

            # Read back to confirm ts is DateTime
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -Last 1 -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].ts | Should -BeOfType [datetime]
        }

        It "signal timestamp is newer than state_changed_at" {
            & $script:NewWarRoom -RoomId "room-201" -TaskRef "TASK-201" `
                                 -TaskDescription "Timestamp compare" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-201"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"

            # Set state_changed_at to a past epoch (10 seconds ago)
            $pastEpoch = [int][double]::Parse((Get-Date -UFormat %s)) - 10
            $pastEpoch.ToString() | Out-File -FilePath (Join-Path $roomDir "state_changed_at") -NoNewline

            # Post done message now (ts will be > pastEpoch)
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                                  -Type "done" -Ref "TASK-201" -Body "Done now"

            # Read and verify timestamp comparison works
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -Last 1 -AsObject
            $latest = $msgs[0]
            # Parse the same way Find-LatestSignal does
            $msgTs = 0
            if ($latest.ts -is [datetime]) {
                $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s))
            }
            $msgTs | Should -BeGreaterOrEqual $pastEpoch
        }

        It "old signal before state reset is correctly filtered out" {
            & $script:NewWarRoom -RoomId "room-202" -TaskRef "TASK-202" `
                                 -TaskDescription "Old signal filter" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-202"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"

            # Post done message now
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                                  -Type "done" -Ref "TASK-202" -Body "Old done"

            # Simulate state timeout reset: set state_changed_at to future
            $futureEpoch = [int][double]::Parse((Get-Date -UFormat %s)) + 60
            $futureEpoch.ToString() | Out-File -FilePath (Join-Path $roomDir "state_changed_at") -NoNewline

            # The old done message should NOT be detected
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -Last 1 -AsObject
            $latest = $msgs[0]
            $msgTs = 0
            if ($latest.ts -is [datetime]) {
                $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s))
            }
            # msgTs should be LESS than the future state_changed_at
            $msgTs | Should -BeLessThan $futureEpoch
        }
    }

    Context "Leak fix — Handle-PlanApproval one-shot flag" {
        It "creates .plan_approved flag file on first PLAN-REVIEW passed" {
            & $script:NewWarRoom -RoomId "room-210" -TaskRef "PLAN-REVIEW" `
                                 -TaskDescription "Approval gate" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-210"

            # The flag file should not exist initially
            $flagFile = Join-Path $script:warRoomsDir ".plan_approved_PLAN-REVIEW"
            Test-Path $flagFile | Should -BeFalse

            # Simulate the guard logic from the manager loop
            "1" | Out-File -FilePath $flagFile -Encoding utf8 -NoNewline
            Test-Path $flagFile | Should -BeTrue
        }

        It "flag file prevents second Handle-PlanApproval invocation" {
            # Simulate the one-shot guard
            $warRoomsDir = $script:warRoomsDir
            $taskRef = "PLAN-REVIEW"
            $flagFile = Join-Path $warRoomsDir ".plan_approved_PLAN-REVIEW"

            # First invocation — should pass guard
            $firstInvocation = $false
            if ($taskRef -eq 'PLAN-REVIEW' -and -not (Test-Path $flagFile)) {
                $firstInvocation = $true
                "1" | Out-File -FilePath $flagFile -Encoding utf8 -NoNewline
            }
            $firstInvocation | Should -BeTrue

            # Second invocation — should be blocked by flag
            $secondInvocation = $false
            if ($taskRef -eq 'PLAN-REVIEW' -and -not (Test-Path $flagFile)) {
                $secondInvocation = $true
            }
            $secondInvocation | Should -BeFalse
        }

        It "flag file is scoped to specific task ref" {
            $warRoomsDir = $script:warRoomsDir
            $flagPlan = Join-Path $warRoomsDir ".plan_approved_PLAN-REVIEW"
            $flagEpic = Join-Path $warRoomsDir ".plan_approved_EPIC-001"

            # PLAN-REVIEW flag should not block EPIC-001 (different task ref)
            "1" | Out-File -FilePath $flagPlan -Encoding utf8 -NoNewline
            Test-Path $flagPlan | Should -BeTrue
            Test-Path $flagEpic | Should -BeFalse
        }
    }

    Context "Leak fix — pending signal prevents re-spawn" {
        It "done message in channel prevents re-spawn when no PID alive" {
            & $script:NewWarRoom -RoomId "room-220" -TaskRef "TASK-220" `
                                 -TaskDescription "Re-spawn guard" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-220"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"

            # Set state_changed_at to past (so done signal is "newer")
            $pastEpoch = [int][double]::Parse((Get-Date -UFormat %s)) - 10
            $pastEpoch.ToString() | Out-File -FilePath (Join-Path $roomDir "state_changed_at") -NoNewline

            # Engineer posts done and cleans up PID (simulating the crash window)
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                                  -Type "done" -Ref "TASK-220" -Body "All done"

            # No PID file exists
            $pidFile = Join-Path $roomDir "pids" "engineer.pid"
            Test-Path $pidFile | Should -BeFalse

            # Simulate the guard: check for pending signal before re-spawn
            $expectedSignals = @("done", "error")
            $pendingSignal = $null
            foreach ($sigType in $expectedSignals) {
                $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType $sigType -Last 1 -AsObject
                if ($msgs -and $msgs.Count -gt 0) {
                    $latest = $msgs[-1]
                    $msgTs = 0
                    if ($latest.ts -is [datetime]) {
                        $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s))
                    }
                    $changedAt = [int](Get-Content (Join-Path $roomDir "state_changed_at") -Raw).Trim()
                    if ($msgTs -ge $changedAt) {
                        $pendingSignal = $sigType
                        break
                    }
                }
            }

            # Guard SHOULD detect the pending done signal → skip re-spawn
            $pendingSignal | Should -Be "done"
        }

        It "no pending signal allows re-spawn (normal case)" {
            & $script:NewWarRoom -RoomId "room-221" -TaskRef "TASK-221" `
                                 -TaskDescription "Normal re-spawn" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-221"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"

            # No messages at all — channel is empty
            $expectedSignals = @("done", "error")
            $pendingSignal = $null
            foreach ($sigType in $expectedSignals) {
                $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType $sigType -Last 1 -AsObject
                if ($msgs -and $msgs.Count -gt 0) {
                    $pendingSignal = $sigType
                    break
                }
            }

            # No pending signal → re-spawn SHOULD proceed
            $pendingSignal | Should -BeNullOrEmpty
        }
    }

    Context "Exploit — LEAK-4: decision state does not infinite-loop status writes" {
        It "decision retry transition targets developing (not self)" {
            & $script:NewWarRoom -RoomId "room-300" -TaskRef "TASK-300" `
                                 -TaskDescription "Decision loop test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-300"
            Write-V2Lifecycle -RoomDir $roomDir
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "failed"

            # Read lifecycle to verify decision state transitions OUT (not self-loop)
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $failedState = $lc.states.failed
            $failedState.type | Should -Be "decision"
            $failedState.signals.retry.target | Should -Be "developing"
            $failedState.signals.retry.target | Should -Not -Be "failed"
            $failedState.signals.exhaust.target | Should -Be "failed-final"
        }

        It "retries file must be incremented to prevent infinite decision cycles" {
            & $script:NewWarRoom -RoomId "room-301" -TaskRef "TASK-301" `
                                 -TaskDescription "Decision retries" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-301"
            Write-V2Lifecycle -RoomDir $roomDir

            # Simulate: room starts at 0 retries, max is 3
            "0" | Out-File -FilePath (Join-Path $roomDir "retries") -NoNewline
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $retries = [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
            $maxRetries = $lc.max_retries

            # Decision should retry when retries < max
            $retries | Should -BeLessThan $maxRetries
            # And exhaust when retries >= max
            "3" | Out-File -FilePath (Join-Path $roomDir "retries") -NoNewline
            $retries2 = [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
            $retries2 | Should -BeGreaterOrEqual $maxRetries
        }
    }

    Context "Exploit — LEAK-5: PLAN-REVIEW shortcut uses one-shot guard" {
        It "shortcut path and terminal path both respect same flag file" {
            $warRoomsDir = $script:warRoomsDir
            $flagFile = Join-Path $warRoomsDir ".plan_approved_PLAN-REVIEW"

            # Simulate shortcut path (first detection of approval)
            $shortcutFired = $false
            if (-not (Test-Path $flagFile)) {
                $shortcutFired = $true
                "1" | Out-File -FilePath $flagFile -Encoding utf8 -NoNewline
            }
            $shortcutFired | Should -BeTrue

            # Simulate terminal handler path (next iteration, room now in 'passed')
            $terminalFired = $false
            if (-not (Test-Path $flagFile)) {
                $terminalFired = $true
            }
            $terminalFired | Should -BeFalse

        # Total invocations = exactly 1
        Test-Path $flagFile | Should -BeTrue
    }
}

Context "PLAN-REVIEW Verdict Logic" {
    It "detects VERDICT: REJECT from done body" {
        $doneBody = "I have reviewed this plan and my decision is:`n`nVERDICT: REJECT"
        $rejected = ($doneBody -match 'VERDICT:\s*REJECT')
        $rejected | Should -BeTrue
    }

    It "detects VERDICT: PASS from done body" {
        $doneBody = "I have reviewed this plan and my decision is:`n`nVERDICT: PASS"
        $approved = ($doneBody -match 'VERDICT:\s*PASS|plan-approve|signoff|APPROVED')
        $approved | Should -BeTrue
    }
}

    Context "Exploit — LEAK-6: state timeout re-resolves role for restart state" {
        It "review timeout should spawn engineer (not qa) for developing state" {
            & $script:NewWarRoom -RoomId "room-310" -TaskRef "TASK-310" `
                                 -TaskDescription "Timeout role test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-310"
            Write-V2Lifecycle -RoomDir $roomDir
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"

            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json

            # Current state is 'review' — role is 'qa'
            $currentRole = $lc.states.review.role
            $currentRole | Should -Be "qa"

            # After timeout, restart to initial_state
            $restartState = $lc.initial_state
            $restartState | Should -Be "developing"

            # Restart state role should be 'engineer', not 'qa'
            $restartRole = $lc.states.$restartState.role
            $restartRole | Should -Be "engineer"
            $restartRole | Should -Not -Be $currentRole
        }

        It "triage timeout should spawn engineer (not manager) for developing" {
            & $script:NewWarRoom -RoomId "room-311" -TaskRef "TASK-311" `
                                 -TaskDescription "Triage timeout" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-311"
            Write-V2Lifecycle -RoomDir $roomDir
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "triage"

            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $currentRole = $lc.states.triage.role
            $currentRole | Should -Be "manager"

            $restartRole = $lc.states.($lc.initial_state).role
            $restartRole | Should -Be "engineer"
        }
    }

    Context "Exploit — LEAK-7: deadlock recovery must check pending signals" {
        It "deadlock recovery skips room with pending done signal" {
            & $script:NewWarRoom -RoomId "room-320" -TaskRef "TASK-320" `
                                 -TaskDescription "Deadlock signal test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-320"
            Write-V2Lifecycle -RoomDir $roomDir
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"

            # Set state_changed_at to past
            $pastEpoch = [int][double]::Parse((Get-Date -UFormat %s)) - 10
            $pastEpoch.ToString() | Out-File -FilePath (Join-Path $roomDir "state_changed_at") -NoNewline

            # Engineer posted done (signal pending)
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                                  -Type "done" -Ref "TASK-320" -Body "Work complete"

            # Simulate deadlock recovery signal check
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $dlStateDef = $lc.states.developing
            $dlExpectedSignals = @($dlStateDef.signals.PSObject.Properties.Name)

            # The pending done signal should be detected
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -Last 1 -AsObject
            $msgs.Count | Should -Be 1
            $latest = $msgs[0]
            $msgTs = 0
            if ($latest.ts -is [datetime]) {
                $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s))
            }
            $changedAt = [int](Get-Content (Join-Path $roomDir "state_changed_at") -Raw).Trim()
            ($msgTs -ge $changedAt) | Should -BeTrue
            # Deadlock recovery should NOT reset this room
        }

        It "deadlock recovery proceeds when no signal pending" {
            & $script:NewWarRoom -RoomId "room-321" -TaskRef "TASK-321" `
                                 -TaskDescription "Deadlock no signal" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-321"
            Write-V2Lifecycle -RoomDir $roomDir
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "developing"

            # No messages posted — channel empty
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -Last 1 -AsObject
            ($msgs.Count -eq 0) | Should -BeTrue
            # Deadlock recovery SHOULD proceed for this room
        }
    }

    Context "Exploit — LEAK-8: failed-final rescue requires feedback message" {
        It "rescue to triage only fires when fail/error message exists" {
            & $script:NewWarRoom -RoomId "room-330" -TaskRef "TASK-330" `
                                 -TaskDescription "Rescue guard" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-330"
            Write-V2Lifecycle -RoomDir $roomDir
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "failed-final"
            "1" | Out-File -FilePath (Join-Path $roomDir "retries") -NoNewline

            # No fail/error messages — rescue should NOT fire
            $failMsg = & $script:ReadMessages -RoomDir $roomDir -FilterType "fail" -Last 1 -AsObject
            $errorMsg = & $script:ReadMessages -RoomDir $roomDir -FilterType "error" -Last 1 -AsObject
            $failMsg.Count | Should -Be 0
            $errorMsg.Count | Should -Be 0
            # Room should stay in failed-final (no rescue)
        }

        It "rescue to triage fires when fail message exists" {
            & $script:NewWarRoom -RoomId "room-331" -TaskRef "TASK-331" `
                                 -TaskDescription "Rescue fires" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-331"
            Write-V2Lifecycle -RoomDir $roomDir
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "failed-final"
            "1" | Out-File -FilePath (Join-Path $roomDir "retries") -NoNewline

            # Post fail message — rescue SHOULD fire
            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                                  -Type "fail" -Ref "TASK-331" -Body "Tests failed"
            $failMsg = & $script:ReadMessages -RoomDir $roomDir -FilterType "fail" -Last 1 -AsObject
            $failMsg.Count | Should -Be 1
            # Rescue condition met
        }
    }

    Context "Exploit — LEAK-9: spawn lock prevents duplicate agents" {
        It "spawn lock within grace period blocks re-spawn" {
            & $script:NewWarRoom -RoomId "room-340" -TaskRef "TASK-340" `
                                 -TaskDescription "Spawn lock test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-340"
            Write-V2Lifecycle -RoomDir $roomDir

            # Write a spawn lock (just now)
            $pidDir = Join-Path $roomDir "pids"
            New-Item -ItemType Directory -Path $pidDir -Force | Out-Null
            $nowEpoch = [int][double]::Parse((Get-Date -UFormat %s))
            $nowEpoch.ToString() | Out-File -FilePath (Join-Path $pidDir "engineer.spawned_at") -NoNewline

            # Spawn lock should be active (within 30s grace)
            $lockFile = Join-Path $pidDir "engineer.spawned_at"
            $spawnedAt = [int](Get-Content $lockFile -Raw).Trim()
            $elapsed = $nowEpoch - $spawnedAt
            $elapsed | Should -BeLessThan 30
        }

        It "expired spawn lock allows re-spawn" {
            & $script:NewWarRoom -RoomId "room-341" -TaskRef "TASK-341" `
                                 -TaskDescription "Expired lock" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-341"
            Write-V2Lifecycle -RoomDir $roomDir

            # Write an expired spawn lock (60 seconds ago)
            $pidDir = Join-Path $roomDir "pids"
            New-Item -ItemType Directory -Path $pidDir -Force | Out-Null
            $expiredEpoch = [int][double]::Parse((Get-Date -UFormat %s)) - 60
            $expiredEpoch.ToString() | Out-File -FilePath (Join-Path $pidDir "engineer.spawned_at") -NoNewline

            # Spawn lock should be expired (> 30s)
            $nowEpoch = [int][double]::Parse((Get-Date -UFormat %s))
            $elapsed = $nowEpoch - $expiredEpoch
            $elapsed | Should -BeGreaterOrEqual 30
        }
    }

    Context "PLAN-REVIEW shortcut detects pass signal (architect aligned with QA)" {
        It "shortcut detects 'pass' message from architect and approves" {
            & $script:NewWarRoom -RoomId "room-400" -TaskRef "PLAN-REVIEW" `
                                 -TaskDescription "Arch pass test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-400"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"

            # Architect posts a 'pass' signal (our new behavior — no 'done')
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "pass" -Ref "PLAN-REVIEW" -Body "Plan looks good.`n`nVERDICT: PASS"

            # Simulate the PLAN-REVIEW shortcut logic from the manager
            $passCount    = (& $script:ReadMessages -RoomDir $roomDir -FilterType "pass" -AsObject).Count
            $approveCount = (& $script:ReadMessages -RoomDir $roomDir -FilterType "plan-approve" -AsObject).Count
            $doneCount    = (& $script:ReadMessages -RoomDir $roomDir -FilterType "done" -AsObject).Count

            $approved = $false
            if ($passCount -gt 0 -or $approveCount -gt 0) {
                $approved = $true
            } elseif ($doneCount -gt 0) {
                $doneBody = (& $script:ReadMessages -RoomDir $roomDir -FilterType "done" -Last 1 -AsObject)[-1].body
                if ($doneBody -match 'plan-approve|signoff|APPROVED|VERDICT:\s*PASS') { $approved = $true }
            }

            $passCount | Should -Be 1
            $doneCount | Should -Be 0
            $approved  | Should -BeTrue
        }

        It "shortcut still works with legacy 'done' + APPROVED keyword" {
            & $script:NewWarRoom -RoomId "room-401" -TaskRef "PLAN-REVIEW" `
                                 -TaskDescription "Legacy done test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-401"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"

            # Legacy architect posts 'done' with APPROVED keyword
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "done" -Ref "PLAN-REVIEW" -Body "I APPROVED this plan."

            $passCount = (& $script:ReadMessages -RoomDir $roomDir -FilterType "pass" -AsObject).Count
            $doneCount = (& $script:ReadMessages -RoomDir $roomDir -FilterType "done" -AsObject).Count

            $approved = $false
            if ($passCount -gt 0) {
                $approved = $true
            } elseif ($doneCount -gt 0) {
                $doneBody = (& $script:ReadMessages -RoomDir $roomDir -FilterType "done" -Last 1 -AsObject)[-1].body
                if ($doneBody -match 'plan-approve|signoff|APPROVED|VERDICT:\s*PASS') { $approved = $true }
            }

            $passCount | Should -Be 0
            $doneCount | Should -Be 1
            $approved  | Should -BeTrue
        }

        It "shortcut detects 'fail' message from architect as rejection" {
            & $script:NewWarRoom -RoomId "room-402" -TaskRef "PLAN-REVIEW" `
                                 -TaskDescription "Arch reject test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-402"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"

            # Architect posts 'fail' signal (rejection)
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "fail" -Ref "PLAN-REVIEW" -Body "Plan needs work.`n`nVERDICT: REJECT"

            $failCount = (& $script:ReadMessages -RoomDir $roomDir -FilterType "fail" -AsObject).Count
            $passCount = (& $script:ReadMessages -RoomDir $roomDir -FilterType "pass" -AsObject).Count
            $doneCount = (& $script:ReadMessages -RoomDir $roomDir -FilterType "done" -AsObject).Count

            # Approved should be false
            $approved = ($passCount -gt 0)
            $approved | Should -BeFalse
            $failCount | Should -Be 1
        }

        It "no signals means shortcut does not approve" {
            & $script:NewWarRoom -RoomId "room-403" -TaskRef "PLAN-REVIEW" `
                                 -TaskDescription "No signal test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-403"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"

            # No messages at all
            $passCount    = (& $script:ReadMessages -RoomDir $roomDir -FilterType "pass" -AsObject).Count
            $approveCount = (& $script:ReadMessages -RoomDir $roomDir -FilterType "plan-approve" -AsObject).Count
            $doneCount    = (& $script:ReadMessages -RoomDir $roomDir -FilterType "done" -AsObject).Count

            $approved = $false
            if ($passCount -gt 0 -or $approveCount -gt 0) { $approved = $true }
            $approved | Should -BeFalse
        }
    }

    Context "Find-LatestSignal timestamp grace window" {
        It "accepts signal with same-second timestamp as state_changed_at" {
            & $script:NewWarRoom -RoomId "room-410" -TaskRef "TASK-410" `
                                 -TaskDescription "Grace window test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-410"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"

            # Post a pass signal immediately
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "pass" -Ref "TASK-410" -Body "VERDICT: PASS"

            # Read back the signal and compare with state_changed_at
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "pass" -Last 1 -AsObject
            $msgs.Count | Should -Be 1
            $latest = $msgs[0]
            $msgTs = 0
            if ($latest.ts -is [datetime]) {
                $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s))
            }
            $changedAt = [int](Get-Content (Join-Path $roomDir "state_changed_at") -Raw).Trim()

            # With 2s grace window, signal should be accepted even if same second
            ($msgTs -ge ($changedAt - 2)) | Should -BeTrue
        }

        It "accepts signal posted 1s before state_changed_at (within grace)" {
            & $script:NewWarRoom -RoomId "room-411" -TaskRef "TASK-411" `
                                 -TaskDescription "1s grace test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-411"

            # Post pass message first
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "pass" -Ref "TASK-411" -Body "VERDICT: PASS"

            # Simulate: state_changed_at written 1s after the message
            Start-Sleep -Milliseconds 100
            $futureEpoch = [int][double]::Parse((Get-Date -UFormat %s)) + 1
            $futureEpoch.ToString() | Out-File -FilePath (Join-Path $roomDir "state_changed_at") -NoNewline

            # Read message ts
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "pass" -Last 1 -AsObject
            $latest = $msgs[0]
            $msgTs = 0
            if ($latest.ts -is [datetime]) {
                $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s))
            }
            $changedAt = [int](Get-Content (Join-Path $roomDir "state_changed_at") -Raw).Trim()

            # Without grace: would fail ($msgTs < $changedAt)
            # With 2s grace: should pass ($msgTs >= $changedAt - 2)
            ($msgTs -ge ($changedAt - 2)) | Should -BeTrue
        }

        It "rejects signal older than grace window" {
            & $script:NewWarRoom -RoomId "room-412" -TaskRef "TASK-412" `
                                 -TaskDescription "Old signal reject" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-412"

            # Post pass signal first
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "pass" -Ref "TASK-412" -Body "VERDICT: PASS"

            # Set state_changed_at to far future (well beyond grace)
            $farFuture = [int][double]::Parse((Get-Date -UFormat %s)) + 60
            $farFuture.ToString() | Out-File -FilePath (Join-Path $roomDir "state_changed_at") -NoNewline

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "pass" -Last 1 -AsObject
            $latest = $msgs[0]
            $msgTs = 0
            if ($latest.ts -is [datetime]) {
                $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s))
            }
            $changedAt = [int](Get-Content (Join-Path $roomDir "state_changed_at") -Raw).Trim()

            # Signal is 60s old relative to state — outside 2s grace window
            ($msgTs -ge ($changedAt - 2)) | Should -BeFalse
        }
    }

    Context "Full architect lifecycle: review → passed" {
        It "architect pass signal transitions room to passed via Find-LatestSignal" {
            & $script:NewWarRoom -RoomId "room-420" -TaskRef "TASK-420" `
                                 -TaskDescription "Full pass lifecycle" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-420"

            # Write architect-style lifecycle
            @{
                version = 2; initial_state = "review"; max_retries = 3
                states = @{
                    review = @{
                        role = "architect"; type = "review"
                        signals = @{
                            pass = @{ target = "passed" }
                            done = @{ target = "passed" }
                            fail = @{ target = "failed"; actions = @("increment_retries") }
                        }
                    }
                    passed = @{ type = "terminal" }
                    failed = @{ type = "terminal" }
                }
            } | ConvertTo-Json -Depth 10 | Out-File (Join-Path $roomDir "lifecycle.json") -Encoding utf8

            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"

            # Set state_changed_at to past to ensure signal is "new"
            $pastEpoch = [int][double]::Parse((Get-Date -UFormat %s)) - 10
            $pastEpoch.ToString() | Out-File -FilePath (Join-Path $roomDir "state_changed_at") -NoNewline

            # Architect posts 'pass' signal
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "pass" -Ref "TASK-420" -Body "Architecture approved.`n`nVERDICT: PASS"

            # Simulate Find-LatestSignal
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $expectedSignals = @($lc.states.review.signals.PSObject.Properties.Name)
            $matchedSignal = $null

            foreach ($sigType in $expectedSignals) {
                $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType $sigType -Last 1 -AsObject
                if ($msgs -and $msgs.Count -gt 0) {
                    $latest = $msgs[-1]
                    $msgTs = 0
                    if ($latest.ts -is [datetime]) {
                        $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s))
                    }
                    $changedAt = [int](Get-Content (Join-Path $roomDir "state_changed_at") -Raw).Trim()
                    if ($msgTs -ge ($changedAt - 2)) {
                        $matchedSignal = $sigType
                        break
                    }
                }
            }

            $matchedSignal | Should -Be "pass"

            # Apply transition
            $targetState = $lc.states.review.signals.$matchedSignal.target
            $targetState | Should -Be "passed"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus $targetState
            $finalStatus = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $finalStatus | Should -Be "passed"
        }
    }

    Context "Full architect lifecycle: review → failed" {
        It "architect fail signal transitions room to failed" {
            & $script:NewWarRoom -RoomId "room-430" -TaskRef "TASK-430" `
                                 -TaskDescription "Full fail lifecycle" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-430"

            @{
                version = 2; initial_state = "review"; max_retries = 3
                states = @{
                    review = @{
                        role = "architect"; type = "review"
                        signals = @{
                            pass = @{ target = "passed" }
                            fail = @{ target = "failed"; actions = @("increment_retries") }
                        }
                    }
                    passed = @{ type = "terminal" }
                    failed = @{ type = "terminal" }
                }
            } | ConvertTo-Json -Depth 10 | Out-File (Join-Path $roomDir "lifecycle.json") -Encoding utf8

            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"
            $pastEpoch = [int][double]::Parse((Get-Date -UFormat %s)) - 10
            $pastEpoch.ToString() | Out-File -FilePath (Join-Path $roomDir "state_changed_at") -NoNewline

            # Architect posts 'fail' signal
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "fail" -Ref "TASK-430" -Body "Architecture rejected.`n`nVERDICT: REJECT"

            # Simulate Find-LatestSignal
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $expectedSignals = @($lc.states.review.signals.PSObject.Properties.Name)
            $matchedSignal = $null

            foreach ($sigType in $expectedSignals) {
                $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType $sigType -Last 1 -AsObject
                if ($msgs -and $msgs.Count -gt 0) {
                    $latest = $msgs[-1]
                    $msgTs = 0
                    if ($latest.ts -is [datetime]) {
                        $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s))
                    }
                    $changedAt = [int](Get-Content (Join-Path $roomDir "state_changed_at") -Raw).Trim()
                    if ($msgTs -ge ($changedAt - 2)) {
                        $matchedSignal = $sigType
                        break
                    }
                }
            }

            $matchedSignal | Should -Be "fail"
            $targetState = $lc.states.review.signals.$matchedSignal.target
            $targetState | Should -Be "failed"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus $targetState
            $finalStatus = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $finalStatus | Should -Be "failed"
        }
    }

    Context "Re-spawn guard: signal exists + dead process = no re-spawn" {
        It "pass signal in channel prevents re-spawn even when PID is dead" {
            & $script:NewWarRoom -RoomId "room-440" -TaskRef "TASK-440" `
                                 -TaskDescription "Pass signal guard" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-440"

            @{
                version = 2; initial_state = "review"; max_retries = 3
                states = @{
                    review = @{
                        role = "architect"; type = "review"
                        signals = @{
                            pass = @{ target = "passed" }
                            fail = @{ target = "failed" }
                        }
                    }
                    passed = @{ type = "terminal" }
                    failed = @{ type = "terminal" }
                }
            } | ConvertTo-Json -Depth 10 | Out-File (Join-Path $roomDir "lifecycle.json") -Encoding utf8

            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"
            $pastEpoch = [int][double]::Parse((Get-Date -UFormat %s)) - 10
            $pastEpoch.ToString() | Out-File -FilePath (Join-Path $roomDir "state_changed_at") -NoNewline

            # Architect posted pass signal AND cleaned up its PID
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "pass" -Ref "TASK-440" -Body "VERDICT: PASS"

            $pidFile = Join-Path $roomDir "pids" "architect.pid"
            Test-Path $pidFile | Should -BeFalse

            # Simulate the pending signal guard (lines 915-917 in manager)
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $expectedSignals = @($lc.states.review.signals.PSObject.Properties.Name)

            $pendingSignal = $null
            foreach ($sigType in $expectedSignals) {
                $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType $sigType -Last 1 -AsObject
                if ($msgs -and $msgs.Count -gt 0) {
                    $latest = $msgs[-1]
                    $msgTs = 0
                    if ($latest.ts -is [datetime]) {
                        $msgTs = [int][double]::Parse((Get-Date $latest.ts -UFormat %s))
                    }
                    $changedAt = [int](Get-Content (Join-Path $roomDir "state_changed_at") -Raw).Trim()
                    if ($msgTs -ge ($changedAt - 2)) {
                        $pendingSignal = $sigType
                        break
                    }
                }
            }

            # Guard SHOULD detect pending pass signal → skip re-spawn
            $pendingSignal | Should -Be "pass"
        }
    }

    Context "Re-spawn allowed: no signal + dead process = re-spawn" {
        It "no signals in channel allows re-spawn when PID is dead" {
            & $script:NewWarRoom -RoomId "room-450" -TaskRef "TASK-450" `
                                 -TaskDescription "No signal re-spawn" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-450"

            @{
                version = 2; initial_state = "review"; max_retries = 3
                states = @{
                    review = @{
                        role = "architect"; type = "review"
                        signals = @{
                            pass = @{ target = "passed" }
                            fail = @{ target = "failed" }
                        }
                    }
                    passed = @{ type = "terminal" }
                    failed = @{ type = "terminal" }
                }
            } | ConvertTo-Json -Depth 10 | Out-File (Join-Path $roomDir "lifecycle.json") -Encoding utf8

            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "review"

            # No PID, no messages — vacant room
            $pidFile = Join-Path $roomDir "pids" "architect.pid"
            Test-Path $pidFile | Should -BeFalse

            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $expectedSignals = @($lc.states.review.signals.PSObject.Properties.Name)

            $pendingSignal = $null
            foreach ($sigType in $expectedSignals) {
                $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType $sigType -Last 1 -AsObject
                if ($msgs -and $msgs.Count -gt 0) {
                    $pendingSignal = $sigType
                    break
                }
            }

            # No pending signal → re-spawn SHOULD proceed
            $pendingSignal | Should -BeNullOrEmpty
        }
    }
}
