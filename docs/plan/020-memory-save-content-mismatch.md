# Plan 020: Fix Memory Save Content Mismatch

**Status:** Draft
**Date:** 2026-05-15

---

## Problem

When an agent calls `save_memory`, the content it saves is **shorter** than what it writes to the conversation. Example from the architect agent:

**What was saved to memory** (inside `memory_save_memory {...}`):
```
## Plan Review: Gold Mining Game MVP
### Plan Structure
- 2 Epics...
### Architecture Highlights
1. Separation of Concerns...
### Key Schemas
(typescript interfaces)
### Refinements Made
1-4 bullet points
### Verdict: PASS
```

**What the agent wrote to the conversation** (after the tool call):
```
## Plan Review Complete
### Plan Quality Assessment
(full table with 6 rows)
### Refinements Made
(detailed explanations per task)
### Architecture Summary
(ASCII art diagram)
### Key Schemas Saved
(explanation of cross-room visibility)
```

The conversation output has a quality assessment table, architecture diagram, and explanations that the memory note does not. Another agent searching memory later gets the short version, missing the detail.

---

## Root Cause

The agent constructs the `save_memory` content and its conversation response as **two separate compositions**. The LLM writes a summary for memory, then writes a richer response for the user. Nothing in the system forces them to be the same.

The architect's `ROLE.md` says:
```
save_memory(
  content="<paste the full content — complete ADR, schema definition, or API contract>",
  ...
)
```

But "paste the full content" is ambiguous — the agent interprets it as "paste a summary of my findings" rather than "paste everything I'm about to write."

The `save_memory` tool docstring says:
```
Good memories are 3-10 sentences and capture:
- WHAT happened or was decided
- WHY it matters
- HOW it works in practice
- GOTCHAS or edge cases
```

"3-10 sentences" actively encourages the agent to summarize rather than save the full output. The tool instruction conflicts with the role instruction.

---

## Analysis: Why This Happens

1. **Timing**: The agent calls `save_memory` BEFORE writing its conversation response. It hasn't composed the full output yet when it decides what to save.

2. **Tool description conflict**: The `save_memory` docstring says "3-10 sentences." The role says "paste the full content." The agent follows the tool description because it's closer to the call site.

3. **No feedback loop**: The agent never sees what was actually saved. It gets back `{"status": "saved"}` and moves on. It doesn't know the saved content differs from its conversation output.

4. **No post-output save**: There's no mechanism to save the conversation output AFTER the agent finishes writing it. The agent must decide what to save before it writes its response.

---

## Fix Options

### Option A: Change tool description to encourage full content (low effort)

Update the `save_memory` docstring in both `memory_mcp.py` and `mcp_server.py`:

**Before:**
```
Good memories are 3-10 sentences and capture:
```

**After:**
```
Save your COMPLETE output — not a summary. Include tables, diagrams,
schemas, and all detail. Other agents can ONLY see memory — they
cannot read your conversation output. If you write it, save it.
```

**Pros:** Simple change, no code logic changes.
**Cons:** LLMs may still summarize. Longer content = slower LLM analysis.

### Option B: Role prompts tell agents to save AFTER composing (medium effort)

Update `ROLE.md` for all roles to instruct:

```
## Memory Save Rule
1. First compose your COMPLETE response
2. Then call save_memory with the FULL response content
3. Do NOT compose a separate shorter version for memory
```

**Pros:** Clear instruction, works with existing tool.
**Cons:** Requires updating every role. Agents may not follow it.

### Option C: Auto-capture agent output to memory (high effort)

Add a post-processing step in `Invoke-Agent.ps1` or the MCP layer that:
1. After the agent finishes, reads the full output from `architect-output.txt`
2. Calls `save_memory` with the full output automatically
3. Deduplicates against what the agent already saved

**Pros:** Guaranteed complete capture regardless of agent behavior.
**Cons:** Complex, may double-save, output file includes tool calls and ANSI codes.

### Option D: Combine A + B (recommended)

Change the tool description AND the role prompts. The tool description removes the "3-10 sentences" guidance and says "save complete output." The role prompts give a concrete workflow: compose first, then save the full thing.

---

## Recommended Fix (Option D)

### File changes

#### 1. `dashboard/routes/memory_mcp.py` — update tool docstring

