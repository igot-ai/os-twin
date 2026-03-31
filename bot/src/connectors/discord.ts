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
  REST,
  Routes,
  SlashCommandBuilder,
} from 'discord.js';
import fs from 'fs';
import fsp from 'fs/promises';
import path from 'path';
import { EOL } from 'os';

import { Platform, Connector, ConnectorConfig, ConnectorStatus, HealthCheckResult, SetupStep, ValidationResult } from './base';
import { routeCommand, routeCallback, handleStatefulText, BotResponse, Button } from '../commands';
import { askAgent } from '../agent-bridge';
import { getSession } from '../sessions';
import { transcribeAndLaunch } from '../audio-transcript';
import { mdConvert, chunk } from './utils';

// Voice command imports
import * as pingCommand from '../commands/ping';
import * as joinCommand from '../commands/join';
import * as leaveCommand from '../commands/leave';

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

const DISCORD_MSG_LIMIT = 2000;
const LOGS_DIR = path.resolve(__dirname, '../../logs');

export class DiscordConnector implements Connector {
  public readonly platform: Platform = 'discord';
  public status: ConnectorStatus = 'disconnected';
  public client: Client | null = null;
  private voiceCommands: Collection<string, VoiceCommand> = new Collection();

  constructor() {
    if (!fs.existsSync(LOGS_DIR)) fs.mkdirSync(LOGS_DIR, { recursive: true });
    
    const vCmds: VoiceCommand[] = [pingCommand, joinCommand, leaveCommand];
    for (const cmd of vCmds) {
      this.voiceCommands.set(cmd.data.name, cmd);
    }
  }

  public async start(config: ConnectorConfig): Promise<void> {
    const token = config.credentials.token;
    const clientId = config.credentials.client_id;
    const guildId = config.credentials.guild_id;

    if (!token || !clientId) {
      this.status = 'error';
      throw new Error('Discord token or client_id is missing in credentials');
    }

    this.status = 'connecting';
    this.client = new Client({
      intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildVoiceStates,
      ],
    });

