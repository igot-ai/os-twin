#!/usr/bin/env python3
"""Debug: Check what env reaches the server subprocess."""
import os
import sys

# Simulate what cli.py does
for v in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_GENAI_USE_VERTEXAI"):
    os.environ.pop(v, None)

# Read API key from .ostwin/.env
env_path = os.path.expanduser("~/.ostwin/.env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("GOOGLE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["GOOGLE_API_KEY"] = key
                break

print(f"GOOGLE_API_KEY in env: {bool(os.environ.get('GOOGLE_API_KEY'))}")
print(f"GOOGLE_CLOUD_PROJECT in env: {repr(os.environ.get('GOOGLE_CLOUD_PROJECT'))}")
print(f"GOOGLE_CLOUD_LOCATION in env: {repr(os.environ.get('GOOGLE_CLOUD_LOCATION'))}")

# Now check what _build_server_env produces
from deepagents_cli.server import ServerProcess
import types

_orig_start = ServerProcess.start

async def _debug_start(self, *, timeout=60):
    from deepagents_cli.server import _build_server_env
    env = _build_server_env()
    print(f"\nSERVER ENV - GOOGLE_API_KEY: {bool(env.get('GOOGLE_API_KEY'))}, len={len(env.get('GOOGLE_API_KEY',''))}")
    print(f"SERVER ENV - GOOGLE_CLOUD_PROJECT: {repr(env.get('GOOGLE_CLOUD_PROJECT'))}")
    print(f"SERVER ENV - GOOGLE_CLOUD_LOCATION: {repr(env.get('GOOGLE_CLOUD_LOCATION'))}")
    await _orig_start(self, timeout=timeout)

ServerProcess.start = _debug_start

import asyncio
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
