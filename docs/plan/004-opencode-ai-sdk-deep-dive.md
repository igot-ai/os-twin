# Plan: Integrate AI SDK Provider for OpenCode

**Status:** Proposed
**Date:** 2026-04-21
**Package:** [`ai-sdk-provider-opencode-sdk`](https://github.com/ben-vargas/ai-sdk-provider-opencode-sdk) v3.x
**Related:** [unified-llm-module.md](./unified-llm-module.md), [vertex-ai-consolidation.md](./vertex-ai-consolidation.md)

## What It Is

A TypeScript library that wraps OpenCode's HTTP server as a [Vercel AI SDK](https://sdk.vercel.ai/docs) provider. It lets any TypeScript application call LLMs through OpenCode instead of calling provider APIs directly.

### The layers

```
Your TypeScript code
  │
  ▼
Vercel AI SDK  (generateText, streamText, streamObject)
  │
  ▼
ai-sdk-provider-opencode-sdk  (this library)
  │  - creates/manages OpenCode sessions
  │  - converts AI SDK format ↔ OpenCode format
  │  - handles streaming, tool approval, structured output
  │
  ▼  HTTP (localhost:4096)
OpenCode Server
  │  - routes to configured provider (Anthropic, Google, OpenAI)
  │  - manages auth (API keys, ADC)
  │  - executes tools (file read/write, shell, etc.)
  │  - enforces permissions
  │
  ▼
LLM API  (Gemini, Claude, GPT, etc.)
```

### What it provides

| Feature | Support |
|---|---|
| `generateText()` | Full |
| `streamText()` | Full (SSE streaming) |
| `streamObject()` | Partial (native JSON schema, needs fallback for reliability) |
| Multi-turn conversations | Full (session-based) |
| Tool observation | Full (see tool calls/results in stream, but can't define custom tools) |
| Tool approvals | Full (approve/reject tool execution) |
| Agent selection | Full (`build`, `plan`, `general`, `explore`) |
| Model selection | Full (`provider/model` format) |
| Abort/cancellation | Full (AbortSignal) |
| Embeddings | **None** (throws `NoSuchModelError`) |
| Image generation | **None** |
| Custom tools | **None** (tools are server-side only) |

### What it does NOT do

- **No embeddings.** The `embeddingModel()` method throws. All embedding calls (memory, knowledge, zvec) must use a different path.
- **No Python support.** TypeScript/Node.js only. The Python side of the codebase (memory system, knowledge graph, plan agent) cannot use this.
- **No custom tool definitions.** You can observe OpenCode's server-side tools (file read, shell, etc.), but you cannot register your own tools through this provider. The bot's current function-calling tools (`list_plans`, `create_plan`, etc.) would need to be either moved server-side or handled differently.

## How It Works Internally

### Session lifecycle

```
1. Provider creates an OpenCode session:
   POST /session.create → { id: "ses_abc123" }

2. Each generateText/streamText call sends a prompt to that session:
   POST /session.prompt {
     sessionID: "ses_abc123",
     model: { providerID: "google", modelID: "gemini-3-flash-preview" },
     parts: [{ type: "text", text: "user message" }],
     agent: "build",
   }

3. For streaming, it subscribes to server-sent events:
   GET /event.subscribe → SSE stream
   Events: message.updated, message.completed, tool-call, tool-result, etc.

4. Session persists across calls (multi-turn conversation)
```

### Model selection

Models use `providerID/modelID` format:

```typescript
opencode("google/gemini-3-flash-preview")    // Gemini
opencode("anthropic/claude-sonnet-4-5")       // Claude
opencode("openai/gpt-4o")                    // GPT
```

The provider extracts `providerID` and `modelID`, sends them in the request body. OpenCode routes to the correct backend.

### Tool execution

OpenCode executes tools **server-side**. The provider can only observe:

```typescript
const result = streamText({
  model: opencode("google/gemini-3-flash-preview"),
  prompt: "List files in the current directory",
});

for await (const part of result.fullStream) {
  switch (part.type) {
    case "tool-call":
      // OpenCode called a tool (e.g., "bash", "read_file")
      console.log(`Tool: ${part.toolName}`);
      break;
    case "tool-result":
      // Tool execution result
      console.log(`Result: ${part.result}`);
      break;
    case "tool-approval-request":
      // Tool needs permission (e.g., write to file)
      console.log(`Approve? ${part.approvalId}`);
      break;
  }
}
```

### Structured output

```typescript
import { Output, generateText } from "ai";

const result = await generateText({
  model: opencode("google/gemini-3-flash-preview"),
  prompt: "Extract entities from this text...",
  experimental_output: Output.object({
    schema: z.object({
      entities: z.array(z.object({
        name: z.string(),
        type: z.string(),
      })),
    }),
  }),
});
```

Uses OpenCode's native `json_schema` format. Not 100% reliable with all models — the library recommends a fallback pattern: try structured output, retry, then fall back to prompt-based JSON extraction.

## How It Would Change Our Codebase

### Current bot architecture

```
User message
  │
  ▼
agent-bridge.ts
  │  - builds Gemini chat history
  │  - defines function declarations (list_plans, create_plan, etc.)
  │  - calls GoogleGenerativeAI.sendMessage()
  │  - dispatches tool calls to executeTool()
  │  - loops until model returns text (not tool call)
  │
  ▼
@google/generative-ai SDK
  │
  ▼
Google Gemini API
```

### With this provider

```
User message
  │
  ▼
agent-bridge.ts (rewritten)
  │  - calls generateText() or streamText()
  │  - model = opencode("google/gemini-3-flash-preview")
  │  - observes tool calls in stream
  │
  ▼
Vercel AI SDK
  │
  ▼
ai-sdk-provider-opencode-sdk
  │
  ▼
OpenCode Server (:4096)
  │
  ▼
Google Gemini API (or Claude, GPT)
```

### Key difference: tool calling

**Current approach:** The bot defines 12 function declarations (`list_plans`, `create_plan`, `get_plan_status`, etc.). Gemini calls them, the bot executes them locally via `executeTool()`, sends results back to Gemini. The bot controls the entire tool loop.

**With OpenCode provider:** Tools are server-side. The bot's 12 tools would need to be either:

1. **Registered as OpenCode MCP tools** — Write an MCP server that exposes `list_plans`, `create_plan`, etc. OpenCode calls them automatically. The bot just observes results in the stream.
2. **Kept client-side with a different pattern** — Use the AI SDK's `tools` parameter, but this library ignores custom tools (`Custom tool definitions are ignored. OpenCode executes tools server-side.`). So this doesn't work.
3. **Hybrid** — Use OpenCode for general chat/reasoning, but intercept when the bot needs to call dashboard APIs. Send a system prompt that makes the model output structured commands, parse them client-side.

Option 1 (MCP tools) is the cleanest but requires building a new MCP server for the dashboard API. Option 3 is fragile. This is the biggest migration challenge.

## What Works Without Changes

| Feature | Works? | Notes |
|---|---|---|
| Basic chat (greeting, Q&A) | Yes | `generateText()` with conversation history |
| Multi-turn sessions | Yes | Provider manages sessions automatically |
| Model switching | Yes | Change `opencode("google/...")` to `opencode("anthropic/...")` |
| Streaming responses | Yes | `streamText()` with SSE |
| Audio transcription | Unclear | Needs multimodal input (audio bytes). AI SDK supports it but untested with OpenCode provider. |

## What Needs New Work

| Feature | Effort | Details |
|---|---|---|
| Bot tool calling (12 tools) | High | Must move tools to MCP server or redesign the tool dispatch |
| Dashboard API MCP server | High | New server exposing `list_plans`, `create_plan`, etc. as MCP tools |
| OpenCode server lifecycle | Medium | Bot needs to start/manage the server. Currently not running standalone. |
| Trivial message detection | Low | Keep client-side, skip OpenCode for "hi", "thanks" |
| Context caching | Low | Keep client-side, cache dashboard API responses |

## Architecture Options

### Option A: Full OpenCode integration (tool calling via MCP)

```
Bot → AI SDK → OpenCode → Gemini
                  ↕
            MCP Dashboard Server (new)
            ├── list_plans
            ├── create_plan
            ├── get_plan_status
            ├── launch_plan
            ├── get_war_room_status
            ├── get_logs
            ├── search_skills
            ├── get_plan_assets
            ├── get_memories
            └── ...
```

**Pros:** Bot becomes thin (just UI glue). All intelligence is in OpenCode + MCP tools.
**Cons:** Requires building a new MCP server. Tool calling is no longer in the bot's control.

### Option B: OpenCode for chat, keep local tool dispatch

```
Bot → AI SDK → OpenCode → Gemini  (for chat/reasoning only)
Bot → executeTool() → Dashboard API  (for tool calls, same as today)
```

**Pros:** Minimal change to tool dispatch. Still get multi-provider model switching.
**Cons:** Can't use OpenCode's native tool execution. The tool calling loop stays in bot code. Model can't autonomously use OpenCode tools (file read, shell, etc.).

### Option C: Don't use this provider, go direct Vertex AI

```
Bot → @google-cloud/vertexai → Vertex AI → Gemini
```

**Pros:** Simplest. No OpenCode server dependency. Direct auth via ADC.
**Cons:** Single provider (Google). No OpenCode agent features.

## Migration Estimate

### Option A (Full OpenCode + MCP)

| Component | Lines | Effort |
|---|---|---|
| New MCP Dashboard Server | ~300 | High |
| Rewrite `agent-bridge.ts` | ~200 | High |
| OpenCode server lifecycle in bot | ~50 | Medium |
| Update bot tests | ~150 | Medium |
| Update `audio-transcript.ts` | ~30 | Low |
| **Total** | ~730 | 2-3 days |

### Option B (OpenCode chat + local tools)

| Component | Lines | Effort |
|---|---|---|
| Rewrite `agent-bridge.ts` chat logic | ~100 | Medium |
| Keep `executeTool()` as-is | 0 | None |
| OpenCode server lifecycle | ~50 | Medium |
| Update bot tests | ~80 | Medium |
| **Total** | ~230 | 1 day |

## Limitations to Be Aware Of

1. **No embeddings** — The provider explicitly throws on `embeddingModel()`. Memory, knowledge, and zvec embedding calls cannot use this. A separate embedding solution is still needed.

2. **No custom tools** — The provider ignores `tools` passed to `generateText()`. All tool definitions must be in OpenCode's config or via MCP servers. The bot's 12 dashboard API tools need a different approach.

3. **Beta quality** — 88 stars, 2 contributors, v3.0.2. The library warns about inconsistent structured output reliability depending on model/backend route.

4. **Server dependency** — Requires OpenCode running on port 4096. The bot currently has zero external dependencies for LLM calls. This adds a process to manage.

5. **Latency** — Extra HTTP hop through OpenCode server adds ~50-100ms per request.

6. **Auth passthrough** — OpenCode handles auth. The bot no longer controls which API key or credential is used. Configuration moves to OpenCode's config, not the bot's `.env`.

## Recommendations

| Scenario | Recommendation |
|---|---|
| Bot needs multi-provider switching | Use this provider (Option B) |
| Bot needs OpenCode agents (build, plan, explore) | Use this provider (Option A) |
| Bot only needs Gemini + tool calling | Direct Vertex AI (Option C) is simpler |
| Python LLM consolidation | This library doesn't help. Use `shared/llm/` module. |
| Embedding consolidation | This library doesn't help. Use litellm or direct SDK. |

## Decision Checklist

Before implementation:

- [ ] Choose Option A, B, or C
- [ ] If A: design the MCP Dashboard Server tool schema
- [ ] If A or B: decide how to manage OpenCode server lifecycle (bot starts it? systemd? separate process?)
- [ ] Test audio transcription with multimodal input through OpenCode
- [ ] Evaluate structured output reliability for bot tool-calling responses
- [ ] Confirm the 12 bot tools can work with the chosen architecture