    this.client.on('interactionCreate', async (interaction) => {
      if (interaction.isButton()) {
        const userId = String(interaction.user.id);
        const data = interaction.customId;

        await interaction.deferUpdate().catch(() => {});
        const responses = await routeCallback(userId, 'discord', data);
        if (responses.length) {
          await this.sendToChannel(interaction.channel as TextChannel, responses);
        }
        return;
      }

      if (!interaction.isChatInputCommand()) return;

      const commandName = interaction.commandName;
      const voiceCmd = this.voiceCommands.get(commandName);
      if (voiceCmd) {
        try {
          await voiceCmd.execute(interaction);
        } catch (error) {
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

      const userId = String(interaction.user.id);
      const longRunning = ['draft', 'edit', 'startplan', 'new', 'restart', 'transcribe', 'feedback', 'preferences', 'subscriptions', 'progress'].includes(commandName);
      if (longRunning) await interaction.deferReply();

      let args = '';
      if (commandName === 'draft') {
        args = interaction.options.getString('idea') || '';
      } else if (commandName === 'feedback') {
        args = interaction.options.getString('text') || '';
      }

      const responses = await routeCommand(userId, 'discord', commandName, args);
      await this.sendToInteraction(interaction, responses);
    });

    this.client.on('messageCreate', async (message: Message) => {
      if (message.author.bot) return;
      if (!message.guild) return;

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

      const logFile = path.join(LOGS_DIR, `${entry.channelName}-${entry.channelId}.jsonl`);
      fsp.appendFile(logFile, JSON.stringify(entry) + EOL)
        .catch(err => console.warn('[LOG] Failed to persist:', err.message));

      if (this.client?.user && message.mentions.has(this.client.user.id)) {
        const question = message.content
          .replace(new RegExp(`<@!?${this.client.user.id}>`, 'g'), '')
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

      const userId = String(message.author.id);
      const session = getSession(userId, 'discord');
      if (['drafting', 'editing', 'awaiting_idea'].includes(session.mode)) {
        const msgText = message.content.trim();
        if (msgText && !msgText.startsWith('/')) {
          const responses = await handleStatefulText(userId, 'discord', msgText);
          await this.sendToChannel(message.channel as TextChannel, responses);
        }
      }
    });

    // Register commands
    await this.deployCommands(token, clientId, guildId);

    this.client.once('ready', () => {
      console.log(`[DISCORD] Logged in as ${this.client?.user?.tag}`);
      this.status = 'connected';
    });

    this.client.on('voiceStateUpdate', (oldState: VoiceState, _newState: VoiceState) => {
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
              if (saved.length > 0) {
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

    await this.client.login(token);
  }

  public async stop(): Promise<void> {
    if (this.client) {
      this.client.destroy();
      this.client = null;
    }
    this.status = 'disconnected';
  }

  public async healthCheck(): Promise<HealthCheckResult> {
    if (this.status !== 'connected' || !this.client || !this.client.isReady()) {
      return { status: 'unhealthy', message: `Client is ${this.status}` };
    }
    return { status: 'healthy', details: { ping: this.client.ws.ping } };
  }

  public async sendMessage(targetId: string, response: BotResponse): Promise<void> {
    if (!this.client) throw new Error('Discord bot not started');
    const channel = await this.client.channels.fetch(targetId);
    if (channel?.isTextBased()) {
      await this.sendToChannel(channel as TextChannel, [response]);
    } else {
      throw new Error(`Channel ${targetId} is not text-based`);
    }
  }

  public getSetupInstructions(): SetupStep[] {
    return [
      {
        title: 'Create Discord App',
        description: 'Create an application on Discord Developer Portal.',
        instructions: '1. Go to https://discord.com/developers/applications\n2. Click "New Application"\n3. Go to "Bot" section and copy the Token.',
      }
    ];
  }

  public validateConfig(config: ConnectorConfig): ValidationResult {
    const errors: string[] = [];
    if (!config.credentials.token) errors.push('Missing Discord token');
    if (!config.credentials.client_id) errors.push('Missing Discord client_id');
    return {
      valid: errors.length === 0,
      errors: errors.length > 0 ? errors : undefined,
    };
  }

  private buildButtons(buttons: Button[][]): ActionRowBuilder<ButtonBuilder>[] {
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

  private async sendToInteraction(interaction: ChatInputCommandInteraction, responses: BotResponse[]): Promise<void> {
    let first = true;
    for (const resp of responses) {
      const convertedText = mdConvert(resp.text || '');
      const components = resp.buttons ? this.buildButtons(resp.buttons) : [];
      const chunksArr = chunk(convertedText, DISCORD_MSG_LIMIT);

      for (let i = 0; i < chunksArr.length; i++) {
        const payload = {
          content: chunksArr[i],
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

  private async sendToChannel(channel: TextChannel, responses: BotResponse[]): Promise<void> {
    for (const resp of responses) {
      const convertedText = mdConvert(resp.text || '');
      const components = resp.buttons ? this.buildButtons(resp.buttons) : [];
      const chunksArr = chunk(convertedText, DISCORD_MSG_LIMIT);
      for (let i = 0; i < chunksArr.length; i++) {
        await channel.send({
          content: chunksArr[i],
          components: i === 0 ? components : [],
        });
      }
    }
  }

  private async deployCommands(token: string, clientId: string, guildId?: string): Promise<void> {
    const commands = [
      new SlashCommandBuilder().setName('menu').setDescription('Main Control Center'),
      new SlashCommandBuilder().setName('dashboard').setDescription('Real-time War-Room progress'),
      new SlashCommandBuilder().setName('status').setDescription('List running War-Rooms'),
      new SlashCommandBuilder().setName('compact').setDescription('Latest messages from agents'),
      new SlashCommandBuilder().setName('plans').setDescription('List all project Plans'),
      new SlashCommandBuilder().setName('errors').setDescription('Error summary with root causes'),
      new SlashCommandBuilder().setName('skills').setDescription('View available AI skills'),
      new SlashCommandBuilder().setName('usage').setDescription('Stats report'),
      new SlashCommandBuilder().setName('help').setDescription('Detailed user guide'),
      new SlashCommandBuilder()
        .setName('draft')
        .setDescription('Draft a new Plan with AI')
        .addStringOption(opt => opt.setName('idea').setDescription('Your project idea').setRequired(false)),
      new SlashCommandBuilder().setName('edit').setDescription('Select a plan to edit with AI'),
      new SlashCommandBuilder().setName('viewplan').setDescription('View a plan\'s content'),
      new SlashCommandBuilder().setName('startplan').setDescription('Select and launch a plan'),
      new SlashCommandBuilder().setName('cancel').setDescription('Exit current editing session'),
      new SlashCommandBuilder().setName('transcribe').setDescription('Transcribe a voice recording and optionally draft a plan'),
      new SlashCommandBuilder().setName('new').setDescription('Wipe old War-Room data to start fresh'),
      new SlashCommandBuilder().setName('restart').setDescription('Reboot the Command Center background process'),
      new SlashCommandBuilder().setName('join').setDescription('Join your voice channel and stream live audio'),
      new SlashCommandBuilder().setName('leave').setDescription('Disconnect and save all recordings'),
      new SlashCommandBuilder().setName('ping').setDescription('Check bot latency'),
    ];

    const rest = new REST({ version: '10' }).setToken(token);
    try {
      console.log(`[DISCORD] Registering ${commands.length} commands...`);
      const route = guildId
        ? Routes.applicationGuildCommands(clientId, guildId)
        : Routes.applicationCommands(clientId);
      await rest.put(route, { body: commands.map(c => c.toJSON()) });
      console.log(`[DISCORD] Successfully registered commands.`);
    } catch (error: any) {
      console.error('[DISCORD] Failed to register commands:', error.message);
    }
  }
}
