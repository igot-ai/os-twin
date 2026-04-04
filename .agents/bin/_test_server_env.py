#!/usr/bin/env python3
"""Test that deepagents server subprocess gets GOOGLE_API_KEY."""
import os
import sys

print(f"GOOGLE_API_KEY in env: {'GOOGLE_API_KEY' in os.environ}")
print(f"GOOGLE_API_KEY length: {len(os.environ.get('GOOGLE_API_KEY', ''))}")
print(f"GEMINI_API_KEY in env: {'GEMINI_API_KEY' in os.environ}")

key = os.environ.get('GOOGLE_API_KEY', '')
if key:
    print(f"Key prefix: {key[:15]}...")
else:
    print("NO KEY FOUND")
    sys.exit(1)

# Now test the actual server startup path
print("\n=== Testing server_manager.server_session path ===")
from deepagents_cli._server_config import ServerConfig
from deepagents_cli.server_manager import _capture_project_context, _build_server_env, _apply_server_config

project_context = _capture_project_context()
config = ServerConfig.from_cli_args(
    project_context=project_context,
    model_name="google_genai:gemini-2.5-flash",
    assistant_id="agent",
    auto_approve=True,
    enable_shell=True,
    no_mcp=True,
    interactive=False,
)
_apply_server_config(config)

# Check what env the server subprocess would get
server_env = _build_server_env()
print(f"\nServer subprocess env GOOGLE_API_KEY: {'GOOGLE_API_KEY' in server_env}")
if 'GOOGLE_API_KEY' in server_env:
    print(f"Server key length: {len(server_env['GOOGLE_API_KEY'])}")
else:
    print("CRITICAL: Server subprocess would NOT have GOOGLE_API_KEY!")
    
# List all DA_SERVER_ env vars
da_vars = {k: v for k, v in server_env.items() if k.startswith("DA_SERVER")}
print(f"\nDA_SERVER env vars: {list(da_vars.keys())}")
for k, v in da_vars.items():
    print(f"  {k} = {v[:80]}...")
