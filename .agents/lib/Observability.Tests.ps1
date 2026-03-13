# Agent OS — Observability Module Pester Tests

BeforeAll {
    Import-Module (Join-Path $PSScriptRoot "Observability.psm1") -Force
}

AfterAll {
    Remove-Module -Name "Observability" -ErrorAction SilentlyContinue
}

Describe "Observability Module" {

    Context "Trace ID Generation" {
        It "generates unique trace IDs" {
            $id1 = New-TraceId
            $id2 = New-TraceId
            $id1 | Should -Not -Be $id2
            $id1.Length | Should -Be 16
        }

        It "generates unique span IDs" {
            $id1 = New-SpanId
            $id2 = New-SpanId
            $id1 | Should -Not -Be $id2
            $id1.Length | Should -Be 8
        }
    }

    Context "Trace Creation" {
        It "creates a trace with required fields" {
            $trace = New-Trace -Name "test-trace"
            $trace.TraceId | Should -Not -BeNullOrEmpty
            $trace.Name | Should -Be "test-trace"
            $trace.StartedAt | Should -Not -BeNullOrEmpty
            $trace.Spans.Count | Should -Be 0
            $trace.Events.Count | Should -Be 0
        }

        It "creates a trace with room context" {
            $trace = New-Trace -Name "room-test" -RoomId "room-001" -TaskRef "TASK-001"
            $trace.RoomId | Should -Be "room-001"
            $trace.TaskRef | Should -Be "TASK-001"
        }
    }

    Context "Span Management" {
        BeforeEach {
            $script:trace = New-Trace -Name "span-test"
        }

        It "starts a span with trace context" {
            $span = Start-Span -Trace $script:trace -Name "test-span"
            $span.SpanId | Should -Not -BeNullOrEmpty
            $span.TraceId | Should -Be $script:trace.TraceId
            $span.Name | Should -Be "test-span"
            $span.Status | Should -Be "running"
        }

        It "adds span to trace" {
            Start-Span -Trace $script:trace -Name "span-1" | Out-Null
            $script:trace.Spans.Count | Should -Be 1
        }

        It "supports parent span" {
            $parent = Start-Span -Trace $script:trace -Name "parent"
            $child = Start-Span -Trace $script:trace -Name "child" -ParentSpanId $parent.SpanId
            $child.ParentSpanId | Should -Be $parent.SpanId
        }

        It "supports span attributes" {
            $span = Start-Span -Trace $script:trace -Name "attr-span" -Attributes @{
                role = "engineer"
                task = "TASK-001"
            }
            $span.Attributes.role | Should -Be "engineer"
            $span.Attributes.task | Should -Be "TASK-001"
        }

        It "completes a span with status and duration" {
            $span = Start-Span -Trace $script:trace -Name "timed-span"
            Start-Sleep -Milliseconds 50
            Complete-Span -Span $span -Status "ok"

            $span.Status | Should -Be "ok"
            $span.EndedAt | Should -Not -BeNullOrEmpty
            $span.Duration | Should -BeGreaterThan 0
        }

        It "completes a span with error status" {
            $span = Start-Span -Trace $script:trace -Name "error-span"
            Complete-Span -Span $span -Status "error" -Attributes @{ error = "timeout" }

            $span.Status | Should -Be "error"
            $span.Attributes.error | Should -Be "timeout"
        }
    }

    Context "Event Logging" {
        BeforeEach {
            $script:trace = New-Trace -Name "event-test"
            $env:AGENT_OS_LOG_DIR = Join-Path $TestDrive "logs-$(Get-Random)"
        }

        AfterEach {
            Remove-Item Env:AGENT_OS_LOG_DIR -ErrorAction SilentlyContinue
        }

        It "writes events with trace context" {
            $span = Start-Span -Trace $script:trace -Name "event-span"
            Write-TraceEvent -Span $span -Trace $script:trace -Level INFO -Message "Test event"

            $span.Events.Count | Should -Be 1
            $span.Events[0].trace_id | Should -Be $script:trace.TraceId
            $span.Events[0].span_id | Should -Be $span.SpanId
        }

        It "writes events to trace events list" {
            Write-TraceEvent -Trace $script:trace -Level WARN -Message "Warning event"
            $script:trace.Events.Count | Should -Be 1
        }

        It "includes custom properties" {
            $span = Start-Span -Trace $script:trace -Name "prop-span"
            Write-TraceEvent -Span $span -Level INFO -Message "With props" -Properties @{
                retries = 3
                room = "room-001"
            }

            $span.Events[0].retries | Should -Be 3
            $span.Events[0].room | Should -Be "room-001"
        }

        It "writes to trace.jsonl file" {
            Write-TraceEvent -Trace $script:trace -Level INFO -Message "File test"

            $traceLog = Join-Path $env:AGENT_OS_LOG_DIR "trace.jsonl"
            Test-Path $traceLog | Should -BeTrue
            $content = Get-Content $traceLog -Raw
            $content | Should -Match "File test"
        }
    }

    Context "Metrics" {
        BeforeEach {
            $script:trace = New-Trace -Name "metrics-test"
        }

        It "records counter metrics" {
            Add-Metric -Trace $script:trace -Name "retries" -Value 1 -Type "counter"
            Add-Metric -Trace $script:trace -Name "retries" -Value 2 -Type "counter"

            $val = Get-MetricValue -Trace $script:trace -Name "retries"
            $val | Should -Be 2
        }

        It "records gauge metrics" {
            Add-Metric -Trace $script:trace -Name "active_rooms" -Value 5 -Type "gauge"
            $val = Get-MetricValue -Trace $script:trace -Name "active_rooms"
            $val | Should -Be 5
        }

        It "records metrics with labels" {
            Add-Metric -Trace $script:trace -Name "duration" -Value 120.5 -Type "histogram" `
                        -Labels @{ room = "room-001"; role = "engineer" }

            $metrics = $script:trace.Metrics["duration"]
            $metrics[0].labels.room | Should -Be "room-001"
        }

        It "returns null for missing metric" {
            $val = Get-MetricValue -Trace $script:trace -Name "nonexistent"
            $val | Should -BeNullOrEmpty
        }
    }

    Context "Report Export" {
        BeforeEach {
            $script:trace = New-Trace -Name "report-test" -RoomId "room-001" -TaskRef "TASK-RPT"
            $env:AGENT_OS_LOG_DIR = Join-Path $TestDrive "logs-$(Get-Random)"
        }

        AfterEach {
            Remove-Item Env:AGENT_OS_LOG_DIR -ErrorAction SilentlyContinue
        }

        It "exports a trace report as JSON" {
            $span = Start-Span -Trace $script:trace -Name "work"
            Write-TraceEvent -Span $span -Trace $script:trace -Level INFO -Message "Did work"
            Complete-Span -Span $span -Status "ok"

            Add-Metric -Trace $script:trace -Name "retries" -Value 1

            $reportFile = Export-TraceReport -Trace $script:trace
            Test-Path $reportFile | Should -BeTrue

            $report = Get-Content $reportFile -Raw | ConvertFrom-Json
            $report.trace_id | Should -Be $script:trace.TraceId
            $report.name | Should -Be "report-test"
            $report.room_id | Should -Be "room-001"
            $report.task_ref | Should -Be "TASK-RPT"
            $report.spans.Count | Should -Be 1
            $report.spans[0].status | Should -Be "ok"
        }

        It "exports to custom path" {
            $customPath = Join-Path $TestDrive "custom-report.json"
            Export-TraceReport -Trace $script:trace -OutputPath $customPath
            Test-Path $customPath | Should -BeTrue
        }

        It "includes metrics summary in report" {
            Add-Metric -Trace $script:trace -Name "count" -Value 42 -Type "counter"
            $reportFile = Export-TraceReport -Trace $script:trace

            $report = Get-Content $reportFile -Raw | ConvertFrom-Json
            $report.metrics.count.last | Should -Be 42
            $report.metrics.count.type | Should -Be "counter"
        }
    }
}
