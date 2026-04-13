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
        with open(config_path) as f:
            config = json.load(f)
    else:
        config = {"$schema": "https://opencode.ai/config.json"}

    # Ensure "permission" key exists as a dict
    read_perm = {
        "*": "allow",
        "*.env": "allow",
        "*.env.*": "allow",
        "*.env.example": "allow",
    }
    perm = config.get("permission")
    if perm is None:
        config["permission"] = {}
        config["permission"] = read_perm
    if isinstance(perm, str):
        # e.g. "allow" — convert to dict, preserving intent
        config["permission"] = {"*": perm}
        perm = config["permission"]
    elif not isinstance(perm, dict):
        config["permission"] = {}
        perm = config["permission"]

    # Ensure "read" sub-key is a dict with .env allowed
    read_perm = perm.get("read") if isinstance(perm, dict) else None
    if isinstance(perm, dict):
        if isinstance(read_perm, str):
            perm["read"] = {
                "*": read_perm,
                "*.env": "allow",
                "*.env.*": "allow",
                "*.env.example": "allow",
            }
        elif isinstance(read_perm, dict):
            read_perm.setdefault("*", "allow")
            read_perm["*.env"] = "allow"
            read_perm["*.env.*"] = "allow"
            read_perm["*.env.example"] = "allow"
        else:
            perm["read"] = {
                "*": "allow",
                "*.env": "allow",
                "*.env.*": "allow",
                "*.env.example": "allow",
            }

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print("    Permissions: read *.env → allow")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <opencode_config_path>", file=sys.stderr)
        sys.exit(1)
    patch_permissions(sys.argv[1])
