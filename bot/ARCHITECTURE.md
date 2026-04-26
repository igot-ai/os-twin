# Bot Architecture — OS Twin Unified Bot Gateway

The OS Twin bot is the **user-facing interface** to the Ostwin multi-agent war-room orchestrator. Internally referred to as "master" by the team, it is the single entry point through which end-users manage projects, monitor agents, and query knowledge — all from Discord, Telegram, or Slack.

The bot is **not** an ostwin agent role. It's a standalone Node.js/TypeScript application that calls the Gemini SDK directly for AI capabilities and the dashboard REST API for data.

---

## System Context

```
                                    Ostwin System
                          ┌─────────────────────────────────┐
 Discord ──┐              │                                 │
            │             │  ┌─────────────┐                │
 Telegram ──┼── Bot ──────┼─►│ Dashboard   │◄── install.sh  │
            │  (Node.js)  │  │ (FastAPI)   │    compiles     │
 Slack ─────┘             │  │ :9000       │    configs       │
                          │  └──────┬──────┘                │
              Gemini SDK  │         │                        │
              (AI brain)  │         ▼                        │
                          │  ┌─────────────────┐            │
                          │  │ War-Room Engine  │            │
                          │  │ (PowerShell)     │            │
                          │  │                  │            │
                          │  │  ┌──────────┐   │            │
                          │  │  │ opencode │   │            │
                          │  │  │ agents   │   │            │
                          │  │  │          │   │            │
                          │  │  │ engineer │   │            │
                          │  │  │ qa       │   │            │
                          │  │  │ architect│   │            │
                          │  │  └──────────┘   │            │
                          │  └─────────────────┘            │
                          │         │                        │
                          │         ▼                        │
                          │  ┌─────────────┐                │
                          │  │ Memory MCP  │                │
                          │  │ .memory/    │                │
                          │  └─────────────┘                │
                          └─────────────────────────────────┘

 The bot talks to the Dashboard API only — never directly to
 war-rooms, agents, or the memory MCP server. The dashboard
 serves as the single gateway to all backend data.
```

---

## High-Level Architecture

```
User (Discord / Telegram / Slack)
  │
  ├─ Slash command (/status, /plans, /draft, /clear, ...)
  │     └─► routeCommand() → hardcoded handlers (instant, no AI)
  │
  ├─ Button click (inline keyboard callbacks)
  │     └─► routeCallback() → hardcoded handlers
  │
  └─ Free text (@mention on Discord, any text on Telegram)
        └─► askAgent() → Gemini AI with function-calling tools
              │
              ├─ Reads session.chatHistory (persistent, last 10 turns)
              ├─ Fetches live plan/room data from dashboard API
              ├─ Gemini decides which tool(s) to call
              ├─ Executes tool calls (up to 5 rounds)
              ├─ Collects file attachments (e.g. memory graph PNG)
              ├─ Saves conversation turn to session
              │
              └─ Returns { text, attachments? } to connector
                    │
                    ├─ Discord: message.reply({ content, files })
                    └─ Telegram: ctx.reply() + ctx.replyWithPhoto()
```

---

## Connectors (`src/connectors/`)

Platform adapters that receive messages and route them. Each connector translates platform-specific events into a common flow.

| Connector | AI trigger | Command trigger | File attachments |
|---|---|---|---|
| `discord.ts` | `@mention` the bot | Slash commands (`/status`) | `AttachmentBuilder` |
| `telegram.ts` | Any non-command text | `/command` messages | `ctx.replyWithPhoto()` |
| `slack.ts` | App mentions | Slash commands | Not yet implemented |

### Connector Lifecycle

```
Bot starts (index.ts)
  │
  └─ registry.startAll()
       │
       ├─ discord.start(config)
       │     ├─ client.login(token)
       │     ├─ deployCommands(token, clientId, guildId)
       │     ├─ Register event handlers:
       │     │     messageCreate → route @mentions to askAgent()
       │     │     interactionCreate → route slash commands to routeCommand()
       │     └─ voiceStateUpdate → voice channel tracking
       │
       ├─ telegram.start(config)
       │     ├─ Register command handlers → routeCommand()
       │     ├─ Register text handler → askAgent()
       │     ├─ Register file handlers → asset staging
       │     └─ bot.launch() (polling mode)
       │
       └─ slack.start(config)
             └─ (similar pattern)
```

### Discord Message Routing (detailed)

