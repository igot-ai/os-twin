with open("/mnt/e/OS Twin/os-twin/.agents/mcp/memory-core.py", "a") as f1:
    with open("/mnt/e/OS Twin/os-twin/.agents/mcp/knowledge_patch.py", "r") as f2:
        f1.write("\n")
        f1.write(f2.read())
