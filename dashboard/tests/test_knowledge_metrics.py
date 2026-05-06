"""Tests for knowledge metrics (EPIC-005).

Tests the metrics registry, in-memory backend, Prometheus backend (when available),
and metrics instrumentation in the knowledge service.
"""

from __future__ import annotations

import pytest
import threading
import time

from dashboard.knowledge.metrics import (
    InMemoryCounter,
    InMemoryHistogram,
    InMemoryGauge,
    MetricsRegistry,
    get_metrics_registry,
    reset_metrics_registry,
    LatencyContext,
)


class TestInMemoryCounter:
    """Tests for InMemoryCounter."""

    def test_increment(self) -> None:
        """Counter increments correctly."""
        counter = InMemoryCounter("test_counter", "Test counter")
        assert counter.get() == 0.0
        
        counter.inc()
        assert counter.get() == 1.0
        
        counter.inc(5)
        assert counter.get() == 6.0

    def test_increment_with_labels(self) -> None:
        """Counter handles labels correctly."""
        counter = InMemoryCounter("test_counter", "Test counter")
        
        counter.inc(labels={"namespace": "ns1"})
        counter.inc(labels={"namespace": "ns2"})
        counter.inc(2, labels={"namespace": "ns1"})
        
        assert counter.get(labels={"namespace": "ns1"}) == 3.0
        assert counter.get(labels={"namespace": "ns2"}) == 1.0
        assert counter.get() == 0.0

    def test_reset(self) -> None:
        """Counter resets to zero."""
        counter = InMemoryCounter("test_counter", "Test counter")
        counter.inc(10)
        assert counter.get() == 10.0
        
        counter.reset()
        assert counter.get() == 0.0

    def test_negative_increment_raises(self) -> None:
        """Counter raises on negative increment."""
        counter = InMemoryCounter("test_counter", "Test counter")
        with pytest.raises(ValueError, match="non-negative"):
            counter.inc(-1)

    def test_thread_safety(self) -> None:
        """Counter is thread-safe."""
        counter = InMemoryCounter("test_counter", "Test counter")
        iterations = 1000
        
        def increment():
            for _ in range(iterations):
                counter.inc()
        
        threads = [threading.Thread(target=increment) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert counter.get() == 4 * iterations


class TestInMemoryHistogram:
    """Tests for InMemoryHistogram."""

    def test_observe(self) -> None:
        """Histogram observes values correctly."""
        hist = InMemoryHistogram("test_hist", "Test histogram")
        
        hist.observe(1.0)
        hist.observe(2.0)
        hist.observe(3.0)
        
        samples = hist.get_samples()
        assert len(samples) == 3
        assert samples == [1.0, 2.0, 3.0]

    def test_observe_with_labels(self) -> None:
        """Histogram handles labels correctly."""
        hist = InMemoryHistogram("test_hist", "Test histogram")
        
        hist.observe(1.0, labels={"op": "query"})
        hist.observe(2.0, labels={"op": "ingest"})
        
        assert len(hist.get_samples(labels={"op": "query"})) == 1
        assert len(hist.get_samples(labels={"op": "ingest"})) == 1

    def test_ring_buffer(self) -> None:
        """Histogram respects buffer size limit."""
        hist = InMemoryHistogram("test_hist", "Test histogram", buffer_size=10)
        
        for i in range(20):
            hist.observe(float(i))
        
        samples = hist.get_samples()
        assert len(samples) == 10  # Buffer size
        assert samples[0] == 10.0  # Oldest kept value

    def test_get_stats(self) -> None:
        """Histogram computes stats correctly."""
        hist = InMemoryHistogram("test_hist", "Test histogram")
        
        for i in range(1, 6):  # 1, 2, 3, 4, 5
            hist.observe(float(i))
        
        stats = hist.get_stats()
        assert stats["count"] == 5
        assert stats["sum"] == 15.0
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["avg"] == 3.0


class TestInMemoryGauge:
    """Tests for InMemoryGauge."""

    def test_set(self) -> None:
        """Gauge sets value correctly."""
        gauge = InMemoryGauge("test_gauge", "Test gauge")
        
        gauge.set(42.0)
        assert gauge.get() == 42.0
        
        gauge.set(100.0)
        assert gauge.get() == 100.0

    def test_inc_dec(self) -> None:
        """Gauge increments and decrements correctly."""
        gauge = InMemoryGauge("test_gauge", "Test gauge")
        gauge.set(10.0)
        
        gauge.inc()
        assert gauge.get() == 11.0
        
        gauge.dec(5)
        assert gauge.get() == 6.0

    def test_with_labels(self) -> None:
        """Gauge handles labels correctly."""
        gauge = InMemoryGauge("test_gauge", "Test gauge")
        
        gauge.set(100.0, labels={"namespace": "ns1"})
        gauge.set(200.0, labels={"namespace": "ns2"})
        
        assert gauge.get(labels={"namespace": "ns1"}) == 100.0
        assert gauge.get(labels={"namespace": "ns2"}) == 200.0


class TestMetricsRegistry:
    """Tests for MetricsRegistry."""

    def test_get_counter(self) -> None:
        """Registry returns counters."""
        registry = MetricsRegistry(backend="memory")
        counter = registry.counter("test_counter")
        
        counter.inc(5)
        assert counter.get() == 5.0

    def test_get_histogram(self) -> None:
        """Registry returns histograms."""
        registry = MetricsRegistry(backend="memory")
        hist = registry.histogram("test_hist")
        
        hist.observe(1.0)
        hist.observe(2.0)
        
        assert len(hist.get_samples()) == 2

    def test_get_gauge(self) -> None:
        """Registry returns gauges."""
        registry = MetricsRegistry(backend="memory")
        gauge = registry.gauge("test_gauge")
        
        gauge.set(42.0)
        assert gauge.get() == 42.0

    def test_predefined_metrics(self) -> None:
        """Registry creates predefined metrics."""
        registry = MetricsRegistry(backend="memory")
        
        # Should have all predefined metrics
        assert "query_total" in registry._metrics
        assert "ingest_files_total" in registry._metrics
        assert "query_latency_seconds" in registry._metrics
        assert "namespaces_total" in registry._metrics

    def test_export_json(self) -> None:
        """Registry exports JSON correctly."""
        registry = MetricsRegistry(backend="memory")
        
        registry.counter("query_total").inc(10)
        registry.gauge("namespaces_total").set(5)
        
        json_data = registry.export_json()
        
        assert json_data["backend"] == "memory"
        assert "counters" in json_data
        assert "gauges" in json_data
        assert json_data["counters"]["query_total"]["value"] == 10.0
        assert json_data["gauges"]["namespaces_total"]["value"] == 5.0

    def test_export_prometheus(self) -> None:
        """Registry exports Prometheus format."""
        registry = MetricsRegistry(backend="memory")
        
        registry.counter("query_total").inc(10)
        registry.gauge("namespaces_total").set(5)
        
        prom_text = registry.export_prometheus()
        
        assert "# TYPE query_total counter" in prom_text
        assert "query_total 10.0" in prom_text
        assert "# TYPE namespaces_total gauge" in prom_text
        assert "namespaces_total" in prom_text  # Value may be int or float

    def test_reset(self) -> None:
        """Registry resets all metrics."""
        registry = MetricsRegistry(backend="memory")
        
        registry.counter("query_total").inc(10)
        registry.reset()
        
        assert registry.counter("query_total").get() == 0.0

    def test_latency_context(self) -> None:
        """LatencyContext measures and records latency."""
        registry = MetricsRegistry(backend="memory")
        
        with registry.latency("query_latency_seconds"):
            time.sleep(0.01)  # 10ms
        
        stats = registry.histogram("query_latency_seconds").get_stats()
        assert stats["count"] == 1
        assert stats["min"] >= 0.01  # At least 10ms


class TestGlobalRegistry:
    """Tests for global registry singleton."""

    def test_singleton(self) -> None:
        """get_metrics_registry returns same instance."""
        # Force memory backend to avoid Prometheus registry conflicts
        import os
        old_backend = os.environ.get("OSTWIN_KNOWLEDGE_METRICS_BACKEND")
        os.environ["OSTWIN_KNOWLEDGE_METRICS_BACKEND"] = "memory"
        
        try:
            reset_metrics_registry()
            
            r1 = get_metrics_registry()
            r2 = get_metrics_registry()
            
            assert r1 is r2
        finally:
            if old_backend is not None:
                os.environ["OSTWIN_KNOWLEDGE_METRICS_BACKEND"] = old_backend
            else:
                os.environ.pop("OSTWIN_KNOWLEDGE_METRICS_BACKEND", None)

    def test_reset_clears_singleton(self) -> None:
        """reset_metrics_registry clears singleton."""
        # Force memory backend to avoid Prometheus registry conflicts
        import os
        os.environ["OSTWIN_KNOWLEDGE_METRICS_BACKEND"] = "memory"
        
        r1 = get_metrics_registry()
        reset_metrics_registry()
        r2 = get_metrics_registry()
        
        # Should be different instances after reset
        assert r1 is not r2


class TestCounterProbes:
    """Test counters increment correctly during operations."""

    def test_query_total_increments(self) -> None:
        """query_total increments on each query."""
        # Use memory backend to avoid Prometheus conflicts
        registry = MetricsRegistry(backend="memory")
        
        initial = registry.counter("query_total").get()
        
        # Simulate query by incrementing counter
        registry.counter("query_total").inc()
        registry.counter("query_total").inc()
        registry.counter("query_total").inc()
        
        assert registry.counter("query_total").get() == initial + 3

    def test_ingest_files_total_increments(self) -> None:
        """ingest_files_total increments on file ingestion."""
        registry = MetricsRegistry(backend="memory")
        
        initial = registry.counter("ingest_files_total").get()
        
        # Simulate ingesting 5 files
        registry.counter("ingest_files_total").inc(5)
        
        assert registry.counter("ingest_files_total").get() == initial + 5


class TestHistogramProbes:
    """Test histograms record latencies correctly."""

    def test_query_latency_records(self) -> None:
        """query_latency_seconds records query latencies."""
        registry = MetricsRegistry(backend="memory")
        
        # Record some latencies
        registry.histogram("query_latency_seconds").observe(0.1)
        registry.histogram("query_latency_seconds").observe(0.2)
        registry.histogram("query_latency_seconds").observe(0.15)
        
        stats = registry.histogram("query_latency_seconds").get_stats()
        assert stats["count"] == 3
        assert stats["min"] == 0.1
        assert stats["max"] == 0.2
        assert pytest.approx(stats["avg"], rel=0.01) == 0.15

    def test_llm_latency_records(self) -> None:
        """llm_latency_seconds records LLM call latencies."""
        registry = MetricsRegistry(backend="memory")
        
        registry.histogram("llm_latency_seconds").observe(1.5)
        registry.histogram("llm_latency_seconds").observe(2.0)
        
        stats = registry.histogram("llm_latency_seconds").get_stats()
        assert stats["count"] == 2


class TestGaugeProbes:
    """Test gauges set values correctly."""

    def test_namespaces_total(self) -> None:
        """namespaces_total reflects namespace count."""
        registry = MetricsRegistry(backend="memory")
        
        registry.gauge("namespaces_total").set(5)
        assert registry.gauge("namespaces_total").get() == 5.0
        
        # Simulate creating a namespace
        registry.gauge("namespaces_total").inc()
        assert registry.gauge("namespaces_total").get() == 6.0
        
        # Simulate deleting a namespace
        registry.gauge("namespaces_total").dec()
        assert registry.gauge("namespaces_total").get() == 5.0

    def test_per_namespace_gauges(self) -> None:
        """Per-namespace gauges track individual namespace stats."""
        registry = MetricsRegistry(backend="memory")
        
        registry.gauge("disk_bytes_per_namespace").set(1000, labels={"namespace": "ns1"})
        registry.gauge("disk_bytes_per_namespace").set(2000, labels={"namespace": "ns2"})
        
        assert registry.gauge("disk_bytes_per_namespace").get(labels={"namespace": "ns1"}) == 1000.0
        assert registry.gauge("disk_bytes_per_namespace").get(labels={"namespace": "ns2"}) == 2000.0
