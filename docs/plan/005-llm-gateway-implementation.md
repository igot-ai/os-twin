# Plan 005: Unified AI Gateway — Implementation Design

**Status:** Ready for implementation
**Date:** 2026-04-21
**Supersedes:** unified-llm-module.md, vertex-ai-consolidation.md
**Scope:** Python + TypeScript — ALL LLM and embedding calls, no exceptions

## Overview

One HTTP service. Two endpoints. Every AI call in the entire codebase routes through it. Zero provider-specific SDKs remain in production code.

```
  Python callers                TypeScript callers
  ├─ memory system              ├─ bot chat
  ├─ knowledge graph            └─ bot audio transcription
  ├─ plan agent
  └─ zvec store
        │                              │
        ▼                              ▼
    Python client              TypeScript client
    (import or HTTP)           (HTTP fetch)
        │                              │
        └──────────┐    ┌──────────────┘
                   ▼    ▼
          ┌─────────────────────┐
          │   AI Gateway        │
          │   POST /v1/complete │──► Vertex AI (Gemini, Claude)
          │   POST /v1/embed   │──► Vertex AI or local SentenceTransformer
          │   port 4200        │
          └─────────────────────┘
                   │
                   ▼
          One auth (ADC), one config, one process
```

---

## Part 1: The Service

### 1.1 Architecture

A lightweight FastAPI server with 2 endpoints. Runs as a sidecar process alongside the dashboard (port 9000) and OpenCode (port 4096).

```
.agents/shared/ai/
├── server.py            # FastAPI app: POST /v1/complete, POST /v1/embed
├── config.py            # Configuration loading (env vars, defaults)
├── completion.py        # Vertex AI completion via litellm
├── embedding.py         # Cloud (Vertex) + local (SentenceTransformer) embedding
├── retry.py             # Exponential backoff with jitter
├── errors.py            # Error hierarchy
├── client.py            # Python client: get_completion(), get_embedding()
│                        #   → in-process if server unavailable, HTTP if server running
├── requirements.txt     # litellm, sentence-transformers, fastapi, uvicorn
└── tests/
    ├── test_server.py
    ├── test_completion.py
    ├── test_embedding.py
    └── test_client.py
```

### 1.2 HTTP API

#### `POST /v1/complete`

Supports both simple prompt-in/text-out AND multi-turn with function calling.

**Simple completion:**
```json
{
  "prompt": "Extract keywords from this text...",
  "model": "vertex_ai/gemini-3-flash-preview",
  "system": "You are a helpful assistant.",
  "response_format": {"type": "json_schema", "json_schema": {"name": "r", "schema": {...}}},
  "max_tokens": 4096,
  "temperature": 0.0
}
```

**Multi-turn with function calling (for bot chat loop):**
```json
{
  "messages": [
    {"role": "system", "content": "You are a project management assistant."},
    {"role": "user", "content": "Create a plan for a todo app"},
    {"role": "assistant", "content": null, "tool_calls": [{"id": "call_1", "function": {"name": "create_plan", "arguments": "{\"idea\": \"todo app\"}"}}]},
    {"role": "tool", "tool_call_id": "call_1", "content": "{\"plan_id\": \"todo-app\"}"},
    {"role": "user", "content": "Now launch it"}
  ],
  "model": "vertex_ai/gemini-3-flash-preview",
  "tools": [
    {"type": "function", "function": {"name": "list_plans", "description": "...", "parameters": {...}}},
    {"type": "function", "function": {"name": "create_plan", "description": "...", "parameters": {...}}}
  ]
}
```

**Response (text):**
```json
{
  "text": "Here are the keywords: ...",
  "model": "vertex_ai/gemini-3-flash-preview",
  "tool_calls": null,
  "usage": {"input_tokens": 150, "output_tokens": 50}
}
```

**Response (tool call):**
```json
{
  "text": null,
  "model": "vertex_ai/gemini-3-flash-preview",
  "tool_calls": [
    {"id": "call_1", "function": {"name": "create_plan", "arguments": "{\"idea\": \"todo app\"}"}}
  ],
  "usage": {"input_tokens": 150, "output_tokens": 30}
}
```