```
messageCreate event
  │
  ├─ Ignore if: bot author, system message, outside allowed channels
  │
  ├─ Extract: userId, session, attachments, isMention
  │
  ├─ Process file attachments → stage for later use
  │
  ├─ Is @mention?
  │     │
  │     ├─ YES:
  │     │     ├─ Strip bot mention from text
  │     │     ├─ Build agent context (userId, platform, referenced msg, attachments)
  │     │     ├─ askAgent(question, context)
  │     │     │     └─ Returns { text, attachments? }
  │     │     ├─ Build reply:
  │     │     │     content: result.text
  │     │     │     files: result.attachments → AttachmentBuilder[]
  │     │     └─ message.reply(replyOptions)
  │     │
  │     └─ NO:
  │           └─ (non-mention messages are ignored in Discord)
  │
  └─ After reply: flush any staged file attachments to the plan
```

### Telegram Message Routing (detailed)

```
bot.on('text') event
  │
  ├─ Starts with '/'? → skip (handled by command handlers)
  │
  ├─ askAgent(msgText, { userId, platform: 'telegram', attachments })
  │     └─ Returns { text, attachments? }
  │
  ├─ ctx.reply(result.text)
  │
  ├─ For each result.attachment:
  │     └─ ctx.replyWithPhoto({ source: buffer, filename: name })
  │
  └─ Flush staged file attachments if plan now exists
```

---

## Agent Bridge (`src/agent-bridge.ts`)

The core AI engine. Every free-text message flows through `askAgent()`.

### `askAgent()` Flow

```
askAgent(question, context) → Promise<AgentResponse>
  │
  ├─ 1. Reset _pendingAttachments = []
  │
  ├─ 2. Load session & chat history
  │     session = getSession(userId, platform)
  │     recentHistory = session.chatHistory.slice(-20)  // last 10 turns
  │
  ├─ 3. Sanitize history for Gemini
  │     sanitizeHistory():
  │       - Merge consecutive same-role messages
  │       - Ensure history starts with "user" role
  │     toGeminiHistory():
  │       - Map "assistant" → "model" (Gemini's role name)
  │       - Wrap content in parts: [{ text }] format
  │
  ├─ 4. Fetch live context (parallel API calls)
  │     ┌─ api.getPlans()  → current plans list with status/completion
  │     └─ api.getRooms()  → active war-room statuses
  │
  ├─ 5. Build system prompt
  │     ┌─ Identity: "You are OS Twin..."
  │     ├─ Tool routing rules (CREATE → create_plan, STATUS → list_plans, etc.)
  │     ├─ ## Current Plans (live data)
  │     ├─ ## Active War-Rooms (live data)
  │     ├─ ## Active Plan (from session.activePlanId, if set)
  │     ├─ ## Referenced Message (if replying to bot message)
  │     └─ ## Attached Files (if user sent files with the message)
  │
  ├─ 6. Start Gemini chat session
  │     model.startChat({
  │       history: geminiHistory,        // persistent conversation memory
  │       systemInstruction: systemPrompt // live context + rules
  │       tools: toolDeclarations        // 12 function-calling tools
  │     })
  │
  ├─ 7. Send user's question
  │     chat.sendMessage(question)
  │
  ├─ 8. Function-calling loop (up to 5 rounds)
  │     ┌─ Check response.functionCalls()
  │     ├─ If tools requested:
  │     │     ├─ Execute all tool calls in parallel
  │     │     │     └─ executeTool(call, ctx) → { name, response }
  │     │     │           (tools may push to _pendingAttachments)
  │     │     ├─ Send function responses back to Gemini
  │     │     └─ Repeat loop
  │     └─ If no tools: extract text response, exit loop
  │
  ├─ 9. Persist conversation turn
  │     session.chatHistory.push({ role: 'user', content: question })
  │     session.chatHistory.push({ role: 'assistant', content: answer })
  │     Trim to MAX_PERSISTED_MESSAGES (50)
  │     persistAfterMessage() → debounced 2s write to disk
  │
  └─ 10. Return AgentResponse
        {
          text: answer (truncated to 1900 chars for Discord),
          attachments: _pendingAttachments or undefined
        }
```

### Return Type

```typescript
interface AgentResponse {
  text: string;
  attachments?: Array<{ buffer: Buffer; name: string }>;
}
```

The `attachments` array is populated by tools during execution. Currently only `get_memories` produces attachments (the memory graph PNG). Connectors handle attachments per-platform:

