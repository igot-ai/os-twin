import os
import sys
from pathlib import Path
import pytest

# CRITICAL: Set metrics backend to memory BEFORE any imports that might load metrics.py
# This ensures the MetricsRegistry uses in-memory backend from the start of the test session
os.environ["OSTWIN_KNOWLEDGE_METRICS_BACKEND"] = "memory"

# Add project root to PYTHONPATH for imports like `from dashboard.api import app`
project_root = Path(__file__).parent.parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add agentic_memory paths for Memory ↔ Knowledge Bridge tests
# The bridge imports from agentic_memory.memory_note which requires these paths
# IMPORTANT: Use source copy first (has get_knowledge_links method), only fall back to installed copy
agentic_memory_source = project_root / ".agents" / "memory"
agentic_memory_installed = Path.home() / ".ostwin" / ".agents" / "memory"

# Prefer source copy over installed copy
preferred_path = agentic_memory_source if agentic_memory_source.exists() else agentic_memory_installed
if str(preferred_path) not in sys.path:
    sys.path.insert(0, str(preferred_path))


def pytest_configure(config):
    """Register custom pytest markers used across the suite."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (real model load / network — deselect with -m 'not slow')",
    )


@pytest.fixture(autouse=True)
def isolated_test_env(tmp_path):
    """
    Provide an isolated environment for all tests.
    Sets necessary environment variables so tests do not
    pollute the global state or real zvec datasets.
    """
    # Isolate zvec to prevent 'zvec init failed' due to concurrency
    zvec_dir = tmp_path / ".zvec"
    os.environ["OSTWIN_ZVEC_DIR"] = str(zvec_dir)
    os.environ["OSTWIN_PROJECT_DIR"] = str(tmp_path / "project")
    
    # Fake API Key for tests that use authentication
    os.environ["OSTWIN_AUTH_KEY"] = "test-key"
    os.environ["OSTWIN_API_KEY"] = "test-key"
    
    yield


@pytest.fixture(autouse=True)
def reset_metrics():
    """
    Reset the metrics registry before each test to avoid Prometheus
    registry collisions when tests run sequentially.
    
    Forces in-memory backend by default for reliable value tracking.
    Tests that specifically need Prometheus can override the env var.
    Also clears the Prometheus global registry to prevent collisions.
    """
    # Ensure in-memory backend for tests (already set at module level, but reinforce)
    old_backend = os.environ.get("OSTWIN_KNOWLEDGE_METRICS_BACKEND")
    os.environ["OSTWIN_KNOWLEDGE_METRICS_BACKEND"] = "memory"
    
    # Reset the global registry singleton
    try:
        from dashboard.knowledge.metrics import reset_metrics_registry
        reset_metrics_registry()
    except ImportError:
        pass  # Module not available yet
    
    # Clear Prometheus global registry to prevent collisions
    # This is needed because prometheus_client uses a global REGISTRY
    # that persists across test runs
    try:
        import prometheus_client
        # Unregister all collectors from the default registry
        collectors = list(prometheus_client.REGISTRY._names_to_collectors.values())
        for collector in collectors:
            try:
                prometheus_client.REGISTRY.unregister(collector)
            except Exception:
                pass  # Ignore errors during unregister
    except ImportError:
        pass  # prometheus_client not installed
    
    yield
    
    # Restore original backend setting
    if old_backend is not None:
        os.environ["OSTWIN_KNOWLEDGE_METRICS_BACKEND"] = old_backend
    else:
        os.environ.pop("OSTWIN_KNOWLEDGE_METRICS_BACKEND", None)
    
    # Reset again after test for cleanliness
    try:
        from dashboard.knowledge.metrics import reset_metrics_registry
        reset_metrics_registry()
    except ImportError:
        pass
    
    # Clear Prometheus global registry again
    try:
        import prometheus_client
        collectors = list(prometheus_client.REGISTRY._names_to_collectors.values())
        for collector in collectors:
            try:
                prometheus_client.REGISTRY.unregister(collector)
            except Exception:
                pass
    except ImportError:
        pass
