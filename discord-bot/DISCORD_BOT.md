# Discord Bot — OS Twin

## 1. Technology Stack
- **Language:** JavaScript (CommonJS)
- **Framework:** Discord.js (v14+)
- **Runtime:** Node.js (v18+)
- **Voice:** @discordjs/voice + prism-media (Opus decoding)
- **AI Bridge:** Google Generative AI (Gemini) for question answering
- **Package Manager:** pnpm (recommended)

## 2. Project Structure

```text
discord-bot/
  src/
    commands/         # Slash commands (join, leave, ping)
    agent-bridge.js   # Discord <-> Ostwin dashboard bridge (Gemini-powered)
    client.js         # Discord client setup, event handlers, message logging
    deploy-commands.js# Register slash commands with Discord API
    index.js          # Entry point (validates token, logs in)
  test/               # Mocha + Chai + Sinon unit tests
  recordings/         # Voice recordings output (gitignored)
  logs/               # Message logs per channel (gitignored)
```

## 3. Features

### Slash Commands
- `/ping` — Latency check
- `/join` — Join the user's voice channel, stream and record audio per-user as PCM files
- `/leave` — Disconnect and save all recordings

### Agent Bridge (@mention)
When the bot is @mentioned in a text channel, it:
1. Queries the Ostwin dashboard API for plans, war-rooms, stats, and semantic search
2. Sends context + question to Gemini
3. Replies with the AI-synthesized answer

### Voice Recording
- Per-user PCM recording (48kHz, 16-bit, stereo)
- Auto-disconnect when all humans leave the voice channel
- Recordings saved to `recordings/` directory

### Message Logging
- Captures all non-bot guild messages to per-channel JSON files in `logs/`

## 4. Setup

```bash
cp .env.example .env    # Fill in your tokens
pnpm install
pnpm run deploy         # Register slash commands
pnpm start              # Start the bot
```

### Required Environment Variables
| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Bot token from Discord Developer Portal |
| `DISCORD_CLIENT_ID` | Yes | Application ID from Discord Developer Portal |
| `GUILD_ID` | No | Test server ID (guild-scoped commands if set) |
| `DASHBOARD_URL` | No | Ostwin dashboard URL (default: `http://localhost:9000`) |
| `OSTWIN_API_KEY` | No | API key for dashboard authentication |
| `GOOGLE_API_KEY` | Yes* | Google AI API key (*required for @mention agent) |
| `GEMINI_MODEL` | No | Gemini model to use (default: `gemini-2.0-flash`) |

### Discord Developer Portal Setup
1. Enable **Message Content Intent** under Bot settings (required for @mention detection)
2. Grant the bot **Connect** and **Speak** permissions for voice features

## 5. Security
- Bot token stored in `.env` (gitignored)
- Never commit `.env` files
- Gateway intents follow least-privilege principle
- User input sanitized via Discord's slash command typing
