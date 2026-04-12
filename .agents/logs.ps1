<#
.SYNOPSIS
    Agent OS — Channel Log Viewer (PowerShell port of logs.sh)

.DESCRIPTION
    View and filter JSONL channel messages across war-rooms.

.PARAMETER RoomId
    Specific room to view logs for (e.g. room-001). If omitted, shows all rooms.

.PARAMETER Follow
    Tail -f style: watch for new messages.

.PARAMETER Type
    Filter by message type (task, done, review, pass, fail, fix, error, signoff).

.PARAMETER From
    Filter by sender role (engineer, qa, manager, architect).

.PARAMETER Last
    Show only the last N messages.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$RoomId,

    [Alias('f')]
    [switch]$Follow,

    [string]$Type,

    [string]$From,

    [int]$Last = 0
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path $PSCommandPath -Parent
$AgentsDir = $ScriptDir
$WarroomsDir = if ($env:WARROOMS_DIR) { $env:WARROOMS_DIR } else { Join-Path $AgentsDir "war-rooms" }

# ─── Message formatter ──────────────────────────────────────────────────────

$TypeIcons = @{
    "task"    = "TASK"
    "done"    = " OK "
    "review"  = " QA "
    "pass"    = "PASS"
    "fail"    = "FAIL"
    "fix"     = " FIX"
    "error"   = " ERR"
    "signoff" = "SIGN"
    "release" = " REL"
}

function Format-ChannelMessage {
    param([PSObject]$Msg)

    # Apply filters
    if ($Type -and $Msg.type -ne $Type) { return $null }
    if ($From -and $Msg.from -ne $From) { return $null }

    $ts = if ($Msg.ts.Length -gt 19) { $Msg.ts.Substring(0, 19) } else { $Msg.ts }
    $fromR = if ($Msg.from) { $Msg.from } else { "?" }
    $toR = if ($Msg.to) { $Msg.to } else { "?" }
    $mtype = if ($Msg.type) { $Msg.type } else { "?" }
    $ref = if ($Msg.ref) { $Msg.ref } else { "?" }
    $body = if ($Msg.body) { ($Msg.body -replace "`n", " ") } else { "" }
    if ($body.Length -gt 120) { $body = $body.Substring(0, 120) }

    $icon = if ($TypeIcons.ContainsKey($mtype)) { $TypeIcons[$mtype] } else { $mtype.ToUpper().Substring(0, [Math]::Min(4, $mtype.Length)) }

    return "$ts [$icon] ${fromR}->${toR} ${ref}: $body"
}

function Read-JsonlFile {
    param([string]$Path)
    $messages = @()
    foreach ($line in Get-Content $Path -ErrorAction SilentlyContinue) {
        $trimmed = $line.Trim()
        if (-not $trimmed) { continue }
        try {
            $msg = $trimmed | ConvertFrom-Json
            $messages += $msg
        }
        catch { continue }
    }
    return $messages
}

# ─── Main logic ──────────────────────────────────────────────────────────────

if ($RoomId) {
    # Single room
    $roomDir = Join-Path $WarroomsDir $RoomId
    if (-not (Test-Path $roomDir -PathType Container)) {
        Write-Error "[ERROR] Room not found: $RoomId"
        exit 1
    }

    $channelFile = Join-Path $roomDir "channel.jsonl"
    if (-not (Test-Path $channelFile)) {
        Write-Host "[INFO] No messages in $RoomId."
        exit 0
    }

    if ($Follow) {
        Write-Host "[LOGS] Following $RoomId (Ctrl+C to stop)..."
        # Use Get-Content -Wait for follow mode
        Get-Content $channelFile -Wait -Tail 0 | ForEach-Object {
            $trimmed = $_.Trim()
            if (-not $trimmed) { return }
            try {
                $msg = $trimmed | ConvertFrom-Json
                $formatted = Format-ChannelMessage -Msg $msg
                if ($formatted) { Write-Host $formatted }
            }
            catch { }
        }
    }
    else {
        $messages = Read-JsonlFile -Path $channelFile
        if ($Last -gt 0 -and $messages.Count -gt $Last) {
            $messages = $messages[-$Last..-1]
        }
        foreach ($msg in $messages) {
            $formatted = Format-ChannelMessage -Msg $msg
            if ($formatted) { Write-Host $formatted }
        }
    }
}
else {
    # All rooms
    $allMessages = @()

    if (Test-Path $WarroomsDir) {
        foreach ($roomDir in Get-ChildItem -Path $WarroomsDir -Directory -Filter "room-*" -ErrorAction SilentlyContinue) {
            $channelFile = Join-Path $roomDir.FullName "channel.jsonl"
            if (-not (Test-Path $channelFile)) { continue }
            $allMessages += Read-JsonlFile -Path $channelFile
        }
    }

    # Sort by timestamp
    $allMessages = $allMessages | Sort-Object { $_.ts }

    # Apply --last
    if ($Last -gt 0 -and $allMessages.Count -gt $Last) {
        $allMessages = $allMessages[-$Last..-1]
    }

    foreach ($msg in $allMessages) {
        $formatted = Format-ChannelMessage -Msg $msg
        if ($formatted) { Write-Host $formatted }
    }
}
