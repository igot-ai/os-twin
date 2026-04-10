#Requires -Version 7.0
# Agent OS — File Locking Module
#
# Provides exclusive file-based locking for cross-process synchronisation.
# Uses [System.IO.File]::Open() with FileShare.None to acquire an OS-level
# exclusive lock, preventing TOCTOU races on shared files like status,
# channel.jsonl, and PID files.
#
# Import:
#   Import-Module "$PSScriptRoot/Lock.psm1"

function Invoke-WithFileLock {
    <#
    .SYNOPSIS
        Executes a script block while holding an exclusive file lock.
    .DESCRIPTION
        Acquires an OS-level exclusive lock on the specified lock file using
        [System.IO.File]::Open() with FileShare.None. Retries until the lock
        is acquired or the timeout expires. The lock is always released in the
        finally block, even if the script block throws.
    .PARAMETER LockFile
        Path to the lock file. Will be created if it does not exist.
    .PARAMETER ScriptBlock
        The script block to execute while the lock is held.
    .PARAMETER TimeoutMs
        Maximum time in milliseconds to wait for the lock. Default: 5000.
    .PARAMETER RetryIntervalMs
        Time in milliseconds between retry attempts. Default: 50.
    .OUTPUTS
        Whatever the ScriptBlock returns.
    .EXAMPLE
        Invoke-WithFileLock -LockFile "/tmp/my.lock" -ScriptBlock { "hello" | Out-File /tmp/data.txt }
    #>
    [CmdletBinding()]
    [OutputType([object])]
    param(
        [Parameter(Mandatory)]
        [string]$LockFile,

        [Parameter(Mandatory)]
        [scriptblock]$ScriptBlock,

        [int]$TimeoutMs = 5000,

        [int]$RetryIntervalMs = 50
    )

    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
    $lock = $null
    try {
        while ([DateTime]::UtcNow -lt $deadline) {
            try {
                $lock = [System.IO.File]::Open(
                    $LockFile,
                    [System.IO.FileMode]::OpenOrCreate,
                    [System.IO.FileAccess]::ReadWrite,
                    [System.IO.FileShare]::None
                )
                break
            }
            catch [System.IO.IOException] {
                Start-Sleep -Milliseconds $RetryIntervalMs
            }
        }
        if (-not $lock) {
            throw "Failed to acquire lock on '$LockFile' within ${TimeoutMs}ms"
        }
        # Execute the protected script block
        & $ScriptBlock
    }
    finally {
        if ($lock) {
            $lock.Close()
            $lock.Dispose()
        }
    }
}

Export-ModuleMember -Function Invoke-WithFileLock
