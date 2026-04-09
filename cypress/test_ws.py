import subprocess
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / ".agents"

cmd = ["pwsh", "-c", f". {AGENTS_DIR / 'plan' / 'Expand-Plan.ps1'} -PlanFile {AGENTS_DIR / 'plans' / 'test-repro.md'} -AgentCmd deepagents"]
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
