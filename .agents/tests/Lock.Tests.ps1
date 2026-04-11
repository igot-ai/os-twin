#Requires -Version 7.0
# Agent OS — Lock Module Pester Tests
#
# Tests for Invoke-WithFileLock: basic execution, timeout behaviour,
# concurrent serialisation, and lock-file release.

BeforeAll {
    Import-Module (Join-Path (Resolve-Path "$PSScriptRoot/../.agents/lib").Path "Lock.psm1") -Force
}

AfterAll {
    Remove-Module -Name "Lock" -ErrorAction SilentlyContinue
}

# ─── Invoke-WithFileLock ─────────────────────────────────────────────────────

Describe "Invoke-WithFileLock" {

    It "executes the script block and returns its result" {
        $lockFile = Join-Path $TestDrive "basic.lock"
        $result = Invoke-WithFileLock -LockFile $lockFile -ScriptBlock { 42 }
        $result | Should -Be 42
    }

    It "creates the lock file if it does not exist" {
        $lockFile = Join-Path $TestDrive "create-test.lock"
        Invoke-WithFileLock -LockFile $lockFile -ScriptBlock { $true } | Out-Null
        Test-Path $lockFile | Should -BeTrue
    }

    It "releases the lock after execution so the file can be reopened" {
        $lockFile = Join-Path $TestDrive "release.lock"
        Invoke-WithFileLock -LockFile $lockFile -ScriptBlock { "first" } | Out-Null

        # A second call should succeed immediately -- the lock was released
        $result = Invoke-WithFileLock -LockFile $lockFile -ScriptBlock { "second" }
        $result | Should -Be "second"
    }

    It "releases the lock even when the script block throws" {
        $lockFile = Join-Path $TestDrive "throw.lock"
        { Invoke-WithFileLock -LockFile $lockFile -ScriptBlock { throw "boom" } } |
            Should -Throw "boom"

        # Lock must be released -- next call should succeed
        $result = Invoke-WithFileLock -LockFile $lockFile -ScriptBlock { "recovered" }
        $result | Should -Be "recovered"
    }

    It "throws on timeout when the lock is held by another handle" {
        $lockFile = Join-Path $TestDrive "timeout.lock"

        # Acquire the lock externally so Invoke-WithFileLock cannot get it
        $externalLock = [System.IO.File]::Open(
            $lockFile,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
        try {
            { Invoke-WithFileLock -LockFile $lockFile -ScriptBlock { "nope" } -TimeoutMs 200 -RetryIntervalMs 50 } |
                Should -Throw "*Failed to acquire lock*"
        }
        finally {
            $externalLock.Close()
            $externalLock.Dispose()
        }
    }

    It "serialises concurrent calls so writes do not interleave" {
        $lockFile = Join-Path $TestDrive "concurrent.lock"
        $outputFile = Join-Path $TestDrive "concurrent-output.txt"
        "" | Out-File -FilePath $outputFile -Encoding utf8 -NoNewline

        # Use background jobs to simulate concurrent writers
        $jobs = 1..5 | ForEach-Object {
            $idx = $_
            Start-Job -ScriptBlock {
                param($ModulePath, $LockPath, $OutPath, $Index)
                Import-Module $ModulePath -Force
                Invoke-WithFileLock -LockFile $LockPath -ScriptBlock {
                    # Append our index -- under lock, so lines should not interleave
                    "writer-$Index" | Out-File -Append -FilePath $OutPath -Encoding utf8
                }
            } -ArgumentList (Join-Path (Resolve-Path "$PSScriptRoot/../.agents/lib").Path "Lock.psm1"), $lockFile, $outputFile, $idx
        }

        $jobs | Wait-Job -Timeout 30 | Out-Null
        $jobs | ForEach-Object {
            $_ | Receive-Job -ErrorAction SilentlyContinue | Out-Null
            $_ | Remove-Job -Force
        }

        $lines = Get-Content $outputFile | Where-Object { $_ -match '\S' }
        $lines.Count | Should -Be 5
        # Each writer should appear exactly once
        foreach ($i in 1..5) {
            $lines | Should -Contain "writer-$i"
        }
    }

    It "passes variables from the outer scope into the script block" {
        $lockFile = Join-Path $TestDrive "scope.lock"
        $outerValue = "hello-from-outer"
        $result = Invoke-WithFileLock -LockFile $lockFile -ScriptBlock { $outerValue }
        $result | Should -Be "hello-from-outer"
    }
}
