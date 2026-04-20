
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

os.environ["OSTWIN_KNOWLEDGE_DIR"] = "/tmp/test-curator-probe"
os.environ["OSTWIN_MCP_ACTOR"] = "knowledge-curator"

from dashboard.knowledge.mcp_server import knowledge_delete_namespace, knowledge_restore_namespace

# 1. Try delete without confirm
print("--- Test: Delete without confirm ---")
res1 = knowledge_delete_namespace("test-ns")
print(f"Result: {res1}")

# 2. Try delete with confirm
print("\n--- Test: Delete with confirm ---")
res2 = knowledge_delete_namespace("test-ns", confirm=True)
print(f"Result: {res2}")

# 3. Try restore with overwrite=True without confirm
print("\n--- Test: Restore overwrite without confirm ---")
res3 = knowledge_restore_namespace("/tmp/fake.tar.zst", overwrite=True)
print(f"Result: {res3}")

# 4. Try restore with overwrite=True with confirm
print("\n--- Test: Restore overwrite with confirm ---")
# This will fail with FILE_NOT_FOUND but should pass the gate
res4 = knowledge_restore_namespace("/tmp/fake.tar.zst", overwrite=True, confirm=True)
print(f"Result: {res4}")