- **Discord**: `AttachmentBuilder(buffer, { name })` — appears as embedded file
- **Telegram**: `ctx.replyWithPhoto({ source: buffer })` — appears as inline image

### Available Tools

The AI agent has 12 tools it can call autonomously. Gemini reads the user's message and tool descriptions, then decides which tool(s) to invoke. No keyword matching or regex — pure LLM function-calling.

#### Plan Management

| Tool | Description | API Endpoint |
|---|---|---|
| `list_plans` | List all plans with status and completion % | `GET /api/plans` |
| `get_plan_status` | Detailed status of a specific plan | `GET /api/plans/{id}` + `GET /api/plans/{id}/epics` |
| `create_plan` | Draft a new plan from a user idea | `POST /api/plans/create` |
| `refine_plan` | Modify an existing plan (add features, change epics) | `POST /api/plans/refine` + `POST /api/plans/{id}/save` |
| `launch_plan` | Start a plan — spawn war-rooms for each epic | `POST /api/plans/{id}/launch` |
| `resume_plan` | Resume a failed/stopped plan | `POST /api/plans/{id}/resume` |

#### Monitoring

| Tool | Description | API Endpoint |
|---|---|---|
| `get_war_room_status` | War-room progress, stats, completion rates | `GET /api/rooms` + `GET /api/stats` |
| `get_logs` | Read agent channel messages from a war-room | `GET /api/rooms/{id}/channel` |
| `get_health` | System health (manager, bot, war-rooms) | `GET /api/manager/status` + `GET /api/bot/status` |

#### Skills & Assets

| Tool | Description | API Endpoint |
|---|---|---|
| `search_skills` | Search ClawHub skill marketplace | `GET /api/skills/clawhub-search` |
| `get_plan_assets` | List artifacts/deliverables produced by a plan | `GET /api/plans/{id}/assets` |

#### Memory & Knowledge

| Tool | Description | API Endpoints | Attachments |
|---|---|---|---|
| `get_memories` | List knowledge notes, directory tree, and graph visualization | `GET /api/amem/{id}/notes` | `memory-graph.png` |
| | | `GET /api/amem/{id}/stats` | |
| | | `GET /api/amem/{id}/tree` | |
| | | `GET /api/amem/{id}/graph-image` | |

The `get_memories` tool is unique — it fetches 4 endpoints in parallel and produces a file attachment (the memory graph PNG). The tool response includes:

```
{
  success: true,
  total_notes: 12,
  has_graph_image: true,
  directory_tree: "├── architecture\n│   └── gold-mining\n│       └── ...",
  stats: { total_tags, total_keywords, categories },
  memories: [{ title, path, tags, keywords, excerpt, links_count }, ...],
  message: "Found 12 memory note(s)..."
}
```

Gemini uses this data to compose a rich text response. The connector then attaches the PNG alongside the text.

### Tool Execution Flow (get_memories example)

```
User: "@os-twin what did the agents learn about gold-mining.plan?"
  │
  ▼
askAgent()
  │
  ├─ Gemini sees: user question + get_memories tool description
  ├─ Gemini decides: call get_memories({ plan_id: "gold-mining.plan" })
  │
  ▼
executeTool("get_memories", { plan_id: "gold-mining.plan" })
  │
  ├─ Parallel fetch:
  │     ├─ GET /api/amem/gold-mining.plan/notes    → 12 notes (titles, tags, excerpts)
  │     ├─ GET /api/amem/gold-mining.plan/stats    → tag/keyword counts
  │     ├─ GET /api/amem/gold-mining.plan/tree     → directory tree string
  │     └─ GET /api/amem/gold-mining.plan/graph-image → 200KB PNG
  │
  ├─ Push graph PNG to _pendingAttachments
  │
  └─ Return tool response to Gemini
       │
       ▼
Gemini composes text response using the tool data:
  "Found 12 memory notes for gold-mining.plan.
   Categories: Architecture (1), Code (9), Documentation (2)
   
   Key memories:
   - Gold Mining Game Architecture (architecture/gold-mining)
   - src/GameEngine.ts — Core game logic (code/game-engine)
   ...
   
   Directory tree:
   ├── architecture/...
   ├── code/...
   └── documentation/..."
  │
  ▼
Discord connector sends:
  ├─ Text: Gemini's formatted response
  └─ File: memory-graph.png (attached via AttachmentBuilder)
```

---

## Sessions (`src/sessions.ts`)

Persistent session storage keyed by `platform:userId`.

### Data Structure

