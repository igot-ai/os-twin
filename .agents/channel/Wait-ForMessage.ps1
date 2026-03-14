<#
.SYNOPSIS
    Blocks until a specific message type appears in a war-room channel.

.DESCRIPTION
    Polls the channel.jsonl file at regular intervals until a message matching
    the specified type (and optional filters) appears. Returns the matching message.

    Replaces: channel/wait-for.sh

.PARAMETER RoomDir
    Path to the war-room directory.
.PARAMETER WaitType
    Message type to wait for (e.g. done, pass, fail).
.PARAMETER FilterFrom
    Optional. Only match messages from this role.
.PARAMETER FilterRef
    Optional. Only match messages with this task/epic reference.
.PARAMETER TimeoutSeconds
    Maximum seconds to wait. 0 = wait forever. Default: 0.
.PARAMETER PollIntervalSeconds
    Seconds between polls. Default: 3.

.EXAMPLE
    ./Wait-ForMessage.ps1 -RoomDir "./war-rooms/room-001" -WaitType "done"
    ./Wait-ForMessage.ps1 -RoomDir "./war-rooms/room-001" -WaitType "pass" -FilterFrom "qa" -TimeoutSeconds 600

.OUTPUTS
    [string] JSON of the matching message, or error JSON on timeout.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RoomDir,

    [Parameter(Mandatory)]
    [string[]]$WaitType,

    [string]$FilterFrom = '',
    [string]$FilterRef = '',
    [int]$TimeoutSeconds = 0,
    [int]$PollIntervalSeconds = 3
)

$ReadMessages = Join-Path $PSScriptRoot "Read-Messages.ps1"
$elapsed = 0

while ($true) {
    if (Test-Path (Join-Path $RoomDir "channel.jsonl")) {
        # Build filter arguments
        $readArgs = @{
            RoomDir    = $RoomDir
            FilterType = $WaitType
            Last       = 1
            AsObject   = $true
        }
        if ($FilterFrom) { $readArgs['FilterFrom'] = $FilterFrom }
        if ($FilterRef) { $readArgs['FilterRef'] = $FilterRef }

        $msgs = & $ReadMessages @readArgs

        if ($msgs -and $msgs.Count -gt 0) {
            # Found a matching message — return it as JSON
            $result = $msgs[-1] | ConvertTo-Json -Compress -Depth 10
            Write-Output $result
            exit 0
        }
    }

    # Check timeout
    if ($TimeoutSeconds -gt 0 -and $elapsed -ge $TimeoutSeconds) {
        $errorObj = @{
            error          = "timeout"
            waited_seconds = $elapsed
        } | ConvertTo-Json -Compress
        Write-Error $errorObj
        exit 1
    }

    Start-Sleep -Seconds $PollIntervalSeconds
    $elapsed += $PollIntervalSeconds
}
