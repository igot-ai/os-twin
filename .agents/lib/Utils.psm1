# Agent OS — Shared Utilities Module
#
# Import:
#   Import-Module "$PSScriptRoot/Utils.psm1"
#
# Replaces: lib/utils.sh
# Provides: config reading, status management, PID tracking, text truncation

function Read-OstwinConfig {
    <#
    .SYNOPSIS
        Reads a value from the Agent OS config.json using a dot-separated key path.
    .PARAMETER KeyPath
        Dot-separated key path, e.g. "manager.poll_interval_seconds"
    .PARAMETER ConfigPath
        Optional path to config.json. Defaults to AGENT_OS_CONFIG env var or .agents/config.json.
    .EXAMPLE
        Read-OstwinConfig -KeyPath "manager.max_concurrent_rooms"
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$KeyPath,

        [string]$ConfigPath = ''
    )

    if (-not $ConfigPath) {
        $ConfigPath = if ($env:AGENT_OS_CONFIG) { $env:AGENT_OS_CONFIG }
                      elseif ($env:AGENTS_DIR) { Join-Path $env:AGENTS_DIR "config.json" }
                      else {
                          $agentsDir = (Resolve-Path (Join-Path $PSScriptRoot "..") -ErrorAction SilentlyContinue).Path
                          Join-Path $agentsDir "config.json"
                      }
    }

    if (-not (Test-Path $ConfigPath)) {
        throw "Config file not found: $ConfigPath"
    }

    $config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
    $keys = $KeyPath.Split('.')
    $current = $config

    foreach ($key in $keys) {
        if ($null -eq $current) {
            throw "Key path '$KeyPath' not found in config: null at '$key'"
        }
        $current = $current.$key
    }

    if ($current -is [bool]) {
        return $current.ToString().ToLower()
    }

    return $current
}

function Test-Underspecified {
    <#
    .SYNOPSIS
        Checks if a plan or epic section is underspecified.
    .PARAMETER Content
        The markdown content of the full plan or a single epic section.
    .PARAMETER MinDod
        Minimum number of checkboxes in Definition of Done. Default: 5.
    .PARAMETER MinAc
        Minimum number of checkboxes in Acceptance Criteria. Default: 5.
    .PARAMETER MinBullets
        Minimum number of bullet points in description. Default: 2.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Content,
        [int]$MinDod = 5,
        [int]$MinAc = 5,
        [int]$MinBullets = 2
    )

    $epicPattern = '(?m)^#{2,3}\s+(EPIC-\d+)\s*[-—–]\s*(.+)$'
    
    # If the content contains multiple "## EPIC-NNN" headers, iterate through them
    $epicMatches = [regex]::Matches($Content, $epicPattern)
    
    if ($epicMatches.Count -gt 0) {
        foreach ($em in $epicMatches) {
            $epicStart = $em.Index
            $nextMatch = $epicMatches | Where-Object { $_.Index -gt $epicStart } | Select-Object -First 1
            $epicEnd = if ($nextMatch) { $nextMatch.Index } else { $Content.Length }
            $epicSection = $Content.Substring($epicStart, $epicEnd - $epicStart)
            
            if (Test-SingleEpicUnderspecified -EpicSection $epicSection -MinDod $MinDod -MinAc $MinAc -MinBullets $MinBullets) {
                return $true
            }
        }
        return $false
    }
    else {
        # Check as a single epic section
        return Test-SingleEpicUnderspecified -EpicSection $Content -MinDod $MinDod -MinAc $MinAc -MinBullets $MinBullets
    }
}

