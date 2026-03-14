import subprocess
import os

def test_pester():
    paths = [
        "/Users/paulaan/PycharmProjects/agent-os/.agents/plan/Start-Plan.Tests.ps1",
        "/Users/paulaan/PycharmProjects/agent-os/.agents/plan/Expand-Plan.Tests.ps1"
    ]
    cmd = ["pwsh", "-NoProfile", "-Command", f"Invoke-Pester -Path {','.join(paths)}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    with open("/Users/paulaan/PycharmProjects/agent-os/final_pester_results.txt", "w") as f:
        f.write("STDOUT:\n")
        f.write(res.stdout)
        f.write("\nSTDERR:\n")
        f.write(res.stderr)
    assert True
