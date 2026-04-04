#!/usr/bin/env python3
"""Debug: Full server pipeline trace with env dumping."""
import os
import sys
import asyncio

# Clean env at Python level
for v in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_GENAI_USE_VERTEXAI"):
    os.environ.pop(v, None)

# Set API key  
env_path = os.path.expanduser("~/.ostwin/.env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("GOOGLE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["GOOGLE_API_KEY"] = key
                break

# Patch the scaffold to inject an env dump into server_graph.py
from deepagents_cli import server_manager as _sm
import shutil
from pathlib import Path

_orig_scaffold = _sm._scaffold_workspace

def _patched_scaffold(work_dir):
    _orig_scaffold(work_dir)
    # Patch the server_graph.py to log env info
    sg_path = work_dir / "server_graph.py"
    content = sg_path.read_text()
    inject = '''
import os as _os
_google_vars = {k: v for k, v in _os.environ.items() if 'GOOGLE' in k or 'VERTEX' in k or 'GENAI' in k}
print(f"[SERVER_GRAPH] GOOGLE env vars in subprocess: {_google_vars}", flush=True)
print(f"[SERVER_GRAPH] GOOGLE_API_KEY present: {bool(_os.environ.get('GOOGLE_API_KEY'))}, len={len(_os.environ.get('GOOGLE_API_KEY',''))}", flush=True)
print(f"[SERVER_GRAPH] GOOGLE_CLOUD_PROJECT: {_os.environ.get('GOOGLE_CLOUD_PROJECT')}", flush=True)
'''
    content = inject + content
    sg_path.write_text(content)
    print(f"[DEBUG] Patched server_graph.py at {sg_path}")

_sm._scaffold_workspace = _patched_scaffold

# Also patch stop to print final log
from deepagents_cli import server as _srv
_orig_stop = _srv.ServerProcess.stop

def _patched_stop(self):
    if self._log_file:
        try:
            self._log_file.flush()
            content = Path(self._log_file.name).read_text(errors='replace')
            # Find our debug prints
            for line in content.split('\n'):
                if '[SERVER_GRAPH]' in line:
                    print(line)
            # Also find the error
            for line in content.split('\n'):
                if 'ChatGoogleGenerativeAIError' in line or 'Unauthorized' in line:
                    print(f"[ERROR] {line[:200]}")
        except Exception as e:
            print(f"[DEBUG] Could not read log: {e}")
    _orig_stop(self)

_srv.ServerProcess.stop = _patched_stop

from deepagents_cli.non_interactive import run_non_interactive

async def main():
    return await run_non_interactive(
        message="Say hello in one word",
        model_name="google_genai:gemini-2.5-flash",
        quiet=False,
        no_mcp=True,
    )

code = asyncio.run(main())
print(f"\nExit code: {code}")
sys.exit(code)