function Test-SingleEpicUnderspecified {
    param([string]$EpicSection, [int]$MinDod, [int]$MinAc, [int]$MinBullets)
    
    $dodPattern = '(?s)#### Definition of Done\s*\n(.*?)(?=####|^## EPIC-|---|\z)'
    $acPattern  = '(?s)#### Acceptance Criteria\s*\n(.*?)(?=####|^## EPIC-|---|\z)'
    
    # Extract description body: from first newline after header to first subheader or end
    $descBody = ""
    $firstNewline = $EpicSection.IndexOf("`n")
    if ($firstNewline -ge 0) {
        $firstSubheader = $EpicSection.IndexOf("`n####", $firstNewline)
        if ($firstSubheader -gt 0) {
            $descBody = $EpicSection.Substring($firstNewline + 1, $firstSubheader - $firstNewline - 1).Trim()
        } else {
            # Check for the start of the next EPIC or a horizontal rule if not already handled
            $nextEpic = $EpicSection.IndexOf("`n## EPIC-", $firstNewline)
            $hr = $EpicSection.IndexOf("`n---", $firstNewline)
            $endIndex = $EpicSection.Length
            if ($nextEpic -gt 0 -and $nextEpic -lt $endIndex) { $endIndex = $nextEpic }
            if ($hr -gt 0 -and $hr -lt $endIndex) { $endIndex = $hr }
            $descBody = $EpicSection.Substring($firstNewline + 1, $endIndex - $firstNewline - 1).Trim()
        }
    }
    
    $dodCount = 0
    if ($EpicSection -match $dodPattern) {
        $dodBlock = $Matches[1]
        $dodCount = ([regex]::Matches($dodBlock, '(?m)^[-*] \[[ x]\]\s*(.+)')).Count
    }
    
    $acCount = 0
    if ($EpicSection -match $acPattern) {
        $acBlock = $Matches[1]
        $acCount = ([regex]::Matches($acBlock, '(?m)^[-*] \[[ x]\]\s*(.+)')).Count
    }

    $bulletCount = 0
    if ($descBody) {
        # Count structured content: dash/asterisk bullets, numbered items, OR paragraphs (50+ char lines)
        $bulletCount = ([regex]::Matches($descBody, '(?m)^([-*]\s+|\d+\.\s+)')).Count
        if ($bulletCount -lt $MinBullets) {
            # Fall back to counting substantial paragraphs (lines with 50+ chars)
            $paraCount = ([regex]::Matches($descBody, '(?m)^.{50,}')).Count
            if ($paraCount -gt $bulletCount) { $bulletCount = $paraCount }
        }
    }
    
    return ($dodCount -lt $MinDod -or $acCount -lt $MinAc -or $bulletCount -lt $MinBullets)
}

function Set-WarRoomStatus {
    <#
    .SYNOPSIS
        Atomically writes a war-room status with audit trail.
    .PARAMETER RoomDir
        Path to the war-room directory.
    .PARAMETER NewStatus
        The new status to set.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$RoomDir,

        [Parameter(Mandatory)]
        [ValidatePattern('^[a-z][a-z0-9-]*$')]
        [string]$NewStatus
    )

    if (-not (Test-Path $RoomDir)) {
        throw "War-room directory not found: $RoomDir"
    }

    $statusFile = Join-Path $RoomDir "status"
    $oldStatus = if (Test-Path $statusFile) { (Get-Content $statusFile -Raw).Trim() } else { 'unknown' }

    # Write new status
    $NewStatus | Out-File -FilePath $statusFile -Encoding utf8 -NoNewline

    # Write state_changed_at (Unix epoch)
    $epoch = [int][double]::Parse((Get-Date -UFormat %s))
    $epoch.ToString() | Out-File -FilePath (Join-Path $RoomDir "state_changed_at") -Encoding utf8 -NoNewline

    # Append to audit trail
    $ts = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $auditLine = "$ts STATUS $oldStatus -> $NewStatus"
    $auditLine | Out-File -Append -FilePath (Join-Path $RoomDir "audit.log") -Encoding utf8
}

function Test-PidAlive {
    <#
    .SYNOPSIS
        Checks if a PID (read from a .pid file) is still running.
    .PARAMETER PidFile
        Path to the .pid file.
    .OUTPUTS
        [bool] True if the process is alive.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$PidFile
    )

    if (-not (Test-Path $PidFile)) {
        return $false
    }

    $pidStr = (Get-Content $PidFile -Raw -ErrorAction SilentlyContinue)
    if ([string]::IsNullOrWhiteSpace($pidStr)) {
        return $false
    }
    $pidStr = $pidStr.Trim()
    if (-not $pidStr -or -not ($pidStr -match '^\d+$')) {
        return $false
    }

    $pid = [int]$pidStr
    try {
        $proc = Get-Process -Id $pid -ErrorAction Stop
        return ($null -ne $proc)
    }
    catch {
        return $false
    }
}

