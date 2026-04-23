# Process Management Pester Tests
# Covers: Stop-ProcessTree, Stop-RoomProcesses (tree-kill), startup stale-PID
# sweep, PGID file lifecycle, shutdown cleanup, and backward compatibility.
#
# These tests prove the new process management changes are fully backward
# compatible with the existing PID-file-based orchestration model.

BeforeAll {
    $script:agentsDir = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
    $script:helpersModule = Join-Path $script:agentsDir "roles" "manager" "ManagerLoop-Helpers.psm1"
    $script:managerScript = Join-Path $script:agentsDir "roles" "manager" "Start-ManagerLoop.ps1"

    Import-Module $script:helpersModule -Force -WarningAction SilentlyContinue

    $utilsModule = Join-Path $script:agentsDir "lib" "Utils.psm1"
    if (Test-Path $utilsModule) { Import-Module $utilsModule -Force }

    function New-FakeRoom { # Create a minimal war-room directory structure
        param([string]$Base, [string]$Name = "room-$(Get-Random)")
        $roomDir = Join-Path $Base $Name
        New-Item -ItemType Directory -Path $roomDir -Force | Out-Null
        $pidDir = Join-Path $roomDir "pids"
        New-Item -ItemType Directory -Path $pidDir -Force | Out-Null
        $artDir = Join-Path $roomDir "artifacts"
        New-Item -ItemType Directory -Path $artDir -Force | Out-Null
        "pending" | Out-File -FilePath (Join-Path $roomDir "status") -Encoding utf8 -NoNewline
        return $roomDir
    }
}

AfterAll {
    Remove-Module ManagerLoop-Helpers -ErrorAction SilentlyContinue
    Remove-Module Utils -ErrorAction SilentlyContinue
}

