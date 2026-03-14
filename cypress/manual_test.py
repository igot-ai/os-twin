import subprocess
import os

import os
print(f"I AM RUNNING FROM: {os.getcwd()}")
print(f"MY PATH IS: {__file__}")
cmd = [
    "pwsh", "-File", "/Users/paulaan/PycharmProjects/agent-os/.agents/run_fix_test.ps1"
]
res = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT_START")
print(res.stdout)
print("STDOUT_END")
print("STDERR_START")
print(res.stderr)
print("STDERR_END")
exit(res.returncode)