```json
// ~/.ostwin/sessions.json
{
  "discord:123456789": {
    "userId": "123456789",
    "platform": "discord",
    "activePlanId": "gold-mining.plan",
    "mode": "idle",
    "chatHistory": [
      { "role": "user", "content": "is the plan running?" },
      { "role": "assistant", "content": "The Gold Mining Game is 66.7% complete..." },
      { "role": "user", "content": "show me what agents learned" },
      { "role": "assistant", "content": "Found 12 memory notes..." }
    ],
    "lastActivity": 1718456789000,
    "workingDir": "/home/user/projects/gold-mining"
  },
  "telegram:987654321": {
    "...": "separate session, separate history"
  }
}
```

### Session Fields

| Field | Purpose | Used by |
|---|---|---|
| `chatHistory` | Conversation memory — last 10 turns sent to Gemini | `askAgent()`, `handleStatefulText()` |
| `activePlanId` | Injected into system prompt — AI knows "the plan" | `askAgent()` system prompt |
| `mode` | `idle`, `editing`, `drafting`, `awaiting_idea` | Slash command routing |
| `workingDir` | Target directory for new plans | `create_plan`, `refine_plan` tools |
| `lastActivity` | Timestamp for session expiry | `getSession()` cleanup |
| `pendingAttachments` | Staged files (not persisted to disk) | Asset upload flow |

### Persistence

| Property | Value |
|---|---|
| **Storage** | `~/.ostwin/sessions.json` |
| **Write strategy** | Debounced every 2 seconds |
| **Write method** | Atomic (write to tmp file, then `rename()`) |
| **Survives restarts** | Yes — `_loadFromDisk()` on startup |
| **Session TTL** | 30 minutes of inactivity |
| **Cleanup** | Expired sessions discarded on load |

### History Limits

| Limit | Value | Reason |
|---|---|---|
| Sent to Gemini per call | 20 messages (10 turns) | Keep prompt size reasonable |
| Persisted to disk | 50 messages | Retain broader context |
| Session timeout | 30 minutes | Auto-reset stale sessions |

### Shared History

Both the AI agent (`askAgent()`) and plan-editing (`handleStatefulText()`) paths read and write to the **same** `chatHistory` array. This is intentional:

- After editing a plan via `/draft`, switching to `@mention` mode preserves context — the AI knows what you just drafted
- After asking status via `@mention`, switching to `/edit` preserves context — the plan editor knows what you discussed
- No confusing "which conversation am I in?" — one array, one context

### Session Lifecycle

```
Bot starts
  │
  └─ _loadFromDisk()
       ├─ Read ~/.ostwin/sessions.json
       ├─ Discard sessions older than 30 min
       └─ Log: "[SESSIONS] Restored N session(s) from disk"

User sends first message
  │
  └─ getSession("discord:12345")
       └─ Creates: { mode: 'idle', chatHistory: [], activePlanId: null }

User creates plan: "@os-twin build me a todo app"
  │
  └─ askAgent() → Gemini calls create_plan tool
       └─ Session: activePlanId = "abc123", chatHistory grows

User asks: "@os-twin is the plan running?"
  │
  └─ askAgent() sees activePlanId in prompt
       └─ Gemini knows "the plan" = "abc123"

User types /clear
  │
  └─ chatHistory = [] (activePlanId preserved)

User types /cancel
  │
  └─ Entire session reset to defaults

30 minutes pass with no activity
  │
  └─ Next getSession() creates fresh session (old one expired)
```

---

## Commands (`src/commands.ts`)

42 slash commands with hardcoded handlers. These bypass the AI entirely for instant, deterministic responses.

### Command Categories

#### Plans & AI
| Command | Description | Deferred |
|---|---|---|
| `/menu` | Main Control Center | |
| `/help` | Detailed user guide | |
| `/draft <idea>` | Draft a new Plan with AI | Yes |
| `/edit` | Select a plan to edit with AI | Yes |
| `/viewplan` | View a plan's content | Yes |
| `/startplan` | Select and launch a plan | Yes |
| `/resume` | Resume a failed or stopped plan | Yes |
| `/assets` | List assets for the active plan | Yes |
| `/transcribe` | Transcribe voice recording to plan | Yes |
| `/setdir <path>` | Set target project directory | |
| `/cancel` | Exit editing session, clear session | |
| `/clear` | Clear conversation history (keep session) | |
| `/feedback <text>` | Send feedback to dashboard | Yes |

