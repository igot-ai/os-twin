from fastapi.testclient import TestClient
from dashboard.api import app
from dashboard.auth import get_current_user
from dashboard.knowledge.metrics import reset_metrics_registry, get_metrics_registry
import os

# Override auth
def override_get_current_user():
    return {"email": "test@example.com", "sub": "test-user"}

app.dependency_overrides[get_current_user] = override_get_current_user

# Force memory backend
os.environ["OSTWIN_KNOWLEDGE_METRICS_BACKEND"] = "memory"
reset_metrics_registry()

# Re-initialize to see if it picks up memory
from dashboard.knowledge.metrics import MetricsRegistry
reg = MetricsRegistry(backend="memory")
print(f"Registry backend: {reg._backend}, use_prometheus: {reg._use_prometheus}")

client = TestClient(app)

# Check JSON export
print("\nJSON Metrics (forced memory in reg):")
metrics = get_metrics_registry()
# Manual increment
metrics.counter("query_total").inc(123)
resp = client.get("/api/knowledge/metrics")
print(resp.json()["counters"]["query_total"])

# Check Prometheus export
print("\nPrometheus Metrics:")
resp = client.get("/api/knowledge/metrics/prometheus")
print(resp.text[:500])
