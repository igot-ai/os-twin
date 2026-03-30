/**
 * discord.ts — Discord bot adapter using discord.js v14.
 *
 * Handles: slash commands, buttons, @mention Q&A, voice recording.
 * Delegates command logic to commands.ts.
 */

import {
  Client,
  GatewayIntentBits,
  Collection,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  ChatInputCommandInteraction,
  Message,
  VoiceState,
  TextChannel,
} from 'discord.js';
import fs from 'fs';
import fsp from 'fs/promises';
import path from 'path';
import { EOL } from 'os';

import config from './config';
import { routeCommand, routeCallback, handleStatefulText, BotResponse, Button } from './commands';
import { askAgent } from './agent-bridge';
import { getSession } from './sessions';
import { transcribeAndLaunch } from './audio-transcript';

// Voice command imports
import * as pingCommand from './commands/ping';
import * as joinCommand from './commands/join';
import * as leaveCommand from './commands/leave';

// ── Types ─────────────────────────────────────────────────────────

export interface VoiceCommand {
  data: { name: string };
  execute: (interaction: ChatInputCommandInteraction) => Promise<any>;
}

interface LogEntry {
  id: string;
  guildId: string;
  channelId: string;
  channelName: string;
  userId: string;
  username: string;
  content: string;
  timestamp: string;
}

// ── Constants ─────────────────────────────────────────────────────

const DISCORD_MSG_LIMIT = 2000;
const LOGS_DIR = path.resolve(__dirname, '../logs');
if (!fs.existsSync(LOGS_DIR)) fs.mkdirSync(LOGS_DIR, { recursive: true });

// ── Helpers ───────────────────────────────────────────────────────

/** Convert Telegram-style *bold* to Discord **bold** */
export function mdConvert(text: string): string {
  return text.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '**$1**');
}

/** Split text into chunks within Discord's limit */
export function chunk(text: string, limit = DISCORD_MSG_LIMIT): string[] {
  if (text.length <= limit) return [text];
  const chunks: string[] = [];
  let remaining = text;
  while (remaining.length > 0) {
    if (remaining.length <= limit) { chunks.push(remaining); break; }
    let split = remaining.lastIndexOf('\n', limit);
    if (split === -1) split = remaining.lastIndexOf(' ', limit);
    if (split === -1) split = limit;
    chunks.push(remaining.slice(0, split));
    remaining = remaining.slice(split).trimStart();
  }
  return chunks;
}

/** Build Discord ActionRow buttons from response buttons */
function buildButtons(buttons: Button[][]): ActionRowBuilder<ButtonBuilder>[] {
  const rows: ActionRowBuilder<ButtonBuilder>[] = [];
  const dangerPrefixes = ['menu:launch_confirm', 'cmd:restart', 'cmd:new'];
  for (const row of buttons.slice(0, 5)) {
    const actionRow = new ActionRowBuilder<ButtonBuilder>();
    for (const btn of row.slice(0, 5)) {
      let style = ButtonStyle.Primary;
      if (btn.callbackData.includes('Back') || btn.callbackData === 'menu:main') {
        style = ButtonStyle.Secondary;
      } else if (dangerPrefixes.some(p => btn.callbackData.startsWith(p))) {
        style = ButtonStyle.Danger;
      }
      actionRow.addComponents(
        new ButtonBuilder()
          .setCustomId(btn.callbackData)
          .setLabel(btn.label)
          .setStyle(style)
      );
    }
    rows.push(actionRow);
  }
  return rows;
}

/** Send response objects to a Discord interaction */
async function sendToInteraction(interaction: ChatInputCommandInteraction, responses: BotResponse[]): Promise<void> {
  let first = true;
  for (const resp of responses) {
    const convertedText = mdConvert(resp.text || '');
    const components = resp.buttons ? buildButtons(resp.buttons) : [];
    const chunks = chunk(convertedText);

    for (let i = 0; i < chunks.length; i++) {
      const payload = {
        content: chunks[i],
        components: i === 0 ? components : [],
      };

      if (first && !interaction.replied && !interaction.deferred) {
        await interaction.reply(payload);
        first = false;
      } else {
        await interaction.followUp(payload);
      }
    }
  }
}

/** Send response objects to a Discord channel */
async function sendToChannel(channel: TextChannel, responses: BotResponse[]): Promise<void> {
  for (const resp of responses) {
    const convertedText = mdConvert(resp.text || '');
    const components = resp.buttons ? buildButtons(resp.buttons) : [];
    const chunksArr = chunk(convertedText);
    for (let i = 0; i < chunksArr.length; i++) {
      await channel.send({
        content: chunksArr[i],
        components: i === 0 ? components : [],
      });
    }
  }
}

// ── Bot setup ─────────────────────────────────────────────────────