function Get-TruncatedText {
    <#
    .SYNOPSIS
        Truncates text to a maximum number of characters, appending a notice if truncated.
    .PARAMETER Text
        The text to potentially truncate.
    .PARAMETER MaxBytes
        Maximum character count (approximates bytes for ASCII text).
    .OUTPUTS
        [string] The possibly truncated text.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [AllowEmptyString()]
        [string]$Text,

        [Parameter(Mandatory)]
        [int]$MaxBytes
    )

    if ($Text.Length -le $MaxBytes) {
        return $Text
    }

    $truncated = $Text.Substring(0, $MaxBytes)
    $notice = "`n`n[TRUNCATED: original size $($Text.Length) bytes. Full content available in brief.md]"
    return "$truncated$notice"
}

function Get-CleanAgentText {
    <#
    .SYNOPSIS
        Removes control characters and optional tool noise from agent output.
    .PARAMETER Text
        The raw agent text to sanitize.
    .PARAMETER StripToolNoise
        Removes common CLI/tooling noise lines when set.
    .OUTPUTS
        [string] Sanitized text.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [AllowEmptyString()]
        [string]$Text,

        [switch]$StripToolNoise
    )

    if ([string]::IsNullOrEmpty($Text)) {
        return ""
    }

    $normalized = $Text -replace "`r`n", "`n"
    $normalized = $normalized -replace "`r", "`n"
    $normalized = [regex]::Replace($normalized, "[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "")

    $noisePatterns = @(
        '^\s*🔧',
        '[Cc]alling tool:',
        '^\w{0,5}\s*tool:',
        '^Loading MCP',
        '^Running task non-interactively',
        '^Starting LangGraph server',
        '^CLI:\s',
        '^Thread:\s',
        '^\s*Server ready$',
        '^Agent active',
        '^Usage Stats',
        '^\s*Reqs\s+InputTok',
        '^\s*(gemini|claude|gpt)-',
        '^✓ Task completed',
        '^System\.Management\.Automation'
    )

    $lines = foreach ($line in ($normalized -split "`n")) {
        if (-not $StripToolNoise) {
            $line
            continue
        }

        $trimmed = $line.Trim()
        if (-not $trimmed) {
            $line
            continue
        }

        $skip = $false
        foreach ($pattern in $noisePatterns) {
            if ($trimmed -match $pattern) {
                $skip = $true
                break
            }
        }

        if (-not $skip) {
            $line
        }
    }

    $joined = ($lines -join "`n").Trim()
    if (-not $joined) {
        return ""
    }

    return [regex]::Replace($joined, "(`n\s*){3,}", "`n`n")
}

function Get-RecoverableStatusFromAudit {
    <#
    .SYNOPSIS
        Returns the latest valid audited status for a room.
    .DESCRIPTION
        Scans audit.log backwards and returns the most recent status that
        matches the supplied valid state set. If the latest audit line points to
        an invalid status, the previous valid target or source state is used.
    .PARAMETER RoomDir
        Path to the war-room directory.
    .PARAMETER ValidStatuses
        Optional list of acceptable statuses. When omitted, any audited status
        matching the status naming convention can be returned.
    .OUTPUTS
        [string] Recoverable status or $null.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$RoomDir,

        [string[]]$ValidStatuses = @()
    )

    $auditFile = Join-Path $RoomDir "audit.log"
    if (-not (Test-Path $auditFile)) {
        return $null
    }

    $lines = @(Get-Content $auditFile -ErrorAction SilentlyContinue)
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        $line = $lines[$i]
        if ($line -notmatch 'STATUS\s+([a-z][a-z0-9-]*)\s+->\s+([a-z][a-z0-9-]*)') {
            continue
        }

        $fromStatus = $Matches[1]
        $toStatus = $Matches[2]
        if ($ValidStatuses.Count -eq 0 -or $toStatus -in $ValidStatuses) {
            return $toStatus
        }
        if ($ValidStatuses.Count -eq 0 -or $fromStatus -in $ValidStatuses) {
            return $fromStatus
        }
    }

    return $null
}

