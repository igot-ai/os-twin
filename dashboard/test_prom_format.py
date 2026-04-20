from dashboard.knowledge.metrics import MetricsRegistry
import os

# Create a registry and check its prometheus export
reg = MetricsRegistry(backend="memory") # Use memory but export as prometheus format
reg.counter("test_counter").inc(5)
reg.gauge("test_gauge").set(10)

prom_text = reg.export_prometheus()
print("Prometheus Text Export:")
print(prom_text)

# Check if it looks valid
assert "# HELP test_counter" in prom_text
assert "# TYPE test_counter counter" in prom_text
assert "test_counter 5.0" in prom_text
assert "# HELP test_gauge" in prom_text
assert "# TYPE test_gauge gauge" in prom_text
assert "test_gauge 10.0" in prom_text
print("\nFormat check PASSED")
