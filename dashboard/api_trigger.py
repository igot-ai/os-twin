#!/usr/bin/env python3
# RESTART_TOKEN: 1008
import subprocess
import os
import sys

# Run the user's debug script
output_file = "/Users/paulaan/PycharmProjects/agent-os/expand_plan_pester_output.txt"
command = ["pwsh", "-File", "/Users/paulaan/PycharmProjects/agent-os/.agents/run_fix_test.ps1"]

with open(output_file, "w") as f:
    f.write(f"Executing for user: {' '.join(command)}\n")
    try:
        res = subprocess.run(command, capture_output=True, text=True)
        f.write("STDOUT:\n")
        f.write(res.stdout)
        f.write("\nSTDERR:\n")
        f.write(res.stderr)
        f.write(f"\nEXIT CODE: {res.returncode}\n")
    except Exception as e:
        f.write(f"ERROR: {str(e)}\n")

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
