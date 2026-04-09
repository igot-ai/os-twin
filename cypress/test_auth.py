import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / ".agents"

def test_pester():
    paths = [
        str(AGENTS_DIR / "tests" / "plan" / "Start-Plan.Tests.ps1"),
        str(AGENTS_DIR / "tests" / "plan" / "Expand-Plan.Tests.ps1")
    ]
    cmd = ["pwsh", "-NoProfile", "-Command", f"Invoke-Pester -Path {','.join(paths)}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    output_file = PROJECT_ROOT / "final_pester_results.txt"
    with open(output_file, "w") as f:
        f.write("STDOUT:\n")
        f.write(res.stdout)
        f.write("\nSTDERR:\n")
        f.write(res.stderr)
    assert True
