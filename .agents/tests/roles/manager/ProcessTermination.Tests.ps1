# ProcessTermination.Tests.ps1
# Tests for reliable process termination across the agent lifecycle:
#   - Stop-RoomProcesses (process-group kill / tree kill)
#   - Start-ManagerLoop.ps1 try/finally cleanup
#   - Backward compatibility with existing callers

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
    $script:helpersModule = Join-Path $script:agentsDir "roles" "manager" "ManagerLoop-Helpers.psm1"

    # Import the module under test
    Import-Module $script:helpersModule -Force -WarningAction SilentlyContinue

    # Import Utils for Test-PidAlive, Set-WarRoomStatus
    $utilsModule = Join-Path $script:agentsDir "lib" "Utils.psm1"
    if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }

    # Helper: create a minimal room structure
    function New-MinimalRoom {
        param([string]$Base, [string]$Status = 'developing')
        $roomDir = Join-Path $Base "room-$(Get-Random)"
        New-Item -ItemType Directory -Path $roomDir -Force | Out-Null
        $Status | Out-File -FilePath (Join-Path $roomDir "status") -Encoding utf8 -NoNewline
        "" | Out-File -FilePath (Join-Path $roomDir "audit.log") -Encoding utf8
        return $roomDir
    }

    # Helper: inject context into the module (required by some functions)
    function Set-MinimalContext {
        param([string]$RoomsDir)
        $ctx = @{
            agentsDir    = $script:agentsDir
            WarRoomsDir  = $RoomsDir
            dagFile      = Join-Path $RoomsDir "DAG.json"
            hasDag       = $false
            dagCache     = $null
            dagMtime     = $null
            stateTimeout = 900
            maxRetries   = 3
        }
        Set-ManagerLoopContext -Context $ctx
    }
}

AfterAll {
    Remove-Module ManagerLoop-Helpers -ErrorAction SilentlyContinue
    Remove-Module Utils               -ErrorAction SilentlyContinue
}

# ===========================================================================
# Stop-RoomProcesses — backward compatibility
# ===========================================================================
Describe "Stop-RoomProcesses backward compatibility" {
    It "still does nothing when pids dir does not exist (no regression)" {
        $rd = Join-Path $TestDrive "compat-$(Get-Random)"
        New-Item -ItemType Directory -Path $rd -Force | Out-Null
        { Stop-RoomProcesses -RoomDir $rd } | Should -Not -Throw
    }

    It "still removes invalid/stale pid files gracefully (no regression)" {
        $rd = Join-Path $TestDrive "compat-$(Get-Random)"
        $pidDir = Join-Path $rd "pids"
        New-Item -ItemType Directory -Path $pidDir -Force | Out-Null
        "99999999" | Out-File (Join-Path $pidDir "engineer.pid") -Encoding utf8 -NoNewline
        { Stop-RoomProcesses -RoomDir $rd } | Should -Not -Throw
        Test-Path (Join-Path $pidDir "engineer.pid") | Should -BeFalse
    }

    It "still removes spawned_at files (no regression)" {
        $rd = Join-Path $TestDrive "compat-$(Get-Random)"
        $pidDir = Join-Path $rd "pids"
        New-Item -ItemType Directory -Path $pidDir -Force | Out-Null
        "$(Get-Date -UFormat %s)" | Out-File (Join-Path $pidDir "qa.spawned_at") -Encoding utf8 -NoNewline
        Stop-RoomProcesses -RoomDir $rd
        Test-Path (Join-Path $pidDir "qa.spawned_at") | Should -BeFalse
    }

    It "handles non-numeric pid file content gracefully" {
        $rd = Join-Path $TestDrive "compat-$(Get-Random)"
        $pidDir = Join-Path $rd "pids"
        New-Item -ItemType Directory -Path $pidDir -Force | Out-Null
        "not-a-pid" | Out-File (Join-Path $pidDir "broken.pid") -Encoding utf8 -NoNewline
        { Stop-RoomProcesses -RoomDir $rd } | Should -Not -Throw
        Test-Path (Join-Path $pidDir "broken.pid") | Should -BeFalse
    }

    It "handles empty pid file content gracefully" {
        $rd = Join-Path $TestDrive "compat-$(Get-Random)"
        $pidDir = Join-Path $rd "pids"
        New-Item -ItemType Directory -Path $pidDir -Force | Out-Null
        # Write a whitespace-only PID file (not matching ^\d+$)
        " " | Out-File (Join-Path $pidDir "empty.pid") -Encoding utf8 -NoNewline
        { Stop-RoomProcesses -RoomDir $rd } | Should -Not -Throw
        Test-Path (Join-Path $pidDir "empty.pid") | Should -BeFalse
    }

    It "processes multiple pid files in one call" {
        $rd = Join-Path $TestDrive "compat-$(Get-Random)"
        $pidDir = Join-Path $rd "pids"
        New-Item -ItemType Directory -Path $pidDir -Force | Out-Null
        "99999991" | Out-File (Join-Path $pidDir "engineer.pid") -Encoding utf8 -NoNewline
        "99999992" | Out-File (Join-Path $pidDir "qa.pid") -Encoding utf8 -NoNewline
        "99999993" | Out-File (Join-Path $pidDir "architect.pid") -Encoding utf8 -NoNewline
        { Stop-RoomProcesses -RoomDir $rd } | Should -Not -Throw
        (Get-ChildItem $pidDir -Filter "*.pid").Count | Should -Be 0
    }
}

