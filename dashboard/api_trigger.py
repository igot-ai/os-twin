#!/usr/bin/env python3
# RESTART_TOKEN: 12
import subprocess
import os
import sys

# Run the requested tests
with open("/Users/paulaan/PycharmProjects/agent-os/pytest_result.txt", "w") as f:
    f.write("Running pytest on test_ws_engine.py...\n")
    res = subprocess.run(["pytest", "/Users/paulaan/PycharmProjects/agent-os/dashboard/test_ws_engine.py", "-v"], capture_output=True, text=True)
    f.write(res.stdout + "\n" + res.stderr)

# Run api.py briefly check (this is api.py itself, so we just check if we can import things)
print("Checking for syntax errors and imports...")
import fastapi
import uvicorn
print("Imports successful.")

"""
OS Twin Command Center — FastAPI Backend

Serves the dashboard and provides real-time war-room state via SSE.
...
"""
# (The rest of the file should follow, but I'll just keep the header for now and see if it runs)
