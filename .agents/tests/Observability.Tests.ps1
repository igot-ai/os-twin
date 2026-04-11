#Requires -Version 7.0

BeforeAll {
    Import-Module "$PSScriptRoot/../.agents/lib/Observability.psm1" -Force
}

Describe 'Observability Module' {

    Context 'Trace ID generation' {
        It 'generates a 16-char hex trace ID' {
            $id = New-TraceId
            $id | Should -Match '^[a-f0-9]{16}$'
        }

        It 'generates unique trace IDs' {
            $id1 = New-TraceId
            $id2 = New-TraceId
            $id1 | Should -Not -Be $id2
        }
    }

    Context 'Span ID generation' {
        It 'generates an 8-char hex span ID' {
            $id = New-SpanId
            $id | Should -Match '^[a-f0-9]{8}$'
        }
    }

    Context 'Trace lifecycle' {
        It 'creates a trace with required fields' {
            $trace = New-Trace -Name 'test-trace'
            $trace.TraceId | Should -Not -BeNullOrEmpty
            $trace.Name | Should -Be 'test-trace'
            $trace.Spans.Count | Should -Be 0
            $trace.Events.Count | Should -Be 0
        }

        It 'creates a trace with optional fields' {
            $trace = New-Trace -Name 'test' -RoomId 'room-001' -TaskRef 'EPIC-001'
            $trace.RoomId | Should -Be 'room-001'
            $trace.TaskRef | Should -Be 'EPIC-001'
        }
    }

    Context 'Span lifecycle' {
        It 'starts a span linked to trace' {
            $trace = New-Trace -Name 'test'
            $span = Start-Span -Trace $trace -Name 'work-span'
            $span.TraceId | Should -Be $trace.TraceId
            $span.Name | Should -Be 'work-span'
            $span.Status | Should -Be 'running'
            $trace.Spans.Count | Should -Be 1
        }

        It 'completes a span with duration' {
            $trace = New-Trace -Name 'test'
            $span = Start-Span -Trace $trace -Name 'work'
            Start-Sleep -Milliseconds 50
            Complete-Span -Span $span -Status 'ok'
            $span.Status | Should -Be 'ok'
            $span.Duration | Should -BeGreaterThan 0
            $span.EndedAt | Should -Not -BeNullOrEmpty
        }
    }

    Context 'Metrics' {
        It 'adds a metric to trace' {
            $trace = New-Trace -Name 'test'
            Add-Metric -Trace $trace -Name 'request_count' -Value 1 -Type 'counter'
            $trace.Metrics['request_count'].Count | Should -Be 1
        }

        It 'retrieves last metric value' {
            $trace = New-Trace -Name 'test'
            Add-Metric -Trace $trace -Name 'cpu' -Value 45.2 -Type 'gauge'
            Add-Metric -Trace $trace -Name 'cpu' -Value 52.1 -Type 'gauge'
            $val = Get-MetricValue -Trace $trace -Name 'cpu'
            $val | Should -Be 52.1
        }

        It 'returns null for unknown metric' {
            $trace = New-Trace -Name 'test'
            $val = Get-MetricValue -Trace $trace -Name 'nonexistent'
            $val | Should -BeNullOrEmpty
        }
    }

    Context 'Trace events' {
        It 'writes event to span and trace' {
            $trace = New-Trace -Name 'test'
            $span = Start-Span -Trace $trace -Name 'work'
            Write-TraceEvent -Span $span -Trace $trace -Level INFO -Message 'hello'
            $span.Events.Count | Should -Be 1
            $trace.Events.Count | Should -Be 1
        }
    }

    Context 'Report export' {
        It 'exports trace report to JSON file' {
            $trace = New-Trace -Name 'export-test'
            $span = Start-Span -Trace $trace -Name 'work'
            Complete-Span -Span $span -Status 'ok'
            Add-Metric -Trace $trace -Name 'items' -Value 42 -Type 'counter'

            $outPath = Join-Path $TestDrive "trace-test.json"
            $result = Export-TraceReport -Trace $trace -OutputPath $outPath
            $result | Should -Be $outPath
            Test-Path $outPath | Should -Be $true

            $report = Get-Content $outPath -Raw | ConvertFrom-Json
            $report.trace_id | Should -Be $trace.TraceId
            $report.spans.Count | Should -Be 1
            $report.metrics.items.last | Should -Be 42
        }
    }
}
