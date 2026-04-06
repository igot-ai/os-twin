#!/bin/bash
# Monkey-patch deepagents-cli to fix MCP ClosedResourceError bug
# Reference: https://github.com/langchain-ai/deepagents/pull/2228
#
# Usage: bash patch-deepagents-mcp.sh
# Re-run after: uv tool upgrade deepagents-cli

set -e

# Find the deepagents-cli package directory
SITE_PACKAGES=""
for candidate in \
  "$HOME/.local/share/uv/tools/deepagents-cli/lib/python3.*/site-packages/deepagents_cli" \
  "$HOME/.local/share/uv/tools/deepagents-cli/lib/python3/site-packages/deepagents_cli"; do
  # Use glob expansion
  for dir in $candidate; do
    if [[ -d "$dir" ]]; then
      SITE_PACKAGES="$dir"
      break 2
    fi
  done
done

if [[ -z "$SITE_PACKAGES" ]]; then
  echo "ERROR: Could not find deepagents_cli package directory"
  echo "Searched: ~/.local/share/uv/tools/deepagents-cli/lib/python3.*/site-packages/deepagents_cli"
  exit 1
fi

echo "Found deepagents_cli at: $SITE_PACKAGES"

SERVER_GRAPH="$SITE_PACKAGES/server_graph.py"
MCP_TOOLS="$SITE_PACKAGES/mcp_tools.py"

# Verify files exist
if [[ ! -f "$SERVER_GRAPH" ]]; then
  echo "ERROR: $SERVER_GRAPH not found"
  exit 1
fi
if [[ ! -f "$MCP_TOOLS" ]]; then
  echo "ERROR: $MCP_TOOLS not found"
  exit 1
fi

# Check if already patched
if grep -q "stateless=True" "$SERVER_GRAPH" 2>/dev/null; then
  echo "Already patched (server_graph.py has stateless=True)"
  exit 0
fi

echo "Patching server_graph.py..."

# Patch 1: server_graph.py — add stateless=True to resolve_and_load_mcp_tools call
python3 - "$SERVER_GRAPH" <<'PYEOF'
import sys

path = sys.argv[1]
with open(path) as f:
    content = f.read()

old = """                resolve_and_load_mcp_tools(
                    explicit_config_path=config.mcp_config_path,
                    no_mcp=config.no_mcp,
                    trust_project_mcp=config.trust_project_mcp,
                    project_context=project_context,
                )"""

new = """                resolve_and_load_mcp_tools(
                    explicit_config_path=config.mcp_config_path,
                    no_mcp=config.no_mcp,
                    trust_project_mcp=config.trust_project_mcp,
                    project_context=project_context,
                    stateless=True,
                )"""

if old not in content:
    print(f"WARNING: Could not find expected code block in {path}")
    print("The file may have been updated. Manual patching required.")
    sys.exit(1)

content = content.replace(old, new)
with open(path, 'w') as f:
    f.write(content)
print(f"  ✓ Patched {path}")
PYEOF

echo "Patching mcp_tools.py..."

# Patch 2: mcp_tools.py — add stateless parameter and per-call session branch
python3 - "$MCP_TOOLS" <<'PYEOF'
import sys

path = sys.argv[1]
with open(path) as f:
    content = f.read()

errors = []

# Patch 2a: Add stateless param to _load_tools_from_config
old_sig = """async def _load_tools_from_config(
    config: dict[str, Any],
) -> tuple[list[BaseTool], MCPSessionManager, list[MCPServerInfo]]:"""

new_sig = """async def _load_tools_from_config(
    config: dict[str, Any],
    *,
    stateless: bool = False,
) -> tuple[list[BaseTool], MCPSessionManager, list[MCPServerInfo]]:"""

if old_sig in content:
    content = content.replace(old_sig, new_sig)
    print("  ✓ Added stateless param to _load_tools_from_config")
else:
    if "stateless: bool = False" not in content.split("_load_tools_from_config")[1][:200]:
        errors.append("Could not find _load_tools_from_config signature to patch")

# Patch 2b: Add stateless branch in tool loading loop
old_loop = """            session = await manager.exit_stack.enter_async_context(
                client.session(server_name)
            )
            tools = await load_mcp_tools(
                session, server_name=server_name, tool_name_prefix=True
            )"""

new_loop = """            if stateless:
                tools = await load_mcp_tools(
                    None,
                    connection=connections[server_name],
                    server_name=server_name,
                    tool_name_prefix=True,
                )
            else:
                session = await manager.exit_stack.enter_async_context(
                    client.session(server_name)
                )
                tools = await load_mcp_tools(
                    session, server_name=server_name, tool_name_prefix=True
                )"""

if old_loop in content:
    content = content.replace(old_loop, new_loop)
    print("  ✓ Added stateless branch in tool loading loop")
else:
    if "if stateless:" not in content:
        errors.append("Could not find tool loading loop to patch")

# Patch 2c: Add stateless param to resolve_and_load_mcp_tools
old_resolve = """    project_context: ProjectContext | None = None,
) -> tuple[list[BaseTool], MCPSessionManager | None, list[MCPServerInfo]]:"""

new_resolve = """    project_context: ProjectContext | None = None,
    stateless: bool = False,
) -> tuple[list[BaseTool], MCPSessionManager | None, list[MCPServerInfo]]:"""

if old_resolve in content:
    content = content.replace(old_resolve, new_resolve)
    print("  ✓ Added stateless param to resolve_and_load_mcp_tools")
else:
    if "stateless: bool = False" not in content.split("resolve_and_load_mcp_tools")[1][:300]:
        errors.append("Could not find resolve_and_load_mcp_tools signature to patch")

# Patch 2d: Pass stateless through to _load_tools_from_config
old_return = "    return await _load_tools_from_config(merged)"
new_return = "    return await _load_tools_from_config(merged, stateless=stateless)"

if old_return in content:
    content = content.replace(old_return, new_return)
    print("  ✓ Pass stateless through to _load_tools_from_config")
else:
    if "stateless=stateless" not in content:
        errors.append("Could not find _load_tools_from_config(merged) return to patch")

if errors:
    for e in errors:
        print(f"  ✗ {e}")
    print("\nThe file may already be patched or have been updated.")
    print("Check manually if needed.")
    sys.exit(1)

with open(path, 'w') as f:
    f.write(content)
print(f"  ✓ Patched {path}")
PYEOF

echo ""
echo "Done! deepagents-cli MCP is now patched."
echo "MCP tools will use per-call sessions in server mode (stateless=True)."
echo ""
echo "NOTE: Re-run this script after upgrading deepagents-cli:"
echo "  uv tool upgrade deepagents-cli && bash $0"
