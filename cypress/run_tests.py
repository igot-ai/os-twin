import subprocess
import os

print("Running Start-Plan Tests...")
res = subprocess.run(["pwsh", "-NoProfile", "-Command", "Invoke-Pester -Path /Users/paulaan/PycharmProjects/agent-os/.agents/plan/Expand-Plan.Tests.ps1 -PassThru"], capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
exit(res.returncode)
