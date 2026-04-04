#!/usr/bin/env python3
"""Test langchain-google-genai directly to isolate the deepagents error."""
import os
import sys

# Read the API key from .ostwin/.env directly  
env_path = os.path.expanduser("~/.ostwin/.env")
key = ""
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("GOOGLE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if not key:
    # Try project .env
    project_env = "/mnt/e/OS Twin/os-twin/.env"
    if os.path.exists(project_env):
        with open(project_env) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GOOGLE_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

print(f"API Key length: {len(key)}")
print(f"API Key prefix: {key[:15]}..." if key else "NO KEY FOUND")

if not key:
    print("ERROR: No GOOGLE_API_KEY found in either env file")
    sys.exit(1)

os.environ["GOOGLE_API_KEY"] = key

# Test 1: Direct langchain-google-genai
print("\n=== Test 1: Direct ChatGoogleGenerativeAI (gemini-2.5-flash) ===")
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    resp = llm.invoke("Say hello in one word")
    print(f"SUCCESS: {resp.content[:100]}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")

# Test 2: With gemini-3.1-pro-preview
print("\n=== Test 2: gemini-3.1-pro-preview ===")
try:
    llm2 = ChatGoogleGenerativeAI(model="gemini-3.1-pro-preview")
    resp2 = llm2.invoke("Say hello in one word")
    print(f"SUCCESS: {resp2.content[:100]}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
