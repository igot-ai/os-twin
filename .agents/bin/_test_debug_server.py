#!/usr/bin/env python3
"""Debug: run deepagents pipeline and capture the langgraph dev server log."""
import os
import sys
import asyncio
import tempfile
from pathlib import Path

# Ensure we have the API key
key = ""
env_path = os.path.expanduser("~/.ostwin/.env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("GOOGLE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if not key:
    print("ERROR: No GOOGLE_API_KEY found")
    sys.exit(1)

os.environ["GOOGLE_API_KEY"] = key
print(f"GOOGLE_API_KEY set (length: {len(key)})")

# Patch _build_server_env to log what happens
from deepagents_cli import server as _srv

_original_build = _srv._build_server_env.__wrapped__ if hasattr(_srv._build_server_env, '__wrapped__') else _srv._build_server_env

# Patch ServerProcess.start to capture the log
_original_start = _srv.ServerProcess.start

async def _patched_start(self, *, timeout=60):
    """Patched start that keeps the log file."""
    await _original_start(self, timeout=timeout)
    if self._log_file:
        log_path = self._log_file.name
        print(f"\n=== SERVER LOG FILE: {log_path} ===")
        try:
            content = Path(log_path).read_text(errors='replace')
            print(content[:5000])
        except Exception as e:
            print(f"Could not read log: {e}")

_srv.ServerProcess.start = _patched_start

# Also patch stop to preserve and dump the log
_original_stop = _srv.ServerProcess.stop

def _patched_stop(self):
    if self._log_file:
        log_path = self._log_file.name
        print(f"\n=== FINAL SERVER LOG: {log_path} ===")
        try:
            self._log_file.flush()
            content = Path(log_path).read_text(errors='replace')
            print(content[-5000:])
        except Exception as e:
            print(f"Could not read log: {e}")
    _original_stop(self)

_srv.ServerProcess.stop = _patched_stop

# Now run the actual deepagents pipeline
from deepagents_cli.non_interactive import run_non_interactive

async def main():
    exit_code = await run_non_interactive(
        message="Say hello in one word",
        model_name="google_genai:gemini-2.5-flash",
        quiet=False,
        no_mcp=True,
    )
    print(f"\nExit code: {exit_code}")
    return exit_code

code = asyncio.run(main())
sys.exit(code)
