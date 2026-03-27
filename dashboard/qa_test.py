
import requests
import time
import subprocess
import os

def test_endpoints():
    os.chdir("/Users/paulaan/PycharmProjects/agent-os/.agents/dashboard/")
    # Start the server in the background
    process = subprocess.Popen(["python3", "api.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(2)  # Wait for server to start
    
    base_url = os.environ.get("DASHBOARD_URL", "http://localhost:" + os.environ.get("OSTWIN_DASHBOARD_PORT", "9000"))
    try:
        # Test health
        res = requests.get(f"{base_url}/api/health")
        print(f"Health: {res.status_code}")
        print(res.json())
        
        # Test plans
        res = requests.get(f"{base_url}/api/plans")
        print(f"Plans: {res.status_code}")
        print(res.json())
        
        # Test goals
        res = requests.get(f"{base_url}/api/goals")
        print(f"Goals: {res.status_code}")
        print(res.json())
        
        # Test room action
        res = requests.post(f"{base_url}/api/rooms/room-002/action", json={"action": "test_action"})
        print(f"Room Action: {res.status_code}")
        print(res.json())
        
        # Verify control file created
        control_file = "/Users/paulaan/PycharmProjects/agent-os/.agents/dashboard/.war-rooms/room-002/control"
        if os.path.exists(control_file):
            print(f"Control file created: {open(control_file).read()}")
        else:
            print("Control file NOT created")

    except Exception as e:
        print(f"Error during testing: {e}")
    finally:
        process.terminate()

if __name__ == "__main__":
    test_endpoints()
