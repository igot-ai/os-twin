import json
import os
import sys
from fastapi.testclient import TestClient

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from api import app
    print("✓ Successfully imported 'app' from api.py")
except ImportError as e:
    print(f"✗ Failed to import 'app' from api.py: {e}")
    sys.exit(1)

try:
    import fastapi
    import httpx
    print(f"✓ fastapi installed: {fastapi.__version__}")
    print(f"✓ httpx installed: {httpx.__version__}")
except ImportError as e:
    print(f"✗ Missing dependency: {e}")
    sys.exit(1)

client = TestClient(app)

def test_endpoint(name, method, url, **kwargs):
    print(f"\n[Testing {name}] {method} {url}")
    try:
        if method == "GET":
            response = client.get(url)
        elif method == "POST":
            response = client.post(url, **kwargs)
        else:
            print(f"Unsupported method: {method}")
            return
        
        print(f"Status: {response.status_code}")
        # Only print first 200 chars of response to keep it clean
        resp_json = response.json()
        resp_str = json.dumps(resp_json, indent=2)
        if len(resp_str) > 500:
            print(f"Response: {resp_str[:500]}...\n(truncated)")
        else:
            print(f"Response: {resp_str}")
        return response
    except Exception as e:
        print(f"Error testing {name}: {e}")
        return None

if __name__ == "__main__":
    print("--- Starting API Endpoint Verification ---")
    
    # 1. GET /api/plans
    test_endpoint("GET Plans", "GET", "/api/plans")
    
    # 2. POST /api/plans/{plan_id}/status
    plan_id = "plan-20260313-211747"
    test_endpoint("Update Plan Status", "POST", f"/api/plans/{plan_id}/status", json={"status": "verified"})
    
    # 3. GET /api/goals
    test_endpoint("GET Goals", "GET", "/api/goals")
    
    # 4. POST /api/rooms/room-001/action
    test_endpoint("Room Action", "POST", "/api/rooms/room-001/action", json={"action": "reboot"})
    
    print("\n--- Verification Complete ---")
