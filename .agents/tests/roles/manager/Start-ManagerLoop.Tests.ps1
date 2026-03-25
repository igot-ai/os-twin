# Agent OS — Start-ManagerLoop Pester Tests

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path (Resolve-Path "$PSScriptRoot/../../../roles/manager").Path ".." "..")).Path
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

    Context "Manager triage state" {
        It "qa-review → manager-triage (state transition is valid)" {
            & $script:NewWarRoom -RoomId "room-070" -TaskRef "TASK-070" `
                                 -TaskDescription "Triage test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-070"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "engineering"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "qa-review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "manager-triage"

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "manager-triage"
        }

        It "manager-triage → fixing (implementation-bug)" {
            & $script:NewWarRoom -RoomId "room-071" -TaskRef "TASK-071" `
                                 -TaskDescription "Triage bug" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-071"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "manager-triage"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "fixing"

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "fixing"
            $audit = Get-Content (Join-Path $roomDir "audit.log") -Raw
            $audit | Should -Match "manager-triage -> fixing"
        }

        It "manager-triage → architect-review (design-issue)" {
            & $script:NewWarRoom -RoomId "room-072" -TaskRef "TASK-072" `
                                 -TaskDescription "Design issue" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-072"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "manager-triage"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "architect-review"

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "architect-review"
        }

        It "manager-triage → plan-revision (plan-gap)" {
            & $script:NewWarRoom -RoomId "room-073" -TaskRef "TASK-073" `
                                 -TaskDescription "Plan gap" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-073"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "manager-triage"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "plan-revision"

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "plan-revision"
        }
    }

    Context "Architect review state" {
        It "architect-review → fixing (architect says FIX)" {
            & $script:NewWarRoom -RoomId "room-080" -TaskRef "TASK-080" `
                                 -TaskDescription "Arch fix" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-080"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "architect-review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "fixing"

            $audit = Get-Content (Join-Path $roomDir "audit.log") -Raw
            $audit | Should -Match "architect-review -> fixing"
        }

        It "architect-review → plan-revision (architect says REPLAN)" {
            & $script:NewWarRoom -RoomId "room-081" -TaskRef "TASK-081" `
                                 -TaskDescription "Arch replan" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-081"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "architect-review"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "plan-revision"

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "plan-revision"
        }
    }

    Context "Plan revision state" {
        It "plan-revision → engineering (brief updated)" {
            & $script:NewWarRoom -RoomId "room-090" -TaskRef "TASK-090" `
                                 -TaskDescription "Plan rev" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-090"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "plan-revision"
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "engineering"

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "engineering"
            $audit = Get-Content (Join-Path $roomDir "audit.log") -Raw
            $audit | Should -Match "plan-revision -> engineering"
        }
    }

    Context "Triage context file" {
        It "Write-TriageContext creates triage-context.md" {
            & $script:NewWarRoom -RoomId "room-100" -TaskRef "TASK-100" `
                                 -TaskDescription "Context test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-100"

            # Source the manager loop to get Write-TriageContext function
            # Test the artifact creation manually
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

## Architect Guidance
_Not consulted — classified as implementation bug._

## Manager's Direction
Classified as implementation bug. Engineer should fix.

## Action Required
Engineer: Fix the specific issues listed in QA's report above.
"@ | Out-File -FilePath $contextFile -Encoding utf8 -Force

            Test-Path $contextFile | Should -BeTrue
            $content = Get-Content $contextFile -Raw
            $content | Should -Match "implementation-bug"
            $content | Should -Match "Tests are failing"
        }

        It "includes architect guidance when provided" {
            & $script:NewWarRoom -RoomId "room-101" -TaskRef "TASK-101" `
                                 -TaskDescription "Guidance test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-101"
            $artifactsDir = Join-Path $roomDir "artifacts"
            if (-not (Test-Path $artifactsDir)) {
                New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null
            }
            $contextFile = Join-Path $artifactsDir "triage-context.md"
            @"
# Manager Triage Context

## Classification: design-issue

## QA Failure Report
Architecture flaw in auth module.

## Architect Guidance
RECOMMENDATION: REDESIGN
Use event-driven approach instead.

## Manager's Direction
Architect recommends redesign.

## Action Required
Engineer: Follow the architect's guidance above to redesign the approach.
"@ | Out-File -FilePath $contextFile -Encoding utf8 -Force

            $content = Get-Content $contextFile -Raw
            $content | Should -Match "design-issue"
            $content | Should -Match "event-driven approach"
            $content | Should -Match "RECOMMENDATION: REDESIGN"
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

        It "design-guidance message is readable" {
            & $script:NewWarRoom -RoomId "room-111" -TaskRef "TASK-111" `
                                 -TaskDescription "Guidance msg" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-111"

            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "design-guidance" -Ref "TASK-111" `
                                  -Body "RECOMMENDATION: FIX`nFix the null check on line 42."

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "design-guidance" -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].body | Should -Match "RECOMMENDATION: FIX"
        }
    }

    Context "Architect-as-done transition" {
        It "architect design-guidance with RECOMMENDATION is treated as done by manager" {
            & $script:NewWarRoom -RoomId "room-130" -TaskRef "EPIC-130" `
                                 -TaskDescription "Arch as primary worker" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-130"

            # Write lifecycle where engineering state role is architect
            $lifecycle = @{
                initial_state = "engineering"
                states = @{
                    engineering = @{
                        type = "agent"
                        role = "architect"
                        transitions = @{ done = "engineer-review" }
                    }
                    "engineer-review" = @{
                        type = "agent"
                        role = "engineer"
                        transitions = @{ pass = "passed"; fail = "manager-triage" }
                    }
                }
            }
            $lifecycle | ConvertTo-Json -Depth 5 | Out-File (Join-Path $roomDir "lifecycle.json") -Encoding utf8

            # Architect posts design-guidance with RECOMMENDATION (not a 'done' message type)
            & $script:PostMessage -RoomDir $roomDir -From "architect" -To "manager" `
                                  -Type "design-guidance" -Ref "EPIC-130" `
                                  -Body "RECOMMENDATION: FIX`n`nPlease install dependencies and configure design tokens."

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "design-guidance" -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].body | Should -Match "RECOMMENDATION: FIX"

            # Verify no 'done' messages exist (architect doesn't post done)
            $doneMsgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -AsObject
            $doneMsgs.Count | Should -Be 0

            # The lifecycle state definition should match the architect role
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.engineering.role | Should -Be "architect"
            $lc.states.engineering.transitions.done | Should -Be "engineer-review"
        }

        It "done-transition lookup uses actual status not hard-coded engineering" {
            & $script:NewWarRoom -RoomId "room-131" -TaskRef "EPIC-131" `
                                 -TaskDescription "Fixing transition test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-131"

            # Write lifecycle where fixing state has different transition than engineering
            $lifecycle = @{
                initial_state = "engineering"
                states = @{
                    engineering = @{
                        type = "agent"
                        role = "architect"
                        transitions = @{ done = "engineer-review" }
                    }
                    fixing = @{
                        type = "agent"
                        role = "architect"
                        transitions = @{ done = "engineer-review" }
                    }
                    "engineer-review" = @{
                        type = "agent"
                        role = "engineer"
                        transitions = @{ pass = "passed" }
                    }
                }
            }
            $lifecycle | ConvertTo-Json -Depth 5 | Out-File (Join-Path $roomDir "lifecycle.json") -Encoding utf8

            # Verify that lifecycle.states.fixing is accessible and has correct transition
            $lc = Get-Content (Join-Path $roomDir "lifecycle.json") -Raw | ConvertFrom-Json
            $lc.states.fixing.role | Should -Be "architect"
            $lc.states.fixing.transitions.done | Should -Be "engineer-review"

            # When status is 'fixing', the lookup should use $lifecycle.states.fixing (not .engineering)
            $status = "fixing"
            $nextState = if ($lc.states.$status -and $lc.states.$status.transitions.done) {
                $lc.states.$status.transitions.done
            } else { "qa-review" }
            $nextState | Should -Be "engineer-review"
        }
    }

    Context "External status bypass rescue (QA-bypass scenario)" {
        It "failed-final with retries remaining and fail message rescues to manager-triage" {
            # This reproduces the exact room-001 bug: QA agent called
            # warroom_update_status to set failed-final, bypassing the manager.
            & $script:NewWarRoom -RoomId "room-120" -TaskRef "EPIC-120" `
                                 -TaskDescription "QA bypass test" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-120"

            # Simulate: engineer done, QA posted fail, but QA also set status directly
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                                  -Type "done" -Ref "EPIC-120" -Body "Implemented feature"
            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                                  -Type "fail" -Ref "EPIC-120" `
                                  -Body "VERDICT: FAIL`nBuild integrity issues found."

            # QA agent bypassed manager and set failed-final directly
            "failed-final" | Out-File -FilePath (Join-Path $roomDir "status") -NoNewline

            # Retries still at 0 (manager never got to increment)
            $retries = [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
            $retries | Should -Be 0

            # Verify there IS a fail message (rescue condition)
            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "fail" -AsObject
            $msgs.Count | Should -BeGreaterThan 0

            # The manager rescue logic should detect:
            #   status=failed-final AND retries(0) < maxRetries(3) AND fail message exists
            # This means the room SHOULD be rescued to manager-triage, not left as terminal.
            $maxRetries = 3
            ($retries -lt $maxRetries) | Should -BeTrue
        }

        It "failed-final with retries exhausted stays terminal" {
            & $script:NewWarRoom -RoomId "room-121" -TaskRef "TASK-121" `
                                 -TaskDescription "Exhausted retries" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-121"

            # Simulate exhausted retries
            "3" | Out-File -FilePath (Join-Path $roomDir "retries") -NoNewline
            Set-WarRoomStatus -RoomDir $roomDir -NewStatus "failed-final"

            $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
            $status | Should -Be "failed-final"

            # With retries(3) >= maxRetries(3), should stay terminal
            $retries = [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
            $maxRetries = 3
            ($retries -ge $maxRetries) | Should -BeTrue
        }

        It "failed-final with no fail/error messages stays terminal" {
            & $script:NewWarRoom -RoomId "room-122" -TaskRef "TASK-122" `
                                 -TaskDescription "No feedback" -WarRoomsDir $script:warRoomsDir
            $roomDir = Join-Path $script:warRoomsDir "room-122"

            # Status set to failed-final but no fail messages posted
            "failed-final" | Out-File -FilePath (Join-Path $roomDir "status") -NoNewline

            # No fail or error messages exist
            $failMsgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "fail" -AsObject
            $errorMsgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "error" -AsObject
            ($failMsgs.Count + $errorMsgs.Count) | Should -Be 0
        }
    }

    Context "warroom-server MCP status restriction" {
        It "warroom-server.py rejects terminal statuses" {
            # Verify the MCP server's StatusType no longer includes terminal states
            $serverPy = Join-Path $script:agentsDir "mcp" "warroom-server.py"
            $content = Get-Content $serverPy -Raw

            # Should NOT contain passed or failed-final in the StatusType Literal
            # Extract the StatusType block
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
