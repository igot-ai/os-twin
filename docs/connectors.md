# Connector Architecture

The OS Twin bot uses a **plugin-driven connector architecture** to deliver a consistent command experience across Telegram, Discord, and Slack. Every connector implements the same interface, registers commands from a single shared registry, and routes user actions through a platform-agnostic command layer.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        index.ts (entry)                        │
│  Creates connectors → registers in registry → starts all       │
└────────────┬───────────────────┬──────────────────┬────────────┘
             │                   │                  │
    ┌────────▼───────┐  ┌───────▼────────┐  ┌──────▼───────┐
    │   Telegram      │  │   Discord       │  │   Slack       │
    │   Connector     │  │   Connector     │  │   Connector   │
    └────────┬───────┘  └───────┬────────┘  └──────┬───────┘
             │                   │                  │
             └───────────┬───────┴──────────┬───────┘
                         │                  │
               ┌─────────▼──────┐  ┌───────▼──────────┐
               │  commands.ts   │  │  agent-bridge.ts  │
               │  (shared       │  │  (AI Q&A via      │
               │   command       │  │   Gemini)         │
               │   router)       │  │                   │
               └─────────┬──────┘  └───────┬──────────┘
                         │                  │
                    ┌────▼──────────────────▼────┐
                    │         api.ts              │
                    │   (Dashboard REST client)   │
                    └────────────────────────────┘
```

## File structure

```
bot/src/connectors/
├── base.ts        # Connector interface + shared types
├── registry.ts    # ConnectorRegistry singleton (lifecycle manager)
├── discord.ts     # DiscordConnector implementation
├── telegram.ts    # TelegramConnector implementation
├── slack.ts       # SlackConnector implementation
└── utils.ts       # Shared utilities (markdown, chunking, asset typing)
```

Supporting files outside `connectors/`:

| File | Role |
|---|---|
| `commands.ts` | Central `COMMAND_REGISTRY`, `BotResponse` type, command implementations, `routeCommand()` / `routeCallback()` |
| `agent-bridge.ts` | Gemini-powered AI agent with function-calling tools |
| `api.ts` | Dashboard REST API client (46+ endpoints) |
| `sessions.ts` | In-memory per-user session state |
| `notifications.ts` | WebSocket listener that pushes dashboard events to users |
| `asset-staging.ts` | File attachment staging buffer (stage -> flush lifecycle) |
| `index.ts` | Entry point that wires everything together |

## The Connector interface

Every connector implements the `Connector` interface defined in `base.ts`:

```typescript
interface Connector {
  readonly platform: Platform;        // 'telegram' | 'discord' | 'slack'
  status: ConnectorStatus;            // 'disconnected' | 'connecting' | 'connected' | 'error'
  start(config: ConnectorConfig): Promise<void>;
  stop(): Promise<void>;
  healthCheck(): Promise<HealthCheckResult>;
  sendMessage(targetId: string, response: BotResponse): Promise<void>;
  getSetupInstructions(): SetupStep[];
  validateConfig(config: ConnectorConfig): ValidationResult;
}
```

Key supporting types:

- **`ConnectorConfig`** -- Carries credentials, settings, authorized users, pairing code, and notification preferences for a platform.
- **`HealthCheckResult`** -- `{ status: 'healthy' | 'unhealthy' | 'warning', message?, details? }`
- **`SetupStep`** -- Guided setup instructions (`{ title, description, instructions }`).
- **`ValidationResult`** -- `{ valid: boolean, errors?: string[] }`

## ConnectorRegistry

The `ConnectorRegistry` class in `registry.ts` is a **singleton** that manages the full lifecycle of all connectors:

```typescript
const registry = new ConnectorRegistry();

// 1. Register connector instances
registry.register(new TelegramConnector());
registry.register(new DiscordConnector());
registry.register(new SlackConnector());

// 2. Load persisted configs from ~/.ostwin/channels.json
await registry.loadConfigs();

// 3. Start all enabled connectors in parallel
await registry.startAll();

