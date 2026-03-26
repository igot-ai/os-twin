require('dotenv').config();
const { Client, GatewayIntentBits, Collection } = require('discord.js');
const fs = require('fs');
const path = require('path');

// Initialize Discord Client
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildVoiceStates,
  ],
});

client.commands = new Collection();

// Load Commands
const commandsPath = path.join(__dirname, 'commands');
if (fs.existsSync(commandsPath)) {
  const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js'));
  for (const file of commandFiles) {
    const filePath = path.join(commandsPath, file);
    const command = require(filePath);
    if ('data' in command && 'execute' in command) {
      client.commands.set(command.data.name, command);
    } else {
      console.warn(`[WARNING] The command at ${filePath} is missing a required "data" or "execute" property.`);
    }
  }
}

// Handle Client Ready
client.once('ready', () => {
  console.log(`[READY] Logged in as ${client.user.tag}`);
});

// Handle Interactions (Slash Commands)
client.on('interactionCreate', async interaction => {
  if (!interaction.isChatInputCommand()) return;

  const command = client.commands.get(interaction.commandName);

  if (!command) {
    console.error(`No command matching ${interaction.commandName} was found.`);
    return;
  }

  try {
    await command.execute(interaction);
  } catch (error) {
    console.error(`[CMD ERROR] ${interaction.commandName}:`, error);
    try {
      const msg = { content: 'There was an error while executing this command!', flags: 64 };
      if (interaction.replied || interaction.deferred) {
        await interaction.followUp(msg);
      } else {
        await interaction.reply(msg);
      }
    } catch (replyError) {
      console.error('[CMD ERROR] Could not send error response:', replyError.message);
    }
  }
});

// ── Capture text messages from Discord channels ─────────────────────
const MAX_MESSAGE_BUFFER = 100;
const messageBuffer = [];
const LOGS_DIR = path.resolve(__dirname, '../logs');
if (!fs.existsSync(LOGS_DIR)) fs.mkdirSync(LOGS_DIR, { recursive: true });

client.on('messageCreate', (message) => {
  // Ignore bots (including ourselves)
  if (message.author.bot) return;
  // Ignore DMs — only guild messages
  if (!message.guild) return;

  const entry = {
    id: message.id,
    guildId: message.guild.id,
    channelId: message.channel.id,
    channelName: message.channel.name,
    userId: message.author.id,
    username: message.author.username,
    content: message.content,
    timestamp: message.createdAt.toISOString(),
  };

  // In-memory buffer
  messageBuffer.push(entry);
  if (messageBuffer.length > MAX_MESSAGE_BUFFER) messageBuffer.shift();

  // Persist to per-channel JSON file
  const logFile = path.join(LOGS_DIR, `${entry.channelName}-${entry.channelId}.json`);
  let existing = [];
  try {
    if (fs.existsSync(logFile)) {
      existing = JSON.parse(fs.readFileSync(logFile, 'utf-8'));
    }
  } catch { /* corrupted file — start fresh */ }
  existing.push(entry);
  fs.writeFileSync(logFile, JSON.stringify(existing, null, 2));

  console.log(`💬 [MSG] #${entry.channelName} | ${entry.username}: ${entry.content}`);

  // ── @mention → ask ostwin agent ───────────────────────────────────
  if (client.user && message.mentions.has(client.user.id)) {
    const { askAgent } = require('./agent-bridge');

    // Strip the @mention from the question
    const question = message.content
      .replace(new RegExp(`<@!?${client.user.id}>`, 'g'), '')
      .trim();

    if (!question) return;

    // Show typing indicator while processing
    message.channel.sendTyping().catch(() => {});

    console.log(`🤖 [AGENT] ${entry.username} asked: ${question}`);

    askAgent(question)
      .then((answer) => {
        message.reply(answer).catch(err =>
          console.error('❌ [AGENT] Failed to reply:', err.message)
        );
      })
      .catch((err) => {
        console.error('❌ [AGENT] Bridge error:', err);
        message.reply('⚠️ Sorry, I couldn\'t reach the ostwin backend. Is the dashboard running?')
          .catch(() => {});
      });
  }
});

// ── Auto-disconnect when all users leave the voice channel ──────────
const { sessions, cleanupSession } = require('./commands/join');

client.on('voiceStateUpdate', (oldState, _newState) => {
  // Only care when someone LEAVES a channel
  const leftChannel = oldState.channel;
  if (!leftChannel) return;

  const guildId = leftChannel.guild.id;
  const session = sessions.get(guildId);
  if (!session) return;

  // Only act on the channel the bot is in
  if (leftChannel.id !== session.channelId) return;

  // Count non-bot members still in the channel
  const humans = leftChannel.members.filter(m => !m.user.bot).size;

  if (humans === 0) {
    console.log(`📭 [AUTO] All users left ${leftChannel.name} — saving and disconnecting...`);
    const { saved } = cleanupSession(guildId);
    console.log(`📭 [AUTO] Saved ${saved.length} recording(s), disconnected from guild ${guildId}`);
  }
});

module.exports = client;
module.exports.messageBuffer = messageBuffer;
