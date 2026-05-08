#Requires -Version 7.0
# Agent OS — Structured Logging Module
#
# Import:
#   Import-Module "$PSScriptRoot/Log.psm1"
#
# Usage:
#   Write-OstwinLog -Level INFO -Message "Manager started"
#   Write-OstwinLog -Level WARN -Message "Room stuck" -Properties @{ room_id = "room-001" }
#   Write-OstwinJsonLog -Level INFO -Event "manager_started" -Data @{ max_concurrent = 50 }

# --- Module-level state ---
$script:LogLevelMap = @{
    'DEBUG' = 0
    'INFO'  = 1
    'WARN'  = 2
    'ERROR' = 3
}

function Get-OstwinLogDir {
    <#
    .SYNOPSIS
        Resolves the log directory from environment or convention.
    #>
    [CmdletBinding()]
    param()

    $agentsDir = if ($env:AGENTS_DIR) { $env:AGENTS_DIR }
                 else { (Resolve-Path (Join-Path $PSScriptRoot ".." -ErrorAction SilentlyContinue)).Path }

    $logDir = if ($env:AGENT_OS_LOG_DIR) { $env:AGENT_OS_LOG_DIR }
              else { Join-Path $agentsDir "logs" }

    if (-not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }

    return $logDir
}

function Get-OstwinLogLevel {
    <#
    .SYNOPSIS
        Returns the current minimum log level (from env or default INFO).
    #>
    [CmdletBinding()]
    param()

    $level = if ($env:AGENT_OS_LOG_LEVEL) { $env:AGENT_OS_LOG_LEVEL.ToUpper() } else { 'INFO' }
    if (-not $script:LogLevelMap.ContainsKey($level)) {
        $level = 'INFO'
    }
    return $level
}

function Write-OstwinLog {
    <#
    .SYNOPSIS
        Writes a structured log line to stderr and to the ostwin.log file.
    .PARAMETER Level
        Log level: DEBUG, INFO, WARN, ERROR
    .PARAMETER Message
        The log message.
    .PARAMETER Properties
        Optional hashtable of key=value pairs appended to the log line.
    .PARAMETER Caller
        Optional caller name (auto-detected if not supplied).
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateSet('DEBUG', 'INFO', 'WARN', 'ERROR')]
        [string]$Level,

        [Parameter(Mandatory)]
        [string]$Message,

        [hashtable]$Properties = @{},

        [string]$Caller = ''
    )

    # Level gate
    $currentLevel = Get-OstwinLogLevel
    if ($script:LogLevelMap[$Level] -lt $script:LogLevelMap[$currentLevel]) {
        return
    }

    # Timestamp
    $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

    # Caller detection
    if (-not $Caller) {
        $callStack = Get-PSCallStack
        $Caller = if ($callStack.Count -gt 1) { $callStack[1].FunctionName } else { 'main' }
        if ($Caller -eq '<ScriptBlock>') { $Caller = 'main' }
    }

    # Build line
    $propStr = ''
    if ($Properties.Count -gt 0) {
        $propStr = ' ' + (($Properties.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ' ')
    }
    $line = "[$ts] [$Level] [$Caller] $Message$propStr"

    # Write to stderr
    Write-Host $line -ForegroundColor $(
        switch ($Level) {
            'DEBUG' { 'DarkGray' }
            'INFO'  { 'White' }
            'WARN'  { 'Yellow' }
            'ERROR' { 'Red' }
        }
    )

    # Write to file
    try {
        $logDir = Get-OstwinLogDir
        $logFile = Join-Path $logDir 'ostwin.log'
        $line | Out-File -Append -FilePath $logFile -Encoding utf8
    }
    catch {
        # Log file write failure to stderr only (avoid infinite recursion)
        Write-Warning "Log file write failed: $($_.Exception.Message)"
    }
}

function Write-OstwinJsonLog {
    <#
    .SYNOPSIS
        Writes a structured JSON log event to ostwin.jsonl.
    .PARAMETER Level
        Log level: DEBUG, INFO, WARN, ERROR
    .PARAMETER Event
        Event name (e.g. "manager_started", "room_created").
    .PARAMETER Data
        Optional hashtable of event data.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateSet('DEBUG', 'INFO', 'WARN', 'ERROR')]
        [string]$Level,

        [Parameter(Mandatory)]
        [string]$Event,

        [hashtable]$Data = @{}
    )

    $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

    $entry = @{
        ts    = $ts
        level = $Level
        event = $Event
        data  = $Data
    }

    try {
        $logDir = Get-OstwinLogDir
        $jsonlFile = Join-Path $logDir 'ostwin.jsonl'
        ($entry | ConvertTo-Json -Compress -Depth 5) | Out-File -Append -FilePath $jsonlFile -Encoding utf8
    }
    catch {
        Write-Warning "JSON log file write failed: $($_.Exception.Message)"
    }
}

Export-ModuleMember -Function Write-OstwinLog, Write-OstwinJsonLog, Get-OstwinLogDir, Get-OstwinLogLevel
