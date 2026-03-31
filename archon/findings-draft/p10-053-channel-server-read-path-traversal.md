Phase: 10
Sequence: 053
Slug: channel-server-read-path-traversal
Verdict: VALID
Rationale: The read_messages and get_latest MCP tools in channel-server.py use attacker-controlled room_dir in open() calls with no containment check, enabling arbitrary file reads from any location accessible to the MCP server process.
Severity-Original: HIGH
PoC-Status: pending
Origin-Finding: security/findings-draft/p8-043-mcp-room-dir-path-traversal.md
Origin-Pattern: AP-043

## Summary

The `read_messages` tool (`.agents/mcp/channel-server.py:105-165`) and `get_latest` tool (`.agents/mcp/channel-server.py:168-197`) both accept `room_dir` and open `os.path.join(room_dir, "channel.jsonl")` for reading. With no path containment check, an attacker can point `room_dir` at any directory containing a file named `channel.jsonl`, reading its full contents. More critically, if an attacker has previously written attacker-controlled content to `channel.jsonl` at an arbitrary path (using the `post_message` write primitive confirmed in p8-043), they can read it back — closing the full read/write loop. This also enables reading any file named `channel.jsonl` anywhere on the filesystem.

## Location

- **Tool 1**: `.agents/mcp/channel-server.py:105` -- `read_messages(room_dir, ...)`
- **Path construction**: `.agents/mcp/channel-server.py:136` -- `channel_file = os.path.join(room_dir, "channel.jsonl")`
- **File read**: `.agents/mcp/channel-server.py:142` -- `with open(channel_file, "r") as f`
- **Tool 2**: `.agents/mcp/channel-server.py:168` -- `get_latest(room_dir, msg_type)`
- **Path construction**: `.agents/mcp/channel-server.py:179` -- `channel_file = os.path.join(room_dir, "channel.jsonl")`
- **File read**: `.agents/mcp/channel-server.py:185` -- `with open(channel_file, "r") as f`

## Attacker Control

Full control over `room_dir`. File contents are line-iterated and JSON-parsed (lines failing JSON parse are skipped), but any valid JSONL content at the target path is returned in full.

## Trust Boundary Crossed

MCP client (direct or via prompt-injected agent) to arbitrary filesystem read. The channel-server process reads arbitrary files from the server filesystem.

## Impact

- Read any file named `channel.jsonl` accessible to the process — including attacker-planted files with exfiltrated data
- Combined with `post_message` (p8-043 write primitive), full read/write cycle: write content to any path as `channel.jsonl`, then read it back via `read_messages`
- The JSONL parse filter means only valid JSON lines are returned — but multi-line structured files often contain valid JSON lines
- Enables covert data staging and retrieval inside an agent-controlled environment

## Evidence

1. `channel-server.py:136` -- `channel_file = os.path.join(room_dir, "channel.jsonl")` — no realpath or containment check
2. `channel-server.py:142` -- `with open(channel_file, "r") as f` — direct open with user-controlled path
3. `channel-server.py:179` -- same pattern in `get_latest`
4. No `os.path.realpath()`, no prefix check, no validation at any layer
5. Same root cause as confirmed write variants in p8-043 (`post_message` at channel-server.py:78-79)

## Reproduction Steps

1. Plant a valid JSONL file at a target location (or use an existing one):
   ```bash
   echo '{"type":"task","from":"attacker","to":"victim","body":"secret","ref":"T1","ts":"2024-01-01T00:00:00Z"}' > /tmp/exfil/channel.jsonl
   ```
2. With MCP client access, invoke `read_messages`:
   ```json
   {"tool": "read_messages", "arguments": {"room_dir": "../../../../tmp/exfil"}}
   ```
3. Observe the file contents returned as a JSON array
4. Alternatively, use `post_message` to write to `../../../../tmp/exfil` first, then read back with `read_messages`
