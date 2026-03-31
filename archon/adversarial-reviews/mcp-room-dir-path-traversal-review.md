# Adversarial Review: mcp-room-dir-path-traversal

## Step 1 -- Restate and Decompose

The MCP tool functions `update_status`, `report_progress` (warroom-server.py) and `post_message` (channel-server.py) accept a `room_dir` string parameter that is passed directly to `os.makedirs()` and `open()` without path validation. An attacker who can invoke MCP tools can supply arbitrary paths (absolute or traversal-relative) to create directories and write files anywhere the server process can access.

### Sub-claims

- **Sub-claim A**: Attacker controls `room_dir` parameter -- SUPPORTED. The `room_dir` is a plain string parameter with no validation constraints beyond a description annotation. Any MCP client (or agent influenced by prompt injection) can supply any value.
- **Sub-claim B**: `room_dir` reaches `os.makedirs()` and `open()` without sanitization -- CONFIRMED by independent code trace. Zero path validation exists: no `os.path.realpath()`, no prefix containment, no allowlist, no regex.
- **Sub-claim C**: Arbitrary directory creation and file writes occur -- CONFIRMED by reproduction. Files with partially attacker-controlled content are written to the specified path.

## Step 2 -- Independent Code Path Trace

### warroom-server.py:update_status (lines 42-84)
1. `room_dir: Annotated[str, Field(description=...)]` -- no validation
2. Line 61: `os.makedirs(room_dir, exist_ok=True)` -- direct use
3. Line 62: `os.path.join(room_dir, "status")` -- direct join
4. Lines 71, 76, 81: writes `status`, `state_changed_at`, `audit.log`
5. `status` value IS validated against Literal type, but the PATH is not

### warroom-server.py:report_progress (lines 120-142)
1. Same pattern: `room_dir` -> `os.makedirs` -> `os.path.join` -> `open()`
2. `message` field is free-form and written to `progress.json`

### channel-server.py:post_message (lines 57-103)
1. Same pattern: `room_dir` -> `os.makedirs` -> `os.path.join` -> `open()`
2. `body` field is free-form (truncated to 65536 bytes) and written to `channel.jsonl`

### Validation/Sanitization Found: NONE
- No `os.path.realpath()` anywhere in either file
- No prefix/containment check
- No allowlist of valid room directories
- No path component filtering

## Step 3 -- Protection Surface Search

| Layer | Protection Found | Blocks Attack? |
|-------|-----------------|----------------|
| Language/Type | `str` type -- no constraints | No |
| Pydantic | `Field(description=...)` only -- no validators | No |
| MCP Framework | FastMCP provides no path sandboxing | No |
| Application | No path validation logic whatsoever | No |
| Middleware | stdio transport -- no WAF, proxy, or auth | No |
| Documentation | No SECURITY.md or known-risk documentation | No |

**Conclusion**: Zero protections exist at any layer.

## Step 4 -- Real-Environment Reproduction

### Environment
- Platform: macOS Darwin 25.3.0, Python 3.14
- Commit: 4c06f66 (HEAD of main)
- MCP and Pydantic packages available

### Healthcheck
- Both server files parse and execute successfully
- Tool functions are importable and callable

### Reproduction Results

**Attempt 1 -- Absolute path with update_status + report_progress**: SUCCESS
- `update_status(room_dir="/tmp/mcp-path-traversal-test-12345", status="pending")` created `status`, `state_changed_at`, `audit.log` at `/tmp/mcp-path-traversal-test-12345/`
- `report_progress()` created `progress.json` with attacker-controlled message content

**Attempt 2 -- Relative path traversal with update_status**: SUCCESS
- `update_status(room_dir="../../../../../tmp/mcp-traversal-relative-test", status="engineering")` created files at `/tmp/mcp-traversal-relative-test/`

**Attempt 3 -- Channel server post_message (code-equivalent manual test)**: SUCCESS
- Identical code pattern confirmed to write `channel.jsonl` with attacker-controlled body at arbitrary path