function Get-OstwinAgentsDir {
    <#
    .SYNOPSIS
        Resolves the .agents directory from environment or convention.
    #>
    [CmdletBinding()]
    param()

    if ($env:AGENTS_DIR) {
        return $env:AGENTS_DIR
    }

    # Walk up from this script's location
    $dir = (Resolve-Path (Join-Path $PSScriptRoot "..") -ErrorAction SilentlyContinue).Path
    return $dir
}

function Get-OstwinApiHeaders {
    <#
    .SYNOPSIS
        Returns a hashtable of HTTP headers for authenticated API calls.
    .DESCRIPTION
        Reads OSTWIN_API_KEY from environment variable or from ~/.ostwin/.env.
        Returns @{ 'X-API-Key' = '<key>' } if found, or empty hashtable if not.
    .OUTPUTS
        [hashtable] Headers to splat into Invoke-RestMethod -Headers.
    #>
    [CmdletBinding()]
    param()

    $apiKey = $env:OSTWIN_API_KEY

    # Fallback: read from .env file
    if (-not $apiKey) {
        $envFile = Join-Path $HOME ".ostwin" ".env"
        if (Test-Path $envFile) {
            $match = Select-String -Path $envFile -Pattern '^OSTWIN_API_KEY=(.+)$' | Select-Object -First 1
            if ($match) {
                $apiKey = $match.Matches[0].Groups[1].Value.Trim()
            }
        }
    }

    if ($apiKey) {
        return @{ 'X-API-Key' = $apiKey }
    }
    return @{}
}

function Get-LifecycleSignalNames {
    <#
    .SYNOPSIS
        Returns the effective signal names for a lifecycle state.
    .DESCRIPTION
        Review states historically handled `fail` but not `error`. QA timeouts
        post `error`, so review states implicitly accept `error` as a fallback
        when they define `fail` but omit an explicit `error` transition.
    .PARAMETER StateDef
        Lifecycle state definition object.
    .OUTPUTS
        [string[]] Effective signal names.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [psobject]$StateDef
    )

    if (-not $StateDef.signals) { return @() }

    $signals = @($StateDef.signals.PSObject.Properties.Name)
    $isReviewState = ("$($StateDef.type)" -eq 'review')
    $hasFail = ($signals -contains 'fail')
    $hasError = ($signals -contains 'error')

    if ($isReviewState -and $hasFail -and -not $hasError) {
        $signals += 'error'
    }

    return $signals
}

function Resolve-LifecycleSignalTransition {
    <#
    .SYNOPSIS
        Resolves the transition definition for a lifecycle signal.
    .DESCRIPTION
        For review states, `error` falls back to the `fail` transition when the
        lifecycle does not define an explicit `error` branch.
    .PARAMETER StateDef
        Lifecycle state definition object.
    .PARAMETER Signal
        Signal name to resolve.
    .OUTPUTS
        Transition object or $null.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [psobject]$StateDef,

        [Parameter(Mandatory)]
        [string]$Signal
    )

    if (-not $StateDef.signals) { return $null }

    $explicit = $StateDef.signals.$Signal
    if ($explicit) { return $explicit }

    $isReviewState = ("$($StateDef.type)" -eq 'review')
    if ($isReviewState -and $Signal -eq 'error' -and $StateDef.signals.fail) {
        return $StateDef.signals.fail
    }

    return $null
}

Export-ModuleMember -Function Read-OstwinConfig, Set-WarRoomStatus, Test-PidAlive, Get-TruncatedText, Get-CleanAgentText, Get-RecoverableStatusFromAudit, Get-OstwinAgentsDir, Test-Underspecified, Test-SingleEpicUnderspecified, Get-OstwinApiHeaders, Get-LifecycleSignalNames, Resolve-LifecycleSignalTransition
