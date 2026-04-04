#!/usr/bin/env python3
"""Debug: Trace the exact `google.genai.Client` initialization that happens inside the server."""
import os, sys

# Clean env
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

# Monkeypatch google.genai.Client to trace what params it receives
from google.genai import client as _genai_client

_OrigClient = _genai_client.Client

class _TracingClient(_OrigClient):
    def __init__(self, **kwargs):
        print(f"\n=== google.genai.Client.__init__ called ===", flush=True)
        for k, v in kwargs.items():
            if k == 'api_key':
                print(f"  {k} = '{v[:15]}...' (len={len(v)})", flush=True)
            else:
                print(f"  {k} = {repr(v)}", flush=True)
        # Check internal vertexai detection
        import traceback
        traceback.print_stack(limit=10)
        super().__init__(**kwargs)

_genai_client.Client = _TracingClient

# Also patch in langchain_google_genai
import langchain_google_genai.chat_models as _lcg
_lcg.Client = _TracingClient

# Now test directly 
from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
print(f"\n=== Direct test ===")
resp = llm.invoke("Hello")
print(f"SUCCESS: {resp.content[:50]}")
