# H8 — MCP room_dir Path Traversal

| Field | Value |
|---|---|
| ID | H8 |
| Severity | HIGH |
| CWE | CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal') |
| Phase | 8 |
| Draft | security/findings-draft/p8-043-mcp-room-dir-path-traversal.md |
| PoC-Status | executed |
| Affected Files | .agents/mcp/warroom-server.py:61, 130-131; .agents/mcp/channel-server.py:78-79 |

## Description

Three MCP tool functions accept a `room_dir` string parameter and use it directly in `os.makedirs()` and `open()` calls with no path validation:

```python
# warroom-server.py:61 — update_status
os.makedirs(room_dir, exist_ok=True)
open(os.path.join(room_dir, "status"), "w")       # attacker-controlled path

# warroom-server.py:130-131 — report_progress
os.makedirs(room_dir, exist_ok=True)
open(os.path.join(room_dir, "progress.json"), "w") # attacker-controlled path + content

# channel-server.py:78-79 — post_message
os.makedirs(room_dir, exist_ok=True)
open(os.path.join(room_dir, "channel.jsonl"), "a") # attacker-controlled path + content
```

No `os.path.realpath()` check, no prefix containment (`is_relative_to`), no input validation anywhere in either file. An attacker who can invoke MCP tools — directly as a configured MCP client, or indirectly by injecting an agent's prompt via H6/H7 — can create directories and write files anywhere the MCP server process has permissions.

## Attacker Starting Position

MCP client access (configured agent environment) or indirect access via prompt injection of an agent that uses the warroom/channel MCP servers.

## Impact

- Arbitrary directory creation anywhere on the filesystem
- Arbitrary file write to fixed filenames (`status`, `state_changed_at`, `audit.log`, `progress.json`, `channel.jsonl`) under the traversed path
- Partially controlled file content: `progress.json` message field and `channel.jsonl` body field are free-form attacker input
- High-impact targets: `~/.ssh/authorized_keys` (via channel.jsonl body), `/etc/cron.d/` (cron job injection), config file overwrite, SSH host key replacement
- Chain: H6/H7 (prompt injection) → agent invokes MCP tool with malicious room_dir → arbitrary file write

## Reproduction Steps

1. With MCP client access, invoke `update_status` with a traversal path:
   ```json
   {"tool": "update_status", "arguments": {"room_dir": "../../../../tmp/traversal-test", "status": "pending"}}
   ```
2. Verify: `ls -la /tmp/traversal-test/` shows `status`, `state_changed_at`, `audit.log`.
3. Invoke `report_progress` with attacker-controlled message:
   ```json
   {"tool": "report_progress", "arguments": {"room_dir": "../../../../tmp/traversal-test", "percent": 50, "message": "ATTACKER_CONTROLLED"}}
   ```
4. Verify: `cat /tmp/traversal-test/progress.json` contains the attacker message.
5. Python direct reproduction (no MCP framework):
   ```
   python security/findings/H8-mcp-room-dir-path-traversal/poc.py
   ```

## Evidence

- `warroom-server.py:43`: `room_dir: Annotated[str, Field(...)]` — no path validation in the field definition
- `warroom-server.py:61`: `os.makedirs(room_dir, exist_ok=True)` — no realpath normalization
- Cold verification: reproduction succeeded with both absolute paths and relative traversal — files created at traversed locations with expected content
- `channel-server.py:78`: identical vulnerable pattern in the channel server

## Remediation

1. Add path containment to all three functions:
   ```python
   import os

   ROOMS_BASE = os.path.realpath("/path/to/warrooms")

   def _safe_room_dir(room_dir: str) -> str:
       resolved = os.path.realpath(room_dir)
       if not resolved.startswith(ROOMS_BASE + os.sep):
           raise ValueError(f"room_dir outside allowed base: {room_dir!r}")
       return resolved
   ```
2. Call `_safe_room_dir(room_dir)` at the top of `update_status`, `report_progress`, and `post_message` before any file I/O.
3. Add a test that provides a traversal path and asserts `ValueError` is raised.
4. Harden the prompt injection surface (H6, H7) to reduce the likelihood of agents being manipulated into supplying malicious `room_dir` values.
