<#
.SYNOPSIS
    Reads messages from a war-room JSONL channel with optional filters.

.DESCRIPTION
    Parses channel.jsonl and returns matching messages as JSON array.
    Supports filtering by from, to, type, ref, after (message ID), and last N.

    Replaces: channel/read.sh

.PARAMETER RoomDir
    Path to the war-room directory.
.PARAMETER FilterFrom
    Optional. Filter by sender role.
.PARAMETER FilterTo
    Optional. Filter by recipient role.
.PARAMETER FilterType
    Optional. Filter by message type.
.PARAMETER FilterRef
    Optional. Filter by task/epic reference.
.PARAMETER Last
    Optional. Return only the last N messages.
.PARAMETER After
    Optional. Return only messages after the given message ID.
.PARAMETER AsObject
    If set, returns PSObjects instead of JSON string.

.EXAMPLE
    ./Read-Messages.ps1 -RoomDir "./war-rooms/room-001"
    ./Read-Messages.ps1 -RoomDir "./war-rooms/room-001" -FilterType "done" -Last 1

.OUTPUTS
    [string] JSON array of matching messages (default), or [PSObject[]] with -AsObject.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RoomDir,

    [string]$FilterFrom = '',
    [string]$FilterTo = '',
    [string]$FilterType = '',
    [string]$FilterRef = '',
    [int]$Last = 0,
    [string]$After = '',
    [switch]$AsObject
)

$channelFile = Join-Path $RoomDir "channel.jsonl"

# Return empty array if no channel file
if (-not (Test-Path $channelFile)) {
    if ($AsObject) { return @() }
    Write-Output '[]'
    return
}

$messages = [System.Collections.Generic.List[PSObject]]::new()
$foundAfter = (-not $After)  # If no After filter, start collecting immediately
$lineNum = 0

foreach ($line in (Get-Content $channelFile -Encoding utf8)) {
    $lineNum++
    $trimmed = $line.Trim()
    if (-not $trimmed) { continue }

    # Parse JSON — skip corrupt lines gracefully
    try {
        $msg = $trimmed | ConvertFrom-Json
    }
    catch {
        Write-Warning "Skipping corrupt JSON at line $lineNum"
        continue
    }

    # Handle --after: skip until we find the target message ID
    if (-not $foundAfter) {
        if ($msg.id -eq $After) {
            $foundAfter = $true
        }
        continue
    }

    # Apply filters
    if ($FilterFrom -and $msg.from -ne $FilterFrom) { continue }
    if ($FilterTo -and $msg.to -ne $FilterTo) { continue }
    if ($FilterType -and $msg.type -ne $FilterType) { continue }
    if ($FilterRef -and $msg.ref -ne $FilterRef) { continue }

    $messages.Add($msg)
}

# Apply --last N
if ($Last -gt 0 -and $messages.Count -gt $Last) {
    $messages = [System.Collections.Generic.List[PSObject]]::new(
        $messages.GetRange($messages.Count - $Last, $Last)
    )
}

if ($AsObject) {
    return $messages.ToArray()
}

# Output as JSON array
$output = $messages.ToArray() | ConvertTo-Json -Depth 10 -Compress
# ConvertTo-Json returns a single object (not array) when there's exactly 1 item
if ($messages.Count -eq 1) {
    $output = "[$output]"
}
elseif ($messages.Count -eq 0) {
    $output = '[]'
}

Write-Output $output
