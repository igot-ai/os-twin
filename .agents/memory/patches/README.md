# deepagents-cli MCP Monkey-Patch

## Problem

deepagents-cli v0.0.34 cannot execute MCP tool calls. The `server_graph.py` uses `asyncio.run()` to load MCP tools, which creates a temporary event loop. Any MCP session (stdio/SSE) opened inside that loop dies when `asyncio.run()` exits. Every subsequent tool call fails with `ClosedResourceError`.

Reference PR: https://github.com/langchain-ai/deepagents/pull/2228

## What the patch changes

### File 1: `deepagents_cli/server_graph.py`

Adds `stateless=True` to the `resolve_and_load_mcp_tools()` call so that tool discovery uses a short-lived session, and each tool invocation creates its own fresh session.

```diff
-            mcp_tools, _, mcp_server_info = asyncio.run(
-                resolve_and_load_mcp_tools(
-                    explicit_config_path=config.mcp_config_path,
-                    no_mcp=config.no_mcp,
-                    trust_project_mcp=config.trust_project_mcp,
-                    project_context=project_context,
-                )
-            )
+            mcp_tools, _, mcp_server_info = asyncio.run(
+                resolve_and_load_mcp_tools(
+                    explicit_config_path=config.mcp_config_path,
+                    no_mcp=config.no_mcp,
+                    trust_project_mcp=config.trust_project_mcp,
+                    project_context=project_context,
+                    stateless=True,
+                )
+            )
```

### File 2: `deepagents_cli/mcp_tools.py`

Three changes:

**Change 1**: Add `stateless` parameter to `_load_tools_from_config`:

```diff
 async def _load_tools_from_config(
     config: dict[str, Any],
+    *,
+    stateless: bool = False,
 ) -> tuple[list[BaseTool], MCPSessionManager, list[MCPServerInfo]]:
```

**Change 2**: In the tool loading loop, branch on `stateless`:

```diff
         for server_name, server_config in config["mcpServers"].items():
-            session = await manager.exit_stack.enter_async_context(
-                client.session(server_name)
-            )
-            tools = await load_mcp_tools(
-                session, server_name=server_name, tool_name_prefix=True
-            )
+            if stateless:
+                tools = await load_mcp_tools(
+                    None,
+                    connection=connections[server_name],
+                    server_name=server_name,
+                    tool_name_prefix=True,
+                )
+            else:
+                session = await manager.exit_stack.enter_async_context(
+                    client.session(server_name)
+                )
+                tools = await load_mcp_tools(
+                    session, server_name=server_name, tool_name_prefix=True
+                )
```

**Change 3**: Add `stateless` parameter to `resolve_and_load_mcp_tools` and pass it through:

```diff
 async def resolve_and_load_mcp_tools(
     *,
     explicit_config_path: str | None = None,
     no_mcp: bool = False,
     trust_project_mcp: bool | None = None,
     project_context: ProjectContext | None = None,
+    stateless: bool = False,
 ) -> tuple[list[BaseTool], MCPSessionManager | None, list[MCPServerInfo]]:
```

```diff
-    return await _load_tools_from_config(merged)
+    return await _load_tools_from_config(merged, stateless=stateless)
```

## How it works

- `stateless=False` (default): persistent session, used by CLI interactive mode and ACP — session stays alive for the whole conversation
- `stateless=True`: each tool call opens its own fresh session — used by `server_graph.py` where `asyncio.run()` destroys the event loop after tool discovery

## Requirements

- `langchain-mcp-adapters` must support `connection=` parameter in `load_mcp_tools()` (verified in the version bundled with deepagents-cli 0.0.34)

## Will this break on upgrade?

Yes — upgrading deepagents-cli (`uv tool upgrade deepagents-cli`) will overwrite the patched files. Re-run the patch script after upgrading. If the upstream PR #2228 is merged, the patch becomes unnecessary.
