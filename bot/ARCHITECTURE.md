# Bot Architecture — OS Twin Unified Bot Gateway

This document describes the architecture of the OS Twin bot, which serves as the user-facing interface to the Ostwin multi-agent war-room orchestrator. Users interact with it through Discord, Telegram, or Slack.

---

## Overview

```
User (Discord / Telegram / Slack)
  │
  ├─ Slash command (/status, /plans, /draft, /clear, ...)
  │     └─► routeCommand() → hardcoded handlers (instant, no AI)
  │
  └─ Free text (@mention on Discord, any text on Telegram)
        └─► askAgent() → Gemini AI with function-calling tools
              │
              ├─ Reads session.chatHistory (persistent)
              ├─ Fetches live plan/room data from dashboard API
              ├─ Gemini decides which tool(s) to call
              ├─ Executes tool calls (up to 5 rounds)
              ├─ Returns text response to user
              └─ Saves conversation turn to session
```

## Key Components

### Connectors (`src/connectors/`)

Platform adapters that receive messages and route them.

| Connector | Trigger for AI | Trigger for commands |
|---|---|---|
| `discord.ts` | `@mention` the bot | Slash commands (`/status`) |
| `telegram.ts` | Any non-command text | `/command` messages |
| `slack.ts` | App mentions | Slash commands |

All connectors follow the same pattern:
1. Receive message from platform
2. If slash command → `routeCommand()` (hardcoded handlers in `commands.ts`)
3. If free text → `askAgent()` (AI with tool-calling)

There is **no editing mode routing**. All free-text messages go through the same AI agent path regardless of session state. The AI decides whether to refine a plan, check status, or answer a question based on the message content and available tools.

### Agent Bridge (`src/agent-bridge.ts`)

The core AI engine. Every free-text message flows through `askAgent()`:

```
askAgent(question, context)
  │
  ├─ 1. Load session & chat history
  │     session = getSession(userId, platform)
  │     history = session.chatHistory.slice(-20)  // last 10 turns
  │
  ├─ 2. Sanitize history for Gemini
  │     - Merge consecutive same-role messages
  │     - Ensure history starts with "user"
  │     - Map "assistant" → "model" role
  │     - Wrap content in parts[] format
  │
  ├─ 3. Fetch live context (parallel)
  │     - api.getPlans()  → current plans list
  │     - api.getRooms()  → war-room statuses
  │
  ├─ 4. Build system prompt
  │     - OS Twin identity and rules
  │     - Current plans summary
  │     - Active war-rooms summary
  │     - Active plan context (if user has one selected)
  │     - Referenced message (if replying to bot)
  │     - Attachment metadata (if files staged)
  │
  ├─ 5. Call Gemini with history + tools
  │     model.startChat({
  │       history: geminiHistory,     // conversation memory
  │       systemInstruction: prompt,  // live context
  │       tools: toolDeclarations,    // 13 available tools
  │     })
  │
  ├─ 6. Function-calling loop (up to 5 rounds)
  │     Gemini may call tools → execute → send results back → repeat
  │
  ├─ 7. Persist conversation turn
  │     session.chatHistory.push(user message)
  │     session.chatHistory.push(assistant response)
  │     Trim to 50 messages max
  │     persistAfterMessage() → debounced write to disk
  │
  └─ 8. Return response (truncated to 1900 chars for Discord)
```

### Available Tools

The AI agent has 13 tools it can call autonomously:

| Tool | Purpose | Example trigger |
|---|---|---|
| `list_plans` | List all plans with status and completion % | "show all plans" |
| `get_plan_status` | Detailed status of a specific plan | "what's the status of gold-mining?" |
| `create_plan` | Draft a new plan from a user idea | "build me a todo app" |
| `refine_plan` | Modify an existing plan | "add authentication to EPIC-002" |
| `launch_plan` | Start a plan (spawn war-rooms) | "launch the gold mining plan" |
| `resume_plan` | Resume a failed plan | "retry the failed plan" |
| `get_war_room_status` | War-room progress and stats | "are agents still working?" |
| `get_logs` | Read war-room channel messages | "what are the agents saying?" |
| `get_health` | System health check | "is the system running?" |
| `search_skills` | Search ClawHub skill marketplace | "find a web search skill" |
| `get_plan_assets` | List artifacts/deliverables of a plan | "show me what was built" |
| `get_memories` | List knowledge notes saved by agents | "what did agents learn?" |

