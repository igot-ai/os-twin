import subprocess
import os

def test_pester():
    test_file = "/Users/paulaan/PycharmProjects/agent-os/.agents/plan/Start-Plan.Tests.ps1"
    res = subprocess.run(["pwsh", "-NoProfile", "-Command", f"Invoke-Pester -Path '{test_file}' -Output Detailed"], capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)
    assert res.returncode == 0