Evidence stored at: `security/real-env-evidence/mcp-room-dir-path-traversal/reproduction-log.md`

## Step 5 -- Prosecution and Defense Briefs

### Prosecution Brief

The vulnerability is real and directly exploitable:

1. **Code evidence**: `warroom-server.py:61` and `channel-server.py:78` both call `os.makedirs(room_dir, exist_ok=True)` where `room_dir` is a raw string parameter with zero validation. This is followed by `open()` calls that write files under that path.

2. **No protection at any layer**: Independent search confirms no `realpath()`, no prefix check, no allowlist, no path component filtering exists anywhere in either file or any imported module.

3. **Attacker-controlled content**: `report_progress` writes `message` (free-form string) to `progress.json`. `post_message` writes `body` (up to 64KB free-form string) to `channel.jsonl`. This enables writing semi-controlled content to arbitrary locations.

4. **Reproduction**: Three successful reproductions confirm the vulnerability creates directories and files at attacker-specified locations with attacker-controlled content.

5. **Attack surface**: MCP tools are invoked by agents. If an agent is influenced by prompt injection (a documented attack vector in this codebase per findings p8-040, p8-041), the injected prompt can instruct the agent to call these tools with malicious `room_dir` values.

### Defense Brief

1. **Access prerequisite**: The attacker must be an MCP client (configured in mcp-config.json) or must achieve prompt injection against an agent that has MCP tool access. This is not unauthenticated remote access -- it requires either local access to configure an MCP client or a successful prompt injection chain.

2. **Limited file names**: The attacker cannot choose arbitrary file names. They can only create files named `status`, `state_changed_at`, `audit.log`, `progress.json`, or `channel.jsonl`. This limits the ability to target specific sensitive file paths like `~/.ssh/authorized_keys`.

3. **Partial content control**: For `update_status`, the content is limited to the status allowlist (pending, engineering, qa-review, fixing). For `report_progress` and `post_message`, content is controlled but embedded in JSON structure, making exploitation of format-sensitive targets (like crontab) more difficult.

4. **Stdio transport**: The MCP server runs over stdio, meaning it requires the calling process to launch it directly. There is no network listener for remote exploitation.

5. **Process permissions**: The impact is bounded by the MCP server process's filesystem permissions, which in typical deployment would be a regular user account.

## Step 6 -- Severity Challenge

Starting at MEDIUM.

**Upgrade signals**:
- Arbitrary file write is a high-impact primitive
- The attack can be triggered indirectly via prompt injection (chaining with p8-040/p8-041), making it remotely triggerable in practice
- File content is partially controlled (up to 64KB via `post_message`)

**Downgrade signals**:
- Requires either MCP client access or successful prompt injection as a precondition
- File names are fixed (cannot write to arbitrary filenames)
- Content is embedded in JSON structure (limits some exploitation scenarios)
- Stdio transport means no direct network exposure

**Assessment**: The precondition of needing MCP client access or prompt injection is significant but not unrealistic given this is an agent framework where prompt injection is a known threat. The file name restriction limits but does not eliminate impact (directory creation alone can be disruptive, and writing to unexpected locations can cause DoS or configuration issues).

Challenged severity: **HIGH** -- the combination of arbitrary directory creation + file write with partially controlled content, triggerable via prompt injection chain, crosses a meaningful trust boundary (agent workspace to arbitrary filesystem).

This matches the original severity of HIGH.

## Step 7 -- Verdict

- The prosecution brief survives the defense: while the defense correctly notes preconditions and limitations, no blocking protection was identified that prevents the attack
- Real-environment reproduction succeeded across 3 attempts

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Independent code trace confirms zero path validation on room_dir in 3 MCP tool functions; reproduction succeeded with both absolute paths and relative traversal, writing attacker-influenced content to arbitrary filesystem locations.
Severity-Final: HIGH
PoC-Status: executed
```