The caller (bot) inspects `tool_calls` — if present, executes the tool locally, appends the result as a `tool` message, and calls `/v1/complete` again. The loop stays in the caller. The gateway just does one model call per request.

litellm handles function-calling format translation across providers. Same `tools` JSON works with Gemini, Claude, and GPT — litellm converts to each provider's native format.

Error:
```json
{
  "error": "AuthenticationError",
  "message": "ADC not configured. Run: gcloud auth application-default login"
}
```

#### `POST /v1/embed`

Request:
```json
{
  "texts": ["PostgreSQL indexing strategies", "Docker container orchestration"],
  "model": "vertex_ai/text-embedding-005"
}
```

Response:
```json
{
  "vectors": [[0.012, -0.034, ...], [0.056, 0.078, ...]],
  "model": "vertex_ai/text-embedding-005",
  "dimensions": 768
}
```

For local models:
```json
{
  "texts": ["some text"],
  "model": "local/all-MiniLM-L6-v2"
}
```

Same response shape. The gateway routes `local/*` to SentenceTransformer, everything else to Vertex AI.

#### `GET /health`

```json
{
  "status": "ok",
  "vertex_ai": true,
  "local_models_loaded": ["all-MiniLM-L6-v2"],
  "default_completion_model": "vertex_ai/gemini-3-flash-preview"
}
```

### 1.3 Server implementation (`server.py`)

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn

from .completion import complete
from .embedding import embed
from .config import get_config

app = FastAPI(title="AI Gateway", version="1.0")

class ToolCall(BaseModel):
    id: str
    function: Dict[str, str]  # {"name": "...", "arguments": "..."}

class Message(BaseModel):
    role: str  # "system", "user", "assistant", "tool"
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None

class CompleteRequest(BaseModel):
    # Simple mode: just a prompt
    prompt: Optional[str] = None
    # Multi-turn mode: full message history
    messages: Optional[List[Message]] = None
    model: Optional[str] = None
    system: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None  # function declarations
    max_tokens: int = 4096
    temperature: float = 0.0

class CompleteResponse(BaseModel):
    text: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    model: str
    usage: Optional[Dict[str, int]] = None

class EmbedRequest(BaseModel):
    texts: List[str]
    model: Optional[str] = None

class EmbedResponse(BaseModel):
    vectors: List[List[float]]
    model: str
    dimensions: int

@app.post("/v1/complete", response_model=CompleteResponse)
async def handle_complete(req: CompleteRequest):
    cfg = get_config()
    model = req.model or cfg.default_completion_model
    try:
        result = complete(
            prompt=req.prompt,
            model=model,
            system=req.system,
            response_format=req.response_format,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        return CompleteResponse(text=result.text, model=model, usage=result.usage)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/embed", response_model=EmbedResponse)
async def handle_embed(req: EmbedRequest):
    cfg = get_config()
    model = req.model or cfg.default_cloud_embedding_model
    try:
        vectors = embed(texts=req.texts, model=model)
        return EmbedResponse(vectors=vectors, model=model, dimensions=len(vectors[0]))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def start(host="127.0.0.1", port=4200):
    uvicorn.run(app, host=host, port=port, log_level="info")
```

### 1.4 Completion (`completion.py`)

```python
import litellm
from dataclasses import dataclass
from typing import Optional, Dict, Any
from .config import get_config
from .retry import with_retry
from .errors import AuthError, TimeoutError, GatewayError

@dataclass
class CompletionResult:
    text: str
    usage: Optional[Dict[str, int]] = None

def complete(
    prompt: Optional[str] = None,
    messages: Optional[List[Dict]] = None,
    model: str = "vertex_ai/gemini-3-flash-preview",
    system: Optional[str] = None,
    response_format: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> CompletionResult:
    """Single completion call. Supports simple prompt OR multi-turn messages.

    If the model returns a tool call, `result.tool_calls` is populated
    and `result.text` is None. The caller handles tool execution and
    sends the result back in a follow-up call via `messages`.
    """
    cfg = get_config()

    # Build messages from prompt (simple mode) or use provided messages
    if messages:
        msg_list = [dict(m) for m in messages]  # copy
    else:
        msg_list = []
        if system:
            msg_list.append({"role": "system", "content": system})
        msg_list.append({"role": "user", "content": prompt or ""})

    kwargs = {
        "model": model,
        "messages": msg_list,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "timeout": cfg.completion_timeout,
    }

    # Claude on Vertex needs a specific region
    if "claude" in model.lower() and model.startswith("vertex_ai/"):
        kwargs["vertex_ai_location"] = cfg.vertex_claude_location

    if response_format:
        kwargs["response_format"] = response_format

    # Pass function declarations to litellm — it translates to
    # each provider's native format (Gemini, Claude, GPT all supported)
    if tools:
        kwargs["tools"] = tools

    def _call():
        try:
            response = litellm.completion(**kwargs)
            choice = response.choices[0]
            content = choice.message.content or ""
            usage = None
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                }

            # Check if model wants to call a tool
            tool_calls = None
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]

            return CompletionResult(
                text=content.strip() if content else None,
                tool_calls=tool_calls,
                usage=usage,
            )
        except litellm.AuthenticationError as e:
            raise AuthError(str(e)) from e
        except litellm.Timeout as e:
            raise TimeoutError(str(e)) from e
        except Exception as e:
            raise GatewayError(str(e)) from e

    return with_retry(_call, max_retries=cfg.completion_max_retries)
