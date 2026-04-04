#!/usr/bin/env python3
"""Simulate the exact server subprocess behavior to find the auth bug."""
import os, sys

# 1. Clean env (as our server_graph.py patch does)
for v in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_GENAI_USE_VERTEXAI"):
    os.environ.pop(v, None)

# 2. Check API key state BEFORE config import
print(f"1. API key BEFORE config import: {os.environ.get('GOOGLE_API_KEY', '')[:20]}...")
print(f"   GOOGLE_CLOUD_PROJECT: {os.environ.get('GOOGLE_CLOUD_PROJECT')}")

# 3. Import config (triggers _load_dotenv at module level)
from deepagents_cli.config import create_model, settings

print(f"2. API key AFTER config import: {os.environ.get('GOOGLE_API_KEY', '')[:20]}...")
print(f"   GOOGLE_CLOUD_PROJECT: {os.environ.get('GOOGLE_CLOUD_PROJECT')}")
print(f"   settings.google_api_key: {repr(settings.google_api_key)[:30]}...")

# 4. settings.reload_from_environment (like server_graph.py line 113)
from deepagents_cli.project_utils import get_server_project_context
project_context = get_server_project_context()
if project_context:
    print(f"3. project_context.user_cwd: {project_context.user_cwd}")
    settings.reload_from_environment(start_path=project_context.user_cwd)
    print(f"4. API key AFTER reload: {os.environ.get('GOOGLE_API_KEY', '')[:20]}...")
    print(f"   GOOGLE_CLOUD_PROJECT: {os.environ.get('GOOGLE_CLOUD_PROJECT')}")
    print(f"   settings.google_api_key: {repr(settings.google_api_key)[:30]}...")
else:
    print("3. No project context")

# 5. Try to create the model
print("\n5. Creating model...")
try:
    result = create_model("google_genai:gemini-2.5-flash")
    model = result.model
    print(f"   Model created: {type(model).__name__}")
    print(f"   vertexai: {model.vertexai}")
    print(f"   _use_vertexai: {model._use_vertexai}")
    print(f"   project: {model.project}")
    print(f"   google_api_key: {repr(model.google_api_key)[:30]}...")
    
    # 6. Try invoke
    print("\n6. Testing invoke...")
    resp = model.invoke("Say hello in one word")
    print(f"   SUCCESS: {resp.content[:50]}")
except Exception as e:
    print(f"   ERROR: {e}")
