# Plan: Evaluate `ai-sdk-provider-opencode-sdk` for Bot LLM Consolidation

**Status:** Under evaluation
**Date:** 2026-04-21
**Related:** [unified-llm-module.md](./unified-llm-module.md), [vertex-ai-consolidation.md](./vertex-ai-consolidation.md)

## What is it

[`ai-sdk-provider-opencode-sdk`](https://github.com/ben-vargas/ai-sdk-provider-opencode-sdk) is a community Vercel AI SDK provider that routes LLM calls through OpenCode's local server. It supports `generateText()`, `streamText()`, `streamObject()`, tool observation, session management, and multi-provider model selection.

Version: 3.x (AI SDK v6), beta status, MIT license, 88 stars.

## How it works

```
Bot Code → Vercel AI SDK → OpenCode Provider → OpenCode Server (:4096) → LLM API
                                                    ↕
                                              OpenCode config
                                          (providers, API keys, models)
```

Instead of calling Gemini/Claude/OpenAI SDKs directly, the bot calls OpenCode's local HTTP server, which routes to whichever provider is configured. Model selection is a string: `opencode("google/gemini-3-flash-preview")` or `opencode("anthropic/claude-sonnet-4-5")`.

## What it replaces in our codebase

### Current bot LLM calls (TypeScript)

| File | SDK | Model | Purpose |
|---|---|---|---|
| `bot/src/agent-bridge.ts` | `@google/generative-ai` | `gemini-3-flash-preview` | Chat + function calling |
| `bot/src/audio-transcript.ts` | `@google/generative-ai` | `gemini-3-flash-preview` | Audio transcription |

### With this provider

| File | SDK | Model | Purpose |
|---|---|---|---|
| `bot/src/agent-bridge.ts` | `ai` + `ai-sdk-provider-opencode-sdk` | `opencode("google/gemini-3-flash-preview")` | Chat + function calling |
| `bot/src/audio-transcript.ts` | `ai` + `ai-sdk-provider-opencode-sdk` | `opencode("google/gemini-3-flash-preview")` | Audio transcription |

### Code change example

**Before:**
```typescript
import { GoogleGenerativeAI } from '@google/generative-ai';
const genAI = new GoogleGenerativeAI(config.GOOGLE_API_KEY);
const model = genAI.getGenerativeModel({
    model: 'gemini-3-flash-preview',
    tools: [{ functionDeclarations: TOOLS }],
});
const chat = model.startChat({ history, systemInstruction });
const result = await chat.sendMessage(question);
```

**After:**
```typescript
import { generateText } from 'ai';
import { opencode } from 'ai-sdk-provider-opencode-sdk';

const result = await generateText({
    model: opencode('google/gemini-3-flash-preview', { agent: 'build' }),
    messages: history,
    prompt: question,
});
```

## Scope of impact

| Component | Affected? | Details |
|---|---|---|
| Bot TypeScript (chat, audio) | Yes | Replaces `@google/generative-ai` with Vercel AI SDK + OpenCode provider |
| Memory system (Python) | **No** | TypeScript library, irrelevant to Python |
| Knowledge graph (Python) | **No** | Same |
| Plan agent (Python) | **No** | Same |
| War-room agents | **No** | Already use OpenCode via CLI |
| Dashboard (Python) | **No** | Same |

**This library only addresses the TypeScript side.** The Python LLM consolidation (`shared/llm/` module) is still needed regardless.

## Benefits

1. **Multi-provider switching** -- Change `opencode("google/gemini-3-flash")` to `opencode("anthropic/claude-sonnet-4-5")` without code changes
2. **Session management** -- Built-in session persistence, resume by session ID
3. **Tool observation** -- See OpenCode's tool execution (file reads, code edits) in the stream
4. **Agent selection** -- Route to OpenCode agents (`build`, `plan`, `explore`, `general`)
5. **Unified auth** -- OpenCode handles API keys, bot doesn't need them directly
6. **Vercel AI SDK ecosystem** -- Access to `generateText`, `streamText`, `streamObject` with structured output, abort signals, etc.

## Tradeoffs

1. **Added dependency** -- Bot now requires OpenCode server running on port 4096. Currently the bot calls Gemini directly with zero external dependencies.
2. **Extra latency** -- One more HTTP hop: Bot → OpenCode Server → LLM API. Adds ~50-100ms per request.
3. **Beta status** -- Library is beta, 88 stars, 2 contributors. Not battle-tested at scale.
4. **No embeddings** -- Only supports completion/streaming. Embedding calls (if bot ever needs them) can't go through this provider.
5. **Function calling difference** -- Current bot uses Gemini's native function calling (`tools` in `getGenerativeModel`). The AI SDK has its own tool calling pattern. Migration requires rewriting the tool dispatch loop.
6. **OpenCode server lifecycle** -- Something needs to start/stop the OpenCode server. During `ostwin run`, agents already spawn OpenCode processes. But the bot runs independently — it would need its own server management.

## Relationship to other plans

### vs. Vertex AI consolidation

Not mutually exclusive. OpenCode can be configured to use Vertex AI as its backend. The call chain would be:

```
Bot → AI SDK → OpenCode → Vertex AI → Gemini/Claude
```

This works but adds a layer compared to calling Vertex AI directly:

```
Bot → @google-cloud/vertexai → Vertex AI → Gemini
```

### vs. Unified LLM module (`shared/llm/`)

The unified module solves the **Python** side. This provider solves the **TypeScript** side. They complement each other:

- Python: `shared/llm/get_completion()` → litellm → Vertex AI
- TypeScript: `opencode("google/gemini-3-flash")` → OpenCode → Vertex AI (or direct)

### vs. Direct Vertex AI SDK (`@google-cloud/vertexai`)

| Approach | Pros | Cons |
|---|---|---|
| OpenCode provider | Multi-provider, session management, agent access | Extra hop, beta, server dependency |
| Direct Vertex AI SDK | Fewer dependencies, lower latency, stable | Single provider (Google), no agent features |

## When to use this provider

**Use it if:**
- The bot needs to switch between providers (Gemini, Claude, GPT) dynamically
- The bot should leverage OpenCode agents (build, plan, explore) instead of raw completions
- OpenCode server is already running (e.g., during plan execution)
- The team wants to standardize on Vercel AI SDK for all TypeScript AI code

**Don't use it if:**
- The bot only needs Gemini completions (direct SDK is simpler)
- Latency matters (extra HTTP hop adds ~50-100ms)
- The bot runs standalone without ostwin (no OpenCode server available)

## Migration estimate

| Component | Effort |
|---|---|
| Install `ai` + `ai-sdk-provider-opencode-sdk` | 1 line |
| Rewrite `agent-bridge.ts` tool dispatch | ~100 lines (function calling API differs) |
| Rewrite `audio-transcript.ts` | ~20 lines |
| Add OpenCode server lifecycle to bot startup | ~30 lines |
| Update bot tests (mock AI SDK instead of Gemini SDK) | ~50 lines |
| **Total** | ~200 lines changed |

## Open questions

1. **Server lifecycle** -- Who starts the OpenCode server? The bot process? A separate daemon? `ostwin init`?
2. **Function calling** -- The current bot uses Gemini's native `functionDeclarations` with a custom dispatch loop. The AI SDK has `tools` with a different pattern. How much of the dispatch logic needs rewriting?
3. **Audio transcription** -- Does the AI SDK / OpenCode provider support multimodal input (audio + text)? The current `audio-transcript.ts` sends inline audio data to Gemini.
4. **Testing** -- Bot tests currently mock `@google/generative-ai`. Switching to AI SDK requires new mock patterns. Is `vitest` or `sinon` better for mocking `generateText()`?
5. **Stability** -- The library is beta with 2 contributors. Is this acceptable for production use? Who maintains it if the author stops?