```

### 1.5 Embedding (`embedding.py`)

```python
import threading
import logging
from typing import List, Optional
from .errors import GatewayError

logger = logging.getLogger(__name__)

_local_models = {}
_local_lock = threading.Lock()

def _get_local_model(model_name: str):
    if model_name in _local_models:
        return _local_models[model_name]
    with _local_lock:
        if model_name in _local_models:
            return _local_models[model_name]
        from sentence_transformers import SentenceTransformer
        logger.info("Loading local embedding model: %s", model_name)
        _local_models[model_name] = SentenceTransformer(model_name)
        return _local_models[model_name]

def embed(texts: List[str], model: str) -> List[List[float]]:
    if model.startswith("local/"):
        return _embed_local(texts, model[len("local/"):])
    else:
        return _embed_cloud(texts, model)

def _embed_local(texts: List[str], model_name: str) -> List[List[float]]:
    try:
        st = _get_local_model(model_name)
        return st.encode(texts, convert_to_numpy=True, show_progress_bar=False).tolist()
    except Exception as e:
        raise GatewayError(f"Local embedding failed ({model_name}): {e}") from e

def _embed_cloud(texts: List[str], model: str) -> List[List[float]]:
    import litellm
    try:
        response = litellm.embedding(model=model, input=texts)
        return [item["embedding"] for item in response.data]
    except Exception as e:
        raise GatewayError(f"Cloud embedding failed ({model}): {e}") from e
```

### 1.6 Python client (`client.py`)

Python callers import this. It tries in-process first (fastest), falls back to HTTP if needed.

```python
import os
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Gateway server URL (set when running as separate process)
_GATEWAY_URL = os.environ.get("AI_GATEWAY_URL", "")

