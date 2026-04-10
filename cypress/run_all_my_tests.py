import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / ".agents"

test_paths = [
    str(AGENTS_DIR / "tests" / "plan" / "*.Tests.ps1"),
    str(AGENTS_DIR / "tests" / "*.Tests.ps1")
]
paths_str = ",".join([f"'{p}'" for p in test_paths])
cmd = ["pwsh", "-NoProfile", "-Command", f"Invoke-Pester -Path {paths_str} -Output Detailed"]
print(f"Running: {' '.join(cmd)}")
res = subprocess.run(cmd, capture_output=True, text=True)
output_file = PROJECT_ROOT / "all_tests_results.txt"
with open(output_file, "w") as f:
    f.write(res.stdout)
    f.write(res.stderr)
print("Done.")
