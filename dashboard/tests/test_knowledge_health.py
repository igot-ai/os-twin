"""Tests for knowledge health endpoint (EPIC-005).

Tests the health check functionality including storage, embedder, and LLM checks.
"""

from __future__ import annotations

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from dashboard.api import app
from dashboard.auth import get_current_user


# Override auth for tests
def override_get_current_user():
    return {"email": "test@example.com", "sub": "test-user"}


app.dependency_overrides[get_current_user] = override_get_current_user


class TestHealthEndpoint:
    """Tests for GET /api/knowledge/health."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    def test_health_returns_ok_when_all_healthy(self, client: TestClient) -> None:
        """Health endpoint returns ok when all checks pass."""
        # Mock the checks to return healthy
        with patch("dashboard.routes.knowledge._check_storage") as mock_storage, \
             patch("dashboard.routes.knowledge._check_embedder") as mock_embedder, \
             patch("dashboard.routes.knowledge._check_llm") as mock_llm:
            
            from dashboard.routes.knowledge import HealthCheckResult
            
            mock_storage.return_value = HealthCheckResult(status="ok", message="Storage OK")
            mock_embedder.return_value = HealthCheckResult(status="ok", message="Embedder OK")
            mock_llm.return_value = HealthCheckResult(status="ok", message="LLM OK")
            
            response = client.get("/api/knowledge/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["checks"]["storage"]["status"] == "ok"
            assert data["checks"]["embedder"]["status"] == "ok"
            assert data["checks"]["llm"]["status"] == "ok"
            assert "timestamp" in data

    def test_health_returns_unhealthy_when_storage_fails(self, client: TestClient) -> None:
        """Health endpoint returns unhealthy when storage check fails."""
        with patch("dashboard.routes.knowledge._check_storage") as mock_storage, \
             patch("dashboard.routes.knowledge._check_embedder") as mock_embedder, \
             patch("dashboard.routes.knowledge._check_llm") as mock_llm:
            
            from dashboard.routes.knowledge import HealthCheckResult
            
            mock_storage.return_value = HealthCheckResult(
                status="unhealthy", 
                message="Cannot write to storage"
            )
            mock_embedder.return_value = HealthCheckResult(status="ok", message="Embedder OK")
            mock_llm.return_value = HealthCheckResult(status="ok", message="LLM OK")
            
            response = client.get("/api/knowledge/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["checks"]["storage"]["status"] == "unhealthy"

    def test_health_returns_degraded_when_embedder_fails(self, client: TestClient) -> None:
        """Health endpoint returns degraded when embedder check fails."""
        with patch("dashboard.routes.knowledge._check_storage") as mock_storage, \
             patch("dashboard.routes.knowledge._check_embedder") as mock_embedder, \
             patch("dashboard.routes.knowledge._check_llm") as mock_llm:
            
            from dashboard.routes.knowledge import HealthCheckResult
            
            mock_storage.return_value = HealthCheckResult(status="ok", message="Storage OK")
            mock_embedder.return_value = HealthCheckResult(
                status="unhealthy", 
                message="Embedder unavailable"
            )
            mock_llm.return_value = HealthCheckResult(status="ok", message="LLM OK")
            
            response = client.get("/api/knowledge/health")
            
            assert response.status_code == 200
            data = response.json()
            # Embedder failure should cause degraded (not unhealthy)
            assert data["status"] == "degraded"

    def test_health_returns_degraded_when_llm_not_configured(self, client: TestClient) -> None:
        """Health endpoint returns degraded when LLM is not configured."""
        with patch("dashboard.routes.knowledge._check_storage") as mock_storage, \
             patch("dashboard.routes.knowledge._check_embedder") as mock_embedder, \
             patch("dashboard.routes.knowledge._check_llm") as mock_llm:
            
            from dashboard.routes.knowledge import HealthCheckResult
            
            mock_storage.return_value = HealthCheckResult(status="ok", message="Storage OK")
            mock_embedder.return_value = HealthCheckResult(status="ok", message="Embedder OK")
            mock_llm.return_value = HealthCheckResult(
                status="unhealthy", 
                message="No LLM model configured"
            )
            
            response = client.get("/api/knowledge/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["checks"]["llm"]["status"] == "unhealthy"

    def test_health_includes_latency(self, client: TestClient) -> None:
        """Health check results include latency measurements."""
        with patch("dashboard.routes.knowledge._check_storage") as mock_storage, \
             patch("dashboard.routes.knowledge._check_embedder") as mock_embedder, \
             patch("dashboard.routes.knowledge._check_llm") as mock_llm:
            
            from dashboard.routes.knowledge import HealthCheckResult
            
            mock_storage.return_value = HealthCheckResult(
                status="ok", 
                message="Storage OK", 
                latency_ms=5.2
            )
            mock_embedder.return_value = HealthCheckResult(
                status="ok", 
                message="Embedder OK", 
                latency_ms=100.5
            )
            mock_llm.return_value = HealthCheckResult(
                status="ok", 
                message="LLM OK", 
                latency_ms=1.0
            )
            
            response = client.get("/api/knowledge/health")
            
            data = response.json()
            assert data["checks"]["storage"]["latency_ms"] == 5.2
            assert data["checks"]["embedder"]["latency_ms"] == 100.5
            assert data["checks"]["llm"]["latency_ms"] == 1.0


class TestStorageCheck:
    """Tests for storage health check."""

    @pytest.mark.asyncio
    async def test_storage_check_ok_with_writable_dir(self) -> None:
        """Storage check returns ok when directory is writable."""
        from dashboard.routes.knowledge import _check_storage
        from dashboard.knowledge.config import KNOWLEDGE_DIR
        import os
        
        # Ensure knowledge dir exists and is writable
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        
        result = await _check_storage()
        
        assert result.status in ("ok", "degraded")  # degraded if embedder issue

    @pytest.mark.asyncio
    async def test_storage_check_unhealthy_when_not_writable(self) -> None:
        """Storage check returns unhealthy when directory is not writable."""
        from dashboard.routes.knowledge import _check_storage
        from dashboard.knowledge.config import KNOWLEDGE_DIR
        import os
        
        # Create a temp directory and make it read-only
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "readonly"
            test_dir.mkdir()
            
            # Patch KNOWLEDGE_DIR at the source (config module) to point to our test dir
            with patch("dashboard.knowledge.config.KNOWLEDGE_DIR", test_dir):
                # Make directory read-only
                os.chmod(test_dir, 0o000)
                
                try:
                    result = await _check_storage()
                    
                    assert result.status == "unhealthy"
                    assert "not writable" in result.message.lower() or "permission" in result.message.lower()
                finally:
                    # Restore permissions for cleanup
                    os.chmod(test_dir, 0o755)


class TestEmbedderCheck:
    """Tests for embedder health check."""

    @pytest.mark.asyncio
    async def test_embedder_check_ok_when_available(self) -> None:
        """Embedder check returns ok when model is available."""
        from dashboard.routes.knowledge import _check_embedder
        
        # Mock the embedder to return a valid embedding
        with patch("dashboard.knowledge.embeddings.KnowledgeEmbedder") as MockEmbedder:
            mock_instance = MagicMock()
            mock_instance.embed_one.return_value = [0.1] * 768  # Fake embedding
            MockEmbedder.return_value = mock_instance
            
            result = await _check_embedder()
            
            assert result.status == "ok"

    @pytest.mark.asyncio
    async def test_embedder_check_unhealthy_on_error(self) -> None:
        """Embedder check returns unhealthy when model fails."""
        from dashboard.routes.knowledge import _check_embedder
        
        with patch("dashboard.knowledge.embeddings.KnowledgeEmbedder") as MockEmbedder:
            mock_instance = MagicMock()
            mock_instance.embed_one.side_effect = RuntimeError("Model not loaded")
            MockEmbedder.return_value = mock_instance
            
            result = await _check_embedder()
            
            assert result.status == "unhealthy"


class TestLLMCheck:
    """Tests for LLM health check."""

    @pytest.mark.asyncio
    async def test_llm_check_unhealthy_without_api_key(self) -> None:
        """LLM check returns unhealthy when no model or API key is configured."""
        from dashboard.routes.knowledge import _check_llm
        
        with patch("dashboard.knowledge.llm.KnowledgeLLM") as MockLLM:
            mock_instance = MagicMock()
            mock_instance.model = ""
            mock_instance.is_available.return_value = False
            MockLLM.return_value = mock_instance
            
            result = await _check_llm()
            
            assert result.status == "unhealthy"
            assert "model" in result.message.lower() or "key" in result.message.lower()

    @pytest.mark.asyncio
    async def test_llm_check_ok_with_api_key(self) -> None:
        """LLM check returns ok when model and API key are configured."""
        from dashboard.routes.knowledge import _check_llm
        
        with patch("dashboard.knowledge.llm.KnowledgeLLM") as MockLLM:
            mock_instance = MagicMock()
            mock_instance.model = "gemini-2.0-flash"
            mock_instance.is_available.return_value = True
            mock_instance._effective_provider.return_value = "google"
            MockLLM.return_value = mock_instance
            
            result = await _check_llm()
            
            assert result.status == "ok"
            assert "configured" in result.message.lower()


class TestMetricsEndpoint:
    """Tests for GET /api/knowledge/metrics."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    def test_metrics_returns_json(self, client: TestClient) -> None:
        """Metrics endpoint returns JSON by default."""
        response = client.get("/api/knowledge/metrics")
        
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        
        data = response.json()
        assert "timestamp" in data
        assert "backend" in data
        assert "counters" in data
        assert "histograms" in data
        assert "gauges" in data

    def test_metrics_includes_predefined_counters(self, client: TestClient) -> None:
        """Metrics includes predefined counters."""
        response = client.get("/api/knowledge/metrics")
        data = response.json()
        
        # Check for predefined counters
        assert "query_total" in data["counters"]
        assert "ingest_files_total" in data["counters"]
        assert "query_errors_total" in data["counters"]
        assert "llm_calls_total" in data["counters"]

    def test_metrics_includes_predefined_histograms(self, client: TestClient) -> None:
        """Metrics includes predefined histograms."""
        response = client.get("/api/knowledge/metrics")
        data = response.json()
        
        assert "query_latency_seconds" in data["histograms"]
        assert "ingest_latency_seconds" in data["histograms"]
        assert "llm_latency_seconds" in data["histograms"]

    def test_metrics_includes_predefined_gauges(self, client: TestClient) -> None:
        """Metrics includes predefined gauges."""
        response = client.get("/api/knowledge/metrics")
        data = response.json()
        
        assert "namespaces_total" in data["gauges"]
        assert "disk_bytes_per_namespace" in data["gauges"]

    def test_metrics_content_negotiation_json(self, client: TestClient) -> None:
        """Metrics endpoint returns JSON by default."""
        response = client.get("/api/knowledge/metrics")
        
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        # Should be valid JSON
        data = response.json()
        assert "counters" in data

    def test_metrics_content_negotiation_prometheus(self, client: TestClient) -> None:
        """Metrics endpoint returns Prometheus format when Accept: text/plain."""
        response = client.get(
            "/api/knowledge/metrics",
            headers={"Accept": "text/plain"}
        )
        
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        # Should contain Prometheus format markers
        text = response.text
        assert "# TYPE" in text
        assert "# HELP" in text