The AI reads the user's message and decides which tool(s) to call based on intent. No keyword matching or regex — Gemini's function-calling capability handles all routing decisions.

### Sessions (`src/sessions.ts`)

Persistent session storage keyed by `platform:userId`.

```
~/.ostwin/sessions.json
{
  "discord:123456789": {
    "userId": "123456789",
    "platform": "discord",
    "activePlanId": "gold-mining.plan",
    "mode": "idle",
    "chatHistory": [
      { "role": "user", "content": "is the plan running?" },
      { "role": "assistant", "content": "The Gold Mining Game is 66.7% complete..." }
    ],
    "lastActivity": 1718456789000
  }
}
```

| Property | Purpose |
|---|---|
| `chatHistory` | Conversation memory, sent to Gemini on each call |
| `activePlanId` | Injected into system prompt so AI knows "the plan" |
| `mode` | Legacy field, effectively always "idle" now |
| `lastActivity` | Session expires after 30 min of inactivity |
| `pendingAttachments` | Staged files (not persisted to disk) |

**Persistence details:**
- Written to `~/.ostwin/sessions.json`
- Debounced writes every 2 seconds
- Atomic writes via tmp file + rename
- Survives bot restarts
- Sessions older than 30 minutes are discarded on load

**History limits:**
- Last 20 messages (10 turns) sent to Gemini per call
- Up to 50 messages persisted to disk per session
- Older messages are trimmed on each new turn

### Commands (`src/commands.ts`)

50+ slash commands with hardcoded handlers. These bypass the AI entirely for fast, deterministic responses.

Key commands:
- `/draft <idea>` — Enters editing mode, drafts a plan via `api.refinePlan()`
- `/edit` — Select a plan to edit
- `/cancel` — Exit editing mode, clear session
- `/clear` — Clear conversation history (keeps session/plan)
- `/status` — List running war-rooms
- `/plans` — List all plans
- `/startplan` — Launch a plan
- `/health` — System health check

### Slash Commands vs AI Agent

Both paths can accomplish the same tasks, but they serve different purposes:

| | Slash commands | AI agent (@mention) |
|---|---|---|
| **Speed** | Instant (no AI call) | 1-3 seconds |
| **Intelligence** | Hardcoded logic | LLM-powered decisions |
| **Memory** | No conversation context | Sees last 10 turns |
| **Multi-step** | One action per command | Can chain multiple tools |
| **Plan refinement** | `/draft` enters editing mode | AI calls `refine_plan` tool |
| **Status queries** | `/status` returns formatted list | AI interprets and summarizes |

---

## Message Flow Diagrams

### Discord: @mention

```
User sends: "@os-twin is the plan running?"
  │
  discord.ts: messageCreate event
  │
  ├─ message.author.bot? → skip
  ├─ allowedChannels check → skip if restricted
  ├─ isMention? → YES
  │
  ├─ Strip bot mention from text
  │   question = "is the plan running?"
  │
  └─► askAgent(question, { userId, platform: 'discord' })
        │
        ├─ Load session history (last 10 turns)
        ├─ Fetch live plans & rooms from dashboard
        ├─ Gemini decides: call get_war_room_status tool
        ├─ Execute tool → returns room data
        ├─ Gemini generates text response
        ├─ Save turn to session.chatHistory
        │
        └─► message.reply("The Gold Mining Game is 66.7% complete...")
```

### Discord: Slash command

