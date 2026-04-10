import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / ".agents"

def test_pester():
    test_file = str(AGENTS_DIR / "tests" / "plan" / "Start-Plan.Tests.ps1")
    res = subprocess.run(["pwsh", "-NoProfile", "-Command", f"Invoke-Pester -Path '{test_file}' -Output Detailed"], capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)
    assert res.returncode == 0