// 4. At shutdown, stop all connectors
await registry.stopAll();
```

The registry stores connectors in a `Map<Platform, Connector>` and configs in a `Map<Platform, ConnectorConfig>`. Configs are persisted to `~/.ostwin/channels.json` and can be updated at runtime via `updateConfig()`.

### Config seeding

On first startup, if no config exists for a platform but environment variables are set (e.g. `TELEGRAM_BOT_TOKEN`, `DISCORD_TOKEN`, `SLACK_BOT_TOKEN`), the entry point in `index.ts` seeds default configs into the registry automatically.

## COMMAND_REGISTRY -- Single source of truth

The `COMMAND_REGISTRY` in `commands.ts` is a single array of `CommandDef` objects that defines **every command** the bot supports. All three connectors import and iterate this array to auto-register their platform-specific command handlers.

```typescript
interface CommandDef {
  name: string;           // Command name (e.g. 'draft', 'status')
  description: string;    // Human-readable description
  arg?: string;           // Argument name, if the command accepts one
  argDescription?: string; // Hint text for the argument
  argRequired?: boolean;  // Whether the argument is mandatory (Discord slash commands)
  deferReply?: boolean;   // Whether Discord should show "thinking..." before running
  discordOnly?: boolean;  // If true, skip registration on Telegram/Slack
  telegramMenu?: string;  // Description shown in Telegram's /command quick-list
}
```

### Pre-computed views

To avoid each connector filtering the registry repeatedly, `commands.ts` exports pre-computed subsets:

| Export | Filter | Used by |
|---|---|---|
| `COMMANDS_WITH_ARGS` | Has `arg`, not `discordOnly` | Telegram, Slack |
| `COMMANDS_NO_ARGS` | No `arg`, not `discordOnly` | Telegram, Slack |
| `ALL_PLATFORM_COMMANDS` | Not `discordOnly` | Telegram (menu registration) |
| `TELEGRAM_MENU_COMMANDS` | Has `telegramMenu` | Telegram |
| `DEFERRED_COMMANDS` | Has `deferReply` (as a `Set`) | Discord |

### How each connector uses the registry

**Discord** iterates the full `COMMAND_REGISTRY` to build `SlashCommandBuilder` objects, adding string options for commands that define `arg`. It checks `DEFERRED_COMMANDS` to decide whether to call `interaction.deferReply()` before executing.

**Telegram** iterates `COMMANDS_NO_ARGS` and `COMMANDS_WITH_ARGS` separately to register handlers (argument-less commands use `ctx.command`, argument commands extract the arg from message text). It calls `setMyCommands` with `ALL_PLATFORM_COMMANDS` to populate Telegram's autocomplete menu.

**Slack** iterates `COMMANDS_WITH_ARGS` and `COMMANDS_NO_ARGS` to register individual slash commands (`/draft`, `/status`, etc.) plus the umbrella `/ostwin` command. It also handles button actions matching the pattern `^(menu|cmd|prefs|asset):`.

### Adding a new command

To add a new command that works on all platforms:

1. Add a `CommandDef` entry to `COMMAND_REGISTRY` in `commands.ts`.
2. Add a `case` to the `routeCommand()` switch statement in `commands.ts`.
3. If the command has interactive callbacks, add handlers in `routeCallback()`.

No changes are needed in any connector file -- they dynamically pick up new entries from the registry.

## Platform-agnostic response model

All command implementations return `BotResponse` objects:

```typescript
interface BotResponse {
  text: string;              // Message content (Markdown)
  buttons?: Button[][];      // Optional inline keyboard (rows of buttons)
  file?: { path: string; name: string }; // Optional file attachment
}

