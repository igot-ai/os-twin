---
name: war-room-communication
description: "Use this skill for standard war-room channel communication -- message types, progress reporting, handoff patterns, and protocol rules."
tags: [global, communication, protocol, war-room]
trust_level: core
---

# war-room-communication

## Overview

This skill defines the standard communication protocol for all agents working within a war-room. Every role uses the same message types and channel conventions for consistent, machine-parsable handoffs.

## When to Use

- When any role needs to post or read channel messages
- When learning the communication protocol as a new or dynamic role
- When debugging message flow issues between agents

## Message Types Reference

### Messages Sent by Engineers

| Type | When | Body Must Include |
|------|------|------------------|
| `done` | Work is complete | Summary, files changed, how to test |
| `progress` | Periodic updates | Percentage, current activity |

**Example `done` message:**
```json
{
  "from_role": "engineer",
  "type": "done",
  "epic": "EPIC-001",
  "body": "## Summary\nImplemented user auth module.\n\n## Files\n- src/auth.py\n- tests/test_auth.py\n\n## How to Test\n1. Run `pytest tests/test_auth.py`\n2. Verify all 12 tests pass"
}
```

### Messages Sent by QA

| Type | When | Body Must Include |
|------|------|------------------|
| `pass` | All acceptance criteria met | Confirmation, test results, suggestions |
| `fail` | Issues found | Numbered issues with severity, expected vs actual |
| `escalate` | Design/scope problem | Classification (DESIGN/SCOPE/REQUIREMENTS), reasoning |

**Example `fail` message:**
```json
{
  "from_role": "qa",
  "type": "fail",
  "epic": "EPIC-001",
  "body": "## Issues\n1. **[CRITICAL]** Auth tokens never expire\n   - Expected: 24h expiry\n   - Actual: No expiry set\n2. **[MAJOR]** Missing rate limiting on login endpoint"
}
```

### Messages Sent by Manager

| Type | When | Body Must Include |
|------|------|------------------|
| `task` | Assigning work | Epic/task reference, brief location |
| `review` | Requesting QA review | Reference to engineer's done message |
| `fix` | Routing QA feedback to engineer | QA feedback verbatim, triage context |
| `design-review` | Requesting architect review | Failure context, QA feedback |
| `plan-update` | Brief has been revised | What changed, new requirements |
| `release` | Drafting or finalizing release | RELEASE.md reference |

### Messages Sent by Architect

| Type | When | Body Must Include |
|------|------|------------------|
| `design-guidance` | After reviewing a design issue | Verdict (FIX/REDESIGN/REPLAN), rationale, sketch |

### Messages Received by All Roles

| Type | Source | Action |
|------|--------|--------|
| `signoff` | Any role | Approve the release (respond with confirmation) |

## Progress Reporting

All roles should report progress periodically:

```python
# Report progress at meaningful milestones
report_progress(25, "Reading brief and planning approach")
report_progress(50, "Implementation in progress -- 3 of 6 sub-tasks complete")
report_progress(75, "Running tests and self-verifying")
report_progress(100, "Posting done message")
```

**Rules:**
- Report at 25% intervals minimum
- Include a meaningful message, not just the percentage
- Don't spam progress -- milestone-based, not time-based

## Channel Operations

### Reading Messages

```python
# Read the latest message from a specific role
messages = read_messages(from_role="manager")
latest = messages[-1]

# Read all messages of a specific type
fixes = read_messages(msg_type="fix")
```

### Posting Messages

```python
# Post a message to the channel
post_message(
    from_role="engineer",
    msg_type="done",
    body="## Summary\n..."
)
```

## Handoff Patterns

### Happy Path
```
Manager  task  Engineer  done  Manager  review  QA  pass  Manager  release
```

### Failure Path
```
QA  fail  Manager (triage)  fix  Engineer  done  Manager  review  QA
```

### Escalation Path
```
QA  escalate  Manager (triage)  design-review  Architect  design-guidance  Manager  fix  Engineer
```

## Protocol Rules

1. **Always include the epic/task reference** in every message
2. **Never skip QA** -- every `done` must lead to a `review`
3. **Include QA feedback verbatim** when routing `fix` to engineer
4. **Post to the channel** -- don't communicate out-of-band
5. **Use correct message types** -- the manager parses these programmatically
6. **Progress updates are not done messages** -- only `done` signals completion

## Verification

When using this protocol:
1. Messages use the correct `type` field
2. Required body fields are present for each message type
3. Epic/task reference is included
4. Progress is reported at meaningful milestones