#### Monitoring
| Command | Description | Deferred |
|---|---|---|
| `/dashboard` | Real-time War-Room progress | Yes |
| `/status` | List running War-Rooms | Yes |
| `/compact` | Latest messages from agents | Yes |
| `/errors` | Error summary with root causes | Yes |
| `/logs <room_id>` | View war-room channel messages | Yes |
| `/health` | System health check | Yes |
| `/progress` | Plan progress bars | Yes |
| `/plans` | List all project Plans | Yes |

#### Skills & Roles
| Command | Description | Deferred |
|---|---|---|
| `/skills` | View installed AI skills | Yes |
| `/skillsearch <query>` | Search ClawHub marketplace | Yes |
| `/skillinstall <slug>` | Install a skill from ClawHub | Yes |
| `/skillremove <name>` | Remove an installed skill | Yes |
| `/skillsync` | Sync skills with dashboard | Yes |
| `/roles` | List all agent roles | Yes |
| `/clonerole <role>` | Clone a role for local override | Yes |

#### System
| Command | Description | Deferred |
|---|---|---|
| `/usage` | Stats report | Yes |
| `/config [key]` | View system configuration | Yes |
| `/triage <room_id>` | Triage a failed war-room | Yes |

### Slash Commands vs AI Agent

| | Slash commands | AI agent (@mention) |
|---|---|---|
| **Speed** | Instant (no AI call) | 1-3 seconds |
| **Intelligence** | Hardcoded logic | LLM function-calling |
| **Memory** | No conversation context | Last 10 turns |
| **Multi-step** | One action per command | Chains multiple tools |
| **Attachments** | No | Yes (e.g. memory graph PNG) |
| **Plan refinement** | `/draft` enters editing mode | AI calls `refine_plan` tool |
| **Status queries** | `/status` returns formatted list | AI interprets and summarizes |

Both paths can accomplish the same tasks. Slash commands are shortcuts; the AI agent is the general-purpose interface.

---

## Dashboard API Integration (`src/api.ts`)

All data flows through the dashboard REST API at `http://localhost:9000`.

### API Client Functions

| Function | Method | Endpoint | Returns |
|---|---|---|---|
| `fetchJSON(path)` | GET | Any | Parsed JSON |
| `fetchBinary(path)` | GET | Any | `Buffer` (for images) |
| `postJSON(path, body)` | POST | Any | Parsed JSON |
| `getPlans()` | GET | `/api/plans` | Plan list with status |
| `getPlan(id)` | GET | `/api/plans/{id}` | Single plan |
| `getPlanEpics(id)` | GET | `/api/plans/{id}/epics` | Epic details |
| `refinePlan(params)` | POST | `/api/plans/refine` | Refined plan content |
| `createPlan(params)` | POST | `/api/plans/create` | New plan |
| `savePlan(id, content)` | POST | `/api/plans/{id}/save` | Save confirmation |
| `launchPlan(id, content)` | POST | `/api/plans/{id}/launch` | Launch result |
| `resumePlan(id)` | POST | `/api/plans/{id}/resume` | Resume result |
| `getPlanAssets(id)` | GET | `/api/plans/{id}/assets` | Asset list |
| `getRooms()` | GET | `/api/rooms` | War-room list |
| `getRoomChannel(id)` | GET | `/api/rooms/{id}/channel` | Channel messages |
| `getStats()` | GET | `/api/stats` | Aggregate statistics |
| `getManagerStatus()` | GET | `/api/manager/status` | Manager process info |
| `getBotStatus()` | GET | `/api/bot/status` | Bot process info |

### Authentication

Every request includes `X-API-Key: {OSTWIN_API_KEY}` header. The key is set in `~/.ostwin/.env`.

### Error Handling

All API functions return `{ _error: string }` on failure instead of throwing. This allows tools to return graceful error messages to Gemini, which then presents them to the user in natural language.

---

## Notifications (`src/notifications.ts`)

WebSocket connection to `ws://localhost:9000/api/ws` for real-time push updates.

```
Dashboard WebSocket
  │
  ├─ War-room status changes → forwarded to active Discord/Telegram channels
  ├─ Plan completion events → notification messages
  └─ Agent error events → alert messages
```

If the dashboard is down, the WebSocket reconnects every 5 seconds. This is non-blocking — the bot continues to function without push notifications.

---

## Asset Staging (`src/asset-staging.ts`)

When users send files (images, documents, code) before creating a plan, the bot stages them in memory and flushes them to the dashboard when a plan is created.

