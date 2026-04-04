import os
import sys
import subprocess

if __name__ == "__main__":
    result = subprocess.run(["pytest", "dashboard/tests/test_home_api.py"], capture_output=True, text=True)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
