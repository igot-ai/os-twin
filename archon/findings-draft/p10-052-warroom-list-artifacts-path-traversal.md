Phase: 10
Sequence: 052
Slug: warroom-list-artifacts-path-traversal
Verdict: VALID
Rationale: The list_artifacts MCP tool accepts an attacker-controlled room_dir and passes it to os.walk() without any containment check, enabling recursive directory enumeration of arbitrary filesystem locations.
Severity-Original: MEDIUM
PoC-Status: pending
Origin-Finding: security/findings-draft/p8-043-mcp-room-dir-path-traversal.md
Origin-Pattern: AP-043

## Summary

The `list_artifacts` MCP tool (`.agents/mcp/warroom-server.py:87-116`) accepts `room_dir` and constructs `artifacts_dir = os.path.join(room_dir, "artifacts")` then calls `os.walk(artifacts_dir)`. With no path containment check, an attacker who can invoke MCP tools (directly or via prompt injection) can point `room_dir` at any location where an `artifacts` subdirectory exists or can be created, and receive a full recursive listing of its contents including file names, sizes, and modification times. This is a structural read variant of the confirmed write primitive in p8-043.

## Location

- **Tool**: `.agents/mcp/warroom-server.py:87` -- `list_artifacts(room_dir)`
- **Path construction**: `.agents/mcp/warroom-server.py:98` -- `artifacts_dir = os.path.join(room_dir, "artifacts")`
- **Directory walk**: `.agents/mcp/warroom-server.py:103` -- `for root, _dirs, fnames in os.walk(artifacts_dir)`
- **Metadata leak**: `.agents/mcp/warroom-server.py:107-111` -- file path, size, modification time returned

## Attacker Control

Full control over `room_dir`. The function additionally calls `os.stat(full_path)` on each file — confirming file existence and leaking metadata (size, mtime) for any readable file under the traversed `artifacts/` subdirectory.

## Trust Boundary Crossed

MCP client (direct or via prompt-injected agent) to arbitrary filesystem read. The MCP server process runs with agent-level permissions.

## Impact

- Recursive enumeration of any directory tree named `artifacts` under the supplied path
- File metadata exfiltration (name, size, mtime) without file content being returned
- Combined with the write primitive (p8-043), attacker can: (1) create `<target_dir>/artifacts/` via `update_status` traversal, (2) enumerate it with `list_artifacts`
- Useful for recon: discovering deployment artifacts, build outputs, log files, config snapshots

## Evidence

1. `warroom-server.py:89` -- `room_dir: Annotated[str, Field(...)]` — no validation
2. `warroom-server.py:98` -- `artifacts_dir = os.path.join(room_dir, "artifacts")` — no realpath check
3. `warroom-server.py:103` -- `os.walk(artifacts_dir)` — full recursive walk
4. `warroom-server.py:107-111` -- path, size, mtime returned in JSON response
5. Same root cause as p8-043 `update_status`/`report_progress` — no containment at any layer

## Reproduction Steps

1. With MCP client access, invoke `list_artifacts`:
   ```json
   {"tool": "list_artifacts", "arguments": {"room_dir": "../../../../"}}
   ```
2. The function checks for `../../../../artifacts/` — if that path exists, it returns a full listing
3. To confirm traversal, first create the artifacts dir via `update_status` write primitive:
   ```json
   {"tool": "update_status", "arguments": {"room_dir": "../../../../tmp/probe", "status": "pending"}}
   ```
   Then: `mkdir /tmp/probe/artifacts && cp /etc/hosts /tmp/probe/artifacts/`
4. Invoke `list_artifacts` with `room_dir = "../../../../tmp/probe"` — observe `/etc/hosts` metadata returned