```
User sends screenshot.png
  │
  └─ stageStagedFile(userId, platform, fileData)
       └─ Held in memory (not persisted to disk)

User says: "@os-twin build a game based on this"
  │
  ├─ askAgent() → Gemini calls create_plan
  ├─ Plan created: plan_id = "abc123"
  │
  └─ flushStagedAttachments(userId, platform, planId)
       └─ POST /api/plans/abc123/assets (multipart upload)
```

---

## Configuration (`src/config.ts`)

The bot loads environment variables from multiple `.env` files via `dotenv`:

1. `~/.ostwin/.env` — Primary (API keys, tokens)
2. `./.env` — CWD overrides
3. `../.env` — Project root fallback

### Required Environment Variables

| Variable | Purpose | Required for |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini SDK for AI agent | All AI features |
| `OSTWIN_API_KEY` | Dashboard API authentication | All API calls |
| `DISCORD_TOKEN` | Discord bot token | Discord connector |
| `DISCORD_CLIENT_ID` | Discord application ID | Discord connector |
| `GUILD_ID` | Discord server ID (for command registration) | Discord connector |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | Telegram connector |
| `SLACK_BOT_TOKEN` | Slack bot token | Slack connector |
| `SLACK_APP_TOKEN` | Slack app-level token | Slack connector |

### Optional Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `DASHBOARD_URL` | `http://localhost:9000` | Dashboard API base URL |
| `GEMINI_MODEL` | `gemini-3-flash-preview` | Gemini model for AI agent |

---

## Runtime Dependencies

| Dependency | Purpose | Required? |
|---|---|---|
| **Dashboard** (:9000) | All API calls (plans, rooms, assets, memory) | Yes for data |
| **Google API Key** | Gemini AI agent | Yes for @mention AI |
| **Platform token** | Discord/Telegram/Slack connection | Yes for that platform |
| **matplotlib + networkx** | Memory graph PNG generation (in dashboard) | Yes for graph images |

### Degraded Operation

| Component down | Impact |
|---|---|
| Dashboard | Slash commands fail gracefully, AI tools return errors, bot stays connected |
| Gemini API | @mention AI fails, slash commands still work |
| WebSocket | No push notifications, bot retries every 5s silently |
| Memory API | `get_memories` returns error, other tools unaffected |

---

## File Structure

```
bot/
├── src/
│   ├── index.ts              ← Entry point, starts connectors via registry
│   ├── config.ts             ← Loads env vars from .env files
│   ├── agent-bridge.ts       ← AI agent: Gemini SDK + 12 function-calling tools
│   ├── commands.ts           ← 42 slash command handlers (no AI)
│   ├── sessions.ts           ← Persistent session storage (~/.ostwin/sessions.json)
│   ├── api.ts                ← Dashboard REST API client (fetchJSON, fetchBinary)
│   ├── asset-staging.ts      ← File attachment staging buffer
│   ├── audio-transcript.ts   ← Voice recording transcription
│   ├── notifications.ts      ← Dashboard WebSocket push listener
│   ├── deploy-commands.ts    ← One-shot: registers slash commands with Discord
│   └── connectors/
│       ├── base.ts           ← Connector interface (Platform, ConnectorConfig)
│       ├── registry.ts       ← Connector lifecycle manager (start/stop/health)
│       ├── discord.ts        ← Discord.js adapter (mentions, commands, voice)
│       ├── telegram.ts       ← Telegraf adapter (text, commands, files)
│       ├── slack.ts          ← Slack Bolt adapter
│       └── utils.ts          ← Shared: markdown conversion, chunking, asset type detection
├── package.json
├── tsconfig.json
└── ARCHITECTURE.md           ← This file
```

---

## Running the Bot

### First-time setup

```bash
cd ~/os-twin/bot
pnpm install
pnpm run deploy    # Register slash commands with Discord
```

### Start

```bash
DISCORD_TOKEN="..." DISCORD_CLIENT_ID="..." GUILD_ID="..." pnpm start
```

Or set variables in `~/.ostwin/.env` and just run `pnpm start`.

### Verify

- Console shows: `[DISCORD] Logged in as os-twin#0468`
- Console shows: `[NOTIFICATIONS] Connected to dashboard` (if dashboard is running)
- Console shows: `[SESSIONS] Restored N session(s) from disk` (if previous sessions exist)

### Test

- Discord: `@os-twin hello` → AI response
- Discord: `/status` → war-room list
- Discord: `@os-twin show me the memories for gold-mining.plan` → text + graph PNG
