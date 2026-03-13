# Agent OS — Role Communication Integration Tests
#
# Tests the communication CONTRACT between Manager ↔ Engineer ↔ QA.
# Verifies message formats, routing logic, prompt construction,
# verdict parsing, and retry flow WITHOUT calling real deepagents.

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $script:PostMessage = Join-Path $script:agentsDir "channel" "Post-Message.ps1"
    $script:ReadMessages = Join-Path $script:agentsDir "channel" "Read-Messages.ps1"
    $script:NewWarRoom = Join-Path $script:agentsDir "war-rooms" "New-WarRoom.ps1"

    # Import modules
    $utilsModule = Join-Path $script:agentsDir "lib" "Utils.psm1"
    if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }

    # Helper to create a fully-wired test room
    function New-TestRoom {
        param(
            [string]$RoomId = "room-$(Get-Random)",
            [string]$TaskRef = "TASK-001",
            [string]$Description = "Test task",
            [string]$WarRoomsDir = (Join-Path $TestDrive "wr-$(Get-Random)"),
            [string[]]$DoD = @("Feature working"),
            [string[]]$AC = @("Tests pass")
        )
        New-Item -ItemType Directory -Path $WarRoomsDir -Force | Out-Null
        & $script:NewWarRoom -RoomId $RoomId -TaskRef $TaskRef `
            -TaskDescription $Description -WarRoomsDir $WarRoomsDir `
            -DefinitionOfDone $DoD -AcceptanceCriteria $AC | Out-Null
        return (Join-Path $WarRoomsDir $RoomId)
    }
}

AfterAll {
    Remove-Module -Name "Utils" -ErrorAction SilentlyContinue
}

# ═══════════════════════════════════════════════════════════════════════════════
# 1. MANAGER → ENGINEER COMMUNICATION
# ═══════════════════════════════════════════════════════════════════════════════

