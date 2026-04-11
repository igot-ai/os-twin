import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / ".agents"

print("Running manual test for plan refinement...")
cmd = [
    "pwsh", "-c",
    f". {AGENTS_DIR / 'plan' / 'Start-Plan.ps1'} -PlanFile {AGENTS_DIR / 'plans' / 'test-qa.md'} -ProjectDir {PROJECT_ROOT} -DryRun"
]
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
exit(res.returncode)
