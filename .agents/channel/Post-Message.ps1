<#
.SYNOPSIS
    Posts a message to a war-room JSONL channel.

.DESCRIPTION
    Writes a validated, timestamped JSON message to the war-room's channel.jsonl file.
    Uses file locking for concurrent write safety.

    Replaces: channel/post.sh

.PARAMETER RoomDir
    Path to the war-room directory.
.PARAMETER From
    Sender role (e.g. manager, engineer, qa).
.PARAMETER To
    Recipient role.
.PARAMETER Type
    Message type (task, done, review, pass, fail, fix, error, signoff, release).
.PARAMETER Ref
    Task/Epic reference (e.g. TASK-001, EPIC-001).
.PARAMETER Body
    Message body content.
.PARAMETER ConfigPath
    Optional path to config.json for max message size.

.EXAMPLE
    ./Post-Message.ps1 -RoomDir "./war-rooms/room-001" -From manager -To engineer `
                       -Type task -Ref "TASK-001" -Body "Implement auth"

.OUTPUTS
    [string] The generated message ID.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RoomDir,

    [Parameter(Mandatory)]
    [string]$From,

    [Parameter(Mandatory)]
    [string]$To,

    [Parameter(Mandatory)]
    [ValidateSet('task', 'done', 'review', 'pass', 'fail', 'fix', 'error', 'signoff', 'release', 'plan-review', 'plan-approve', 'plan-reject', 'escalate', 'design-review', 'design-guidance', 'plan-update')]
    [string]$Type,

    [Parameter(Mandatory)]
    [string]$Ref,

    [Parameter(Mandatory)]
    [AllowEmptyString()]
    [string]$Body,

    [string]$ConfigPath = ''
)

# --- Constants ---
# Dynamic role discovery — any role with a role.json is valid
$ValidRoles = @('manager')  # Manager is always valid
$agentsDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$getAvailableRoles = Join-Path $agentsDir "roles" "_base" "Get-AvailableRoles.ps1"
if (Test-Path $getAvailableRoles) {
    try {
        $discovered = & $getAvailableRoles -AgentsDir $agentsDir
        $ValidRoles += ($discovered | ForEach-Object { $_.Name })
    } catch {
        # Fallback to legacy list if discovery fails
        $ValidRoles = @('manager', 'engineer', 'qa', 'architect', 'devops', 'tech-writer', 'security', 'product-owner')
    }
} else {
    $ValidRoles = @('manager', 'engineer', 'qa', 'architect', 'devops', 'tech-writer', 'security', 'product-owner')
}
$DefaultMaxMessageSize = 65536

# --- Resolve config ---
$maxSize = $DefaultMaxMessageSize
if ($ConfigPath -and (Test-Path $ConfigPath)) {
    try {
        $config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
        $maxSize = $config.channel.max_message_size_bytes
    }
    catch { }
}
elseif ($env:AGENT_OS_CONFIG -and (Test-Path $env:AGENT_OS_CONFIG)) {
    try {
        $config = Get-Content $env:AGENT_OS_CONFIG -Raw | ConvertFrom-Json
        $maxSize = $config.channel.max_message_size_bytes
    }
    catch { }
}

# --- Validation ---
if ($From -notin $ValidRoles) {
    Write-Warning "Invalid from role: $From"
}

# --- Body size enforcement ---
if ($Body.Length -gt $maxSize) {
    $originalLength = $Body.Length
    $Body = $Body.Substring(0, $maxSize) + "`n[TRUNCATED: original $originalLength bytes, max $maxSize]"
}

# --- Ensure room directory and channel file exist ---
if (-not (Test-Path $RoomDir)) {
    New-Item -ItemType Directory -Path $RoomDir -Force | Out-Null
}
$channelFile = Join-Path $RoomDir "channel.jsonl"
if (-not (Test-Path $channelFile)) {
    New-Item -ItemType File -Path $channelFile -Force | Out-Null
}

# --- Build message ---
$ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$nanoTicks = [System.DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() * 1000000
$msgId = "$From-$Type-$nanoTicks-$PID"

$msg = [ordered]@{
    v    = 1
    id   = $msgId
    ts   = $ts
    from = $From
    to   = $To
    type = $Type
    ref  = $Ref
    body = $Body
}

$jsonLine = ($msg | ConvertTo-Json -Compress -Depth 5)

# --- Atomic write with file locking ---
$mutex = [System.Threading.Mutex]::new($false, "OstwinChannel_$(($channelFile -replace '[\\\/:]', '_'))")
try {
    $mutex.WaitOne() | Out-Null
    $jsonLine | Out-File -Append -FilePath $channelFile -Encoding utf8 -NoNewline
    "`n" | Out-File -Append -FilePath $channelFile -Encoding utf8 -NoNewline
}
finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}

# --- Output the message ID ---
Write-Output $msgId
