from fastapi.testclient import TestClient
from dashboard.api import app
from dashboard.auth import get_current_user
from dashboard.knowledge.metrics import reset_metrics_registry, get_metrics_registry
import os

# Override auth
def override_get_current_user():
    return {"email": "test@example.com", "sub": "test-user"}

app.dependency_overrides[get_current_user] = override_get_current_user

# Force memory backend for manual probe
os.environ["OSTWIN_KNOWLEDGE_METRICS_BACKEND"] = "memory"
reset_metrics_registry()

client = TestClient(app)

# 1. Check initial metrics
print("Initial metrics:")
resp = client.get("/api/knowledge/metrics")
if resp.status_code != 200:
    print(f"Error {resp.status_code}: {resp.text}")
else:
    print(resp.json()["counters"]["query_total"])

# 2. Simulate 10 queries
metrics = get_metrics_registry()
for _ in range(10):
    metrics.counter("query_total").inc()

# 3. Check metrics again
print("\nMetrics after 10 increments:")
resp = client.get("/api/knowledge/metrics")
if resp.status_code == 200:
    print(resp.json()["counters"]["query_total"])
else:
    print(f"Error {resp.status_code}: {resp.text}")

# 4. Test health endpoint
print("\nHealth status:")
resp = client.get("/api/knowledge/health")
print(resp.json())
