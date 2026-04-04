#!/usr/bin/env python3
"""Debug: Check what ChatGoogleGenerativeAI resolves to inside the server env."""
import os

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

print(f"GOOGLE_API_KEY: {os.environ.get('GOOGLE_API_KEY','')[:15]}...")
print(f"GOOGLE_CLOUD_PROJECT: {os.environ.get('GOOGLE_CLOUD_PROJECT')}")

# Now trace what happens inside init_chat_model
from langchain_google_genai import ChatGoogleGenerativeAI

# Direct instantiation
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")  
print(f"\nDirect instantiation:")
print(f"  vertexai: {llm.vertexai}")
print(f"  _use_vertexai: {llm._use_vertexai}")
print(f"  project: {llm.project}")
print(f"  credentials: {llm.credentials}")
print(f"  google_api_key: {repr(llm.google_api_key)[:30]}...")

# Check via init_chat_model (same as deepagents)
from langchain.chat_models import init_chat_model
llm2 = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
print(f"\ninit_chat_model:")
print(f"  vertexai: {llm2.vertexai}")
print(f"  _use_vertexai: {llm2._use_vertexai}")
print(f"  project: {llm2.project}")
print(f"  google_api_key: {repr(llm2.google_api_key)[:30]}...")

# Try invoke
print(f"\nTesting invoke...")
resp = llm2.invoke("Say hello in one word")
print(f"SUCCESS: {resp.content[:50]}")