def get_completion(
    prompt: str,
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    response_format: Optional[Dict[str, Any]] = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> str:
    """Send prompt, get text back. Works in-process or via HTTP."""
    if _GATEWAY_URL:
        return _http_complete(prompt, model=model, system=system,
                              response_format=response_format,
                              max_tokens=max_tokens, temperature=temperature)

    # In-process (no HTTP hop)
    from .completion import complete
    from .config import get_config
    cfg = get_config()
    result = complete(
        prompt=prompt,
        model=model or cfg.default_completion_model,
        system=system,
        response_format=response_format,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return result.text

def get_embedding(
    texts: List[str],
    *,
    model: Optional[str] = None,
) -> List[List[float]]:
    """Convert texts to vectors. Works in-process or via HTTP."""
    if _GATEWAY_URL:
        return _http_embed(texts, model=model)

    from .embedding import embed
    from .config import get_config
    cfg = get_config()
    return embed(texts=texts, model=model or cfg.default_cloud_embedding_model)

def _http_complete(prompt, **kwargs) -> str:
    import httpx
    resp = httpx.post(
        f"{_GATEWAY_URL}/v1/complete",
        json={"prompt": prompt, **{k: v for k, v in kwargs.items() if v is not None}},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["text"]

def _http_embed(texts, model=None) -> List[List[float]]:
    import httpx
    body = {"texts": texts}
    if model:
        body["model"] = model
    resp = httpx.post(f"{_GATEWAY_URL}/v1/embed", json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()["vectors"]
```

### 1.7 TypeScript client (`bot/src/ai-gateway.ts`)

```typescript
const AI_GATEWAY_URL = process.env.AI_GATEWAY_URL || 'http://127.0.0.1:4200';

// ── Types ──────────────────────────────────────────────────

export interface ToolCall {
  id: string;
  function: { name: string; arguments: string };
}

export interface Message {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content?: string | null;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
}

export interface ToolDeclaration {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
}

export interface CompletionRequest {
  prompt?: string;
  messages?: Message[];
  model?: string;
  system?: string;
  tools?: ToolDeclaration[];
  response_format?: Record<string, unknown>;
  max_tokens?: number;
  temperature?: number;
}

export interface CompletionResponse {
  text: string | null;
  tool_calls: ToolCall[] | null;
  model: string;
  usage?: { input_tokens: number; output_tokens: number };
}

// ── Completion ─────────────────────────────────────────────

export async function complete(req: CompletionRequest): Promise<CompletionResponse> {
  const resp = await fetch(`${AI_GATEWAY_URL}/v1/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ message: resp.statusText }));
    throw new Error(`AI Gateway error: ${err.detail || err.message}`);
  }
  return resp.json();
}

/** Simple prompt → text (no tools). */
export async function getCompletion(
  prompt: string,
  options: Omit<CompletionRequest, 'prompt' | 'messages' | 'tools'> = {},
): Promise<string> {
  const result = await complete({ prompt, ...options });
  return result.text || '';
}

// ── Embedding ──────────────────────────────────────────────

export async function getEmbedding(
  texts: string[],
  model?: string,
): Promise<number[][]> {
  const resp = await fetch(`${AI_GATEWAY_URL}/v1/embed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texts, model }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ message: resp.statusText }));
    throw new Error(`AI Gateway error: ${err.detail || err.message}`);
  }
  const data = await resp.json();
  return data.vectors;
}
```

#### How the bot chat loop migrates

**Before** (hardcoded to Google SDK):
```typescript
import { GoogleGenerativeAI } from '@google/generative-ai';

const genAI = new GoogleGenerativeAI(config.GOOGLE_API_KEY);
const model = genAI.getGenerativeModel({
    model: config.GEMINI_MODEL,
    tools: [{ functionDeclarations: TOOLS }],
});
const chat = model.startChat({ history, systemInstruction });

// Tool calling loop
let result = await chat.sendMessage(question);
while (result.response.functionCalls()) {
    const toolResult = await executeTool(result.response.functionCalls()[0]);
    result = await chat.sendMessage([{ functionResponse: toolResult }]);
}
return result.response.text();
```

**After** (provider-agnostic via gateway):
```typescript
import { complete, type Message, type ToolDeclaration } from './ai-gateway';

const tools: ToolDeclaration[] = TOOLS.map(t => ({
    type: 'function',
    function: { name: t.name, description: t.description, parameters: t.parameters },
}));

const messages: Message[] = [
    { role: 'system', content: systemInstruction },
    ...history,
    { role: 'user', content: question },
];

