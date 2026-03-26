# ARCHITECTURE.md - Discord Bot System Design

## 1. Technology Stack
- **Language:** TypeScript
- **Framework:** Discord.js (v14+)
- **Runtime:** Node.js (v18+)
- **Database:** PostgreSQL (with Prisma ORM) or MongoDB (depending on data structure)
- **Deployment:** Docker + AWS ECS/Fargate or a VPS (DigitalOcean/Linode)

## 2. Project Structure
The project follows a modular, feature-based structure for scalability.

```text
/src
  /commands        # Slash commands organized by category
    /general
    /admin
  /events          # Event listeners (ready, interactionCreate, messageCreate)
  /services        # Business logic and external API integrations
  /models          # Database schemas and types
  /utils           # Helper functions and constants
  /config          # Configuration management (Intents, constants)
  index.ts         # Entry point (Client initialization)
```

## 3. Core Modules

### 3.1. Event Handler
A dynamic event loader that scans the `/events` directory and registers listeners. This avoids a bloated `index.ts`.
- **Logic:** `fs.readdirSync` -> filter `.ts` files -> `client.on(event.name, (...args) => event.execute(...args))`

### 3.2. Command Handler
A robust Slash Command handler using `Collection` for storage and `REST` API for deployment.
- **Storage:** `client.commands = new Collection();`
- **Execution:** Listen to `interactionCreate` -> fetch command from collection -> `await command.execute(interaction);`

### 3.3. Service Layer
Separates Discord-specific logic from business logic. Services (e.g., `UserService`, `LoggingService`) handle database operations or API calls.

## 4. Connection Flow & Sharding
- **Initialization:** Load environment variables -> Register commands to Discord REST -> Initialize Discord Client.
- **Sharding:** Use `ShardingManager` for bots in >2,500 guilds. For smaller bots, internal sharding is sufficient.

## 5. Security Protocols
- **Token Management:**
    - Use `.env` file for local development.
    - For Production, use AWS Secrets Manager or GitHub Secrets for CI/CD.
    - **NEVER** commit `.env` files (already added to `.gitignore`).
- **Least Privilege Gateway Intents:**
    - Disable `GatewayIntentBits.MessageContent` unless necessary (e.g., legacy prefix commands).
    - Use `GatewayIntentBits.Guilds` for core functionality.
    - Enable `GuildMembers` and `GuildPresences` only if the bot is "Privileged" and really needs them.
- **Input Sanitization:**
    - Always treat user input as untrusted. Discord slash commands provide some built-in typing, but manual checks for injection or malicious strings in text inputs are required.
- **Interaction Verification:**
    - If using **Webhooks** instead of the Gateway (Serverless), verify signatures using Discord's public key as per the [API documentation](https://discord.com/developers/docs/interactions/receiving-and-responding#security-and-authorization).

## 6. Scalability & Event Handling
- **Dynamic Loader:** Scans `/src/events/*.ts` and registers them with `client.on()`.
- **Command Collection:** Uses `Map<string, Command>` to store commands and execute them based on `interaction.commandName`.
- **Database Pooling:** Use connection pooling for SQL databases to handle concurrent requests from multiple shards.
- **Sharding:** Ready for `discord.js` sharding manager. Each shard handles ~1,000 to 2,500 servers.

## 7. Verification of SDK
- **Discord.js (v14.x)** is verified to support:
    - Slash Commands (Global and Guild-specific).
    - Buttons, Select Menus, and Modals.
    - All Gateway Intents (Standard and Privileged).
    - API v10 compatibility.
