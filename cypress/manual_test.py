import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / ".agents"

print(f"I AM RUNNING FROM: {os.getcwd()}")
print(f"MY PATH IS: {__file__}")

cmd = [
    "pwsh", "-File", str(AGENTS_DIR / "tests" / "scripts" / "run_fix_test.ps1")
]
res = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT_START")
print(res.stdout)
print("STDOUT_END")
print("STDERR_START")
print(res.stderr)
print("STDERR_END")
exit(res.returncode)
