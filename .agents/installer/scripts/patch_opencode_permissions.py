#!/usr/bin/env python3
"""Patch OpenCode permissions to allow reading .env files.

Usage: python patch_opencode_permissions.py <opencode_config_path>

Ensures the OpenCode config has permission.read entries that allow
agents to access .env files without interactive prompts.
"""

import json
import sys
import os


def patch_permissions(config_path: str) -> None:
    # Load existing config or start fresh
    if os.path.isfile(config_path):
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {"$schema": "https://opencode.ai/config.json"}

    perm = config.get("permission")
    if perm is None:
        perm = {}
        config["permission"] = perm
    elif isinstance(perm, str):
        # e.g. "allow" — convert to dict, preserving intent
        config["permission"] = {"read": {"*": perm}}
        perm = config["permission"]
    elif not isinstance(perm, dict):
        perm = {}
        config["permission"] = perm

    # Ensure "read" sub-key is a dict with .env allowed
    read_perm = perm.get("read")
    if isinstance(read_perm, str):
        perm["read"] = {"*": read_perm}
        read_perm = perm["read"]
    elif not isinstance(read_perm, dict):
        read_perm = {}
        perm["read"] = read_perm

    read_perm.setdefault("*", "allow")
    read_perm["*.env"] = "allow"
    read_perm["*.env.*"] = "allow"
    read_perm["*.env.example"] = "allow"

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print("    Permissions: read *.env -> allow")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <opencode_config_path>", file=sys.stderr)
        sys.exit(1)
    patch_permissions(sys.argv[1])
