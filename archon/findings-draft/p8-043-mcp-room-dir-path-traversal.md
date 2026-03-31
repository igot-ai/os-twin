Phase: 8
Sequence: 043
Slug: mcp-room-dir-path-traversal
Verdict: VALID
Rationale: Complete absence of path validation on room_dir enables arbitrary file creation/write across the filesystem; the chaining potential with prompt injection makes this remotely triggerable, and the impact (arbitrary file write) is severe.
Severity-Original: HIGH
PoC-Status: executed
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-C/debate.md

## Summary

The `room_dir` parameter in MCP tool calls (`update_status`, `report_progress` in warroom-server.py; `post_message` in channel-server.py) is used directly in `os.makedirs()` and `open()` calls with no path validation. An attacker who can invoke MCP tools (directly as a configured client, or indirectly via prompt injection of an agent) can create arbitrary directories and write files anywhere the MCP server process has permissions. Path traversal sequences (e.g., `../../../../etc/cron.d`) are not detected or blocked.

## Location

- `.agents/mcp/warroom-server.py:61` -- `os.makedirs(room_dir, exist_ok=True)`
- `.agents/mcp/warroom-server.py:71-82` -- File writes to `status`, `state_changed_at`, `audit.log` under room_dir
- `.agents/mcp/warroom-server.py:130-131` -- `report_progress()`: makedirs + write `progress.json` with attacker-controlled `message`
- `.agents/mcp/channel-server.py:78-79` -- `post_message()`: makedirs + write `channel.jsonl` with attacker-controlled `body`

## Attacker Control

Full control over `room_dir` path string. For `report_progress`, the `message` field content is also attacker-controlled and written to the file. For `post_message`, the `body` field is attacker-controlled. The `update_status` function writes a value from the status allowlist, but the file PATH is attacker-controlled.

## Trust Boundary Crossed

MCP client (potentially compromised agent via prompt injection) -> arbitrary filesystem locations. The MCP server trusts its client to provide valid room directories, but no containment is enforced.

## Impact

- Arbitrary directory creation via `os.makedirs(room_dir, exist_ok=True)`
- Arbitrary file write to `status`, `state_changed_at`, `audit.log`, `progress.json`, `channel.jsonl` under the traversed path
- File content partially controlled: `progress.json` message field and `channel.jsonl` body field are free-form
- Potential for: cron job injection, SSH authorized_keys manipulation, config file overwrite, depending on process permissions
- Chaining: prompt injection (p8-040, p8-041) -> agent executes MCP tool with malicious room_dir -> arbitrary file write

## Evidence

1. `warroom-server.py:43` -- `room_dir: Annotated[str, Field(...)]` -- no path validation
2. `warroom-server.py:61` -- `os.makedirs(room_dir, exist_ok=True)` -- no realpath check
3. `warroom-server.py:71` -- `open(os.path.join(room_dir, "status"), "w")` -- direct path join
4. `channel-server.py:78` -- `os.makedirs(room_dir, exist_ok=True)` -- same pattern
5. No `os.path.realpath()`, no prefix containment, no path validation anywhere in either file

## Reproduction Steps

1. With MCP client access (or via a prompt-injected agent), invoke `update_status`:
   ```json
   {"tool": "update_status", "arguments": {"room_dir": "../../../../tmp/path-traversal-test", "status": "pending"}}
   ```
2. Verify: `ls -la /tmp/path-traversal-test/` shows created directory with `status`, `state_changed_at`, and `audit.log` files
3. For file content control, invoke `report_progress`:
   ```json
   {"tool": "report_progress", "arguments": {"room_dir": "../../../../tmp/path-traversal-test", "percent": 50, "message": "ATTACKER-CONTROLLED-CONTENT"}}
   ```
4. Verify: `cat /tmp/path-traversal-test/progress.json` contains the attacker's message

## Cold Verification

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Independent code trace confirms zero path validation on room_dir in 3 MCP tool functions; reproduction succeeded with both absolute paths and relative traversal, writing attacker-influenced content to arbitrary filesystem locations.
Severity-Final: HIGH
PoC-Status: executed
```

### Verification Summary

Independent cold verification confirms this finding. The code path was traced from entry point to sink across all three affected functions (`update_status`, `report_progress`, `post_message`). No path validation, sanitization, or containment exists at any layer (language, framework, middleware, or application).

Reproduction was executed successfully in three variants:
1. Absolute path to /tmp via `update_status` -- created `status`, `state_changed_at`, `audit.log` with expected content
2. Relative traversal (`../../../../../tmp/...`) via `update_status` -- created files at traversed location
3. Manual code-equivalent test of `post_message` pattern -- created `channel.jsonl` with attacker-controlled body

The defense brief notes valid mitigating factors (fixed file names, JSON-wrapped content, MCP client access prerequisite) but none constitute a blocking protection. The severity of HIGH is appropriate given the arbitrary file write primitive with partially controlled content, triggerable via the documented prompt injection attack surface.

Full review: `security/adversarial-reviews/mcp-room-dir-path-traversal-review.md`
Evidence: `security/real-env-evidence/mcp-room-dir-path-traversal/reproduction-log.md`
