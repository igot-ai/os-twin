---
title: Channel Format
description: Specification for channel.jsonl message format, types, and file locking.
sidebar:
  order: 7
---

The channel is the communication backbone between agents in a war-room. Messages are stored in `channel.jsonl` — a newline-delimited JSON file with exclusive file locking for concurrent access.

## Message Format

Each line in `channel.jsonl` is a JSON object:

```json
{
  "v": 1,
  "id": "engineer-done-1775215174499753000-85510",
  "ts": "2026-04-03T11:19:34Z",
  "from": "engineer",
  "to": "qa",
  "type": "done",
  "ref": "EPIC-001",
  "body": "Implementation complete. Files: GridView.cs, GridViewTests.cs"
}
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `v` | `int` | Yes | Message schema version (currently `1`) |
| `id` | `string` | Yes | Unique message ID |
| `ts` | `string` | Yes | ISO 8601 timestamp |
| `from` | `string` | Yes | Sender role name |
| `to` | `string` | Yes | Recipient role name |
| `type` | `string` | Yes | Message type (see below) |
| `ref` | `string` | Yes | Task or epic reference |
| `body` | `string` | Yes | Message content (markdown allowed) |

### Message ID Format

IDs follow the pattern: `{role}-{type}-{unix_nanos}-{pid}`

Example: `game-engineer-done-1775215174499753000-85510`

This guarantees uniqueness across concurrent agents on the same machine.

## Message Types

### task

Sent by the manager to assign work to an agent.

```json
{
  "type": "task",
  "from": "manager",
  "to": "game-engineer",
  "body": "Epic description and acceptance criteria..."
}
```

### done

Sent by an agent when work is complete.

```json
{
  "type": "done",
  "from": "engineer",
  "to": "qa",
  "body": "Summary of work, files changed, how to test..."
}
```

The `done` body should include:
- Summary of changes
- Files created or modified
- How to test
- Any known limitations

### review

Sent to request a code review or quality check.

```json
{
  "type": "review",
  "from": "qa",
  "to": "engineer",
  "body": "Review findings and recommendations..."
}
```

### pass

Sent by QA when the review passes.

```json
{
  "type": "pass",
  "from": "qa",
  "to": "manager",
  "body": "All acceptance criteria met. Tests pass."
}
```

### fail

Sent by QA when the review fails.

```json
{
  "type": "fail",
  "from": "qa",
  "to": "manager",
  "body": "Issues found: missing edge case handling..."
}
```

### fix

Sent by the manager to route a fix request back to the engineer.

```json
{
  "type": "fix",
  "from": "manager",
  "to": "engineer",
  "body": "QA found issues. Fix the coordinate mapping..."
}
```

### error

Sent when an agent encounters an unrecoverable error.

```json
{
  "type": "error",
  "from": "engineer",
  "to": "manager",
  "body": "Agent crashed: timeout exceeded after 1200s"
}
```

### signoff

Sent during release coordination to confirm a role's approval.

```json
{
  "type": "signoff",
  "from": "qa",
  "to": "manager",
  "body": "QA approves release. All rooms passed."
}
```

## Type Summary

| Type | Sender | Receiver | Triggers |
|------|--------|----------|----------|
| `task` | manager | any role | Starts work |
| `done` | any role | qa/manager | Signals completion |
| `review` | qa | engineer | Review feedback |
| `pass` | qa | manager | Review approval |
| `fail` | qa | manager | Review rejection |
| `fix` | manager | engineer | Fix request |
| `error` | any role | manager | Error report |
| `signoff` | any role | manager | Release approval |

## File Locking

Channel writes use exclusive file locks (`fcntl.LOCK_EX`) to prevent corruption from concurrent writers. The Python channel module handles this automatically:

```python
# Simplified locking logic
with open(channel_path, 'a') as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    f.write(json.dumps(message) + '\n')
    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

Reads do not acquire locks — they scan the file linearly.

## Channel CLI

The `channel_cmd.py` tool provides CLI access:

```bash
python .agents/bin/channel_cmd.py read --room room-001
python .agents/bin/channel_cmd.py read --room room-001 --type done
python .agents/bin/channel_cmd.py read --room room-001 --last 5
python .agents/bin/channel_cmd.py post --room room-001 --from engineer --to qa --type done --ref EPIC-001 --body "Work complete"
```

## Size Limits

The `max_message_size_bytes` config field (default: `65536`) limits individual message body size. Messages exceeding this are truncated with a warning.

:::caution
Do not edit `channel.jsonl` manually while agents are running. The file lock mechanism assumes append-only access.
:::

:::tip
Use `channel_read_messages` with filters to efficiently query specific message types without parsing the entire file.
:::