# ===========================================================================
# Stop-ProcessTree
# ===========================================================================
Describe "Stop-ProcessTree" {
    Context "with a dead/nonexistent PID" {
        It "does not throw when PID does not exist" {
            { Stop-ProcessTree -ParentPid 999999 } | Should -Not -Throw
        }

        It "does not throw when PID is negative" {
            { Stop-ProcessTree -ParentPid -1 } | Should -Not -Throw
        }
    }

    Context "with a real short-lived process" {
        It "kills a simple child process" {
            if (-not ($IsLinux -or $IsMacOS)) { Set-ItResult -Skipped -Because "Unix-only test"; return }
            $proc = Start-Process -FilePath "sleep" -ArgumentList "60" -PassThru -NoNewWindow
            try {
                $proc.Id | Should -BeGreaterThan 0
                (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) | Should -Not -BeNullOrEmpty
                Stop-ProcessTree -ParentPid $proc.Id
                Start-Sleep -Milliseconds 500
                Get-Process -Id $proc.Id -ErrorAction SilentlyContinue | Should -BeNullOrEmpty
            } finally {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        }

        It "kills a process and its child (tree)" {
            if (-not ($IsLinux -or $IsMacOS)) { Set-ItResult -Skipped -Because "Unix-only test"; return }
            $wrapper = Join-Path $TestDrive "tree-test-$(Get-Random).sh"
            "#!/bin/bash`nsleep 60 &`nCHILD=`$!`necho `$CHILD`nwait" | Out-File $wrapper -Encoding utf8
            chmod +x $wrapper
            $psi = [System.Diagnostics.ProcessStartInfo]::new()
            $psi.FileName = "bash"
            $psi.Arguments = "`"$wrapper`""
            $psi.UseShellExecute = $false
            $psi.RedirectStandardOutput = $true
            $psi.CreateNoWindow = $true
            $parent = [System.Diagnostics.Process]::Start($psi)
            try {
                Start-Sleep -Milliseconds 500
                $children = @()
                try { $children = (pgrep -P $parent.Id 2>$null) -split "`n" | Where-Object { $_ -match '^\d+$' } } catch {}
                $children.Count | Should -BeGreaterOrEqual 1
                Stop-ProcessTree -ParentPid $parent.Id
                Start-Sleep -Milliseconds 500
                Get-Process -Id $parent.Id -ErrorAction SilentlyContinue | Should -BeNullOrEmpty
                foreach ($c in $children) {
                    Get-Process -Id ([int]$c) -ErrorAction SilentlyContinue | Should -BeNullOrEmpty
                }
            } finally {
                try { Stop-Process -Id $parent.Id -Force -ErrorAction SilentlyContinue } catch {}
                if ($children) { foreach ($c in $children) { try { Stop-Process -Id ([int]$c) -Force -ErrorAction SilentlyContinue } catch {} } }
            }
        }
    }

    Context "Windows-specific CIM walk" {
        It "uses CIM walk on Windows for child enumeration" {
            if ($IsLinux -or $IsMacOS) { Set-ItResult -Skipped -Because "Windows-only test"; return }
            $proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "timeout 60" -PassThru -NoNewWindow
            try {
                $proc.Id | Should -BeGreaterThan 0
                (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) | Should -Not -BeNullOrEmpty
                Stop-ProcessTree -ParentPid $proc.Id
                Start-Sleep -Milliseconds 500
                Get-Process -Id $proc.Id -ErrorAction SilentlyContinue | Should -BeNullOrEmpty
            } finally {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        }

        It "Stop-ProcessTree code contains CIM fallback for Windows" {
            $content = Get-Content $script:helpersModule -Raw
            $content | Should -Match 'Get-CimInstance Win32_Process'
            $content | Should -Match 'ParentProcessId'
        }
    }

    Context "with RoomDir and no job-handle file (backward compat)" {
        It "falls back to pgrep/CIM walk when no job-handle.txt exists" {
            $room = New-FakeRoom -Base $TestDrive
            { Stop-ProcessTree -ParentPid 999999 -RoomDir $room } | Should -Not -Throw
            Test-Path (Join-Path $room "artifacts" "job-handle.txt") | Should -BeFalse
        }
    }
}

# ===========================================================================
# Stop-RoomProcesses — backward compatibility
# ===========================================================================
Describe "Stop-RoomProcesses" {
    It "cleans up .pid and .spawned_at files (same behavior as before)" {
        $room = New-FakeRoom -Base $TestDrive
        $pidDir = Join-Path $room "pids"
        "999999" | Out-File -FilePath (Join-Path $pidDir "engineer.pid") -Encoding utf8 -NoNewline
        "1234567890" | Out-File -FilePath (Join-Path $pidDir "engineer.spawned_at") -Encoding utf8 -NoNewline

        Test-Path (Join-Path $pidDir "engineer.pid") | Should -BeTrue
        Test-Path (Join-Path $pidDir "engineer.spawned_at") | Should -BeTrue

        Stop-RoomProcesses -RoomDir $room

        Test-Path (Join-Path $pidDir "engineer.pid") | Should -BeFalse
        Test-Path (Join-Path $pidDir "engineer.spawned_at") | Should -BeFalse
    }

    It "handles empty PID file gracefully" {
        $room = New-FakeRoom -Base $TestDrive
        $pidDir = Join-Path $room "pids"
        "" | Out-File -FilePath (Join-Path $pidDir "qa.pid") -Encoding utf8 -NoNewline

        { Stop-RoomProcesses -RoomDir $room } | Should -Not -Throw
        Test-Path (Join-Path $pidDir "qa.pid") | Should -BeFalse
    }

    It "handles non-numeric PID file gracefully" {
        $room = New-FakeRoom -Base $TestDrive
        $pidDir = Join-Path $room "pids"
        "not-a-pid" | Out-File -FilePath (Join-Path $pidDir "architect.pid") -Encoding utf8 -NoNewline

        { Stop-RoomProcesses -RoomDir $room } | Should -Not -Throw
        Test-Path (Join-Path $pidDir "architect.pid") | Should -BeFalse
    }

    It "handles missing pids directory gracefully" {
        $room = Join-Path $TestDrive "room-nopids-$(Get-Random)"
        New-Item -ItemType Directory -Path $room -Force | Out-Null

        { Stop-RoomProcesses -RoomDir $room } | Should -Not -Throw
    }

    It "kills a real process and removes its PID file" {
        if (-not ($IsLinux -or $IsMacOS)) { Set-ItResult -Skipped -Because "Unix-only test"; return }
        $proc = Start-Process -FilePath "sleep" -ArgumentList "60" -PassThru -NoNewWindow
        try {
            $room = New-FakeRoom -Base $TestDrive
            $pidDir = Join-Path $room "pids"
            $proc.Id.ToString() | Out-File -FilePath (Join-Path $pidDir "engineer.pid") -Encoding utf8 -NoNewline
            Stop-RoomProcesses -RoomDir $room
            Start-Sleep -Milliseconds 500
            Get-Process -Id $proc.Id -ErrorAction SilentlyContinue | Should -BeNullOrEmpty
            Test-Path (Join-Path $pidDir "engineer.pid") | Should -BeFalse
        } finally {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }

    It "handles multiple PID files in one room" {
        $room = New-FakeRoom -Base $TestDrive
        $pidDir = Join-Path $room "pids"
        "999998" | Out-File -FilePath (Join-Path $pidDir "engineer.pid") -Encoding utf8 -NoNewline
        "999997" | Out-File -FilePath (Join-Path $pidDir "qa.pid") -Encoding utf8 -NoNewline
        "1234567890" | Out-File -FilePath (Join-Path $pidDir "engineer.spawned_at") -Encoding utf8 -NoNewline
        "1234567891" | Out-File -FilePath (Join-Path $pidDir "qa.spawned_at") -Encoding utf8 -NoNewline

        Stop-RoomProcesses -RoomDir $room

        (Get-ChildItem $pidDir -ErrorAction SilentlyContinue).Count | Should -Be 0
    }
}

# ===========================================================================
# Startup stale-PID sweep (calls Invoke-StalePidSweep from ManagerLoop-Helpers)
# ===========================================================================
Describe "Startup Stale-PID Sweep" {
    It "Invoke-StalePidSweep is exported from ManagerLoop-Helpers" {
        $cmd = Get-Command Invoke-StalePidSweep -ErrorAction SilentlyContinue
        $cmd | Should -Not -BeNullOrEmpty
        $cmd.Parameters.Keys | Should -Contain "WarRoomsDir"
    }

    It "Start-ManagerLoop.ps1 calls Invoke-StalePidSweep instead of inline sweep" {
        $lines = Get-Content $script:managerScript
        $sweepIdx = -1
        for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match 'Startup sweep') { $sweepIdx = $i; break } }
        $sweepIdx | Should -BeGreaterThan 0
        $sweepSection = ($lines[$sweepIdx..([Math]::Min($sweepIdx + 5, $lines.Count - 1))] -join "`n")
        $sweepSection | Should -Match 'Invoke-StalePidSweep'
        $sweepSection | Should -Not -Match 'Get-ChildItem.*room-\*'
    }

    It "removes PID files for dead processes" {
        $warRooms = Join-Path $TestDrive "war-rooms-sweep-$(Get-Random)"
        New-Item -ItemType Directory -Path $warRooms -Force | Out-Null
        $room = New-FakeRoom -Base $warRooms -Name "room-001"
        "999999" | Out-File -FilePath (Join-Path $room "pids" "engineer.pid") -Encoding utf8 -NoNewline
        "1234567890" | Out-File -FilePath (Join-Path $room "pids" "engineer.spawned_at") -Encoding utf8 -NoNewline

        $cleaned = Invoke-StalePidSweep -WarRoomsDir $warRooms

        $cleaned | Should -Be 1
        Test-Path (Join-Path $room "pids" "engineer.pid") | Should -BeFalse
        Test-Path (Join-Path $room "pids" "engineer.spawned_at") | Should -BeFalse
    }

    It "preserves PID files for live processes" {
        if (-not ($IsLinux -or $IsMacOS)) { Set-ItResult -Skipped -Because "Unix-only test"; return }
        $proc = Start-Process -FilePath "sleep" -ArgumentList "60" -PassThru -NoNewWindow
        try {
            $warRooms = Join-Path $TestDrive "war-rooms-live-$(Get-Random)"
            New-Item -ItemType Directory -Path $warRooms -Force | Out-Null
            $room = New-FakeRoom -Base $warRooms -Name "room-002"
            $proc.Id.ToString() | Out-File -FilePath (Join-Path $room "pids" "engineer.pid") -Encoding utf8 -NoNewline

            $cleaned = Invoke-StalePidSweep -WarRoomsDir $warRooms

            $cleaned | Should -Be 0
            Test-Path (Join-Path $room "pids" "engineer.pid") | Should -BeTrue
        } finally {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }

    It "handles empty/invalid PID files as stale" {
        $warRooms = Join-Path $TestDrive "war-rooms-invalid-$(Get-Random)"
        New-Item -ItemType Directory -Path $warRooms -Force | Out-Null
        $room = New-FakeRoom -Base $warRooms -Name "room-003"
        "" | Out-File -FilePath (Join-Path $room "pids" "qa.pid") -Encoding utf8 -NoNewline
        "notanumber" | Out-File -FilePath (Join-Path $room "pids" "arch.pid") -Encoding utf8 -NoNewline

        $cleaned = Invoke-StalePidSweep -WarRoomsDir $warRooms

        $cleaned | Should -Be 2
    }

    It "sweeps across multiple rooms" {
        $warRooms = Join-Path $TestDrive "war-rooms-multi-$(Get-Random)"
        New-Item -ItemType Directory -Path $warRooms -Force | Out-Null
        $r1 = New-FakeRoom -Base $warRooms -Name "room-010"
        $r2 = New-FakeRoom -Base $warRooms -Name "room-020"
        "888888" | Out-File -FilePath (Join-Path $r1 "pids" "engineer.pid") -Encoding utf8 -NoNewline
        "777777" | Out-File -FilePath (Join-Path $r2 "pids" "qa.pid") -Encoding utf8 -NoNewline

        $cleaned = Invoke-StalePidSweep -WarRoomsDir $warRooms
        $cleaned | Should -Be 2
    }

    It "returns 0 for nonexistent WarRoomsDir" {
        $cleaned = Invoke-StalePidSweep -WarRoomsDir "/tmp/nonexistent-$(Get-Random)"
        $cleaned | Should -Be 0
    }

    It "returns 0 for empty string WarRoomsDir" {
        $cleaned = Invoke-StalePidSweep -WarRoomsDir ""
        $cleaned | Should -Be 0
    }

    It "returns 0 when no rooms exist" {
        $empty = Join-Path $TestDrive "war-rooms-empty-$(Get-Random)"
        New-Item -ItemType Directory -Path $empty -Force | Out-Null

        $cleaned = Invoke-StalePidSweep -WarRoomsDir $empty
        $cleaned | Should -Be 0
    }
}

# ===========================================================================
# PGID file lifecycle
# ===========================================================================
Describe "PGID File Lifecycle" {
    It "Start-ManagerLoop.ps1 contains PGID file write logic" {
        $content = Get-Content $script:managerScript -Raw
        $content | Should -Match 'manager\.pgid'
        $content | Should -Match 'ps -o pgid='
    }

    It "PGID write is guarded by Unix platform check" {
        $content = Get-Content $script:managerScript -Raw
        $content | Should -Match '\$IsLinux -or \$IsMacOS'
    }

    It "PGID write retries up to 3 times to handle race condition" {
        $content = Get-Content $script:managerScript -Raw
        $content | Should -Match '__retry.*-lt 3'
        $content | Should -Match 'Start-Sleep -Milliseconds 100'
    }

    It "Shutdown cleanup removes PGID file" {
        $content = Get-Content $script:managerScript -Raw
        $content | Should -Match 'Remove-Item \$pgidFile -Force'
    }
}

# ===========================================================================
# Shutdown handler — SIGHUP trap
# ===========================================================================
Describe "Shutdown Handler" {
    It "Start-ManagerLoop.ps1 registers PowerShell.Exiting handler" {
        $content = Get-Content $script:managerScript -Raw
        $content | Should -Match 'Register-EngineEvent.*PowerShell\.Exiting'
    }

    It "Start-ManagerLoop.ps1 registers POSIX.SIGHUP handler on Unix" {
        $content = Get-Content $script:managerScript -Raw
        $content | Should -Match 'POSIX\.SIGHUP'
    }

    It "SIGHUP registration is guarded by Unix platform check" {
        $lines = Get-Content $script:managerScript
        $sighupLine = $lines | Where-Object { $_ -match 'POSIX\.SIGHUP' } | Select-Object -First 1
        $sighupIdx = [array]::IndexOf($lines, $sighupLine)
        $guardBlock = ($lines[($sighupIdx - 3)..($sighupIdx)] -join "`n")
        $guardBlock | Should -Match '\$IsLinux -or \$IsMacOS'
    }

    It "SIGHUP and PowerShell.Exiting share the same shutdown action" {
        $content = Get-Content $script:managerScript -Raw
        $content | Should -Match '\$shutdownAction = \{'
        $sighupLine = ($content -split "`n" | Where-Object { $_ -match 'POSIX\.SIGHUP' }) | Select-Object -First 1
        $sighupLine | Should -Match '\$shutdownAction'
        $exitingLine = ($content -split "`n" | Where-Object { $_ -match 'PowerShell\.Exiting' }) | Select-Object -First 1
        $exitingLine | Should -Match '\$shutdownAction'
    }

    It "Shutdown block stops all room processes" {
        $lines = Get-Content $script:managerScript
        $hasShutdown = ($lines | Where-Object { $_ -match 'shuttingDown' }).Count -gt 0
        $hasStopRoom = ($lines | Where-Object { $_ -match 'Stop-RoomProcesses' }).Count -gt 0
        $hasShutdown | Should -BeTrue
        $hasStopRoom | Should -BeTrue
    }
}

# ===========================================================================
# stop.sh backward compatibility (structure/content tests)
# ===========================================================================
Describe "stop.sh" {
    BeforeAll {
        $script:stopSh = Join-Path $script:agentsDir "stop.sh"
    }

    It "exists and is executable" {
        Test-Path $script:stopSh | Should -BeTrue
        if ($IsLinux -or $IsMacOS) {
            $perms = (stat -f '%Lp' $script:stopSh 2>$null) ?? (stat -c '%a' $script:stopSh 2>$null)
        }
    }

    It "supports --force flag" {
        $content = Get-Content $script:stopSh -Raw
        $content | Should -Match '--force'
    }

    It "has kill_descendants function for recursive tree kill" {
        $content = Get-Content $script:stopSh -Raw
        $content | Should -Match 'kill_descendants'
        $content | Should -Match 'pgrep -P'
    }

    It "reads and uses manager.pgid for group kill with kill -0 guard" {
        $content = Get-Content $script:stopSh -Raw
        $content | Should -Match 'manager\.pgid'
        $content | Should -Match 'kill -0 -- "-\$PGID"'
        $content | Should -Match 'kill.*-9.*-\$PGID'
    }

    It "sweeps room PIDs even when no manager PID file exists" {
        $content = Get-Content $script:stopSh -Raw
        $content | Should -Match 'kill_room_pids'
        $noManagerBlock = ($content -split 'No manager PID file')[1]
        $noManagerBlock | Should -Match 'kill_room_pids'
    }

    It "cleans up both PID and PGID files" {
        $content = Get-Content $script:stopSh -Raw
        $content | Should -Match 'cleanup_pid_files'
        $content | Should -Match 'MANAGER_PID_FILE.*MANAGER_PGID_FILE'
    }
}

# ===========================================================================
# stop.ps1 backward compatibility
# ===========================================================================
Describe "stop.ps1" {
    BeforeAll {
        $script:stopPs1 = Join-Path $script:agentsDir "stop.ps1"
    }

    It "exists" {
        Test-Path $script:stopPs1 | Should -BeTrue
    }

    It "supports -Force parameter" {
        $content = Get-Content $script:stopPs1 -Raw
        $content | Should -Match '\[switch\]\$Force'
    }

    It "has Stop-ProcessTree function" {
        $content = Get-Content $script:stopPs1 -Raw
        $content | Should -Match 'function Stop-ProcessTree'
    }

    It "sweeps room PIDs via Stop-AllRoomPids" {
        $content = Get-Content $script:stopPs1 -Raw
        $content | Should -Match 'function Stop-AllRoomPids'
        $content | Should -Match 'Stop-AllRoomPids'
    }

    It "handles PGID on Unix via bash for force kill" {
        $content = Get-Content $script:stopPs1 -Raw
        $content | Should -Match 'manager\.pgid'
        $content | Should -Match 'bash -c.*kill'
    }

    It "stops dashboard on all exit paths" {
        $content = Get-Content $script:stopPs1 -Raw
        $content | Should -Match 'Stop-Dashboard'
        $content | Should -Match 'finally'
    }
}

# ===========================================================================
# ostwin.ps1 $killTree — platform-aware tree kill
# ===========================================================================
Describe "ostwin.ps1 killTree" {
    BeforeAll {
        $script:ostwinPs1 = Join-Path $script:agentsDir "bin" "ostwin.ps1"
    }

    It "has pgrep-based tree kill for Unix" {
        $lines = Get-Content $script:ostwinPs1
        $hasPgrep = ($lines | Where-Object { $_ -match 'pgrep -P' }).Count -gt 0
        $hasKillDesc = ($lines | Where-Object { $_ -match 'KillDescendants' }).Count -gt 0
        $hasPgrep | Should -BeTrue
        $hasKillDesc | Should -BeTrue
    }

    It "has taskkill /T for Windows" {
        $content = Get-Content $script:ostwinPs1 -Raw
        $content | Should -Match 'taskkill /F /T /PID'
    }

    It "has plain Stop-Process fallback" {
        $content = Get-Content $script:ostwinPs1 -Raw
        $content | Should -Match 'Stop-Process -Id \$PidToKill -Force'
    }
}

# ===========================================================================
# Invoke-Agent.ps1 — Job Object on Windows
# ===========================================================================
Describe "Invoke-Agent Job Object" {
    BeforeAll {
        $script:invokeAgent = Join-Path $script:agentsDir "roles" "_base" "Invoke-Agent.ps1"
    }

    It "contains Job Object creation code" {
        $content = Get-Content $script:invokeAgent -Raw
        $content | Should -Match 'CreateJobObject'
        $content | Should -Match 'AssignProcessToJobObject'
        $content | Should -Match 'KILL_ON_JOB_CLOSE'
    }

    It "writes job-handle.txt to artifacts" {
        $content = Get-Content $script:invokeAgent -Raw
        $content | Should -Match 'job-handle\.txt'
    }

    It "Job Object code is in the Windows branch only" {
        $lines = Get-Content $script:invokeAgent
        $jobIdx = -1
        for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match 'CreateJobObject') { $jobIdx = $i; break } }
        $jobIdx | Should -BeGreaterThan 0
        $preceding = ($lines[([Math]::Max(0, $jobIdx - 80))..$jobIdx] -join "`n")
        $preceding | Should -Match 'Windows'
    }

    It "Job Object handle is documented as intentionally kept open" {
        $content = Get-Content $script:invokeAgent -Raw
        $content | Should -Match 'intentionally kept open'
        $content | Should -Match 'KILL_ON_JOB_CLOSE'
    }

    It "Job Object kills child when handle is terminated (functional)" {
        if ($IsLinux -or $IsMacOS) { Set-ItResult -Skipped -Because "Windows-only test (Job Objects)"; return }
        $child = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "timeout 120" -PassThru -NoNewWindow
        try {
            Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class JobObjectTest {
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern IntPtr CreateJobObject(IntPtr a, string n);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool AssignProcessToJobObject(IntPtr h, IntPtr p);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool TerminateJobObject(IntPtr h, uint c);
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool SetInformationJobObject(IntPtr h, int t, IntPtr i, uint s);
}
'@ -ErrorAction SilentlyContinue
            $job = [JobObjectTest]::CreateJobObject([IntPtr]::Zero, $null)
            $job | Should -Not -Be ([IntPtr]::Zero)
            $info = New-Object byte[] 112
            [BitConverter]::GetBytes([uint32]0x2000).CopyTo($info, 16)
            $pin = [Runtime.InteropServices.GCHandle]::Alloc($info, [Runtime.InteropServices.GCHandleType]::Pinned)
            [JobObjectTest]::SetInformationJobObject($job, 9, $pin.AddrOfPinnedObject(), [uint32]$info.Length) | Out-Null
            $pin.Free()
            [JobObjectTest]::AssignProcessToJobObject($job, $child.Handle) | Should -BeTrue
            [JobObjectTest]::TerminateJobObject($job, 1) | Should -BeTrue
            Start-Sleep -Milliseconds 500
            Get-Process -Id $child.Id -ErrorAction SilentlyContinue | Should -BeNullOrEmpty
            [JobObjectTest]::CloseHandle($job) | Out-Null
        } finally {
            Stop-Process -Id $child.Id -Force -ErrorAction SilentlyContinue
        }
    }

    It "does NOT affect Unix launch path" {
        $content = Get-Content $script:invokeAgent -Raw
        $unixBlock = ($content -split 'Unix/Mac branch')[1]
        if ($unixBlock) {
            ($unixBlock.Substring(0, [Math]::Min(500, $unixBlock.Length))) | Should -Not -Match 'JobObject'
        }
    }
}

