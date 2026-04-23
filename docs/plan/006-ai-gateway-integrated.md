# Plan 006: Unified AI Gateway — Integrated with Settings System

**Status:** Ready for implementation
**Date:** 2026-04-22
**Supersedes:** 005-llm-gateway-implementation.md
**Scope:** Python + TypeScript — all LLM and embedding calls, zero provider SDKs remaining

## Module Connections

```
                         ┌─────────────────┐
                         │  Dashboard UI    │
                         │  Settings page   │
                         └────────┬─────────┘
                                  │ configures providers
                                  ▼
                    ┌──────────────────────────┐
                    │  MasterSettings.providers │
                    │  SettingsVault             │
                    │  SettingsResolver          │
                    └────────────┬───────────────┘
                                 │ reads config from
                                 ▼
     ┌──────────────────────────────────────────────────┐
     │                 shared/ai/                        │
     │                                                   │
     │   get_completion()  ──► litellm ──► Vertex AI     │
     │   get_embedding()   ──► litellm ──► Vertex AI     │
     │                     ──► SentenceTransformer (local)│
     └───┬──────┬──────┬──────┬──────┬──────┬────────────┘
         │      │      │      │      │      │
         ▼      ▼      ▼      ▼      ▼      ▼

  memory/     knowledge/  knowledge/  zvec_      dashboard/    bot/
  memory_     llm.py      embeddings  store.py   routes/       agent-
  system.py   (3 calls)   .py         (embed)    ai.py         bridge.ts
  (3 calls)               (embed)                (HTTP for TS) (via HTTP)
```

### Reads from

`dashboard/lib/settings/` — provider config, vault secrets, Vertex AI settings. Falls back to environment variables when dashboard is unavailable (e.g., standalone MCP server).

### Called by (Python, in-process — no HTTP hop)

| Caller | File | Calls |
|---|---|---|
| Memory analysis | `memory/agentic_memory/memory_system.py` | 3 × `get_completion()` |
| Memory embedding | `memory/agentic_memory/retrievers.py` | 2 × `get_embedding()` |
| Knowledge extraction | `dashboard/knowledge/llm.py` | 3 × `get_completion()` |
| Knowledge embedding | `dashboard/knowledge/embeddings.py` | 1 × `get_embedding()` |
| War-room message indexing | `dashboard/zvec_store.py` | 1 × `get_embedding()` |

### Called by (TypeScript, via HTTP to dashboard port 9000)

| Caller | File | Calls |
|---|---|---|
| Bot chat + function calling | `bot/src/agent-bridge.ts` | `complete({ messages, tools })` |
| Audio transcription | `bot/src/audio-transcript.ts` | `getCompletion(prompt)` |

### Exposed via

`dashboard/routes/ai.py` — two routes (`POST /api/ai/complete`, `POST /api/ai/embed`) registered in `dashboard/api.py` on port 9000 alongside all other routes. No new server process.

### Replaces

| Deleted | Why |
|---|---|
| `memory/agentic_memory/llm_controller.py` (570 lines) | 6 controller classes → `get_completion()` |
| `@google/generative-ai` in bot | Hardcoded Google SDK → provider-agnostic `complete()` |
| `anthropic` SDK in knowledge | Direct Anthropic SDK → `get_completion()` |
| Scattered `SentenceTransformer` inits (3 files) | Each file loaded its own model → `get_embedding()` with shared cache |

---

## Why 006 replaces 005

Plan 005 created its own config (`GatewayConfig`, `AI_GATEWAY_PORT`, `LLM_COMPLETION_MODEL` env vars) that duplicates what the settings system already manages. The codebase already has:

- `MasterSettings.providers` — API keys, models, Vertex config, deployment mode
- `SettingsVault` — secure key storage (Keychain on macOS, encrypted file on Linux)
- `SettingsResolver` — resolves vault refs, role overrides, plan/room overrides
- `_sync_vertex_env()` — syncs Vertex AI auth to `.env` and `os.environ`
- `POST /api/settings/test/{provider}` — tests provider connectivity
- Google OAuth2 flow — full ADC setup from the dashboard UI

