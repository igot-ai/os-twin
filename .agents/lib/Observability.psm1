#Requires -Version 7.0

<#
.SYNOPSIS
    Observability module — distributed tracing, metrics, and structured event logging.

.DESCRIPTION
    Extends the base Log module with:
    - Trace/Span IDs for distributed tracing
    - Metrics collection (counters, gauges, histograms)
    - Structured event logging with context propagation
    - Event export to JSONL files for analysis

    Part of Epic 5 — Enhanced Observability.

.EXAMPLE
    Import-Module ./Observability.psm1
    $trace = New-Trace -Name "war-room-001"
    $span = Start-Span -Trace $trace -Name "engineer-run"
    Write-TraceEvent -Span $span -Level INFO -Message "Starting work"
    Complete-Span -Span $span -Status "ok"
    Export-TraceReport -Trace $trace
#>

# --- Trace ID Generation ---
function New-TraceId {
    [CmdletBinding()]
    [OutputType([string])]
    param()
    return [guid]::NewGuid().ToString("N").Substring(0, 16)
}

function New-SpanId {
    [CmdletBinding()]
    [OutputType([string])]
    param()
    return [guid]::NewGuid().ToString("N").Substring(0, 8)
}

# --- Trace Management ---
function New-Trace {
    [CmdletBinding()]
    [OutputType([PSCustomObject])]
    param(
        [Parameter(Mandatory)]
        [string]$Name,

        [string]$RoomId = '',

        [string]$TaskRef = ''
    )

    $traceId = New-TraceId
    $trace = [PSCustomObject]@{
        TraceId   = $traceId
        Name      = $Name
        RoomId    = $RoomId
        TaskRef   = $TaskRef
        StartedAt = (Get-Date).ToUniversalTime()
        Spans     = [System.Collections.Generic.List[PSObject]]::new()
        Metrics   = @{}
        Events    = [System.Collections.Generic.List[PSObject]]::new()
    }

    return $trace
}

# --- Span Management ---
function Start-Span {
    [CmdletBinding()]
    [OutputType([PSCustomObject])]
    param(
        [Parameter(Mandatory)]
        [PSObject]$Trace,

        [Parameter(Mandatory)]
        [string]$Name,

        [string]$ParentSpanId = '',

        [hashtable]$Attributes = @{}
    )

    $span = [PSCustomObject]@{
        SpanId       = New-SpanId
        TraceId      = $Trace.TraceId
        ParentSpanId = $ParentSpanId
        Name         = $Name
        StartedAt    = (Get-Date).ToUniversalTime()
        EndedAt      = $null
        Status       = "running"
        Attributes   = $Attributes
        Events       = [System.Collections.Generic.List[PSObject]]::new()
        Duration     = $null
    }

    $Trace.Spans.Add($span)
    return $span
}

function Complete-Span {
    [CmdletBinding()]
    [OutputType([void])]
    param(
        [Parameter(Mandatory)]
        [PSObject]$Span,

        [string]$Status = "ok",

        [hashtable]$Attributes = @{}
    )

    $Span.EndedAt = (Get-Date).ToUniversalTime()
    $Span.Status = $Status
    $Span.Duration = ($Span.EndedAt - $Span.StartedAt).TotalMilliseconds

    foreach ($key in $Attributes.Keys) {
        $Span.Attributes[$key] = $Attributes[$key]
    }
}

# --- Event Logging with Trace Context ---
function Write-TraceEvent {
    [CmdletBinding()]
    [OutputType([void])]
    param(
        [PSObject]$Span = $null,
        [PSObject]$Trace = $null,

        [Parameter(Mandatory)]
        [ValidateSet('DEBUG', 'INFO', 'WARN', 'ERROR')]
        [string]$Level,

        [Parameter(Mandatory)]
        [string]$Message,

        [hashtable]$Properties = @{}
    )

    $event = [ordered]@{
        ts       = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        level    = $Level
        message  = $Message
        trace_id = if ($Span) { $Span.TraceId } elseif ($Trace) { $Trace.TraceId } else { "" }
        span_id  = if ($Span) { $Span.SpanId } else { "" }
    }

    foreach ($key in $Properties.Keys) {
        $event[$key] = $Properties[$key]
    }

    $eventObj = [PSCustomObject]$event

    # Add to span events
    if ($Span) { $Span.Events.Add($eventObj) }

    # Add to trace events
    if ($Trace) { $Trace.Events.Add($eventObj) }

    # Also write to log file
    $logDir = if ($env:AGENT_OS_LOG_DIR) { $env:AGENT_OS_LOG_DIR }
              else { Join-Path $PSScriptRoot ".." "logs" }

    if (-not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }

    $traceLogFile = Join-Path $logDir "trace.jsonl"
    ($eventObj | ConvertTo-Json -Compress) | Out-File -Append -FilePath $traceLogFile -Encoding utf8
}

