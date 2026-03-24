#!/usr/bin/env python3
"""
memory-server.py — MCP server for OS Twin agent memory operations.

Provides tools for agents to:
  - Append notes to working memory
  - Remove notes from working memory
  - Recall facts from the knowledge base

Transport: stdio (invoked via deepagents --mcp-config)
"""

import json
import os
from datetime import datetime, timezone
from typing import Annotated

import yaml
from pydantic import Field
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agent-os-memory")

MEMORY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "memory",
)


def _working_path(role: str) -> str:
    safe_role = os.path.basename(role)
    return os.path.join(MEMORY_DIR, "working", f"{safe_role}.yml")


def _read_working(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _write_working(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


@mcp.tool()
def memory_note(
    note: Annotated[str, Field(description="The note to append to working memory")],
    domains: Annotated[
        list[str] | None,
        Field(description="Optional domain tags for the note", default=None),
    ] = None,
) -> str:
    """Append a note to the agent's working memory file.

    Uses AGENT_OS_ROLE env var to determine which working memory file to write to.
    Creates the file if it doesn't exist.
    Returns the appended note entry as JSON.
    """
    role = os.environ.get("AGENT_OS_ROLE", "default")
    room_dir = os.environ.get("AGENT_OS_ROOM_DIR", "")
    room_id = os.path.basename(room_dir) if room_dir else "unknown"

    path = _working_path(role)
    data = _read_working(path)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if "notes" not in data:
        data["role"] = role
        data["room_id"] = room_id
        data["notes"] = []

    data["updated_at"] = ts

    entry = {"note": note, "domains": domains or [], "timestamp": ts}
    data["notes"].append(entry)

    _write_working(path, data)

    return json.dumps(entry)


@mcp.tool()
def memory_drop(
    note_substring: Annotated[
        str,
        Field(description="Substring to match against note text — matching notes will be removed"),
    ],
) -> str:
    """Remove notes from working memory where the note text contains the given substring.

    Returns the removed notes as JSON, or "no match" if nothing matched.
    """
    if not note_substring or not note_substring.strip():
        return "error: note_substring must be non-empty"

    role = os.environ.get("AGENT_OS_ROLE", "default")
    path = _working_path(role)
    data = _read_working(path)

    if not data.get("notes"):
        return "no match"

    removed = []
    remaining = []
    for entry in data["notes"]:
        if note_substring in entry.get("note", ""):
            removed.append(entry)
        else:
            remaining.append(entry)

    if not removed:
        return "no match"

    data["notes"] = remaining
    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_working(path, data)

    return json.dumps(removed)


@mcp.tool()
def memory_recall(
    domains: Annotated[
        list[str] | None,
        Field(description="Domain tags to filter by (matches any overlap)", default=None),
    ] = None,
    keyword: Annotated[
        str | None,
        Field(description="Substring to search for in fact text", default=None),
    ] = None,
) -> str:
    """Query the knowledge base for matching facts.

    Searches .agents/memory/knowledge/*.yml files.
    Matches by domain tag overlap OR keyword substring in the fact field.
    Results are sorted by confidence * access_count (descending).
    Returns matching facts as a JSON array.
    """
    knowledge_dir = os.path.join(MEMORY_DIR, "knowledge")
    if not os.path.exists(knowledge_dir):
        return "[]"

    results = []
    domain_set = set(domains) if domains else set()

    for fname in os.listdir(knowledge_dir):
        if not fname.endswith(".yml"):
            continue

        fpath = os.path.join(knowledge_dir, fname)
        with open(fpath) as f:
            fact_data = yaml.safe_load(f)

        if not fact_data or "fact" not in fact_data:
            continue

        matched = False
        if not domain_set and not keyword:
            matched = True
        if domain_set and set(fact_data.get("domains", [])) & domain_set:
            matched = True
        if keyword and keyword.lower() in fact_data.get("fact", "").lower():
            matched = True

        if not matched:
            continue

        confidence = fact_data.get("confidence", 0.5)
        access_count = fact_data.get("access_count", 1)
        fact_data["_score"] = confidence * access_count
        results.append(fact_data)

    results.sort(key=lambda x: x.get("_score", 0), reverse=True)

    return json.dumps(
        [{k: v for k, v in r.items() if k != "_score"} for r in results]
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
