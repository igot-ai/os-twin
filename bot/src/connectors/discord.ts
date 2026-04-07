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
import { mdConvert, chunk, detectEpicRef, guessAssetType } from './utils';
import api, { PlanAsset } from '../api';

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
  private allowedChannels: Set<string> | null = null;  // null = all channels

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

    // Load channel restrictions from settings
    const channels = config.settings?.allowed_channels;
    this.allowedChannels = Array.isArray(channels) && channels.length
      ? new Set(channels.map(String))
      : null;

    if (this.allowedChannels) {
      console.log(`[DISCORD] Channel filter: ${[...this.allowedChannels].join(', ')}`);
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
      // Channel restriction: ignore interactions from non-allowed text channels
      const channelId = interaction.channelId;
      if (this.allowedChannels && channelId && !this.allowedChannels.has(channelId)) {
        if (interaction.isRepliable()) {
          await interaction.reply({ content: '⚠️ This bot is restricted to specific channels.', flags: 64 as const }).catch(() => {});
        }
        return;
      }

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
        // Voice channel restriction: check if the user's voice channel is allowed
        if (this.allowedChannels && (commandName === 'join' || commandName === 'leave')) {
          const member = interaction.member as any;
          const voiceChannelId = member?.voice?.channelId;
          if (voiceChannelId && !this.allowedChannels.has(voiceChannelId)) {
            await interaction.reply({ content: '⚠️ This bot is restricted to specific voice channels.', flags: 64 as const }).catch(() => {});
            return;
          }
        }
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
      } else if (commandName === 'setdir') {
        args = interaction.options.getString('path') || '';
      } else if (commandName === 'feedback') {
        args = interaction.options.getString('text') || '';
      }

      const responses = await routeCommand(userId, 'discord', commandName, args);
      await this.sendToInteraction(interaction, responses);
    });

    this.client.on('messageCreate', async (message: Message) => {
      if (message.author.bot) return;
      if (!message.guild) return;
      if (this.allowedChannels && !this.allowedChannels.has(message.channel.id)) return;

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

      const userId = String(message.author.id);
      const session = getSession(userId, 'discord');
      
      // Update activeEpicRef if found in message content
      const msgEpic = detectEpicRef(message.content);
      if (msgEpic) {
        session.activeEpicRef = msgEpic;
      }

      const botUserId = this.client?.user?.id;
      const isMention = !!(botUserId && message.mentions.has(botUserId));
      const attachments = message.attachments ? Array.from(message.attachments.values()) : [];
      const isStateful = ['drafting', 'editing', 'awaiting_idea'].includes(session.mode);

      // ── Handle attachments: save to active plan regardless of @mention ──
      // For awaiting_idea mode, defer — attachments are saved after the plan is created below.
      const hasPendingAttachments = attachments.length > 0 && (isStateful || isMention);
      const canSaveNow = session.activePlanId && session.activePlanId !== 'new'
        && ['drafting', 'editing'].includes(session.mode);

      if (hasPendingAttachments && canSaveNow) {
        const assetResponses: BotResponse[] = [];
        const uploadResult = await this.persistAttachments(session.activePlanId!, attachments, message.content, session.activeEpicRef);
        if (uploadResult.saved.length > 0) {
          assetResponses.push({ text: this.formatSavedAssets(session.activePlanId!, uploadResult.saved) });
        }
        if (uploadResult.failures.length > 0) {
          assetResponses.push({ text: this.formatFailedAssets(uploadResult.failures) });
        }
        if (assetResponses.length > 0) {
          await this.sendToChannel(message.channel as TextChannel, assetResponses);
        }
      } else if (hasPendingAttachments && !isStateful && !canSaveNow) {
        // Not in any editing/drafting mode and no active plan — warn
        await this.sendToChannel(message.channel as TextChannel, [{
          text: '⚠️ Attachments can only be saved while editing a specific plan. Use /edit to pick a plan first.',
        }]);
      }
      // If awaiting_idea with attachments, we fall through — they'll be saved after draft below.

      // ── @mention: route to plan refine when editing, otherwise Q&A ──
      if (isMention) {
        const question = message.content
          .replace(new RegExp(`<@!?${this.client!.user!.id}>`, 'g'), '')
          .trim();

        if (!question && attachments.length === 0) return;

        // If user is editing a plan, treat @mention text as a plan instruction
        if (isStateful && question) {
          const textResponses = await handleStatefulText(userId, 'discord', question);
          if (textResponses.length > 0) {
            await this.sendToChannel(message.channel as TextChannel, textResponses);
          }
          return;
        }

        // Otherwise fall through to generic Q&A
        if (question) {
          (message.channel as TextChannel).sendTyping().catch(() => {});
          console.log(`🤖 [AGENT] ${entry.username} asked: ${question}`);

          try {
            const answer = await askAgent(question);
            await message.reply(answer);
          } catch (err: any) {
            console.error('❌ [AGENT] Bridge error:', err);
            await message.reply('⚠️ Sorry, I couldn\'t reach the ostwin backend.').catch(() => {});
          }
        }
        return;
      }

      // ── Stateful text: refine/draft plan ──
      if (isStateful) {
        const msgText = message.content.trim();
        const responses: BotResponse[] = [];

        if (msgText && !msgText.startsWith('/')) {
          const textResponses = await handleStatefulText(userId, 'discord', msgText);
          responses.push(...textResponses);
        }

        // After draft/refine, the plan may now exist — save deferred attachments
        if (attachments.length > 0 && !canSaveNow) {
          const updatedSession = getSession(userId, 'discord');
          if (updatedSession.activePlanId && updatedSession.activePlanId !== 'new') {
            const uploadResult = await this.persistAttachments(updatedSession.activePlanId, attachments, message.content, updatedSession.activeEpicRef);
            if (uploadResult.saved.length > 0) {
              responses.push({ text: this.formatSavedAssets(updatedSession.activePlanId, uploadResult.saved) });
            }
            if (uploadResult.failures.length > 0) {
              responses.push({ text: this.formatFailedAssets(uploadResult.failures) });
            }
          }
        }

        if (responses.length > 0) {
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
                    && (!this.allowedChannels || this.allowedChannels.has(ch.id))
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
    if (this.allowedChannels && !this.allowedChannels.has(targetId)) {
      console.warn(`[DISCORD] Blocked sendMessage to non-allowed channel ${targetId}`);
      return;
    }
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

  private async persistAttachments(
    planId: string,
    attachments: Array<{ url?: string; name?: string; contentType?: string | null }>,
    messageContent?: string,
    contextEpicRef?: string
  ): Promise<{ saved: PlanAsset[]; failures: string[] }> {
    const failures: string[] = [];
    const downloadable: Array<{ name: string; contentType?: string; data: Uint8Array }> = [];

    // Detect epic ref from current message content or fallback to session context
    const msgEpic = messageContent ? detectEpicRef(messageContent) : undefined;
    const epicRef = msgEpic || contextEpicRef;

    for (const attachment of attachments) {
      const displayName = attachment.name || 'attachment';
      if (!attachment.url) {
        failures.push(`${displayName}: missing download URL`);
        continue;
      }

      try {
        const response = await fetch(attachment.url);
        if (!response.ok) {
          failures.push(`${displayName}: download failed (${response.status})`);
          continue;
        }

        downloadable.push({
          name: displayName,
          contentType: attachment.contentType || response.headers.get('content-type') || undefined,
          data: new Uint8Array(await response.arrayBuffer()),
        });
      } catch (error: any) {
        failures.push(`${displayName}: ${error.message}`);
      }
    }

    if (!downloadable.length) {
      return { saved: [], failures };
    }

    // Guess asset type from the first file in the batch (they usually share context)
    const firstFile = downloadable[0];
    const assetType = guessAssetType(firstFile.name, firstFile.contentType);

    const uploadResult = await api.uploadPlanAssets(planId, downloadable, {
      epicRef,
      assetType,
    });
    if (uploadResult.error) {
      failures.push(uploadResult.error);
      return { saved: [], failures };
    }

    return { saved: uploadResult.assets, failures };
  }

  private formatSavedAssets(planId: string, assets: PlanAsset[]): string {
    const first = assets[0];
    const epicLabel = (first.bound_epics && first.bound_epics.length > 0)
      ? ` for ${first.bound_epics[0]}`
      : '';
    const typeLabel = (first.asset_type && first.asset_type !== 'other')
      ? ` as ${first.asset_type}`
      : '';

    if (assets.length === 1) {
      return `✅ Saved \`${first.original_name}\`${typeLabel}${epicLabel}.`;
    }

    const lines = [`🖼 *Saved ${assets.length} asset(s) to \`${planId}\`${epicLabel}:*`];
    for (const asset of assets.slice(0, 10)) {
      lines.push(`• \`${asset.original_name}\` → \`${asset.filename}\``);
    }
    if (assets.length > 10) {
      lines.push(`…and ${assets.length - 10} more asset(s).`);
    }
    return lines.join('\n');
  }

  private formatFailedAssets(failures: string[]): string {
    const lines = ['⚠️ *Some attachments could not be saved:*'];
    for (const failure of failures.slice(0, 10)) {
      lines.push(`• ${failure}`);
    }
    if (failures.length > 10) {
      lines.push(`…and ${failures.length - 10} more issue(s).`);
    }
    return lines.join('\n');
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
        .setName('setdir')
        .setDescription('Set target project directory for new plans')
        .addStringOption(opt => opt.setName('path').setDescription('Absolute path to project directory').setRequired(false)),
      new SlashCommandBuilder()
        .setName('draft')
        .setDescription('Draft a new Plan with AI')
        .addStringOption(opt => opt.setName('idea').setDescription('Your project idea').setRequired(false)),
      new SlashCommandBuilder().setName('edit').setDescription('Select a plan to edit with AI'),
      new SlashCommandBuilder().setName('assets').setDescription('List assets saved for the active or selected plan'),
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
