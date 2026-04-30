"""Observability metrics for KnowledgeService (EPIC-005).

This module provides a `MetricsRegistry` with abstract `Counter`/`Histogram`/`Gauge`
interfaces and two backend implementations:

1. **Prometheus backend** (when `prometheus_client` is installed): Real Prometheus
   metric types that integrate with Prometheus scrape endpoints.

2. **In-memory backend** (fallback): A ring buffer storing the last 10,000 samples
   per metric, suitable for JSON export when Prometheus is not available.

Design:
- **Abstract interfaces**: Counter, Histogram, Gauge are protocols that define
  the expected operations (inc, observe, set, etc.)
- **Backend selection**: Automatic detection of `prometheus_client` with graceful
  fallback to in-memory.
- **Thread-safe**: All operations are protected by locks.
- **Content negotiation**: `export_json()` and `export_prometheus()` for REST
  endpoint flexibility.

Metrics exposed:
- Counters: ingest_files_total, ingest_bytes_total, query_total, query_errors_total,
  llm_calls_total, llm_errors_total
- Histograms: ingest_latency_seconds, query_latency_seconds, llm_latency_seconds
- Gauges: namespaces_total, disk_bytes_per_namespace, vector_count_per_namespace,
  entity_count_per_namespace
"""

from __future__ import annotations

import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# Configuration via environment
METRICS_BACKEND: str = os.environ.get("OSTWIN_KNOWLEDGE_METRICS_BACKEND", "auto")
RING_BUFFER_SIZE: int = int(os.environ.get("OSTWIN_KNOWLEDGE_METRICS_BUFFER_SIZE", "10000"))


# ---------------------------------------------------------------------------
# Abstract Interfaces (Protocols)
# ---------------------------------------------------------------------------