Describe "Manager → Engineer Communication" {

    Context "Task assignment (initial spawn)" {
        It "manager posts 'task' message before spawning engineer" {
            $roomDir = New-TestRoom -TaskRef "TASK-100" -Description "Build auth"

            # Manager sends task assignment
            & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
                -Type "task" -Ref "TASK-100" -Body "Implement JWT authentication"

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "task" -AsObject
            # New-WarRoom posts an initial task message, so we expect at least 2
            $msgs.Count | Should -BeGreaterOrEqual 2
            $latest = $msgs[-1]
            $latest.from | Should -Be "manager"
            $latest.to | Should -Be "engineer"
            $latest.type | Should -Be "task"
            $latest.ref | Should -Be "TASK-100"
            $latest.body | Should -Match "JWT"
        }
    }

    Context "Fix routing (after QA failure)" {
        It "manager posts 'fix' message with QA feedback" {
            $roomDir = New-TestRoom -TaskRef "TASK-101"

            # Simulate: engineer done → QA fail → manager routes fix
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                -Type "done" -Ref "TASK-101" -Body "Implemented auth"
            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                -Type "fail" -Ref "TASK-101" -Body "Missing input validation on /login"
            & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
                -Type "fix" -Ref "TASK-101" -Body "Missing input validation on /login"

            $fixes = & $script:ReadMessages -RoomDir $roomDir -FilterType "fix" -AsObject
            $fixes.Count | Should -Be 1
            $fixes[0].from | Should -Be "manager"
            $fixes[0].to | Should -Be "engineer"
            $fixes[0].body | Should -Match "input validation"
        }

        It "fix message is the LATEST message engineer reads" {
            $roomDir = New-TestRoom -TaskRef "TASK-102"

            # Full cycle: task → done → fail → fix
            & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
                -Type "task" -Ref "TASK-102" -Body "Original task"
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                -Type "done" -Ref "TASK-102" -Body "Done first attempt"
            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                -Type "fail" -Ref "TASK-102" -Body "Tests failing"
            & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
                -Type "fix" -Ref "TASK-102" -Body "Fix the tests"

            # Engineer should read the latest task/fix message
            $allMsgs = & $script:ReadMessages -RoomDir $roomDir -AsObject
            $latest = $allMsgs | Where-Object { $_.type -in @('task', 'fix') } |
                Sort-Object { $_.ts } | Select-Object -Last 1
            $latest.type | Should -Be "fix"
            $latest.body | Should -Be "Fix the tests"
        }
    }

    Context "Timeout recovery message" {
        It "manager posts fix message on timeout with timeout info" {
            $roomDir = New-TestRoom -TaskRef "TASK-103"

            & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
                -Type "fix" -Ref "TASK-103" `
                -Body "Previous attempt timed out after 900s. Please try again."

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "fix" -AsObject
            $msgs[0].body | Should -Match "timed out"
            $msgs[0].body | Should -Match "900s"
        }
    }

    Context "Deadlock recovery message" {
        It "manager posts fix message for deadlock recovery" {
            $roomDir = New-TestRoom -TaskRef "TASK-104"

            & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
                -Type "fix" -Ref "TASK-104" `
                -Body "Deadlock recovery: restarting engineer."

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "fix" -AsObject
            $msgs[0].body | Should -Match "Deadlock recovery"
        }
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 2. ENGINEER → MANAGER COMMUNICATION
# ═══════════════════════════════════════════════════════════════════════════════

Describe "Engineer → Manager Communication" {

    Context "Success reporting" {
        It "engineer posts 'done' message with summary to manager" {
            $roomDir = New-TestRoom -TaskRef "TASK-200"

            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                -Type "done" -Ref "TASK-200" `
                -Body "Changes: Added auth.py, Modified app.py. Tests: 5/5 pass."

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].from | Should -Be "engineer"
            $msgs[0].to | Should -Be "manager"
            $msgs[0].type | Should -Be "done"
        }
    }

    Context "Error reporting" {
        It "engineer posts 'error' message on failure" {
            $roomDir = New-TestRoom -TaskRef "TASK-201"

            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                -Type "error" -Ref "TASK-201" `
                -Body "Engineer exited with code 1: ImportError"

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "error" -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].from | Should -Be "engineer"
            $msgs[0].body | Should -Match "ImportError"
        }

        It "engineer posts timeout error" {
            $roomDir = New-TestRoom -TaskRef "TASK-202"

            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                -Type "error" -Ref "TASK-202" `
                -Body "Engineer timed out after 600s"

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "error" -AsObject
            $msgs[0].body | Should -Match "timed out"
        }
    }

    Context "Multiple done messages (retry counting)" {
        It "manager uses done count to track retry completions" {
            $roomDir = New-TestRoom -TaskRef "TASK-203"

            # First attempt done
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                -Type "done" -Ref "TASK-203" -Body "First attempt"
            # Fix requested, second attempt done
            & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
                -Type "fix" -Ref "TASK-203" -Body "Fix needed"
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                -Type "done" -Ref "TASK-203" -Body "Second attempt"

            $doneMsgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -AsObject
            $doneMsgs.Count | Should -Be 2

            # Manager logic: doneCount >= retries + 1 means current attempt is done
            $retries = 1
            $expected = $retries + 1
            $doneMsgs.Count | Should -BeGreaterOrEqual $expected
        }
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 3. QA → MANAGER COMMUNICATION
# ═══════════════════════════════════════════════════════════════════════════════

Describe "QA → Manager Communication" {

    Context "Pass verdict" {
        It "QA posts 'pass' message to manager" {
            $roomDir = New-TestRoom -TaskRef "TASK-300"

            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                -Type "pass" -Ref "TASK-300" `
                -Body "VERDICT: PASS`nAll tests pass. Code is clean."

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "pass" -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].from | Should -Be "qa"
            $msgs[0].to | Should -Be "manager"
            $msgs[0].type | Should -Be "pass"
        }
    }

    Context "Fail verdict" {
        It "QA posts 'fail' message with feedback" {
            $roomDir = New-TestRoom -TaskRef "TASK-301"

            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                -Type "fail" -Ref "TASK-301" `
                -Body "VERDICT: FAIL`nMissing error handling in auth.py"

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "fail" -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].from | Should -Be "qa"
            $msgs[0].body | Should -Match "Missing error handling"
        }
    }

    Context "Error (verdict parse failure)" {
        It "QA posts 'error' when verdict cannot be parsed" {
            $roomDir = New-TestRoom -TaskRef "TASK-302"

            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                -Type "error" -Ref "TASK-302" `
                -Body "Could not parse QA verdict. Full output: some garbled text"

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "error" -AsObject
            $msgs.Count | Should -Be 1
            $msgs[0].from | Should -Be "qa"
        }
    }

    Context "QA process death" {
        It "manager detects QA death and posts error on behalf" {
            $roomDir = New-TestRoom -TaskRef "TASK-303"

            # Manager posts error on behalf of dead QA
            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                -Type "error" -Ref "TASK-303" `
                -Body "QA process terminated without verdict"

            $msgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "error" -AsObject
            $msgs[0].body | Should -Match "terminated without verdict"
        }
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 4. FULL LIFECYCLE — HAPPY PATH
# ═══════════════════════════════════════════════════════════════════════════════

Describe "Full Lifecycle — Happy Path" {

    It "simulates: pending → task → done → qa-pass → passed" {
        $roomDir = New-TestRoom -TaskRef "EPIC-001" `
            -Description "Build dashboard" `
            -DoD @("Dashboard renders", "Tests pass") `
            -AC @("npm run dev works")

        # Verify initial state
        $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
        $status | Should -Be "pending"

        # 1. Manager assigns task
        & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
            -Type "task" -Ref "EPIC-001" -Body "Build a React dashboard"
        Set-WarRoomStatus -RoomDir $roomDir -NewStatus "engineering"

        # 2. Engineer completes work
        & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
            -Type "done" -Ref "EPIC-001" `
            -Body "Dashboard built. Files: App.jsx, Dashboard.jsx. Tests: 3/3 pass."

        # 3. Manager detects done → routes to QA
        $doneMsgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "done" -AsObject
        $doneMsgs.Count | Should -BeGreaterOrEqual 1
        Set-WarRoomStatus -RoomDir $roomDir -NewStatus "qa-review"

        # 4. QA passes
        & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
            -Type "pass" -Ref "EPIC-001" -Body "VERDICT: PASS`nAll requirements met."

        # 5. Manager detects pass → marks passed
        $passMsgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "pass" -AsObject
        $passMsgs.Count | Should -Be 1
        Set-WarRoomStatus -RoomDir $roomDir -NewStatus "passed"

        # Verify final state
        $finalStatus = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
        $finalStatus | Should -Be "passed"

        # Verify audit trail
        $audit = Get-Content (Join-Path $roomDir "audit.log")
        $audit | Should -Contain ($audit | Where-Object { $_ -match "pending -> engineering" })
        $audit | Should -Contain ($audit | Where-Object { $_ -match "engineering -> qa-review" })
        $audit | Should -Contain ($audit | Where-Object { $_ -match "qa-review -> passed" })
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 5. FULL LIFECYCLE — RETRY PATH
# ═══════════════════════════════════════════════════════════════════════════════

Describe "Full Lifecycle — Retry Path" {

    It "simulates: task → done → qa-fail → fix → done → qa-pass" {
        $roomDir = New-TestRoom -TaskRef "TASK-500"

        # 1. Manager assigns
        & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
            -Type "task" -Ref "TASK-500" -Body "Implement login"
        Set-WarRoomStatus -RoomDir $roomDir -NewStatus "engineering"

        # 2. Engineer submits
        & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
            -Type "done" -Ref "TASK-500" -Body "Login implemented"

        # 3. QA fails
        Set-WarRoomStatus -RoomDir $roomDir -NewStatus "qa-review"
        & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
            -Type "fail" -Ref "TASK-500" -Body "VERDICT: FAIL`nNo password hashing"

        # 4. Manager routes feedback, increments retry
        $failMsgs = & $script:ReadMessages -RoomDir $roomDir -FilterType "fail" -AsObject
        $failMsgs.Count | Should -Be 1

        "1" | Out-File -FilePath (Join-Path $roomDir "retries") -NoNewline
        & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
            -Type "fix" -Ref "TASK-500" -Body $failMsgs[0].body
        Set-WarRoomStatus -RoomDir $roomDir -NewStatus "fixing"

        # 5. Engineer fixes and re-submits
        & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
            -Type "done" -Ref "TASK-500" -Body "Added bcrypt hashing"

        # 6. QA passes on retry
        Set-WarRoomStatus -RoomDir $roomDir -NewStatus "qa-review"
        & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
            -Type "pass" -Ref "TASK-500" -Body "VERDICT: PASS"

        Set-WarRoomStatus -RoomDir $roomDir -NewStatus "passed"

        # Verify: 2 done messages, 1 fix, 1 fail, 1 pass
        $allMsgs = & $script:ReadMessages -RoomDir $roomDir -AsObject
        ($allMsgs | Where-Object { $_.type -eq "done" }).Count | Should -Be 2
        ($allMsgs | Where-Object { $_.type -eq "fix" }).Count | Should -Be 1
        ($allMsgs | Where-Object { $_.type -eq "fail" }).Count | Should -Be 1
        ($allMsgs | Where-Object { $_.type -eq "pass" }).Count | Should -Be 1

        # Verify retry count
        $retries = [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
        $retries | Should -Be 1
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 6. FULL LIFECYCLE — FAILED-FINAL
# ═══════════════════════════════════════════════════════════════════════════════

Describe "Full Lifecycle — Max Retries Exhausted" {

    It "reaches failed-final after max retries" {
        $roomDir = New-TestRoom -TaskRef "TASK-600"
        $maxRetries = 3

        Set-WarRoomStatus -RoomDir $roomDir -NewStatus "engineering"

        for ($i = 0; $i -lt $maxRetries; $i++) {
            # Engineer done
            & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" `
                -Type "done" -Ref "TASK-600" -Body "Attempt $($i + 1)"
            # QA fail
            & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" `
                -Type "fail" -Ref "TASK-600" -Body "Still broken attempt $($i + 1)"
            # Manager sends fix (except on last iteration)
            ($i + 1).ToString() | Out-File -FilePath (Join-Path $roomDir "retries") -NoNewline
            if ($i -lt ($maxRetries - 1)) {
                & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
                    -Type "fix" -Ref "TASK-600" -Body "Fix attempt $($i + 1)"
                Set-WarRoomStatus -RoomDir $roomDir -NewStatus "fixing"
            }
        }

        # After max retries, should transition to failed-final
        $retries = [int](Get-Content (Join-Path $roomDir "retries") -Raw).Trim()
        $retries | Should -BeGreaterOrEqual $maxRetries

        Set-WarRoomStatus -RoomDir $roomDir -NewStatus "failed-final"
        $status = (Get-Content (Join-Path $roomDir "status") -Raw).Trim()
        $status | Should -Be "failed-final"

        # Verify message counts
        $allMsgs = & $script:ReadMessages -RoomDir $roomDir -AsObject
        ($allMsgs | Where-Object { $_.type -eq "done" }).Count | Should -Be $maxRetries
        ($allMsgs | Where-Object { $_.type -eq "fail" }).Count | Should -Be $maxRetries
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 7. MESSAGE FORMAT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

Describe "Message Format Validation" {

    It "all messages have required fields: ts, from, to, type, ref, body" {
        $roomDir = New-TestRoom -TaskRef "TASK-700"

        & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
            -Type "task" -Ref "TASK-700" -Body "Do something"

        $msgs = & $script:ReadMessages -RoomDir $roomDir -AsObject
        $msg = $msgs[0]

        $msg.ts | Should -Not -BeNullOrEmpty
        $msg.from | Should -Not -BeNullOrEmpty
        $msg.to | Should -Not -BeNullOrEmpty
        $msg.type | Should -Not -BeNullOrEmpty
        $msg.ref | Should -Not -BeNullOrEmpty
        $msg.body | Should -Not -BeNullOrEmpty
    }

    It "message types follow the contract: task, fix, done, error, pass, fail" {
        $roomDir = New-TestRoom -TaskRef "TASK-701"
        $validTypes = @("task", "fix", "done", "error", "pass", "fail")

        foreach ($t in $validTypes) {
            & $script:PostMessage -RoomDir $roomDir -From "test" -To "test" `
                -Type $t -Ref "TASK-701" -Body "Testing type $t"
        }

        $msgs = & $script:ReadMessages -RoomDir $roomDir -AsObject
        # New-WarRoom posts initial task message, so total = validTypes + 1
        $msgs.Count | Should -BeGreaterOrEqual $validTypes.Count
        foreach ($m in $msgs) {
            $m.type | Should -BeIn $validTypes
        }
    }

    It "sender-receiver pairs follow the contract" {
        $roomDir = New-TestRoom -TaskRef "TASK-702"

        # Manager → Engineer (task, fix)
        & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "task" -Ref "TASK-702" -Body "Go"
        & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" -Type "fix" -Ref "TASK-702" -Body "Fix"

        # Engineer → Manager (done, error)
        & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" -Type "done" -Ref "TASK-702" -Body "Done"
        & $script:PostMessage -RoomDir $roomDir -From "engineer" -To "manager" -Type "error" -Ref "TASK-702" -Body "Err"

        # QA → Manager (pass, fail, error)
        & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" -Type "pass" -Ref "TASK-702" -Body "Pass"
        & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" -Type "fail" -Ref "TASK-702" -Body "Fail"
        & $script:PostMessage -RoomDir $roomDir -From "qa" -To "manager" -Type "error" -Ref "TASK-702" -Body "QA Err"

        $msgs = & $script:ReadMessages -RoomDir $roomDir -AsObject
        # 7 explicit + 1 from New-WarRoom initial task
        $msgs.Count | Should -BeGreaterOrEqual 7

        # Verify routing directions (New-WarRoom's initial msg is also manager→engineer)
        $mgrToEng = $msgs | Where-Object { $_.from -eq "manager" -and $_.to -eq "engineer" }
        $mgrToEng.Count | Should -BeGreaterOrEqual 2
        $engToMgr = $msgs | Where-Object { $_.from -eq "engineer" -and $_.to -eq "manager" }
        $engToMgr.Count | Should -Be 2
        $qaToMgr = $msgs | Where-Object { $_.from -eq "qa" -and $_.to -eq "manager" }
        $qaToMgr.Count | Should -Be 3
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 8. ENGINEER PROMPT CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════════

Describe "Engineer Prompt Construction" {

    It "engineer reads brief.md for task description" {
        $roomDir = New-TestRoom -TaskRef "TASK-800" -Description "Build login page"

        $briefPath = Join-Path $roomDir "brief.md"
        Test-Path $briefPath | Should -BeTrue

        $brief = Get-Content $briefPath -Raw
        $brief | Should -Match "Build login page"
    }

    It "engineer reads latest task/fix message from channel" {
        $roomDir = New-TestRoom -TaskRef "TASK-801"

        & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
            -Type "task" -Ref "TASK-801" -Body "First instruction"
        & $script:PostMessage -RoomDir $roomDir -From "manager" -To "engineer" `
            -Type "fix" -Ref "TASK-801" -Body "Updated instruction"

        $allMsgs = & $script:ReadMessages -RoomDir $roomDir -AsObject
        $taskFixMsgs = $allMsgs | Where-Object { $_.type -in @('task', 'fix') }
        $latest = $taskFixMsgs | Sort-Object { $_.ts } | Select-Object -Last 1

        $latest.type | Should -Be "fix"
        $latest.body | Should -Be "Updated instruction"
    }

    It "config.json contains goals that scope the engineer's work" {
        $roomDir = New-TestRoom -TaskRef "TASK-802" `
            -DoD @("Auth working", "Tests passing") `
            -AC @("POST /login returns 200")

        $config = Get-Content (Join-Path $roomDir "config.json") -Raw | ConvertFrom-Json
        $config.goals.definition_of_done | Should -Contain "Auth working"
        $config.goals.definition_of_done | Should -Contain "Tests passing"
        $config.goals.acceptance_criteria | Should -Contain "POST /login returns 200"
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 9. QA VERDICT PARSING
# ═══════════════════════════════════════════════════════════════════════════════

Describe "QA Verdict Parsing Contract" {

    It "parses 'VERDICT: PASS' at start of line" {
        $output = "VERDICT: PASS`nAll tests passing."
        $verdict = ""
        if ($output -match '(?m)^VERDICT:\s*(PASS|FAIL)') {
            $verdict = $Matches[1].ToUpper()
        }
        $verdict | Should -Be "PASS"
    }

    It "parses 'VERDICT: FAIL' at start of line" {
        $output = "Some preamble`nVERDICT: FAIL`nMissing tests."
        $verdict = ""
        if ($output -match '(?m)^VERDICT:\s*(PASS|FAIL)') {
            $verdict = $Matches[1].ToUpper()
        }
        $verdict | Should -Be "FAIL"
    }

    It "parses VERDICT: anywhere in a line (fallback)" {
        $output = "My review: VERDICT: PASS and everything looks good."
        $verdict = ""
        if ($output -match 'VERDICT:\s*(PASS|FAIL)') {
            $verdict = $Matches[1].ToUpper()
        }
        $verdict | Should -Be "PASS"
    }

    It "parses standalone PASS in first 20 lines (final fallback)" {
        $output = "Review complete.`nPASS`nAll good."
        $verdict = ""
        $first20 = ($output -split "`n" | Select-Object -First 20) -join "`n"
        if ($first20 -match '\b(PASS|FAIL)\b') {
            $verdict = $Matches[1].ToUpper()
        }
        $verdict | Should -Be "PASS"
    }

    It "returns empty when no verdict found" {
        $output = "I reviewed everything and it looks okay I think maybe."
        $verdict = ""
        if ($output -match '(?m)^VERDICT:\s*(PASS|FAIL)') {
            $verdict = $Matches[1].ToUpper()
        }
        if (-not $verdict -and $output -match 'VERDICT:\s*(PASS|FAIL)') {
            $verdict = $Matches[1].ToUpper()
        }
        # Skip standalone check — "okay" could false-positive
        $verdict | Should -BeNullOrEmpty
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 10. EPIC vs TASK DIFFERENTIATION
# ═══════════════════════════════════════════════════════════════════════════════

Describe "Epic vs Task Differentiation" {

    It "detects EPIC- prefix for epic handling" {
        $taskRef = "EPIC-001"
        ($taskRef -match '^EPIC-') | Should -BeTrue
    }

    It "detects TASK- prefix for task handling" {
        $taskRef = "TASK-001"
        ($taskRef -match '^EPIC-') | Should -BeFalse
    }

    It "epic war-room has brief.md with epic description" {
        $roomDir = New-TestRoom -TaskRef "EPIC-010" -Description "Full feature epic"
        $brief = Get-Content (Join-Path $roomDir "brief.md") -Raw
        $brief | Should -Match "Full feature epic"
    }
}