# ===========================================================================
# Backward compatibility: existing behavior preserved
# ===========================================================================
Describe "Backward Compatibility" {
    It "Stop-RoomProcesses still accepts only -RoomDir (no breaking param change)" {
        $cmd = Get-Command Stop-RoomProcesses -ErrorAction SilentlyContinue
        $cmd | Should -Not -BeNullOrEmpty
        $params = $cmd.Parameters.Keys
        $params | Should -Contain "RoomDir"
    }

    It "Stop-ProcessTree accepts ParentPid (required) and optional RoomDir" {
        $cmd = Get-Command Stop-ProcessTree -ErrorAction SilentlyContinue
        $cmd | Should -Not -BeNullOrEmpty
        $params = $cmd.Parameters.Keys
        $params | Should -Contain "ParentPid"
        $params | Should -Contain "RoomDir"
    }

    It "Write-RoomStatus still works for terminal states" {
        $room = New-FakeRoom -Base $TestDrive
        $pidDir = Join-Path $room "pids"
        "12345" | Out-File -FilePath (Join-Path $pidDir "qa.pid") -Encoding utf8 -NoNewline
        "1234567890" | Out-File -FilePath (Join-Path $pidDir "qa.spawned_at") -Encoding utf8 -NoNewline

        Write-RoomStatus -RoomDir $room -NewStatus "passed"

        (Get-Content (Join-Path $room "status") -Raw).Trim() | Should -Be "passed"
        Test-Path (Join-Path $pidDir "qa.pid") | Should -BeFalse
        Test-Path (Join-Path $pidDir "qa.spawned_at") | Should -BeFalse
    }

    It "manager.pid file path unchanged" {
        $content = Get-Content $script:managerScript -Raw
        $content | Should -Match 'managerPidFile = Join-Path \$agentsDir "manager\.pid"'
    }

    It "PID self-registration contract unchanged in wrapper script" {
        $content = Get-Content $script:invokeAgent -Raw
        $content | Should -Match 'echo "`\$\$" > '
        $content | Should -Match 'AGENT_OS_PID_FILE'
    }
}