// Tool calling loop — same logic, provider-agnostic
let response = await complete({ messages, tools });
while (response.tool_calls) {
    for (const call of response.tool_calls) {
        const result = await executeTool(call);
        messages.push({ role: 'assistant', content: null, tool_calls: [call] });
        messages.push({ role: 'tool', tool_call_id: call.id, content: JSON.stringify(result) });
    }
    response = await complete({ messages, tools });
}
return response.text;
```

Same tool dispatch logic (`executeTool`). Same loop. No Google SDK. Works with Gemini, Claude, or GPT — litellm translates the function-calling format on the server side.

`@google/generative-ai` is fully removed from the bot dependencies.

---

## Part 2: Every Caller — Before and After

### Python callers

| # | File | Before | After |
|---|---|---|---|
| 1 | `memory_system.py:616` | `self.llm_controller.llm.get_completion(prompt, response_format=...)` | `get_completion(prompt, response_format=...)` |
| 2 | `memory_system.py:300` | `self.llm_controller.llm.get_completion(prompt)` | `get_completion(prompt)` |
| 3 | `memory_system.py:1645` | `self.llm_controller.llm.get_completion(prompt, response_format=...)` | `get_completion(prompt, response_format=...)` |
| 4 | `knowledge/llm.py:152` | `anthropic.Anthropic().messages.create(model=..., system=..., messages=[...])` | `get_completion(user, system=system, model="vertex_ai/claude-...")` |
| 5 | `retrievers.py:40` | `litellm.embedding(model="gemini/...", input=texts)` | `get_embedding(texts, model="vertex_ai/text-embedding-005")` |
| 6 | `retrievers.py:51` | `SentenceTransformer(name).encode(input)` | `get_embedding(texts, model="local/all-MiniLM-L6-v2")` |
| 7 | `knowledge/embeddings.py:58` | `SentenceTransformer(name).encode(texts)` | `get_embedding(texts, model="local/bge-small-en-v1.5")` |
| 8 | `zvec_store.py:719` | `SentenceTransformer(name).encode(text)` | `get_embedding([text], model="local/harrier-oss-v1-0.6b")[0]` |

All Python callers import from `shared.ai.client`:
```python
from shared.ai.client import get_completion, get_embedding
```

### TypeScript callers

| # | File | Before | After |
|---|---|---|---|
| 9 | `agent-bridge.ts:879-903` | `new GoogleGenerativeAI(key).getGenerativeModel({tools}).startChat({history}).sendMessage(q)` | `complete({ messages, tools })` — same tool dispatch loop, no Google SDK |
| 10 | `audio-transcript.ts:127-138` | `new GoogleGenerativeAI(key).getGenerativeModel({...}).generateContent({parts: [audio, text]})` | `getCompletion(prompt)` |

All TypeScript callers import from `ai-gateway.ts`:
```typescript
import { complete, getCompletion, getEmbedding } from './ai-gateway';
```

`@google/generative-ai` is removed from bot dependencies entirely.

---

## Part 3: What Gets Deleted

| File | Lines | Content |
|---|---|---|
| `memory/agentic_memory/llm_controller.py` | ~570 | 6 controller classes |
| `memory/agentic_memory/retrievers.py` | ~30 | `GeminiEmbeddingFunction`, `SentenceTransformerEmbeddingFunction` |
| `dashboard/knowledge/llm.py` | ~30 | `_get_client()`, `anthropic.Anthropic()`, Anthropic SDK import |
| `dashboard/knowledge/embeddings.py` | ~15 | `_load_model()`, SentenceTransformer import |
| `dashboard/zvec_store.py` | ~10 | SentenceTransformer import and init |
| **Total deleted** | **~655** | |

---

## Part 4: Service Lifecycle

### When does the gateway start?

```
ostwin init
  └─► starts AI Gateway on port 4200
        └─► loads config from env
        └─► pre-loads default local embedding model (background thread)

ostwin run plan.md
  └─► gateway already running
  └─► memory MCP servers call gateway (in-process or HTTP)
  └─► war-room agents call gateway for analysis/embedding

bot start
  └─► bot reads AI_GATEWAY_URL from env
  └─► bot calls gateway for audio transcription
  └─► bot keeps Gemini SDK for chat (phase 1)
```

### Process management

The gateway runs as a background process, managed by `start-dashboard.sh` or `ostwin init`:

```bash
# Start gateway
python -m shared.ai.server &
AI_GATEWAY_PID=$!
echo $AI_GATEWAY_PID > .agents/ai-gateway.pid

