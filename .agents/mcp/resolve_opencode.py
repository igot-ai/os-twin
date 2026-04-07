#!/usr/bin/env python3
"""Resolve MCP config placeholders and write opencode.json.

Shared resolution logic used by:
  - install.sh  (patch_mcp_config phase 3)
  - mcp-extension.sh  (cmd_sync_quiet + cmd_init_project compile)
  - sync-opencode-global.sh  (future — adds tools deny + per-role agent grants)

Usage:
  resolve_opencode.py <config_json> <output_dir> [--env-file <path>]

Rules:
  - command arrays:      resolve ALL {env:*} to literal paths
  - environment/headers: STRIP values containing {env:*} (secrets stay in parent env)
  - url strings:         resolve ALL {env:*} to literal values
  - bare python/python3: resolve to absolute path via shutil.which()
"""
import argparse
import json
import os
import re
import shutil
import sys


def load_env_file(env_path):
    """Load a .env file into a dict (key=value lines, strips quotes)."""
    env = {}
    if not env_path or not os.path.exists(env_path):
        return env
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def resolve_env_refs(text, env_all):
    """Replace {env:VAR} placeholders with values from env_all."""
    return re.sub(
        r'\{env:(\w+)\}',
        lambda m: env_all.get(m.group(1), m.group(0)),
        text,
    )


def resolve_mcp_servers(servers, env_all):
    """Resolve a dict of MCP server configs, returning cleaned configs.

    - command arrays: resolve {env:*} and bare python to absolute paths
    - environment/headers dicts: strip values containing {env:*}
    - url strings: resolve {env:*}
    """
    python_abs = shutil.which('python') or shutil.which('python3') or 'python'
    env_ref_pattern = re.compile(r'\{env:\w+\}')
    resolved = {}

    for name, cfg in servers.items():
        out = {}
        for key, val in cfg.items():
            if key == 'command' and isinstance(val, list):
                resolved_cmd = []
                for i, c in enumerate(val):
                    if isinstance(c, str):
                        c = resolve_env_refs(c, env_all)
                        if i == 0 and c in ('python', 'python3'):
                            c = python_abs
                    resolved_cmd.append(c)
                out[key] = resolved_cmd
            elif key in ('environment', 'headers') and isinstance(val, dict):
                cleaned = {
                    k: v for k, v in val.items()
                    if not (isinstance(v, str) and env_ref_pattern.search(v))
                }
                if cleaned:
                    out[key] = cleaned
            elif key == 'url' and isinstance(val, str):
                out[key] = resolve_env_refs(val, env_all)
            else:
                out[key] = val
        resolved[name] = out

    return resolved


def resolve_and_write(config_path, output_dir, env_file=None, merge=False):
    """Main entry point: load config, resolve, write opencode.json.

    Args:
        config_path: Path to MCP config.json source file.
        output_dir:  Directory to write opencode.json into.
        env_file:    Optional .env file for variable resolution.
        merge:       If True, only update the 'mcp' key in an existing
                     opencode.json, preserving user settings (theme, model,
                     keybinds, etc.). If the file doesn't exist, creates fresh.

    Returns the resolved MCP dict (useful for callers that need to add
    tools/agent blocks on top).
    """
    env_extra = load_env_file(env_file)
    env_all = {**os.environ, **env_extra}

    with open(config_path) as f:
        config = json.load(f)
    servers = config.get('mcp', config.get('mcpServers', {}))

    resolved_mcp = resolve_mcp_servers(servers, env_all)

    os.makedirs(output_dir, exist_ok=True)
    opencode_file = os.path.join(output_dir, 'opencode.json')

    if merge and os.path.exists(opencode_file):
        # Merge: preserve existing user settings, only replace managed keys
        with open(opencode_file) as f:
            try:
                existing = json.load(f)
            except (json.JSONDecodeError, ValueError):
                existing = {}
        existing["$schema"] = "https://opencode.ai/config.json"
        existing["mcp"] = resolved_mcp
        opencode_config = existing
    else:
        opencode_config = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": resolved_mcp,
        }

    with open(opencode_file, 'w') as f:
        json.dump(opencode_config, f, indent=2)
        f.write('\n')

    # Warn about unresolved refs in command arrays
    env_ref_pattern = re.compile(r'\{env:\w+\}')
    unresolved = []
    for name, cfg in resolved_mcp.items():
        for c in cfg.get('command', []):
            if isinstance(c, str) and env_ref_pattern.search(c):
                unresolved.append(c)
    if unresolved:
        print(
            f"  Warning: unresolved in commands (set these vars): "
            f"{', '.join(sorted(set(unresolved)))}",
            file=sys.stderr,
        )

    print(f"  Generated {opencode_file}")
    return resolved_mcp


def main():
    parser = argparse.ArgumentParser(
        description='Resolve MCP config placeholders and write opencode.json'
    )
    parser.add_argument('config', help='Path to MCP config.json')
    parser.add_argument('output_dir', help='Directory for opencode.json output')
    parser.add_argument(
        '--env-file', default=None,
        help='Path to .env or .env.mcp file for variable resolution',
    )
    parser.add_argument(
        '--merge', action='store_true', default=False,
        help='Merge into existing opencode.json (only update mcp key, '
             'preserve user settings like theme/model/keybinds)',
    )
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"Error: config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    resolve_and_write(args.config, args.output_dir, args.env_file, args.merge)


if __name__ == '__main__':
    main()