```python
@mcp.tool()
def save_memory(content, name=None, path=None, tags=None):
    """Save a memory note to the knowledge base.

    Save your COMPLETE output — not a summary. Other agents in other
    war-rooms can ONLY see memory. They cannot read your files or
    conversation output. If you produced it, save it.

    Include: tables, schemas, diagrams, code blocks, decisions,
    trade-offs, and rationale. Longer content is better — the system
    handles summarization automatically for content over 250 words.

    The system will automatically:
    - Generate a name and directory path if not provided
    - Extract keywords and tags for semantic search
    - Find and link related existing memories
    - Create a summary for long content

    Args:
        content: Your COMPLETE output. Do not summarize — save everything.
        name: Optional human-readable name (2-5 words). Auto-generated if omitted.
        path: Optional directory path (e.g. "architecture/plans"). Auto-generated.
        tags: Optional list of tags. Auto-generated if not provided.
    """
```

#### 2. `dashboard/memory/mcp_server.py` — same docstring update

#### 3. `.agents/roles/architect/ROLE.md` — update save workflow

```markdown
## MANDATORY: Save to Memory

**CRITICAL**: Every deliverable you produce MUST be saved to memory.
Other agents in other rooms can ONLY see Memory — they cannot read
your files or conversation output.

**Workflow:**
1. Complete your analysis/review/design FIRST
2. Then call `save_memory` with the FULL output — not a summary
3. Include everything: tables, diagrams, schemas, code blocks

```
save_memory(
  content="<YOUR COMPLETE OUTPUT — everything you just wrote>",
  name="<short name>",
  path="architecture/<category>",
  tags=["<relevant>", "<tags>"]
)
```

DO NOT compose a separate shorter version for memory. Copy your full
response into the content field.
```

#### 4. All other role ROLE.md files that have memory instructions

Apply the same "save FULL output, not summary" instruction.

---

## Verification

After the fix, run a plan and check:
1. The `memory_save_memory` payload in `architect-output.txt` should contain the same content as the conversation response
2. The `.memory/notes/` file should contain tables, diagrams, and all detail from the agent's output
3. Another agent searching memory should find the complete content

```bash
# Compare tool call content vs conversation output
grep -A1 "memory_save_memory" .war-rooms/room-000/artifacts/architect-output.txt

# Check saved note
cat .memory/notes/architecture/*/gold-mining-plan-review.md
```

---

---

## Bug 2: Evolution Overwrites Agent-Provided Metadata

### Discovery

The agent sends `tags=["architecture","plan-review","gold-mining","game"]` but the saved file has `tags=["project-completed","milestone"]`. The agent-provided tags are completely replaced.

### Root cause

In `memory_system.py`, `_apply_strengthen()` at line 1809:
```python
note.tags = response_json["tags_to_update"]  # REPLACES, does not merge
```

And `_apply_update_neighbors()` at line 1823:
```python
neighbor.tags = new_tags[i]      # REPLACES neighbor tags entirely
neighbor.context = new_contexts[i]  # REPLACES neighbor context entirely
```

The evolution LLM decides new tags/context and the code **overwrites** the existing values instead of **merging** them. This means:
- Agent-provided tags are lost
- Neighbor notes have their metadata silently rewritten by unrelated saves
- The frontmatter drifts from what any agent explicitly set

### Fix

#### `_apply_strengthen` — merge tags, don't replace

```python
# Before (line 1809):
note.tags = self._coerce_str_list(response_json["tags_to_update"])

# After:
new_tags = self._coerce_str_list(response_json["tags_to_update"])
merged = list(dict.fromkeys(note.tags + new_tags))  # preserve order, deduplicate
note.tags = merged
```

#### `_apply_update_neighbors` — merge tags, append context

```python
# Before (lines 1822-1826):
neighbor.tags = self._coerce_str_list(new_tags[i])
neighbor.context = ctx

# After:
evolved_tags = self._coerce_str_list(new_tags[i])
neighbor.tags = list(dict.fromkeys(neighbor.tags + evolved_tags))
if i < len(new_contexts):
    ctx = new_contexts[i]
    if isinstance(ctx, str) and ctx:
        # Append evolution context, preserve original
        neighbor.context = f"{neighbor.context} | {ctx}" if neighbor.context and neighbor.context != "General" else ctx
```

### Files to change

| File | Change |
|---|---|
| `dashboard/agentic_memory/memory_system.py:1809` | Merge tags in `_apply_strengthen` |
| `dashboard/agentic_memory/memory_system.py:1822-1826` | Merge tags + append context in `_apply_update_neighbors` |

---

## Summary of Both Bugs

| Bug | Root cause | Fix |
|---|---|---|
| Agent saves summary, not full output | Tool docstring says "3-10 sentences" | Remove length guidance, say "save COMPLETE output" |
| Evolution overwrites agent metadata | `_apply_strengthen` replaces `note.tags` | Merge new tags with existing, don't replace |

## Non-goals

- Auto-capturing agent output (Option C) — too complex for this fix
- Changing the MCP protocol — agents must explicitly call save_memory
- Disabling evolution — it's useful, just needs to merge not replace