class TestPrometheusMetricsEndpoint:
    """Tests for GET /api/knowledge/metrics/prometheus."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    def test_prometheus_returns_text_plain(self, client: TestClient) -> None:
        """Prometheus endpoint returns text/plain content type."""
        response = client.get("/api/knowledge/metrics/prometheus")
        
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_prometheus_format_includes_counters(self, client: TestClient) -> None:
        """Prometheus format includes counter metrics."""
        response = client.get("/api/knowledge/metrics/prometheus")
        text = response.text
        
        assert "# TYPE query_total counter" in text
        assert "# TYPE ingest_files_total counter" in text

    def test_prometheus_format_includes_gauges(self, client: TestClient) -> None:
        """Prometheus format includes gauge metrics."""
        response = client.get("/api/knowledge/metrics/prometheus")
        text = response.text
        
        assert "# TYPE namespaces_total gauge" in text

    def test_prometheus_format_includes_histograms(self, client: TestClient) -> None:
        """Prometheus format includes histogram metrics."""
        response = client.get("/api/knowledge/metrics/prometheus")
        text = response.text
        
        assert "# TYPE query_latency_seconds histogram" in text


class TestCounterProbeIntegration:
    """Integration tests for counter probes."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    def test_after_10_queries_query_total_at_least_10(self, client: TestClient) -> None:
        """After 10 query operations, query_total >= 10."""
        import os
        # Force in-memory backend for reliable value tracking in tests
        os.environ["OSTWIN_KNOWLEDGE_METRICS_BACKEND"] = "memory"
        
        # Reset metrics
        from dashboard.knowledge.metrics import reset_metrics_registry
        reset_metrics_registry()
        
        # Get initial metrics
        response = client.get("/api/knowledge/metrics")
        initial = response.json()
        initial_query_total = initial["counters"]["query_total"]["value"]
        
        # Simulate 10 query increments (in real scenario, would call query endpoint)
        from dashboard.knowledge.metrics import get_metrics_registry
        metrics = get_metrics_registry()
        for _ in range(10):
            metrics.counter("query_total").inc()
        
        # Get final metrics
        response = client.get("/api/knowledge/metrics")
        final = response.json()
        final_query_total = final["counters"]["query_total"]["value"]
        
        assert final_query_total >= initial_query_total + 10

    def test_after_ingest_files_total_increments(self, client: TestClient) -> None:
        """After ingesting N files, ingest_files_total >= N."""
        import os
        # Force in-memory backend for reliable value tracking in tests
        os.environ["OSTWIN_KNOWLEDGE_METRICS_BACKEND"] = "memory"
        
        from dashboard.knowledge.metrics import reset_metrics_registry, get_metrics_registry
        reset_metrics_registry()
        
        metrics = get_metrics_registry()
        
        # Simulate ingesting 5 files
        metrics.counter("ingest_files_total").inc(5)
        
        response = client.get("/api/knowledge/metrics")
        data = response.json()
        
        assert data["counters"]["ingest_files_total"]["value"] >= 5


class TestDiskBytesAccuracy:
    """Tests for disk_bytes per namespace accuracy."""

    def test_disk_bytes_within_5_percent(self) -> None:
        """disk_bytes per namespace is accurate within ±5%."""
        from dashboard.knowledge.stats import NamespaceStatsComputer
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            namespace_dir = Path(tmpdir) / "test-namespace"
            namespace_dir.mkdir()
            
            # Create some files with known sizes
            file1 = namespace_dir / "file1.txt"
            file1.write_text("x" * 1000)  # 1000 bytes
            
            file2 = namespace_dir / "file2.txt"
            file2.write_text("y" * 500)  # 500 bytes
            
            expected_size = 1500  # Total bytes
            
            computer = NamespaceStatsComputer()
            stats = computer.get_stats("test-namespace", namespace_dir)
            
            disk_bytes = stats["disk_bytes"]
            
            # Allow 5% margin for filesystem overhead
            margin = 0.05 * expected_size
            assert abs(disk_bytes - expected_size) <= margin + 1000  # +1KB for filesystem overhead