```
User sends: /status
  │
  discord.ts: interactionCreate event
  │
  ├─ isChatInputCommand? → YES
  ├─ commandName = "status"
  │
  └─► routeCommand(userId, 'discord', 'status', '')
        │
        └─► commands.ts: cmdStatus()
              │
              └─► api.getRooms() → format response → return
```

### Telegram: Free text

```
User sends: "what memories were saved?"
  │
  telegram.ts: bot.on('text')
  │
  ├─ Starts with '/'? → NO (not a command)
  │
  └─► askAgent(msgText, { userId, platform: 'telegram' })
        │
        ├─ Gemini decides: call get_memories tool
        ├─ Execute tool → fetch /api/amem/{plan_id}/notes
        ├─ Gemini generates summary
        │
        └─► ctx.reply("Found 6 memory notes for the plan...")
```

---

## Session Lifecycle

```
Bot starts
  │
  └─ _loadFromDisk() → restore sessions from ~/.ostwin/sessions.json
       │
       └─ Discard sessions older than 30 min

User sends first message
  │
  └─ getSession() → creates new session
       {
         mode: 'idle',
         chatHistory: [],
         activePlanId: null,
         lastActivity: Date.now()
       }

User creates a plan via AI
  │
  └─ askAgent() → Gemini calls create_plan tool
       │
       └─ Session updated:
            activePlanId = "new-plan-id"
            chatHistory = [
              { user: "build me a todo app" },
              { assistant: "I've created a plan..." }
            ]

User asks follow-up
  │
  └─ askAgent() sees activePlanId in system prompt
       Gemini knows "the plan" = "new-plan-id"
       History includes the creation conversation

User types /clear
  │
  └─ chatHistory = []  (plan context remains)

User types /cancel
  │
  └─ Entire session reset (history, plan, mode)

30 minutes of inactivity
  │
  └─ Next getSession() creates fresh session
```

---

## Configuration

The bot reads config from multiple sources (first match wins):

1. `~/.ostwin/.env` — API keys, tokens
2. `./.env` — CWD overrides
3. `../env` — project root fallback

Key environment variables:

| Variable | Purpose | Required |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini API for AI agent | Yes |
| `DISCORD_TOKEN` | Discord bot token | For Discord |
| `DISCORD_CLIENT_ID` | Discord application ID | For Discord |
| `GUILD_ID` | Discord server ID | For Discord |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | For Telegram |
| `DASHBOARD_URL` | Dashboard API URL (default: `http://localhost:9000`) | No |
| `OSTWIN_API_KEY` | Dashboard authentication | Yes |
| `GEMINI_MODEL` | Model name (default: `gemini-3-flash-preview`) | No |

---

## Dependencies

The bot requires:
- **Dashboard running** on port 9000 — for plan/room/asset/memory APIs
- **Google API key** — for Gemini AI agent
- **Platform token** — for Discord/Telegram/Slack connection

If the dashboard is down:
- Slash commands that query APIs will fail gracefully
- AI agent tool calls will return errors
- The bot itself stays connected to Discord/Telegram
- WebSocket notifications will retry every 5 seconds (non-blocking)

---

## File Structure

```
bot/
├── src/
│   ├── index.ts              ← Entry point, registers connectors
│   ├── config.ts             ← Loads env vars from .env files
│   ├── agent-bridge.ts       ← AI agent with Gemini tool-calling
│   ├── commands.ts           ← 50+ slash command handlers
│   ├── sessions.ts           ← Persistent session storage
│   ├── api.ts                ← Dashboard API client
│   ├── asset-staging.ts      ← File attachment buffer
│   ├── audio-transcript.ts   ← Voice transcription
│   ├── notifications.ts      ← Dashboard WebSocket listener
│   └── connectors/
│       ├── base.ts           ← Connector interface
│       ├── registry.ts       ← Connector lifecycle manager
│       ├── discord.ts        ← Discord adapter
│       ├── telegram.ts       ← Telegram adapter
│       ├── slack.ts          ← Slack adapter
│       └── utils.ts          ← Shared utilities
├── package.json
├── tsconfig.json
└── ARCHITECTURE.md           ← This file
```
