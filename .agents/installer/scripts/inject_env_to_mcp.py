#!/usr/bin/env python3
"""Inject .env variables into MCP server environment blocks.

Usage: python inject_env_to_mcp.py <mcp_config_path> <env_file_path>

Reads all KEY=VALUE pairs from the .env file and injects them into
each MCP server's "environment" block where they are referenced
(via ${VAR} or {env:VAR} patterns), or where they resolve existing
placeholder values.
"""

import json
import re
import sys


def inject_env(mcp_path: str, env_path: str) -> None:
    # Parse .env file into a dict
    env_vars = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            # Strip surrounding quotes
            val = val.strip().strip('"').strip("'")
            if key:
                env_vars[key] = val

    if not env_vars:
        sys.exit(0)

    # Read and patch MCP config
    with open(mcp_path) as f:
        config = json.load(f)

    # Support both OpenCode 'mcp' and legacy 'mcpServers' keys
    servers = config.get("mcp", config.get("mcpServers", {}))
    for name, server in servers.items():
        # Remote servers: resolve {env:*} in headers, skip environment injection
        if server.get("type") == "remote":
            hdrs = server.get("headers", {})
            for k, v in list(hdrs.items()):
                if isinstance(v, str) and "{env:" in v:
                    for env_k, env_v in env_vars.items():
                        v = v.replace("{env:" + env_k + "}", env_v)
                    hdrs[k] = v
            continue
        # Support both 'environment' (OpenCode) and 'env' (legacy)
        env_key = (
            "environment"
            if "environment" in server
            else "env" if "env" in server else "environment"
        )
        if env_key not in server:
            server[env_key] = {}
        # Find ${VAR} or {env:VAR} references in this server's config
        server_str = json.dumps(server)
        server_refs = set(re.findall(r"\$\{(\w+)(?:[:-][^}]*)?\}", server_str))
        server_refs |= set(re.findall(r"\{env:(\w+)\}", server_str))
        # Only inject vars that this server references, or resolve existing placeholder env values
        for k, v in env_vars.items():
            if k in server[env_key]:
                cur = server[env_key][k]
                if isinstance(cur, str) and ("${" in cur or "{env:" in cur) and v:
                    server[env_key][k] = v
            elif k in server_refs and v:
                server[env_key][k] = v

    with open(mcp_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print(f"    Injected {len(env_vars)} env var(s) into {len(servers)} MCP server(s)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} <mcp_config_path> <env_file_path>", file=sys.stderr
        )
        sys.exit(1)
    inject_env(sys.argv[1], sys.argv[2])