Plan 006 builds the gateway **on top of this**, not beside it.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Settings System                       │
│  MasterSettings.providers → API keys, models, Vertex    │
│  SettingsVault → secure storage                         │
│  SettingsResolver → resolves ${vault:...} refs          │
│  /api/settings/test/{provider} → connection test        │
└───────────────┬─────────────────────────────────────────┘
                │ reads config from
                ▼
┌─────────────────────────────────────────────────────────┐
│              shared/ai/                                  │
│                                                          │
│  Python callers:                                         │
│    from shared.ai import get_completion, get_embedding   │
│    (in-process, no HTTP hop)                             │
│                                                          │
│  TypeScript callers:                                     │
│    POST /api/ai/complete  ─┐                             │
│    POST /api/ai/embed     ─┤ dashboard routes            │
│                            └─ (no new server process)    │
│                                                          │
│  Routing:                                                │
│    completion → litellm → Vertex AI (Gemini, Claude)     │
│    embedding  → litellm → Vertex AI (cloud)              │
│                → SentenceTransformer (local)              │
└─────────────────────────────────────────────────────────┘
```

### Key differences from 005

| Aspect | 005 | 006 |
|---|---|---|
| Config source | Own env vars (`LLM_COMPLETION_MODEL`, etc.) | `MasterSettings.providers` via `SettingsResolver` |
| API keys | Read from env directly | Read from `SettingsVault` (Keychain/encrypted file) |
| Vertex AI auth | Own ADC setup instructions | Uses existing `_sync_vertex_env()` + Google OAuth flow |
| TypeScript access | Separate server on port 4200 | Dashboard routes (`/api/ai/*`) on existing port 9000 |
| Process management | New process to start/stop | No new process — runs inside dashboard |
| Provider test | None | Uses existing `/api/settings/test/{provider}` |

**No new server process.** The gateway is a Python library (for in-process calls) + two dashboard routes (for TypeScript HTTP calls). Everything runs on the existing dashboard at port 9000.

---

## Part 1: Module Design

### File structure

```
.agents/shared/
└── ai/
    ├── __init__.py          # Public API: get_completion, get_embedding
    ├── completion.py        # Vertex AI completion via litellm
    ├── embedding.py         # Cloud (Vertex) + local (SentenceTransformer)
    ├── config.py            # Reads from MasterSettings.providers
    ├── retry.py             # Exponential backoff with jitter
    ├── errors.py            # Error hierarchy
    └── tests/
        ├── test_completion.py
        ├── test_embedding.py
        └── test_config.py

dashboard/routes/
└── ai.py                   # POST /api/ai/complete, POST /api/ai/embed
                             # (registered in api.py alongside other routes)

bot/src/
└── ai-gateway.ts            # TypeScript client: calls /api/ai/* on dashboard
```

### 1.1 Config reads from settings (`config.py`)

```python
"""AI Gateway configuration — reads from the existing settings system.

Does NOT define its own env vars. All config comes from:
1. MasterSettings.providers (API keys, models, Vertex config)
2. SettingsVault (secure key storage)
3. SettingsResolver (resolves ${vault:...} refs)

Falls back to environment variables only when the dashboard
settings system is unavailable (e.g., standalone MCP server
running without the dashboard).
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class AIConfig:
    # Resolved from settings or env
    provider: str = "vertex_ai"          # litellm provider prefix
    completion_model: str = "gemini-3-flash-preview"
    cloud_embedding_model: str = "text-embedding-005"
    local_embedding_model: str = "all-MiniLM-L6-v2"

    # Vertex AI
    vertex_project: Optional[str] = None
    vertex_location: str = "global"
    vertex_auth_mode: str = "oauth"      # "oauth" or "service_account"
    vertex_claude_location: str = "us-east5"

    # Retry
    timeout: int = 60
    max_retries: int = 2

    def full_completion_model(self) -> str:
        return f"{self.provider}/{self.completion_model}"

    def full_cloud_embedding_model(self) -> str:
        return f"{self.provider}/{self.cloud_embedding_model}"


_config: Optional[AIConfig] = None

def get_config() -> AIConfig:
    """Load config from MasterSettings if available, else from env.

    The settings system handles:
    - API key retrieval from vault
    - Vertex AI project/location from ProviderSettings.google
    - deployment_mode (gemini vs vertex)
    - Auth mode (oauth vs service_account)

    We just read the resolved values.
    """
    global _config
    if _config is not None:
        return _config

    try:
        _config = _load_from_settings()
    except Exception as e:
        logger.info("Settings system unavailable (%s), falling back to env", e)
        _config = _load_from_env()

    return _config


def _load_from_settings() -> AIConfig:
    """Read from MasterSettings.providers.google."""
    from dashboard.lib.settings import SettingsResolver

    resolver = SettingsResolver()
    settings = resolver.load()
    google = settings.providers.google

    if not google or not google.enabled:
        raise ValueError("Google provider not configured in settings")

    # deployment_mode determines the litellm prefix
    is_vertex = (google.deployment_mode or "").lower() == "vertex"
    provider = "vertex_ai" if is_vertex else "gemini"

    return AIConfig(
        provider=provider,
        completion_model=google.default_model or "gemini-3-flash-preview",
        vertex_project=google.project_id,
        vertex_location=google.vertex_location or "global",
        vertex_auth_mode=google.vertex_auth_mode or "oauth",
    )


def _load_from_env() -> AIConfig:
    """Fallback: read from environment variables."""
    return AIConfig(
        provider="vertex_ai",
        completion_model=os.environ.get("LLM_MODEL", "gemini-3-flash-preview"),
        vertex_project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        vertex_location=os.environ.get("VERTEX_LOCATION", "global"),
    )


def reset_config():
    """Force reload on next get_config() call."""
    global _config
    _config = None
```

### 1.2 Completion (`completion.py`)

Same as 005 but model comes from `AIConfig`:

```python
import litellm
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from .config import get_config
from .retry import with_retry
from .errors import AIAuthError, AITimeoutError, AIError

@dataclass
class CompletionResult:
    text: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    usage: Optional[Dict[str, int]] = None

def complete(
    prompt: Optional[str] = None,
    *,
    messages: Optional[List[Dict]] = None,
    model: Optional[str] = None,
    system: Optional[str] = None,
    response_format: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> CompletionResult:
    """Single completion call. Supports prompt OR messages + tools."""
    cfg = get_config()
    model = model or cfg.full_completion_model()

    if messages:
        msg_list = [dict(m) for m in messages]
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
        "timeout": cfg.timeout,
    }
    if "claude" in model.lower() and "vertex_ai" in model:
        kwargs["vertex_ai_location"] = cfg.vertex_claude_location
    if response_format:
        kwargs["response_format"] = response_format
    if tools:
        kwargs["tools"] = tools

    def _call():
        try:
            response = litellm.completion(**kwargs)
            choice = response.choices[0]
            text = (choice.message.content or "").strip() or None
            tool_calls = None
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                tool_calls = [
                    {"id": tc.id, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in choice.message.tool_calls
                ]
            usage = None
            if hasattr(response, "usage") and response.usage:
                usage = {"input_tokens": response.usage.prompt_tokens, "output_tokens": response.usage.completion_tokens}
            return CompletionResult(text=text, tool_calls=tool_calls, usage=usage)
        except litellm.AuthenticationError as e:
            raise AIAuthError(str(e)) from e
        except litellm.Timeout as e:
            raise AITimeoutError(str(e)) from e
        except Exception as e:
            raise AIError(str(e)) from e

    return with_retry(_call, max_retries=cfg.max_retries)
```

### 1.3 Embedding (`embedding.py`)

Same as 005 — routes `local/*` to SentenceTransformer, everything else to litellm.

### 1.4 Public API (`__init__.py`)

```python
from .completion import complete, CompletionResult
from .embedding import embed
from .config import get_config, reset_config, AIConfig
from .errors import AIError, AIAuthError, AITimeoutError

def get_completion(prompt, **kwargs) -> str:
    """Simple prompt → text. For callers that don't need tool_calls."""
    result = complete(prompt, **kwargs)
    return result.text or ""

def get_embedding(texts, **kwargs):
    """texts → vectors."""
    return embed(texts, **kwargs)
```

### 1.5 Dashboard routes (`dashboard/routes/ai.py`)

No new server. Two routes on the existing dashboard (port 9000):

```python
"""AI Gateway routes — exposes shared/ai as HTTP for TypeScript callers."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/api/ai", tags=["ai"])

class CompleteRequest(BaseModel):
    prompt: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None
    model: Optional[str] = None
    system: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None
    max_tokens: int = 4096
    temperature: float = 0.0

class CompleteResponse(BaseModel):
    text: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    model: str
    usage: Optional[Dict[str, int]] = None

class EmbedRequest(BaseModel):
    texts: List[str]
    model: Optional[str] = None

class EmbedResponse(BaseModel):
    vectors: List[List[float]]
    model: str
    dimensions: int

@router.post("/complete", response_model=CompleteResponse)
async def handle_complete(req: CompleteRequest):
    from shared.ai import complete
    from shared.ai.config import get_config
    try:
        cfg = get_config()
        model = req.model or cfg.full_completion_model()
        result = complete(
            prompt=req.prompt,
            messages=req.messages,
            model=model,
            system=req.system,
            tools=req.tools,
            response_format=req.response_format,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        return CompleteResponse(
            text=result.text,
            tool_calls=result.tool_calls,
            model=model,
            usage=result.usage,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/embed", response_model=EmbedResponse)
async def handle_embed(req: EmbedRequest):
    from shared.ai import embed
    from shared.ai.config import get_config
    try:
        cfg = get_config()
        model = req.model or cfg.full_cloud_embedding_model()
        vectors = embed(texts=req.texts, model=model)
        return EmbedResponse(
            vectors=vectors,
            model=model,
            dimensions=len(vectors[0]) if vectors else 0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

Register in `dashboard/api.py`:
```python
from dashboard.routes import ai
app.include_router(ai.router)
```

### 1.6 TypeScript client (`bot/src/ai-gateway.ts`)

Calls dashboard at port 9000, same server the bot already talks to:

```typescript
import config from './config';

// Uses the same DASHBOARD_URL the bot already uses for plans/rooms/etc.
const BASE = config.DASHBOARD_URL;

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

export interface CompleteRequest {
  prompt?: string;
  messages?: Message[];
  model?: string;
  system?: string;
  tools?: Array<{ type: 'function'; function: { name: string; description: string; parameters: Record<string, unknown> } }>;
  response_format?: Record<string, unknown>;
  max_tokens?: number;
  temperature?: number;
}

export interface CompleteResponse {
  text: string | null;
  tool_calls: ToolCall[] | null;
  model: string;
  usage?: { input_tokens: number; output_tokens: number };
}

export async function complete(req: CompleteRequest): Promise<CompleteResponse> {
  const resp = await fetch(`${BASE}/api/ai/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(`AI Gateway: ${err.detail || resp.statusText}`);
  }
  return resp.json();
}

export async function getCompletion(prompt: string, options: Omit<CompleteRequest, 'prompt' | 'messages' | 'tools'> = {}): Promise<string> {
  const result = await complete({ prompt, ...options });
  return result.text || '';
}

export async function getEmbedding(texts: string[], model?: string): Promise<number[][]> {
  const resp = await fetch(`${BASE}/api/ai/embed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texts, model }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(`AI Gateway: ${err.detail || resp.statusText}`);
  }
  return (await resp.json()).vectors;
}
```

No new URL to configure. The bot already knows `DASHBOARD_URL`.

---

## Part 2: Settings Schema Changes

### 2.1 What's missing from the current settings

| shared/ai needs | Exists? | Where to add |
|---|---|---|
| Completion model | Yes | `providers.google.default_model` |
| Vertex vs Gemini mode | Yes | `providers.google.deployment_mode` |
| Vertex project | Yes | `providers.google.project_id` |
| Vertex location | Yes | `providers.google.vertex_location` |
| Vertex auth mode | Yes | `providers.google.vertex_auth_mode` |
| API key | Yes | `providers.google.api_key_ref` → vault |
| **Embedding model (cloud)** | **No** | Add to `ProviderSettings` |
| **Claude Vertex region** | **No** | Add to `ProviderSettings` (Anthropic-specific) |
| **Per-purpose model overrides** | **No** | New `MasterSettings.ai` namespace |
| **Timeout** | **No** | New `MasterSettings.ai` namespace |
| **Max retries** | **No** | New `MasterSettings.ai` namespace |
| **Local embedding model** | **No** | New `MasterSettings.ai` namespace |

### 2.2 Changes to `ProviderSettings` (in `dashboard/models.py`)

Add 2 fields to existing model:

```python
class ProviderSettings(BaseModel):
    api_key_ref: Optional[str] = None
    base_url: Optional[str] = None
    org_id: Optional[str] = None
    enabled: bool = True
    default_model: Optional[str] = None
    deployment_mode: Optional[str] = None
    project_id: Optional[str] = None
    vertex_location: Optional[str] = None
    vertex_auth_mode: Optional[str] = None
    enabled_models: List[str] = Field(default_factory=list)

    # NEW — shared/ai gateway fields
    embedding_model: Optional[str] = None          # e.g. "text-embedding-005" (Google), None = provider default
    vertex_claude_location: Optional[str] = None   # Region for Claude on Model Garden (e.g. "us-east5")
```

These are provider-specific so they belong in `ProviderSettings`, not in a new namespace.

### 2.3 New `AINamespace` (in `dashboard/models.py`)

Gateway-specific settings that aren't provider-bound:

```python
class AINamespace(BaseModel):
    """Shared AI gateway configuration."""

    # Per-purpose model overrides (if set, these override providers.google.default_model)
    completion_model: Optional[str] = None         # Default: providers.google.default_model
    knowledge_model: Optional[str] = None          # Model for knowledge graph (e.g. "vertex_ai/claude-sonnet-4-5-20251022")
    memory_model: Optional[str] = None             # Model for memory analysis (e.g. "vertex_ai/gemini-3-flash-preview")

    # Embedding
    cloud_embedding_model: str = "text-embedding-005"
    local_embedding_model: str = "all-MiniLM-L6-v2"

    # Runtime
    timeout_seconds: int = 60
    max_retries: int = 2

class MasterSettings(BaseModel):
    providers: ProvidersNamespace = Field(default_factory=ProvidersNamespace)
    roles: Dict[str, RoleSettings] = Field(default_factory=dict)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    channels: ChannelsNamespace = Field(default_factory=ChannelsNamespace)
    autonomy: AutonomySettings = Field(default_factory=AutonomySettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    ai: AINamespace = Field(default_factory=AINamespace)      # ← NEW
```

Patched via `PUT /api/settings/ai` — the existing `patch_global_namespace()` handler works automatically since it accepts any namespace in `_VALID_NAMESPACES`.

### 2.4 Config resolution priority

```
shared/ai/config.py resolves each field:

1. MasterSettings.ai.completion_model        (per-purpose override, highest priority)
2. MasterSettings.providers.google.default_model  (provider default)
3. Environment variable (LLM_MODEL)          (fallback for standalone MCP)
4. Hardcoded default ("gemini-3-flash-preview")   (lowest priority)
```

Example: knowledge graph wants Claude, memory wants Gemini:

```json
{
  "providers": {
    "google": {
      "deployment_mode": "vertex",
      "default_model": "gemini-3-flash-preview",
      "vertex_location": "global"
    },
    "anthropic": {
      "vertex_claude_location": "us-east5"
    }
  },
  "ai": {
    "completion_model": "gemini-3-flash-preview",
    "knowledge_model": "vertex_ai/claude-sonnet-4-5-20251022",
    "memory_model": "vertex_ai/gemini-3-flash-preview",
    "cloud_embedding_model": "text-embedding-005",
    "local_embedding_model": "all-MiniLM-L6-v2",
    "timeout_seconds": 60,
    "max_retries": 2
  }
}
```

### 2.5 How callers use per-purpose models

```python
# memory_system.py — uses ai.memory_model (or falls back to ai.completion_model)
from shared.ai import get_completion
response = get_completion(prompt, response_format=...)
# config.py resolves: ai.memory_model → "vertex_ai/gemini-3-flash-preview"

# knowledge/llm.py — uses ai.knowledge_model
response = get_completion(prompt, system=system, purpose="knowledge")
# config.py resolves: ai.knowledge_model → "vertex_ai/claude-sonnet-4-5-20251022"
```

The `purpose` parameter (optional) selects the per-purpose model:

```python
def get_completion(prompt, *, purpose=None, model=None, **kwargs) -> str:
    cfg = get_config()
    if model:
        resolved_model = model  # explicit model wins
    elif purpose == "knowledge":
        resolved_model = cfg.knowledge_model or cfg.completion_model
    elif purpose == "memory":
        resolved_model = cfg.memory_model or cfg.completion_model
    else:
        resolved_model = cfg.completion_model
    ...
```

### 2.6 How config flows end-to-end

```
Dashboard UI (Settings page)
  │
  │  User sets:
  │    providers.google.deployment_mode = "vertex"
  │    providers.google.project_id = "igot-studio"
  │    providers.google.default_model = "gemini-3-flash-preview"
  │    providers.google.embedding_model = "text-embedding-005"
  │    providers.anthropic.vertex_claude_location = "us-east5"
  │    ai.knowledge_model = "vertex_ai/claude-sonnet-4-5-20251022"
  │    ai.timeout_seconds = 60
  │
  ▼
MasterSettings (Pydantic model, persisted to config.json)
  │
  ├─► SettingsVault stores API keys
  ├─► _sync_vertex_env() writes to ~/.ostwin/.env
  ├─► shared.ai.reset_config() invalidates cache
  │
  ▼
shared/ai/config.py reads from SettingsResolver
  │
  ├─► completion_model = "vertex_ai/gemini-3-flash-preview"
  ├─► knowledge_model = "vertex_ai/claude-sonnet-4-5-20251022"
  ├─► cloud_embedding_model = "vertex_ai/text-embedding-005"
  ├─► local_embedding_model = "local/all-MiniLM-L6-v2"
  └─► timeout = 60, max_retries = 2
  │
  ▼
Callers use get_completion() / get_embedding()
  │
  ▼
litellm → Vertex AI (Gemini or Claude) or SentenceTransformer (local)
```

One path. No duplication. Change any model in Settings UI → the right caller uses the new model immediately.

### How settings changes propagate to shared/ai

When the user patches providers via `PUT /api/settings/providers`, four things happen:

```
Dashboard UI → PUT /api/settings/providers
  │
  ├─1► SettingsResolver.patch_namespace("providers", value)  [persists to config.json]
  │
  ├─2► _sync_vertex_env(value)        [writes to ~/.ostwin/.env + os.environ]
  │
  ├─3► shared.ai.reset_config()       [invalidates cached AIConfig]     ← NEW
  │
  └─4► broadcaster.broadcast("settings_updated", {...})   [WebSocket to UI]
```

Step 3 is new. `reset_config()` invalidates the cached `AIConfig` singleton. The next `get_completion()` or `get_embedding()` call re-reads from `SettingsResolver`, picking up the new model/provider/auth.

**Implementation:** One line added to `dashboard/routes/settings.py`, inside `patch_global_namespace()`:

```python
if namespace == "providers":
    _sync_vertex_env(value)
    from shared.ai.config import reset_config
    reset_config()  # invalidate cached AI config so next call reads fresh settings
```

### How each runtime picks up changes

| Runtime | How it gets new config | Delay |
|---|---|---|
| **Dashboard process** (knowledge, zvec_store, `/api/ai/*` routes) | `reset_config()` clears cache → next call reads fresh settings | Immediate |
| **Bot TypeScript** | Calls `/api/ai/complete` on dashboard → dashboard has fresh config | Immediate |
| **Memory MCP server** (separate stdio process) | Reads env vars from `~/.ostwin/.env` at startup. `_sync_vertex_env()` writes to `.env`. | Next agent run (new MCP process loads new `.env`) |
| **OpenCode agents** (war-room) | `_try_opencode_sync()` writes to `opencode.json` + `auth.json`. Each agent spawns fresh. | Next agent run |

For the memory MCP server, there's no hot-reload of config mid-session. This is acceptable because:
1. MCP servers are short-lived stdio processes — one per agent session
2. Each new agent run spawns a new MCP process that loads the current `.env`
3. Settings changes during an active plan run take effect when the next agent starts

If hot-reload is needed later, the MCP server can watch `~/.ostwin/.env` for changes (the dashboard already has `env_watcher.py` for this pattern).

### Settings UI controls for shared/ai

The dashboard Settings page already has provider configuration. After this plan, changing these fields directly affects all AI calls:

| Settings field | shared/ai behavior |
|---|---|
| `providers.google.deployment_mode = "vertex"` | `AIConfig.provider = "vertex_ai"` → litellm uses Vertex AI endpoint |
| `providers.google.deployment_mode = "gemini"` | `AIConfig.provider = "gemini"` → litellm uses AI Studio endpoint |
| `providers.google.default_model` | Default model for all `get_completion()` calls |
| `providers.google.project_id` | Vertex AI project for ADC |
| `providers.google.vertex_location` | Vertex AI region |
| `providers.google.vertex_auth_mode = "oauth"` | Uses ADC (`~/.config/gcloud/application_default_credentials.json`) |
| `providers.google.vertex_auth_mode = "service_account"` | Uses service account JSON from vault |
| `providers.anthropic.api_key_ref` | API key for `vertex_ai/claude-*` (or direct Anthropic if not on Vertex) |

No new Settings UI needed. The existing provider config page already has all these fields. The gateway just reads them.

---

## Part 3: Every Caller — Before and After

### Python callers (in-process, no HTTP)

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

### TypeScript callers (HTTP to dashboard /api/ai/*)

| # | File | Before | After |
|---|---|---|---|
| 9 | `agent-bridge.ts` | `new GoogleGenerativeAI(key).getGenerativeModel({tools}).startChat({history}).sendMessage(q)` | `complete({ messages, tools })` — same dispatch loop, no Google SDK |
| 10 | `audio-transcript.ts` | `new GoogleGenerativeAI(key).getGenerativeModel({...}).generateContent(...)` | `getCompletion(prompt)` |

### What import changes

```python
# Python — every caller
from shared.ai import get_completion, get_embedding
```

```typescript
// TypeScript — every caller
import { complete, getCompletion, getEmbedding } from './ai-gateway';
```

---

## Part 4: What Gets Deleted

| File | Lines | Why |
|---|---|---|
| `memory/agentic_memory/llm_controller.py` | ~570 | 6 controller classes → `get_completion()` |
| `memory/agentic_memory/retrievers.py` | ~30 | Embedding classes → `get_embedding()` |
| `dashboard/knowledge/llm.py` | ~30 | Anthropic SDK → `get_completion()` |
| `dashboard/knowledge/embeddings.py` | ~15 | SentenceTransformer init → `get_embedding()` |
| `dashboard/zvec_store.py` | ~10 | SentenceTransformer init → `get_embedding()` |
| `bot/package.json` | 1 | `@google/generative-ai` dependency removed |
| **Total** | **~655** | |

---

## Part 5: Implementation Phases

### Phase 1: Build `shared/ai/` module + dashboard routes

Files created:
```
.agents/shared/ai/__init__.py, config.py, completion.py, embedding.py, retry.py, errors.py
.agents/shared/ai/tests/test_completion.py, test_embedding.py, test_config.py
dashboard/routes/ai.py
bot/src/ai-gateway.ts, bot/src/__tests__/ai-gateway.test.ts
```

Register `ai.router` in `dashboard/api.py`.

**Exit criteria:** All gateway tests pass (mocked). Dashboard `/api/ai/complete` and `/api/ai/embed` return correct responses. TypeScript client tests pass.

### Phase 2: Migrate Python callers

1. Memory: `llm_controller.llm.get_completion()` → `get_completion()`
2. Memory: embedding classes → `get_embedding()` lambdas
3. Knowledge: `anthropic.Anthropic()` → `get_completion()`
4. Knowledge: `KnowledgeEmbedder` → `get_embedding()`
5. zvec_store: `SentenceTransformer` → `get_embedding()`

**Exit criteria:** 84 memory + 18 knowledge + dashboard tests pass.

### Phase 3: Migrate TypeScript callers

1. `audio-transcript.ts` → `getCompletion()`
2. `agent-bridge.ts` → `complete({ messages, tools })`
3. Remove `@google/generative-ai` from `package.json`

**Exit criteria:** 373 bot tests pass, tsc clean.

### Phase 4: Delete dead code

1. Delete `llm_controller.py`
2. Remove `anthropic`, `openai` SDK imports
3. Remove `@google/generative-ai` dependency

### Phase 5: Verify full unification

```bash
grep -r "google/generative-ai" bot/src/     # → zero
grep -r "import anthropic" dashboard/       # → zero
grep -r "from openai import" .agents/       # → zero
grep -r "llm_controller" .agents/memory/    # → zero
```

All AI calls trace to `shared/ai/` or `/api/ai/*`. All config comes from `MasterSettings.providers`.

---

## Part 6: Standalone Mode (MCP server without dashboard)

The memory MCP server runs as a stdio process — the dashboard may not be running. `config.py` handles this:

```python
def get_config() -> AIConfig:
    try:
        return _load_from_settings()   # Dashboard available → read MasterSettings
    except Exception:
        return _load_from_env()        # Standalone → read env vars
```

In standalone mode, the env vars set by `_sync_vertex_env()` are already in `~/.ostwin/.env`. The MCP server loads `.env` on startup. So even without the dashboard, the config is correct because the settings system already synced to env.

---

## Part 7: Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Dashboard not running when bot calls `/api/ai/*` | High | Bot already depends on dashboard for everything. This adds no new dependency. |
| `SettingsResolver` import fails in MCP server | Medium | Graceful fallback to env vars (already synced by settings). |
| litellm function-calling format differs between providers | Low | litellm normalizes tool calling across Gemini/Claude/GPT natively. |
| Claude not on Vertex in target region | Medium | Configurable model, falls back to Gemini. |
| SentenceTransformer cold start | Low | Pre-load on first call, cached for process lifetime. |

---

## Part 8: Size Summary

| Category | Lines |
|---|---|
| New: `shared/ai/` module | +300 |
| New: `dashboard/routes/ai.py` | +60 |
| New: `bot/src/ai-gateway.ts` | +80 |
| New: tests (Python + TS) | +150 |
| Deleted: `llm_controller.py` | -570 |
| Deleted: embedding classes, SDKs | -100 |
| Caller changes | ~80 |
| **Net** | **-80 lines** |

Less code. No new processes. Integrated with existing settings. 10/10 call sites unified.