@runtime_checkable
class Counter(Protocol):
    """A counter that can only increase (or reset)."""

    def inc(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        """Increment the counter by `amount`."""
        ...

    def reset(self) -> None:
        """Reset the counter to zero."""
        ...

    def get(self, labels: Optional[dict[str, str]] = None) -> float:
        """Get the current value."""
        ...


@runtime_checkable
class Histogram(Protocol):
    """A histogram that observes values (e.g., latency)."""

    def observe(self, value: float, labels: Optional[dict[str, str]] = None) -> None:
        """Observe a value."""
        ...

    def get_samples(self, labels: Optional[dict[str, str]] = None) -> list[float]:
        """Get all observed samples (for in-memory backend)."""
        ...


@runtime_checkable
class Gauge(Protocol):
    """A gauge that can increase, decrease, or be set to a specific value."""

    def inc(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        """Increment the gauge by `amount`."""
        ...

    def dec(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        """Decrement the gauge by `amount`."""
        ...

    def set(self, value: float, labels: Optional[dict[str, str]] = None) -> None:
        """Set the gauge to `value`."""
        ...

    def get(self, labels: Optional[dict[str, str]] = None) -> float:
        """Get the current value."""
        ...


# ---------------------------------------------------------------------------
# In-Memory Backend Implementation
# ---------------------------------------------------------------------------


class InMemoryCounter(Counter):
    """Thread-safe in-memory counter with optional label support."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._value: float = 0.0
        self._labeled_values: dict[str, float] = {}
        self._lock = threading.Lock()

    def _labels_key(self, labels: Optional[dict[str, str]] = None) -> str:
        """Convert labels dict to a string key."""
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def inc(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        if amount < 0:
            raise ValueError("Counter can only be incremented by non-negative values")
        with self._lock:
            key = self._labels_key(labels)
            if key:
                self._labeled_values[key] = self._labeled_values.get(key, 0.0) + amount
            else:
                self._value += amount

    def reset(self) -> None:
        with self._lock:
            self._value = 0.0
            self._labeled_values.clear()

    def get(self, labels: Optional[dict[str, str]] = None) -> float:
        with self._lock:
            key = self._labels_key(labels)
            if key:
                return self._labeled_values.get(key, 0.0)
            return self._value

    def get_all(self) -> dict[str, float]:
        """Get all labeled values plus the base value."""
        with self._lock:
            result = {"": self._value}
            result.update(self._labeled_values)
            return result


class InMemoryHistogram(Histogram):
    """Thread-safe in-memory histogram with ring buffer."""

    def __init__(self, name: str, description: str = "", buffer_size: int = RING_BUFFER_SIZE) -> None:
        self.name = name
        self.description = description
        self._buffer_size = buffer_size
        self._samples: deque[float] = deque(maxlen=buffer_size)
        self._labeled_samples: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _labels_key(self, labels: Optional[dict[str, str]] = None) -> str:
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def observe(self, value: float, labels: Optional[dict[str, str]] = None) -> None:
        with self._lock:
            key = self._labels_key(labels)
            if key:
                if key not in self._labeled_samples:
                    self._labeled_samples[key] = deque(maxlen=self._buffer_size)
                self._labeled_samples[key].append(value)
            else:
                self._samples.append(value)

    def get_samples(self, labels: Optional[dict[str, str]] = None) -> list[float]:
        with self._lock:
            key = self._labels_key(labels)
            if key:
                return list(self._labeled_samples.get(key, deque()))
            return list(self._samples)

    def get_stats(self, labels: Optional[dict[str, str]] = None) -> dict[str, float]:
        """Get histogram statistics (count, sum, min, max, avg)."""
        samples = self.get_samples(labels)
        if not samples:
            return {"count": 0, "sum": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}
        return {
            "count": len(samples),
            "sum": sum(samples),
            "min": min(samples),
            "max": max(samples),
            "avg": sum(samples) / len(samples),
        }

    def get_all(self) -> dict[str, list[float]]:
        """Get all labeled samples plus the base samples."""
        with self._lock:
            result = {"": list(self._samples)}
            for key, samples in self._labeled_samples.items():
                result[key] = list(samples)
            return result


class InMemoryGauge(Gauge):
    """Thread-safe in-memory gauge with optional label support."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._value: float = 0.0
        self._labeled_values: dict[str, float] = {}
        self._lock = threading.Lock()

    def _labels_key(self, labels: Optional[dict[str, str]] = None) -> str:
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def inc(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        with self._lock:
            key = self._labels_key(labels)
            if key:
                self._labeled_values[key] = self._labeled_values.get(key, 0.0) + amount
            else:
                self._value += amount

    def dec(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        with self._lock:
            key = self._labels_key(labels)
            if key:
                self._labeled_values[key] = self._labeled_values.get(key, 0.0) - amount
            else:
                self._value -= amount

    def set(self, value: float, labels: Optional[dict[str, str]] = None) -> None:
        with self._lock:
            key = self._labels_key(labels)
            if key:
                self._labeled_values[key] = value
            else:
                self._value = value

    def get(self, labels: Optional[dict[str, str]] = None) -> float:
        with self._lock:
            key = self._labels_key(labels)
            if key:
                return self._labeled_values.get(key, 0.0)
            return self._value

    def get_all(self) -> dict[str, float]:
        """Get all labeled values plus the base value."""
        with self._lock:
            result = {"": self._value}
            result.update(self._labeled_values)
            return result


# ---------------------------------------------------------------------------
# Prometheus Backend Wrapper
# ---------------------------------------------------------------------------


class PrometheusCounter(Counter):
    """Wrapper around prometheus_client.Counter."""

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Optional[list[str]] = None,
        registry: Optional[Any] = None,
    ) -> None:
        self.name = name
        self.description = description
        self._label_names = label_names or []
        self._registry = registry  # Custom registry to avoid global state collisions
        self._metric: Any = None
        self._init_metric()

    def _init_metric(self) -> None:
        """Lazy initialization of the Prometheus metric."""
        if self._metric is not None:
            return
        try:
            import prometheus_client  # noqa: WPS433

            # Use custom registry if provided, otherwise default (for singletons)
            registry = self._registry if self._registry is not None else prometheus_client.REGISTRY
            if self._label_names:
                self._metric = prometheus_client.Counter(
                    self.name, self.description, self._label_names, registry=registry
                )
            else:
                self._metric = prometheus_client.Counter(self.name, self.description, registry=registry)
        except ImportError:
            logger.warning("prometheus_client not installed, using in-memory counter")
            self.__class__ = InMemoryCounter  # type: ignore
            self.__init__(self.name, self.description)  # type: ignore

    def _labels_dict_to_args(self, labels: Optional[dict[str, str]] = None) -> Optional[tuple[str, ...]]:
        """Convert labels dict to positional args for Prometheus labels()."""
        if not labels or not self._label_names:
            return None
        return tuple(labels.get(name, "") for name in self._label_names)

    def inc(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        self._init_metric()
        if hasattr(self._metric, "labels"):
            label_args = self._labels_dict_to_args(labels)
            if label_args:
                self._metric.labels(*label_args).inc(amount)
            else:
                self._metric.inc(amount)
        else:
            self._metric.inc(amount)

    def reset(self) -> None:
        # Prometheus counters cannot be reset; this is a no-op for compatibility
        logger.warning("Prometheus counters cannot be reset; ignoring reset() call")

    def get(self, labels: Optional[dict[str, str]] = None) -> float:
        # Prometheus counters don't have a direct get() method
        # This is a limitation; use export_json() for the full state
        return 0.0


class PrometheusHistogram(Histogram):
    """Wrapper around prometheus_client.Histogram."""

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Optional[list[str]] = None,
        registry: Optional[Any] = None,
    ) -> None:
        self.name = name
        self.description = description
        self._label_names = label_names or []
        self._registry = registry
        self._metric: Any = None
        self._init_metric()

    def _init_metric(self) -> None:
        if self._metric is not None:
            return
        try:
            import prometheus_client  # noqa: WPS433

            registry = self._registry if self._registry is not None else prometheus_client.REGISTRY
            if self._label_names:
                self._metric = prometheus_client.Histogram(
                    self.name, self.description, self._label_names, registry=registry
                )
            else:
                self._metric = prometheus_client.Histogram(self.name, self.description, registry=registry)
        except ImportError:
            logger.warning("prometheus_client not installed, using in-memory histogram")
            self.__class__ = InMemoryHistogram  # type: ignore
            self.__init__(self.name, self.description)  # type: ignore

    def _labels_dict_to_args(self, labels: Optional[dict[str, str]] = None) -> Optional[tuple[str, ...]]:
        if not labels or not self._label_names:
            return None
        return tuple(labels.get(name, "") for name in self._label_names)

    def observe(self, value: float, labels: Optional[dict[str, str]] = None) -> None:
        self._init_metric()
        if hasattr(self._metric, "labels"):
            label_args = self._labels_dict_to_args(labels)
            if label_args:
                self._metric.labels(*label_args).observe(value)
            else:
                self._metric.observe(value)
        else:
            self._metric.observe(value)

    def get_samples(self, labels: Optional[dict[str, str]] = None) -> list[float]:
        # Prometheus histograms don't expose raw samples directly
        return []


class PrometheusGauge(Gauge):
    """Wrapper around prometheus_client.Gauge."""

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Optional[list[str]] = None,
        registry: Optional[Any] = None,
    ) -> None:
        self.name = name
        self.description = description
        self._label_names = label_names or []
        self._registry = registry
        self._metric: Any = None
        self._init_metric()

    def _init_metric(self) -> None:
        if self._metric is not None:
            return
        try:
            import prometheus_client  # noqa: WPS433

            registry = self._registry if self._registry is not None else prometheus_client.REGISTRY
            if self._label_names:
                self._metric = prometheus_client.Gauge(
                    self.name, self.description, self._label_names, registry=registry
                )
            else:
                self._metric = prometheus_client.Gauge(self.name, self.description, registry=registry)
        except ImportError:
            logger.warning("prometheus_client not installed, using in-memory gauge")
            self.__class__ = InMemoryGauge  # type: ignore
            self.__init__(self.name, self.description)  # type: ignore

    def _labels_dict_to_args(self, labels: Optional[dict[str, str]] = None) -> Optional[tuple[str, ...]]:
        if not labels or not self._label_names:
            return None
        return tuple(labels.get(name, "") for name in self._label_names)

    def inc(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        self._init_metric()
        if hasattr(self._metric, "labels"):
            label_args = self._labels_dict_to_args(labels)
            if label_args:
                self._metric.labels(*label_args).inc(amount)
            else:
                self._metric.inc(amount)
        else:
            self._metric.inc(amount)

    def dec(self, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        self._init_metric()
        if hasattr(self._metric, "labels"):
            label_args = self._labels_dict_to_args(labels)
            if label_args:
                self._metric.labels(*label_args).dec(amount)
            else:
                self._metric.dec(amount)
        else:
            self._metric.dec(amount)

    def set(self, value: float, labels: Optional[dict[str, str]] = None) -> None:
        self._init_metric()
        if hasattr(self._metric, "labels"):
            label_args = self._labels_dict_to_args(labels)
            if label_args:
                self._metric.labels(*label_args).set(value)
            else:
                self._metric.set(value)
        else:
            self._metric.set(value)

    def get(self, labels: Optional[dict[str, str]] = None) -> float:
        # Prometheus gauges don't have a direct get() method
        return 0.0


# ---------------------------------------------------------------------------
# Metrics Registry
# ---------------------------------------------------------------------------


@dataclass
class MetricDefinition:
    """Definition of a metric."""

    name: str
    metric_type: str  # "counter", "histogram", "gauge"
    description: str
    label_names: list[str] = field(default_factory=list)


class MetricsRegistry:
    """Central registry for all knowledge service metrics.

    Supports two backends:
    - "prometheus": Real Prometheus metrics (requires prometheus_client)
    - "memory": In-memory ring buffer (always available)
    - "auto": Try Prometheus, fall back to memory (default)

    Usage:
        metrics = MetricsRegistry()

        # Increment counters
        metrics.counter("query_total").inc()
        metrics.counter("query_errors_total").inc()

        # Observe latencies
        with metrics.latency("query_latency_seconds"):
            # ... do work ...

        # Set gauges
        metrics.gauge("namespaces_total").set(5)

        # Export
        json_data = metrics.export_json()
        prometheus_text = metrics.export_prometheus()
    """

    # Pre-defined metrics for EPIC-005
    PREDEFINED_METRICS: list[MetricDefinition] = [
        # Counters
        MetricDefinition("ingest_files_total", "counter", "Total number of files ingested"),
        MetricDefinition("ingest_bytes_total", "counter", "Total bytes ingested"),
        MetricDefinition("query_total", "counter", "Total number of queries executed"),
        MetricDefinition("query_errors_total", "counter", "Total number of query errors"),
        MetricDefinition("llm_calls_total", "counter", "Total number of LLM calls"),
        MetricDefinition("llm_errors_total", "counter", "Total number of LLM errors"),
        # Histograms
        MetricDefinition("ingest_latency_seconds", "histogram", "Ingestion latency in seconds"),
        MetricDefinition("query_latency_seconds", "histogram", "Query latency in seconds"),
        MetricDefinition("llm_latency_seconds", "histogram", "LLM call latency in seconds"),
        # Gauges
        MetricDefinition("namespaces_total", "gauge", "Total number of namespaces"),
        MetricDefinition(
            "disk_bytes_per_namespace", "gauge", "Disk bytes per namespace", label_names=["namespace"]
        ),
        MetricDefinition(
            "vector_count_per_namespace", "gauge", "Vector count per namespace", label_names=["namespace"]
        ),
        MetricDefinition(
            "entity_count_per_namespace", "gauge", "Entity count per namespace", label_names=["namespace"]
        ),
    ]

    def __init__(self, backend: str = "auto") -> None:
        self._backend = backend
        self._metrics: dict[str, Counter | Histogram | Gauge] = {}
        self._lock = threading.Lock()
        self._prometheus_registry: Any = None
        self._use_prometheus = False

        # Determine backend
        if backend == "auto":
            self._use_prometheus = self._check_prometheus_available()
        elif backend == "prometheus":
            self._use_prometheus = True
        else:
            self._use_prometheus = False

        # Create a custom Prometheus registry to avoid global state collisions
        # Each MetricsRegistry instance gets its own CollectorRegistry
        if self._use_prometheus:
            try:
                from prometheus_client import CollectorRegistry

                self._prometheus_registry = CollectorRegistry()
            except ImportError:
                self._use_prometheus = False

        # Initialize predefined metrics
        self._init_predefined_metrics()

    def _check_prometheus_available(self) -> bool:
        """Check if prometheus_client is available."""
        try:
            import prometheus_client  # noqa: WPS433, F401

            return True
        except ImportError:
            return False

    def _init_predefined_metrics(self) -> None:
        """Initialize all predefined metrics."""
        for definition in self.PREDEFINED_METRICS:
            self._create_metric(definition)

    def _create_metric(self, definition: MetricDefinition) -> Counter | Histogram | Gauge:
        """Create a metric based on the definition."""
        with self._lock:
            if definition.name in self._metrics:
                return self._metrics[definition.name]  # type: ignore

            if self._use_prometheus:
                if definition.metric_type == "counter":
                    metric = PrometheusCounter(
                        definition.name, definition.description, definition.label_names, self._prometheus_registry
                    )
                elif definition.metric_type == "histogram":
                    metric = PrometheusHistogram(
                        definition.name, definition.description, definition.label_names, self._prometheus_registry
                    )
                elif definition.metric_type == "gauge":
                    metric = PrometheusGauge(
                        definition.name, definition.description, definition.label_names, self._prometheus_registry
                    )
                else:
                    raise ValueError(f"Unknown metric type: {definition.metric_type}")
            else:
                if definition.metric_type == "counter":
                    metric = InMemoryCounter(definition.name, definition.description)
                elif definition.metric_type == "histogram":
                    metric = InMemoryHistogram(definition.name, definition.description)
                elif definition.metric_type == "gauge":
                    metric = InMemoryGauge(definition.name, definition.description)
                else:
                    raise ValueError(f"Unknown metric type: {definition.metric_type}")

            self._metrics[definition.name] = metric
            return metric

    def counter(self, name: str) -> Counter:
        """Get or create a counter by name."""
        metric = self._metrics.get(name)
        if metric is None:
            # Create on-demand
            definition = MetricDefinition(name, "counter", f"Counter {name}")
            metric = self._create_metric(definition)
        if not isinstance(metric, Counter):
            raise TypeError(f"Metric {name} is not a counter")
        return metric

    def histogram(self, name: str) -> Histogram:
        """Get or create a histogram by name."""
        metric = self._metrics.get(name)
        if metric is None:
            definition = MetricDefinition(name, "histogram", f"Histogram {name}")
            metric = self._create_metric(definition)
        if not isinstance(metric, Histogram):
            raise TypeError(f"Metric {name} is not a histogram")
        return metric

    def gauge(self, name: str) -> Gauge:
        """Get or create a gauge by name."""
        metric = self._metrics.get(name)
        if metric is None:
            definition = MetricDefinition(name, "gauge", f"Gauge {name}")
            metric = self._create_metric(definition)
        if not isinstance(metric, Gauge):
            raise TypeError(f"Metric {name} is not a gauge")
        return metric

    def latency(self, name: str, labels: Optional[dict[str, str]] = None) -> "LatencyContext":
        """Context manager for measuring latency."""
        return LatencyContext(self.histogram(name), labels)

    def export_json(self) -> dict[str, Any]:
        """Export all metrics as JSON-serializable dict."""
        with self._lock:
            result: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "backend": "prometheus" if self._use_prometheus else "memory",
                "counters": {},
                "histograms": {},
                "gauges": {},
            }

            for name, metric in self._metrics.items():
                if isinstance(metric, InMemoryCounter):
                    result["counters"][name] = {
                        "value": metric.get(),
                        "description": metric.description,
                        "labels": metric.get_all(),
                    }
                elif isinstance(metric, InMemoryHistogram):
                    result["histograms"][name] = {
                        "stats": metric.get_stats(),
                        "description": metric.description,
                        "samples": metric.get_all(),
                    }
                elif isinstance(metric, InMemoryGauge):
                    result["gauges"][name] = {
                        "value": metric.get(),
                        "description": metric.description,
                        "labels": metric.get_all(),
                    }
                elif self._use_prometheus:
                    # For Prometheus metrics, we can't easily get values
                    # Just include the description
                    if isinstance(metric, PrometheusCounter):
                        result["counters"][name] = {"description": metric.description, "backend": "prometheus"}
                    elif isinstance(metric, PrometheusHistogram):
                        result["histograms"][name] = {"description": metric.description, "backend": "prometheus"}
                    elif isinstance(metric, PrometheusGauge):
                        result["gauges"][name] = {"description": metric.description, "backend": "prometheus"}

            return result

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        if self._use_prometheus and self._prometheus_registry:
            try:
                from prometheus_client import generate_latest  # noqa: WPS433

                return generate_latest(self._prometheus_registry).decode("utf-8")
            except ImportError:
                pass

        # Fall back to manual Prometheus format for in-memory metrics
        lines: list[str] = []
        lines.append(f"# Generated at {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"# Backend: memory")

        for name, metric in self._metrics.items():
            if isinstance(metric, InMemoryCounter):
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} counter")
                for label_key, value in metric.get_all().items():
                    if label_key:
                        lines.append(f'{name}{{{label_key}}} {value}')
                    else:
                        lines.append(f"{name} {value}")
            elif isinstance(metric, InMemoryHistogram):
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} histogram")
                stats = metric.get_stats()
                lines.append(f"{name}_count {stats['count']}")
                lines.append(f"{name}_sum {stats['sum']}")
                # For in-memory, we don't have buckets, so just export count/sum
            elif isinstance(metric, InMemoryGauge):
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} gauge")
                for label_key, value in metric.get_all().items():
                    if label_key:
                        lines.append(f'{name}{{{label_key}}} {value}')
                    else:
                        lines.append(f"{name} {value}")

        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        """Reset all metrics (only works for in-memory backend)."""
        with self._lock:
            for metric in self._metrics.values():
                if isinstance(metric, InMemoryCounter):
                    metric.reset()


class LatencyContext:
    """Context manager for measuring latency and recording it in a histogram."""

    def __init__(self, histogram: Histogram, labels: Optional[dict[str, str]] = None) -> None:
        self._histogram = histogram
        self._labels = labels
        self._start_time: Optional[float] = None

    def __enter__(self) -> "LatencyContext":
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._start_time is not None:
            elapsed = time.perf_counter() - self._start_time
            self._histogram.observe(elapsed, labels=self._labels)


# ---------------------------------------------------------------------------
# Global registry singleton
# ---------------------------------------------------------------------------

_global_registry: Optional[MetricsRegistry] = None
_global_registry_lock = threading.Lock()


def get_metrics_registry() -> MetricsRegistry:
    """Get the global metrics registry singleton."""
    global _global_registry
    if _global_registry is not None:
        return _global_registry
    with _global_registry_lock:
        if _global_registry is not None:
            return _global_registry
        # Re-read env var at call time (not module load time) for testability
        backend = os.environ.get("OSTWIN_KNOWLEDGE_METRICS_BACKEND", "auto")
        _global_registry = MetricsRegistry(backend=backend)
        return _global_registry


def reset_metrics_registry() -> None:
    """Reset the global metrics registry (for testing)."""
    global _global_registry
    with _global_registry_lock:
        if _global_registry is not None:
            _global_registry.reset()
        _global_registry = None


__all__ = [
    "Counter",
    "Histogram",
    "Gauge",
    "InMemoryCounter",
    "InMemoryHistogram",
    "InMemoryGauge",
    "PrometheusCounter",
    "PrometheusHistogram",
    "PrometheusGauge",
    "MetricDefinition",
    "MetricsRegistry",
    "LatencyContext",
    "get_metrics_registry",
    "reset_metrics_registry",
    "METRICS_BACKEND",
    "RING_BUFFER_SIZE",
]
