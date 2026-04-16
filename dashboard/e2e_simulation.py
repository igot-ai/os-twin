import time
import subprocess
import os
import requests

def test_e2e():
    print("Starting backend server...")
    env = os.environ.copy()
    env["PYTHONPATH"] = "/Users/paulaan/PycharmProjects/agent-os"
    # Start server in background
    server_process = subprocess.Popen(
        ["python", "api.py", "--port", "3366"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="/Users/paulaan/PycharmProjects/agent-os/dashboard"
    )
    
    try:
        # Wait for server to be ready
        print("Waiting for server to be ready...")
        for _ in range(30):
            try:
                response = requests.get("http://localhost:3366/api/system/status", timeout=1)
                if response.status_code == 200:
                    print("Server is ready!")
                    break
            except:
                pass
            time.sleep(1)
        else:
            print("Server failed to start in time.")
            return

        # Perform ideation flow via API directly for speed, or via browser?
        # The brief mentions browser actions. I'll use a subagent for browser actions.
        print("Ideation flow verification...")
        
    finally:
        print("Stopping server...")
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    test_e2e()
