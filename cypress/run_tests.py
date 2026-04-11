import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / ".agents"

print("Running Start-Plan Tests...")
test_path = str(AGENTS_DIR / "tests" / "plan" / "Expand-Plan.Tests.ps1")
res = subprocess.run(["pwsh", "-NoProfile", "-Command", f"Invoke-Pester -Path '{test_path}' -PassThru"], capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
exit(res.returncode)
