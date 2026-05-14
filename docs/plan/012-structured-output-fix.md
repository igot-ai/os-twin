# Plan 012: Fix Structured Output — Wire response_format to LLM Providers

**Status:** Draft
**Date:** 2026-05-07

---

## Problem

Memory notes are saved with `name: null`, `links: []`, `keywords: []` because the LLM analysis and evolution steps fail silently. The root cause:

```
memory_system.py → completion_fn(prompt, response_format={json_schema})
  → dashboard/ai/completion.py → complete(response_format=schema)
    → client.chat(messages, tools=tools)   ← response_format DROPPED HERE
      → LLM gets no schema constraint
        → returns free text or malformed JSON
          → json.loads() fails silently
            → note saved with empty metadata
```

The `response_format` parameter is accepted by `complete()` but never passed to `client.chat()`. The JSON schema from `analyze_content` and `_get_evolution_decision` is thrown away. The only JSON enforcement is a system prompt: `"You must respond with a JSON object."` — which the model ignores half the time.

---

## What needs to change

### Phase 1: `llm_client.py` — add `response_format` to chat()

**1.1 Abstract base class** — add parameter:
```python
@abstractmethod
async def chat(
    self,
    messages: list[ChatMessage],
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[str] = None,
    response_format: Optional[dict] = None,    # NEW
) -> ChatMessage:
```

**1.2 OpenAIClient.chat()** — pass directly to SDK:
```python
if response_format:
    kwargs["response_format"] = response_format
```
OpenAI SDK natively accepts `{"type": "json_schema", "json_schema": {...}}`.

**1.3 GoogleClient.chat()** — convert to Gemini format:
```python
if response_format:
    schema = response_format.get("json_schema", {}).get("schema", {})
    config_kwargs["response_mime_type"] = "application/json"
    config_kwargs["response_schema"] = schema
```
Gemini SDK accepts `response_mime_type="application/json"` + `response_schema=dict` on `GenerateContentConfig`.

Also fix: config is only created when tools exist. It should also be created when `response_format` is present.

### Phase 2: `completion.py` — wire through

```python
# Before (line 183):
client.chat(chat_messages, tools=tools)

# After:
client.chat(chat_messages, tools=tools, response_format=response_format)
```

Keep the `_SYSTEM_JSON_PROMPT` system message as a safety net.

### Phase 3: `memory_system.py` — fix error logging

```python
# Before (line 657):
print(f"Error analyzing content: {e}")

# After:
logger.error("Error analyzing content", exc_info=True)
```

Same for `process_memory` (lines 1655, 1658): use `logger.exception()`.

---

## Files to change

| File | Change | Lines |
|---|---|---|
| `dashboard/llm_client.py` | Add `response_format` to `chat()` and `chat_stream()` for both OpenAI and Google clients | ~20 |
| `dashboard/ai/completion.py` | Pass `response_format` to `client.chat()` | ~2 |
| `.agents/memory/agentic_memory/memory_system.py` | Replace `print()` with `logger.error(exc_info=True)` | ~6 |

---

## Expected result

After this fix:
- `analyze_content` sends JSON schema to the provider → model returns valid JSON → name, path, keywords, tags extracted reliably
- `_get_evolution_decision` sends evolution schema → model returns structured decision → links created between related notes
- Errors are logged with full tracebacks instead of silently swallowed
- Memory graph shows connected nodes with edges