interface Button {
  label: string;
  callbackData: string;      // Callback identifier (e.g. 'cmd:status')
  url?: string;              // If set, renders as a URL button instead
}
```

Each connector translates `BotResponse` into its native format:

| Platform | Text | Buttons | Special handling |
|---|---|---|---|
| **Discord** | Sent as message content. `*bold*` converted to `**bold**` via `mdConvert()`. Chunked at 2000 chars. | Rendered as `ActionRowBuilder` with `ButtonBuilder` components. | Deferred replies for long-running commands. |
| **Telegram** | Sent with `parse_mode: 'Markdown'`. Chunked at 4096 chars. | Rendered as `Markup.inlineKeyboard()`. | Command menu registered via `setMyCommands`. |
| **Slack** | Converted to Block Kit `section` blocks. `**bold**` converted to `*bold*` for Slack mrkdwn. Links converted from `[label](url)` to `<url\|label>`. | Rendered as `actions` blocks with `button` elements. | Socket Mode for real-time events. |

## Command routing flow

```
User sends /draft "build a todo app"
        │
        ▼
┌───────────────────┐
│  Platform Connector│  (Telegram / Discord / Slack)
│  - Extracts command │
│  - Extracts args    │
│  - Checks auth      │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  routeCommand()   │  commands.ts
│  - Matches command │
│  - Calls handler   │
│  - Returns         │
│    BotResponse[]   │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Platform Connector│
│  - Translates to   │
│    native format   │
│  - Sends to user   │
└───────────────────┘
```

For button presses / callback actions:

```
User clicks a button (e.g. "Launch Plan")
        │
        ▼
┌───────────────────┐
│  Platform Connector│
│  - Extracts        │
│    callbackData    │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  routeCallback()  │  commands.ts
│  - Pattern matches │
│    callbackData    │
│  - Returns         │
│    BotResponse[]   │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Platform Connector│
│  - Sends response  │
└───────────────────┘
```

For free text (not a command):

```
User sends "what's the status of my project?"
        │
        ▼
┌───────────────────┐
│  Platform Connector│
│  - Checks session  │
│    mode            │
└────────┬──────────┘
         │
    ┌────┴────────────────┐
    │ Session is           │ Session is
    │ editing/drafting     │ idle
    ▼                      ▼
┌──────────────┐    ┌──────────────┐
│handleStateful│    │  askAgent()  │
│Text()        │    │  (Gemini AI  │
│(refine plan) │    │   + tools)   │
└──────────────┘    └──────────────┘
```

## Connector implementations

### TelegramConnector

- **Library:** Telegraf
- **Transport:** Long-polling (fire-and-forget `bot.launch()`)
- **Auth:** `/pair <code>` command + `authorized_users` list
- **Commands:** Registered via iteration over `COMMANDS_NO_ARGS` and `COMMANDS_WITH_ARGS`
- **Menu:** All commands registered with Telegram's autocomplete via `setMyCommands(ALL_PLATFORM_COMMANDS)`
- **File handling:** Downloads via Telegram's `getFileLink` API, stages or saves depending on session state
- **Message limit:** 4096 characters (chunked automatically)

### DiscordConnector

- **Library:** discord.js
- **Transport:** WebSocket gateway with intents (Guilds, GuildMessages, MessageContent, GuildVoiceStates)
- **Auth:** Channel restrictions via `allowedChannels` set
- **Commands:** All entries from `COMMAND_REGISTRY` deployed as slash commands via Discord REST API
- **Deferred replies:** Automatically applied for commands in the `DEFERRED_COMMANDS` set
- **File handling:** Downloads from Discord CDN, stages or saves depending on session state
- **Voice:** Supports joining/leaving voice channels, recording audio, and transcription
- **Message limit:** 2000 characters (chunked via `chunk()` utility)

### SlackConnector

- **Library:** @slack/bolt
- **Transport:** Socket Mode (WebSocket, no public URL needed)
- **Auth:** `/pair <code>` command + `authorized_users` list
- **Commands:** Registered as individual slash commands (`/draft`, `/status`, etc.) from both `COMMANDS_WITH_ARGS` and `COMMANDS_NO_ARGS`
- **Buttons:** Action handler matches `^(menu|cmd|prefs|asset):` pattern
- **Formatting:** Converts markdown bold and links to Slack mrkdwn syntax
- **File handling:** Downloads from Slack file URLs
- **Message limit:** Chunked into Block Kit section blocks

## Shared utilities

`connectors/utils.ts` provides platform-agnostic helpers:

| Function | Purpose |
|---|---|
| `mdConvert(text)` | Converts single `*bold*` to `**bold**` (for Discord from generic Markdown) |
| `chunk(text, limit)` | Splits text at newline/space boundaries to fit platform message limits |
| `detectEpicRef(text)` | Extracts `EPIC-NNN` references from user text |
| `guessAssetType(filename, mime)` | Classifies uploaded files into categories: `design-mockup`, `api-spec`, `test-data`, `config`, `reference-doc`, `media`, or `other` |

## Notification routing

The `NotificationRouter` in `notifications.ts` connects to the dashboard via WebSocket and pushes events (room created, updated, removed) to all authorized users across all enabled connectors. Events are filtered by each user's `notification_preferences`.

```
Dashboard WebSocket ──► NotificationRouter
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
               Telegram   Discord    Slack
              (authorized users only, filtered by preferences)