# Health check
curl -s http://127.0.0.1:4200/health
```

For in-process Python callers (like memory MCP server), the gateway can also be used directly without HTTP:

```python
# If AI_GATEWAY_URL is not set, client.py calls completion.py directly
# No HTTP hop, no server needed
from shared.ai.client import get_completion
result = get_completion("test")  # in-process call
```

This dual mode (in-process + HTTP) means:
- Python callers in the same process (memory MCP) → zero latency
- Python callers in other processes → HTTP to port 4200
- TypeScript callers → always HTTP to port 4200

---

## Part 5: Auth

### One auth method: ADC

```bash
gcloud auth application-default login --project igot-studio
gcloud auth application-default set-quota-project igot-studio
```

The gateway uses litellm with `vertex_ai/` prefix, which picks up ADC automatically. No API keys in config files.

### Environment variables

```bash
# Required
GOOGLE_VERTEX_PROJECT=igot-studio
GOOGLE_VERTEX_LOCATION=global

# Optional
AI_GATEWAY_URL=http://127.0.0.1:4200    # For HTTP mode
AI_GATEWAY_PORT=4200                      # Server port
LLM_COMPLETION_MODEL=vertex_ai/gemini-3-flash-preview
LLM_CLOUD_EMBEDDING_MODEL=vertex_ai/text-embedding-005
LLM_LOCAL_EMBEDDING_MODEL=local/all-MiniLM-L6-v2
VERTEX_CLAUDE_LOCATION=us-east5
LLM_TIMEOUT=60
LLM_MAX_RETRIES=2
```

### What gets removed

```bash
# No longer needed:
# GOOGLE_API_KEY        (was used by memory, bot)
# ANTHROPIC_API_KEY     (was used by knowledge graph)
# OPENAI_API_KEY        (was used by plan agent fallback)
```

---

## Part 6: Configuration (`config.py`)

```python
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class GatewayConfig:
    # Completion
    default_completion_model: str = "vertex_ai/gemini-3-flash-preview"
    completion_timeout: int = 60
    completion_max_retries: int = 2

    # Embedding
    default_cloud_embedding_model: str = "vertex_ai/text-embedding-005"
    default_local_embedding_model: str = "local/all-MiniLM-L6-v2"

    # Vertex AI
    vertex_project: Optional[str] = None
    vertex_location: str = "global"
    vertex_claude_location: str = "us-east5"

    # Server
    host: str = "127.0.0.1"
    port: int = 4200

_config: Optional[GatewayConfig] = None

def get_config() -> GatewayConfig:
    global _config
    if _config is not None:
        return _config
    _config = GatewayConfig(
        default_completion_model=os.environ.get("LLM_COMPLETION_MODEL", "vertex_ai/gemini-3-flash-preview"),
        completion_timeout=int(os.environ.get("LLM_TIMEOUT", "60")),
        completion_max_retries=int(os.environ.get("LLM_MAX_RETRIES", "2")),
        default_cloud_embedding_model=os.environ.get("LLM_CLOUD_EMBEDDING_MODEL", "vertex_ai/text-embedding-005"),
        default_local_embedding_model=os.environ.get("LLM_LOCAL_EMBEDDING_MODEL", "local/all-MiniLM-L6-v2"),
        vertex_project=os.environ.get("GOOGLE_VERTEX_PROJECT"),
        vertex_location=os.environ.get("GOOGLE_VERTEX_LOCATION", "global"),
        vertex_claude_location=os.environ.get("VERTEX_CLAUDE_LOCATION", "us-east5"),
        host=os.environ.get("AI_GATEWAY_HOST", "127.0.0.1"),
        port=int(os.environ.get("AI_GATEWAY_PORT", "4200")),
    )
    return _config
