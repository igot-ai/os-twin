import os
import sys
import json
import shutil

# Mocking AGENT_OS_ROOT to a temp directory
temp_root = "/tmp/test_knowledge_epic"
if os.path.exists(temp_root):
    shutil.rmtree(temp_root)
os.makedirs(os.path.join(temp_root, ".agents"))
os.environ["AGENT_OS_ROOT"] = temp_root

# Add mcp/ to path
mcp_path = "/mnt/e/OS Twin/os-twin/.agents/mcp"
sys.path.append(mcp_path)

import importlib.util
_core_path = os.path.join(mcp_path, "memory-core.py")
_spec = importlib.util.spec_from_file_location("memory_core", _core_path)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)

# Test knowledge_add
res1 = core.knowledge_add("Authentication flow description", "room:test", ["auth", "docs"])
print(f"res1: {res1}")

res2 = core.knowledge_add("Database schema for users", "room:test", ["db", "schema"])
print(f"res2: {res2}")

# Test knowledge_list
lst = json.loads(core.knowledge_list())
print(f"List count: {len(lst)}")

# Test knowledge_search (Hybrid)
search_res = json.loads(core.knowledge_search("authentication"))
print(f"Search 'authentication' count: {len(search_res)}")
if len(search_res) > 0:
    print(f"Search top: {search_res[0]['id']} - {search_res[0]['summary']}")

# Test distill (mock)
# Create a dummy ledger entry
ledger_path = core._ledger_path()
os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
with open(ledger_path, "w") as f:
    f.write(json.dumps({"id": "mem-1", "ts": "2024-01-01T00:00:00Z", "kind": "artifact", "room_id": "room-001", "summary": "Did some work", "ref": "TASK-001"}) + "\n")

distill_res = json.loads(core.distill(room_id="room-001"))
print(f"Distill res: {distill_res}")

# Check knowledge list again
lst2 = json.loads(core.knowledge_list())
print(f"List count after distill: {len(lst2)}")