```

## Session management

Sessions are stored in-memory, keyed by `"platform:userId"`. Each session tracks:

- `activePlanId` -- the plan currently being edited
- `mode` -- `idle`, `editing`, `drafting`, or `awaiting_idea`
- `chatHistory` -- conversation context for AI refinement
- `pendingAttachments` -- staged file uploads
- `activeEpicRef` -- current epic context (for targeted uploads)

Sessions auto-reset after 30 minutes of inactivity. Platform isolation ensures that a user's Telegram session is completely independent from their Discord session.

## Complete command list

Commands are grouped by category in the `COMMAND_REGISTRY`:

### Plans & AI

| Command | Description | Argument |
|---|---|---|
| `/menu` | Main Control Center | -- |
| `/help` | Detailed user guide | -- |
| `/draft` | Draft a new Plan with AI | `idea` (optional) |
| `/edit` | Select a plan to edit with AI | -- |
| `/viewplan` | View a plan's content | -- |
| `/startplan` | Select and launch a plan | -- |
| `/resume` | Resume a failed or stopped plan | -- |
| `/assets` | List assets for the active plan | -- |
| `/transcribe` | Transcribe a voice recording | -- |
| `/setdir` | Set target project directory | `path` |
| `/cancel` | Exit current editing session | -- |
| `/feedback` | Send feedback to the dashboard | `text` (required) |

### Monitoring

| Command | Description | Argument |
|---|---|---|
| `/dashboard` | Real-time War-Room progress | -- |
| `/status` | List running War-Rooms | -- |
| `/compact` | Latest messages from agents | -- |
| `/errors` | Error summary with root causes | -- |
| `/logs` | View war-room channel messages | `room_id` (optional) |
| `/health` | System health check | -- |
| `/progress` | Plan progress bars | -- |
| `/plans` | List all project Plans | -- |

### Skills & Roles

| Command | Description | Argument |
|---|---|---|
| `/skills` | View installed AI skills | -- |
| `/skillsearch` | Search ClawHub marketplace | `query` (required) |
| `/skillinstall` | Install a skill from ClawHub | `slug` (required) |
| `/skillremove` | Remove an installed skill | `name` (required) |
| `/skillsync` | Sync skills with dashboard | -- |
| `/roles` | List all agent roles | -- |
| `/clonerole` | Clone a role for project override | `role` (required) |

### System

| Command | Description | Argument |
|---|---|---|
| `/usage` | Stats report | -- |
| `/config` | View system configuration | `key` (optional) |
| `/triage` | Triage a failed war-room | `room_id` (optional) |
| `/clearplans` | Wipe all plan data | -- |
| `/new` | Wipe old War-Room data | -- |
| `/restart` | Reboot the Command Center | -- |
| `/launchdashboard` | Dashboard access info | -- |
| `/preferences` | Notification preferences | -- |
| `/subscriptions` | Event subscription toggles | -- |

### Discord-only

| Command | Description |
|---|---|
| `/join` | Join your voice channel and stream live audio |
| `/leave` | Disconnect and save all recordings |
| `/ping` | Check bot latency |