```

---

## Part 7: Implementation Phases

### Phase 1: Build the gateway service + clients (no callers changed)

**Files created:**
```
.agents/shared/__init__.py
.agents/shared/ai/__init__.py
.agents/shared/ai/server.py
.agents/shared/ai/config.py
.agents/shared/ai/completion.py
.agents/shared/ai/embedding.py
.agents/shared/ai/retry.py
.agents/shared/ai/errors.py
.agents/shared/ai/client.py
.agents/shared/ai/requirements.txt
.agents/shared/ai/tests/test_server.py
.agents/shared/ai/tests/test_completion.py
.agents/shared/ai/tests/test_embedding.py
.agents/shared/ai/tests/test_client.py
bot/src/ai-gateway.ts
bot/src/__tests__/ai-gateway.test.ts
```

**Exit criteria:** Server starts, `/health` returns 200, all gateway tests pass with mocked litellm/SentenceTransformer. TypeScript client tests pass with mocked fetch.

### Phase 2: Migrate Python callers (memory, knowledge, zvec)

1. Memory: replace `llm_controller.llm.get_completion()` → `get_completion()`
2. Memory: replace embedding classes → `get_embedding()` lambdas
3. Knowledge: replace `anthropic.Anthropic()` → `get_completion()`
4. Knowledge: replace `KnowledgeEmbedder._load_model()` → `get_embedding()`
5. zvec_store: replace `SentenceTransformer` → `get_embedding()`

**Exit criteria:** 84 memory + 18 knowledge + dashboard tests pass.

### Phase 3: Migrate TypeScript callers

1. `audio-transcript.ts`: replace `@google/generative-ai` → `getCompletion()`
2. `agent-bridge.ts`: replace `GoogleGenerativeAI` chat loop → `complete()` with `messages` + `tools`
   - Same `executeTool()` dispatch logic, same loop structure
   - `@google/generative-ai` removed from dependencies
   - Tool declarations converted from Gemini format to OpenAI format (litellm standard)
3. Remove `@google/generative-ai` from `package.json`

**Exit criteria:** 373 bot tests pass, tsc clean, `grep -r "google/generative-ai" bot/` returns zero.

### Phase 4: Wire service lifecycle

1. Add gateway start/stop to `start-dashboard.sh`
2. Add health check to `ostwin init`
3. Add `AI_GATEWAY_URL` to MCP config templates
4. PID management (`.agents/ai-gateway.pid`)

### Phase 5: Delete dead code

1. Delete `llm_controller.py` (570 lines)
2. Remove `anthropic` SDK dependency
3. Remove scattered `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY` checks
4. Update docs

### Phase 6: Verify full unification

1. `grep -r "google/generative-ai\|@google/generative-ai" .` → zero hits in production code
2. `grep -r "import anthropic\|from anthropic" .` → zero hits in production code
3. `grep -r "import openai\|from openai" .` → zero hits in production code (except litellm internals)
4. All LLM calls trace to `shared/ai/` (Python in-process) or `AI_GATEWAY_URL` (TypeScript HTTP)
5. All auth goes through ADC — no API keys in `.env` files

---

## Part 8: Test Matrix

| Phase | Test Suite | Count | Expected |
|---|---|---|---|
| 1 | Gateway tests (new) | ~20 | All pass (mocked) |
| 1 | TypeScript client tests (new) | ~5 | All pass (mocked) |
| 2 | Memory unit tests | 80 | All pass |
| 2 | Memory integration tests | 4 | All pass |
| 2 | Knowledge smoke tests | 18 | All pass |
| 3 | Bot tests | 373 | All pass |
| 4 | Full CI | 1661+ | All pass |

---

## Part 9: Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Gateway server down → all AI calls fail | High | In-process fallback for Python. Health check on startup. |
| Extra HTTP hop for TypeScript adds latency | Low | ~5ms localhost, negligible vs ~500ms API call |
| litellm doesn't handle Vertex AI correctly | Low | Well-tested native support |
| Claude not on Vertex in target region | Medium | Configurable model, falls back to Gemini |
| Bot tool-calling format differs between providers | Low | litellm normalizes function-calling format across Gemini/Claude/GPT |
| SentenceTransformer cold start in gateway | Low | Pre-load default model on startup |
| Port 4200 conflict | Low | Configurable via `AI_GATEWAY_PORT` |

---

## Part 10: Size Summary

| Category | Lines |
|---|---|
| New: gateway service + clients (Python + TS) | +550 |
| New: tests (Python + TS) | +180 |
| Deleted: `llm_controller.py` | -570 |
| Deleted: embedding classes, Anthropic client | -85 |
| Deleted: `@google/generative-ai` usage in bot | -100 |
| Caller changes (import + call site) | ~80 changed |
| **Net** | **~-25 lines** (less code, fully unified) |

10 out of 10 call sites unified. Zero provider-specific SDKs in production code. One service, two endpoints, both languages.