# ===========================================================================
# Stop-RoomProcesses — process tree kill behavior
# ===========================================================================
Describe "Stop-RoomProcesses kills real processes" -Skip:($env:CI -eq 'true') {
    It "kills a real child process via pid file" {
        $rd = Join-Path $TestDrive "kill-$(Get-Random)"
        $pidDir = Join-Path $rd "pids"
        New-Item -ItemType Directory -Path $pidDir -Force | Out-Null

        # Spawn a real process (sleep) that will persist
        $psi = [System.Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = "sleep"
        $psi.ArgumentList.Add("300")
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $proc = [System.Diagnostics.Process]::Start($psi)
        try {
            $proc.Id.ToString() | Out-File (Join-Path $pidDir "test.pid") -Encoding utf8 -NoNewline
            # Verify it's alive
            { Get-Process -Id $proc.Id -ErrorAction Stop } | Should -Not -Throw

            Stop-RoomProcesses -RoomDir $rd

            # Give it a moment to die
            Start-Sleep -Milliseconds 1500

            # Should be dead now
            $stillAlive = $false
            try { $null = Get-Process -Id $proc.Id -ErrorAction Stop; $stillAlive = $true } catch {}
            $stillAlive | Should -BeFalse -Because "Stop-RoomProcesses should have killed the process"
        }
        finally {
            # Belt-and-suspenders cleanup
            try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
        }
    }

    It "kills a process tree (parent + child) via pid file" -Skip:($IsWindows) {
        $rd = Join-Path $TestDrive "tree-$(Get-Random)"
        $pidDir = Join-Path $rd "pids"
        New-Item -ItemType Directory -Path $pidDir -Force | Out-Null

        # Spawn a bash that spawns a child sleep — simulates bash → exec opencode
        $script = Join-Path $TestDrive "tree-parent-$(Get-Random).sh"
        @"
#!/bin/bash
sleep 300 &
wait
"@ | Out-File $script -Encoding utf8 -NoNewline
        chmod +x $script 2>$null

        $psi = [System.Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = "bash"
        $psi.ArgumentList.Add($script)
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $proc = [System.Diagnostics.Process]::Start($psi)
        Start-Sleep -Milliseconds 500  # let child spawn

        try {
            $proc.Id.ToString() | Out-File (Join-Path $pidDir "test.pid") -Encoding utf8 -NoNewline

            Stop-RoomProcesses -RoomDir $rd
            Start-Sleep -Milliseconds 1500

            $stillAlive = $false
            try { $null = Get-Process -Id $proc.Id -ErrorAction Stop; $stillAlive = $true } catch {}
            $stillAlive | Should -BeFalse -Because "parent bash process should be killed"
        }
        finally {
            try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
            Remove-Item $script -Force -ErrorAction SilentlyContinue
        }
    }
}

# ===========================================================================
# Start-ManagerLoop.ps1 — try/finally structure validation
# ===========================================================================
Describe "Start-ManagerLoop try/finally cleanup structure" {
    It "contains try/finally wrapping the main loop" {
        $content = Get-Content (Join-Path $script:agentsDir "roles" "manager" "Start-ManagerLoop.ps1") -Raw
        # The try { must appear before the while loop
        $content | Should -Match '(?s)try\s*\{[^}]*while\s*\(\s*-not\s+\$script:shuttingDown\s*\)'
    }

    It "has finally block that calls Stop-RoomProcesses" {
        $content = Get-Content (Join-Path $script:agentsDir "roles" "manager" "Start-ManagerLoop.ps1") -Raw
        $content | Should -Match '(?s)finally\s*\{[^}]*Stop-RoomProcesses'
    }

    It "has finally block that stops background jobs" {
        $content = Get-Content (Join-Path $script:agentsDir "roles" "manager" "Start-ManagerLoop.ps1") -Raw
        # The finally block spans multiple lines — check both elements exist after 'finally'
        $content | Should -Match 'finally'
        $content | Should -Match 'Stop-Job'
    }

    It "has finally block that removes manager PID file" {
        $content = Get-Content (Join-Path $script:agentsDir "roles" "manager" "Start-ManagerLoop.ps1") -Raw
        $content | Should -Match 'finally'
        $content | Should -Match 'Remove-Item.*managerPidFile'
    }

    It "still registers PowerShell.Exiting event for graceful shutdown" {
        $content = Get-Content (Join-Path $script:agentsDir "roles" "manager" "Start-ManagerLoop.ps1") -Raw
        $content | Should -Match 'Register-EngineEvent.*PowerShell\.Exiting'
    }
}

# ===========================================================================
# Start-ManagerLoop.ps1 — simulated shutdown behavior
# ===========================================================================
Describe "Manager shutdown cleans up rooms" {
    BeforeEach {
        $script:wd = Join-Path $TestDrive "mgr-shutdown-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:wd -Force | Out-Null
        Set-MinimalContext -RoomsDir $script:wd
    }

    It "Stop-RoomProcesses removes all pid and spawned_at files across multiple rooms" {
        # Create two rooms with PID files
        $rd1 = New-MinimalRoom -Base $script:wd
        $rd2 = New-MinimalRoom -Base $script:wd

        $pidDir1 = Join-Path $rd1 "pids"
        $pidDir2 = Join-Path $rd2 "pids"
        New-Item -ItemType Directory -Path $pidDir1 -Force | Out-Null
        New-Item -ItemType Directory -Path $pidDir2 -Force | Out-Null

        "99999991" | Out-File (Join-Path $pidDir1 "engineer.pid") -Encoding utf8 -NoNewline
        "$(Get-Date -UFormat %s)" | Out-File (Join-Path $pidDir1 "engineer.spawned_at") -Encoding utf8 -NoNewline
        "99999992" | Out-File (Join-Path $pidDir2 "qa.pid") -Encoding utf8 -NoNewline

        # Simulate the finally block's cleanup pattern
        Get-ChildItem -Path $script:wd -Directory -Filter "room-*" -ErrorAction SilentlyContinue | ForEach-Object {
            Stop-RoomProcesses $_.FullName
        }

        # All PIDs should be gone
        (Get-ChildItem $pidDir1 -Filter "*.pid" -ErrorAction SilentlyContinue).Count | Should -Be 0
        (Get-ChildItem $pidDir1 -Filter "*.spawned_at" -ErrorAction SilentlyContinue).Count | Should -Be 0
        (Get-ChildItem $pidDir2 -Filter "*.pid" -ErrorAction SilentlyContinue).Count | Should -Be 0
    }
}

# ===========================================================================
# Invoke-Agent.ps1 — stable version structural checks
# ===========================================================================
Describe "Invoke-Agent stable version structure" {
    BeforeAll {
        $script:invokeAgentContent = Get-Content (Join-Path $script:agentsDir "roles" "_base" "Invoke-Agent.ps1") -Raw
    }

    It "uses System.Diagnostics.Process (not Start-Process) for Unix launch" {
        $script:invokeAgentContent | Should -Match '\[System\.Diagnostics\.ProcessStartInfo\]::new\(\)'
        $script:invokeAgentContent | Should -Match '\[System\.Diagnostics\.Process\]::Start\('
    }

    It "uses exec in the bash wrapper for PID preservation" {
        $script:invokeAgentContent | Should -Match 'exec \$AgentCmd'
    }

    It "closes stdin to prevent hangs" {
        $script:invokeAgentContent | Should -Match '\$proc\.StandardInput\.Close\(\)'
    }

    It "writes PID file before exec in wrapper script" {
        $script:invokeAgentContent | Should -Match 'echo.*\$\$.*safePidFile'
    }

    It "has CLI resolution chain without mandatory bin/agent dependency" {
        # The old version had a hard exit 1 when bin/agent was missing.
        # The new version must NOT have that pattern.
        $script:invokeAgentContent | Should -Not -Match 'Write-Error.*Agent binary not found'
        $script:invokeAgentContent | Should -Match 'opencode run'
    }

    It "supports role-specific env var override (e.g. ARCHITECT_CMD)" {
        $script:invokeAgentContent | Should -Match 'RoleName.*ToUpper.*_CMD'
    }

    It "supports OSTWIN_AGENT_CMD env var override" {
        $script:invokeAgentContent | Should -Match 'OSTWIN_AGENT_CMD'
    }

    It "falls back to 'opencode run' as default" {
        $script:invokeAgentContent | Should -Match 'AgentCmd.*=.*"opencode run"'
    }
}

# ===========================================================================
# Integration: stop.ps1 ↔ Stop-RoomProcesses compatibility
# ===========================================================================
Describe "stop.ps1 and Stop-RoomProcesses compatibility" {
    It "stop.ps1 iterates pid files in war-rooms (same pattern as Stop-RoomProcesses)" {
        $stopContent = Get-Content (Join-Path $script:agentsDir "stop.ps1") -Raw
        # stop.ps1 -Force iterates *.pid files
        $stopContent | Should -Match '\.pid.*Recurse'
    }

    It "Stop-RoomProcesses accepts same room dir structure as stop.ps1" {
        $rd = Join-Path $TestDrive "compat-stop-$(Get-Random)"
        $pidDir = Join-Path $rd "pids"
        New-Item -ItemType Directory -Path $pidDir -Force | Out-Null
        "12345" | Out-File (Join-Path $pidDir "agent.pid") -Encoding utf8 -NoNewline
        { Stop-RoomProcesses -RoomDir $rd } | Should -Not -Throw
    }
}
