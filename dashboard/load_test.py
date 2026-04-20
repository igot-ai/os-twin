import os
import sys

# SET ENV VAR BEFORE IMPORTS
os.environ["OSTWIN_API_KEY"] = "test-key"

import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Ensure dashboard is importable
sys.path.insert(0, os.getcwd())

def run_query(client, headers):
    start = time.time()
    response = client.post(
        "/api/knowledge/namespaces/test-ns/query",
        headers=headers,
        json={"query": "test load", "mode": "raw"}
    )
    end = time.time()
    return response.status_code, (end - start) * 1000

async def main():
    from dashboard.api import app
    from dashboard.routes.knowledge import _get_service
    
    mock_service = MagicMock()
    # Simulate some latency
    def mocked_query(*args, **kwargs):
        time.sleep(0.1) # 100ms
        res = MagicMock()
        res.query = "test"
        res.mode = "raw"
        res.namespace = "test-ns"
        res.chunks = []
        res.entities = []
        res.answer = None
        res.citations = []
        res.latency_ms = 100
        res.warnings = []
        return res
        
    mock_service.query.side_effect = mocked_query
    
    # We need to make sure _get_service returns our mock_service
    headers = {"Authorization": "Bearer test-key"}
    
    with patch("dashboard.routes.knowledge._get_service", return_value=mock_service):
        with TestClient(app) as client:
            with ThreadPoolExecutor(max_workers=50) as executor:
                loop = asyncio.get_event_loop()
                futures = [
                    loop.run_in_executor(executor, run_query, client, headers)
                    for _ in range(50)
                ]
                results = await asyncio.gather(*futures)
                
    latencies = [r[1] for r in results]
    status_codes = [r[0] for r in results]
    
    print(f"Total requests: {len(results)}")
    print(f"Success count: {status_codes.count(200)}")
    print(f"Errors (non-200): {len([s for s in status_codes if s != 200])}")
    if status_codes.count(200) > 0:
        print(f"Min latency: {min(latencies):.2f}ms")
        print(f"Max latency: {max(latencies):.2f}ms")
        print(f"Avg latency: {sum(latencies)/len(latencies):.2f}ms")
        
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        print(f"p95 latency: {p95:.2f}ms")
    else:
        if len(results) > 0:
             print(f"First error detail: {results[0]}")

if __name__ == "__main__":
    asyncio.run(main())