# --- Metrics ---
function Add-Metric {
    [CmdletBinding()]
    [OutputType([void])]
    param(
        [Parameter(Mandatory)]
        [PSObject]$Trace,

        [Parameter(Mandatory)]
        [string]$Name,

        [Parameter(Mandatory)]
        [double]$Value,

        [ValidateSet('counter', 'gauge', 'histogram')]
        [string]$Type = 'counter',

        [hashtable]$Labels = @{}
    )

    if (-not $Trace.Metrics[$Name]) {
        $Trace.Metrics[$Name] = [System.Collections.Generic.List[PSObject]]::new()
    }

    $Trace.Metrics[$Name].Add([PSCustomObject]@{
        ts     = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        value  = $Value
        type   = $Type
        labels = $Labels
    })
}

function Get-MetricValue {
    [CmdletBinding()]
    [OutputType([double])]
    param(
        [Parameter(Mandatory)]
        [PSObject]$Trace,

        [Parameter(Mandatory)]
        [string]$Name
    )

    $metrics = $Trace.Metrics[$Name]
    if (-not $metrics -or $metrics.Count -eq 0) { return $null }

    $lastEntry = $metrics[-1]
    return $lastEntry.value
}

# --- Report Generation ---
function Export-TraceReport {
    [CmdletBinding()]
    [OutputType([string])]
    param(
        [Parameter(Mandatory)]
        [PSObject]$Trace,

        [string]$OutputPath = ''
    )

    $report = [ordered]@{
        version    = 1
        trace_id   = $Trace.TraceId
        name       = $Trace.Name
        room_id    = $Trace.RoomId
        task_ref   = $Trace.TaskRef
        started_at = $Trace.StartedAt.ToString('yyyy-MM-ddTHH:mm:ssZ')
        duration_ms = if ($Trace.Spans.Count -gt 0) {
            $Trace.Spans | Where-Object { $_.Duration } | Measure-Object -Property Duration -Sum |
                Select-Object -ExpandProperty Sum
        } else { 0 }

        spans = @()
        metrics = @{}
        event_count = $Trace.Events.Count
    }

    foreach ($span in $Trace.Spans) {
        $report.spans += [ordered]@{
            span_id        = $span.SpanId
            parent_span_id = $span.ParentSpanId
            name           = $span.Name
            status         = $span.Status
            duration_ms    = $span.Duration
            event_count    = $span.Events.Count
            attributes     = $span.Attributes
        }
    }

    foreach ($metricName in $Trace.Metrics.Keys) {
        $entries = $Trace.Metrics[$metricName]
        $report.metrics[$metricName] = [ordered]@{
            count = $entries.Count
            last  = $entries[-1].value
            type  = $entries[-1].type
        }
    }

    if (-not $OutputPath) {
        $logDir = if ($env:AGENT_OS_LOG_DIR) { $env:AGENT_OS_LOG_DIR }
                  else { Join-Path $PSScriptRoot ".." "logs" }
        if (-not (Test-Path $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        $OutputPath = Join-Path $logDir "trace-$($Trace.TraceId).json"
    }

    $report | ConvertTo-Json -Depth 10 | Out-File -FilePath $OutputPath -Encoding utf8

    Write-Output $OutputPath
}

Export-ModuleMember -Function @(
    'New-TraceId',
    'New-SpanId',
    'New-Trace',
    'Start-Span',
    'Complete-Span',
    'Write-TraceEvent',
    'Add-Metric',
    'Get-MetricValue',
    'Export-TraceReport'
)