export function createDiscordBot(): Client | null {
  if (!config.DISCORD_TOKEN) {
    console.log('[DISCORD] No DISCORD_TOKEN set. Discord bot disabled.');
    return null;
  }

  const client = new Client({
    intents: [
      GatewayIntentBits.Guilds,
      GatewayIntentBits.GuildMessages,
      GatewayIntentBits.MessageContent,
      GatewayIntentBits.GuildVoiceStates,
    ],
  });

  const commands = new Collection<string, VoiceCommand>();

  // Load voice commands
  const voiceCommands: VoiceCommand[] = [pingCommand, joinCommand, leaveCommand];
  for (const cmd of voiceCommands) {
    commands.set(cmd.data.name, cmd);
  }

  // ── Ready ─────────────────────────────────────────────────────
  client.once('ready', () => {
    console.log(`[DISCORD] Logged in as ${client.user?.tag}`);
  });

  // ── Interactions (slash commands + buttons) ────────────────────
  client.on('interactionCreate', async (interaction) => {
    // Button interactions
    if (interaction.isButton()) {
      const userId = String(interaction.user.id);
      const data = interaction.customId;

      await interaction.deferUpdate().catch(() => {});
      const responses = await routeCallback(userId, 'discord', data);
      if (responses.length) {
        await sendToChannel(interaction.channel as TextChannel, responses);
      }
      return;
    }

    // Slash commands
    if (!interaction.isChatInputCommand()) return;

    const commandName = interaction.commandName;

    // Check if it's a voice command (join/leave/ping)
    const voiceCmd = commands.get(commandName);
    if (voiceCmd) {
      try {
        await voiceCmd.execute(interaction);
      } catch (error: any) {
        console.error(`[CMD ERROR] ${commandName}:`, error);
        const msg = { content: 'There was an error executing this command!', flags: 64 as const };
        if (interaction.replied || interaction.deferred) {
          await interaction.followUp(msg).catch(() => {});
        } else {
          await interaction.reply(msg).catch(() => {});
        }
      }
      return;
    }

    // Shared bot commands
    const userId = String(interaction.user.id);
    const longRunning = ['draft', 'edit', 'startplan', 'new', 'restart', 'transcribe'].includes(commandName);
    if (longRunning) await interaction.deferReply();

    const args = commandName === 'draft'
      ? (interaction.options.getString('idea') || '')
      : '';

    const responses = await routeCommand(userId, 'discord', commandName, args);
    await sendToInteraction(interaction, responses);
  });

  // ── Message logging + @mention Q&A + stateful text ────────────
  const MAX_MESSAGE_BUFFER = 100;
  const messageBuffer: LogEntry[] = [];

  client.on('messageCreate', async (message: Message) => {
    if (message.author.bot) return;
    if (!message.guild) return;

    // Log message
    const entry: LogEntry = {
      id: message.id,
      guildId: message.guild.id,
      channelId: message.channel.id,
      channelName: (message.channel as TextChannel).name || 'unknown',
      userId: message.author.id,
      username: message.author.username,
      content: message.content,
      timestamp: message.createdAt.toISOString(),
    };

    messageBuffer.push(entry);
    if (messageBuffer.length > MAX_MESSAGE_BUFFER) messageBuffer.shift();

    const logFile = path.join(LOGS_DIR, `${entry.channelName}-${entry.channelId}.jsonl`);
    fsp.appendFile(logFile, JSON.stringify(entry) + EOL)
      .catch(err => console.warn('[LOG] Failed to persist:', err.message));

    // @mention → agent Q&A
    if (client.user && message.mentions.has(client.user.id)) {
      const question = message.content
        .replace(new RegExp(`<@!?${client.user.id}>`, 'g'), '')
        .trim();

      if (!question) return;

      (message.channel as TextChannel).sendTyping().catch(() => {});
      console.log(`🤖 [AGENT] ${entry.username} asked: ${question}`);

      try {
        const answer = await askAgent(question);
        await message.reply(answer);
      } catch (err: any) {
        console.error('❌ [AGENT] Bridge error:', err);
        await message.reply('⚠️ Sorry, I couldn\'t reach the ostwin backend.').catch(() => {});
      }
      return;
    }

    // Stateful text (editing/drafting)
    const userId = String(message.author.id);
    const session = getSession(userId, 'discord');
    if (['drafting', 'editing', 'awaiting_idea'].includes(session.mode)) {
      const msgText = message.content.trim();
      if (msgText && !msgText.startsWith('/')) {
        const responses = await handleStatefulText(userId, 'discord', msgText);
        await sendToChannel(message.channel as TextChannel, responses);
      }
    }
  });

  // ── Auto-disconnect from voice when all humans leave ──────────
  client.on('voiceStateUpdate', (oldState: VoiceState, _newState: VoiceState) => {
    const leftChannel = oldState.channel;
    if (!leftChannel) return;

    try {
      const guildId = leftChannel.guild.id;
      const session = joinCommand.sessions.get(guildId);
      if (!session) return;
      if (leftChannel.id !== session.channelId) return;

      const humans = leftChannel.members.filter(m => !m.user.bot).size;
      if (humans === 0) {
        console.log(`📭 [AUTO] All users left ${leftChannel.name} — saving and disconnecting...`);
        joinCommand.cleanupSession(guildId)
          .then(async ({ saved }) => {
            console.log(`📭 [AUTO] Saved ${saved.length} recording(s)`);
            // Auto-pipeline: transcribe → plan → launch
            if (saved.length > 0) {
              // Find a text channel in the guild to post updates
              const guild = leftChannel.guild;
              const textChannel = guild.channels.cache.find(
                ch => ch.isTextBased() && !ch.isVoiceBased()
              ) as TextChannel | undefined;

              const send = async (msg: string) => {
                try { await textChannel?.send(msg); } catch { /* best effort */ }
              };

              const result = await transcribeAndLaunch(saved, send);
              if (result.error) {
                await send(`⚠️ Voice-to-code: ${result.error}`);
              } else {
                await send(`🎙→📝→🚀 *Voice-to-Code Complete!*\nPlan \`${result.planId}\` launched. Use /dashboard to monitor.`);
              }
            }
          })
          .catch(err => console.error('[AUTO] Cleanup error:', err.message));
      }
    } catch {
      // Voice commands not available, ignore
    }
  });

  return client;
}

export function startDiscord(): void {
  const client = createDiscordBot();
  if (!client) return;

  console.log('[DISCORD] Starting bot...');
  client.login(config.DISCORD_TOKEN).catch(error => {
    console.error('[DISCORD] Failed to login:', error.message);
  });
}
